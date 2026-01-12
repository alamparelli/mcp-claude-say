#!/usr/bin/env python3
"""
Claude-Say MCP Server
Text-to-speech MCP server for macOS using the native 'say' command.
Provides queue management and speech control for Claude Code.
"""

import subprocess
import threading
import os
from queue import Queue, Empty
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("claude-say")

# Global state
speech_queue: Queue = Queue()
current_process: subprocess.Popen | None = None
process_lock = threading.Lock()
worker_thread: threading.Thread | None = None

# Ready notification sound (macOS system sound)
READY_SOUND = "/System/Library/Sounds/Pop.aiff"

def play_ready_sound():
    """Play a short notification sound to indicate ready to listen."""
    if os.path.exists(READY_SOUND):
        subprocess.Popen(
            ["afplay", READY_SOUND],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

def clear_listen_segments():
    """Clear segments from claude-listen to avoid feedback loop."""
    import shutil
    segment_dir = "/tmp/claude-segments"
    if os.path.exists(segment_dir):
        for f in os.listdir(segment_dir):
            try:
                os.remove(os.path.join(segment_dir, f))
            except:
                pass


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

    # Clear any segments recorded during TTS (feedback loop prevention)
    clear_listen_segments()

    # Play ready sound to indicate listening is active
    play_ready_sound()

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


if __name__ == "__main__":
    mcp.run()
