#!/usr/bin/env python3
"""
Claude-Say MCP Server
Text-to-speech MCP server for macOS using the native 'say' command.
Provides queue management and speech control for Claude Code.
"""

import subprocess
import threading
from queue import Queue, Empty
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("claude-say")

# Global state
speech_queue: Queue = Queue()
current_process: subprocess.Popen | None = None
process_lock = threading.Lock()
worker_thread: threading.Thread | None = None


def speech_worker():
    """Worker thread that processes the speech queue sequentially."""
    global current_process
    while True:
        try:
            item = speech_queue.get(timeout=1.0)
        except Empty:
            continue

        if item is None:  # Stop signal
            break

        text, voice, rate = item

        # Build the command (voice is optional)
        cmd = ["/usr/bin/say", "-r", str(rate)]
        if voice:
            cmd.extend(["-v", voice])
        cmd.append(text)

        with process_lock:
            current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        current_process.wait()

        with process_lock:
            current_process = None

        speech_queue.task_done()


def ensure_worker_running():
    """Ensure the worker thread is running."""
    global worker_thread
    if worker_thread is None or not worker_thread.is_alive():
        worker_thread = threading.Thread(target=speech_worker, daemon=True)
        worker_thread.start()


# Trailing silence in milliseconds to prevent last word from being cut off
TRAILING_SILENCE_MS = 300


@mcp.tool()
def speak(text: str, voice: str | None = None, speed: float = 1.1) -> str:
    """
    Add text to the speech synthesis queue.

    Args:
        text: The text to speak
        voice: Voice to use (None = default Siri/system voice)
        speed: Speech speed (0.5 = slow, 1.0 = normal, 1.1 = default, 2.0 = fast)

    Returns:
        Confirmation that text was added to queue
    """
    ensure_worker_running()
    rate = int(speed * 175)  # 175 words/min = normal speed

    # Add trailing silence so the last word is fully heard
    # macOS say command supports [[slnc N]] where N is silence in milliseconds
    text_with_silence = f"{text} [[slnc {TRAILING_SILENCE_MS}]]"

    speech_queue.put((text_with_silence, voice, rate))
    preview = text[:50] + "..." if len(text) > 50 else text
    return f"Added to queue: {preview}"


@mcp.tool()
def speak_and_wait(text: str, voice: str | None = None, speed: float = 1.1) -> str:
    """
    Speak text and wait until speech is finished before returning.
    Use this instead of speak() + polling queue_status() to reduce API round trips.

    Args:
        text: The text to speak
        voice: Voice to use (None = default Siri/system voice)
        speed: Speech speed (0.5 = slow, 1.0 = normal, 1.1 = default, 2.0 = fast)

    Returns:
        Confirmation that speech has completed
    """
    ensure_worker_running()
    rate = int(speed * 175)  # 175 words/min = normal speed

    # Add trailing silence so the last word is fully heard
    text_with_silence = f"{text} [[slnc {TRAILING_SILENCE_MS}]]"

    speech_queue.put((text_with_silence, voice, rate))

    # Wait for the queue to be processed
    speech_queue.join()

    return "Speech completed"


@mcp.tool()
def stop_speaking() -> str:
    """
    Stop current speech immediately and clear the queue.

    Returns:
        Confirmation of stop
    """
    global current_process

    # Clear the queue
    items_cleared = 0
    while not speech_queue.empty():
        try:
            speech_queue.get_nowait()
            items_cleared += 1
        except Empty:
            break

    # Stop current process
    with process_lock:
        if current_process and current_process.poll() is None:
            current_process.terminate()
            current_process = None
            return f"Stopped. {items_cleared} message(s) cleared from queue."

    return f"Nothing playing. {items_cleared} message(s) cleared from queue."


@mcp.tool()
def skip() -> str:
    """
    Skip to the next message in queue (stops current message).

    Returns:
        Confirmation of skip
    """
    global current_process

    with process_lock:
        if current_process and current_process.poll() is None:
            current_process.terminate()
            return "Current message skipped, moving to next."

    return "No message currently playing."


@mcp.tool()
def list_voices() -> str:
    """
    List available voices on the system.

    Returns:
        List of installed voices
    """
    result = subprocess.run(
        ["/usr/bin/say", "-v", "?"],
        capture_output=True,
        text=True
    )

    # Parse and format voices
    voices = []
    for line in result.stdout.strip().split("\n")[:20]:  # Limit to 20
        parts = line.split()
        if parts:
            voice_name = parts[0]
            lang = parts[1] if len(parts) > 1 else ""
            voices.append(f"- {voice_name} ({lang})")

    return "Available voices:\n" + "\n".join(voices)


@mcp.tool()
def queue_status() -> str:
    """
    Get the current speech queue status.

    Returns:
        Number of pending messages and current state
    """
    global current_process

    queue_size = speech_queue.qsize()

    with process_lock:
        is_speaking = current_process is not None and current_process.poll() is None

    status = "Speaking" if is_speaking else "Silent"
    return f"Status: {status}\nMessages in queue: {queue_size}"


if __name__ == "__main__":
    mcp.run()
