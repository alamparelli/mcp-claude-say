#!/usr/bin/env python3
"""
Claude-Say MCP Server
Text-to-speech MCP server with Chatterbox neural TTS and macOS voice fallback.
Provides queue management and speech control for Claude Code.
"""

import subprocess
import threading
import os
import time
import urllib.request
import json
from queue import Queue, Empty
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("claude-say")

# Global state
speech_queue: Queue = Queue()
current_process: subprocess.Popen | None = None
process_lock = threading.Lock()
worker_thread: threading.Thread | None = None

# TTS Service configuration (env-configurable)
CHATTERBOX_URL = os.getenv("CHATTERBOX_URL", "http://127.0.0.1:8123")
USE_CHATTERBOX = os.getenv("USE_CHATTERBOX", "1") == "1"
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "female_voice")

# Health check cache to avoid blocking worker thread
_last_health_check = 0.0
_health_ok = False
_health_lock = threading.Lock()
HEALTH_CHECK_TTL = 2.0  # seconds

# Ready notification sound (macOS system sound)
READY_SOUND = "/System/Library/Sounds/Pop.aiff"


def chatterbox_available() -> bool:
    """
    Check if Chatterbox TTS service is running.
    Caches result for HEALTH_CHECK_TTL seconds to avoid blocking.
    Thread-safe via lock.
    """
    global _last_health_check, _health_ok
    now = time.time()

    with _health_lock:
        if now - _last_health_check < HEALTH_CHECK_TTL:
            return _health_ok
        try:
            req = urllib.request.urlopen(f"{CHATTERBOX_URL}/health", timeout=1)
            data = json.loads(req.read().decode())
            _health_ok = data.get("model_loaded", False)
        except:
            _health_ok = False
        _last_health_check = now
        return _health_ok


def speak_with_chatterbox(text: str, blocking: bool = True, voice: str | None = None) -> bool:
    """
    Speak using Chatterbox TTS service.
    Returns True if successful, False if service unavailable.
    """
    try:
        endpoint = "/speak" if blocking else "/speak_async"
        payload = {"text": text, "voice": voice or DEFAULT_VOICE}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{CHATTERBOX_URL}{endpoint}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        response = urllib.request.urlopen(req, timeout=60)
        return response.status == 200
    except:
        return False


def stop_chatterbox() -> bool:
    """Stop Chatterbox playback."""
    try:
        req = urllib.request.Request(
            f"{CHATTERBOX_URL}/stop",
            method="POST"
        )
        urllib.request.urlopen(req, timeout=2)
        return True
    except:
        return False


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

        text, voice, rate, use_neural = item

        # Try Chatterbox for neural TTS (if enabled and no specific voice requested)
        if use_neural and USE_CHATTERBOX and chatterbox_available():
            # Remove macOS-specific silence markup for Chatterbox
            clean_text = text.replace(f" [[slnc {TRAILING_SILENCE_MS}]]", "")
            if speak_with_chatterbox(clean_text, blocking=True):
                speech_queue.task_done()
                continue
            # Fall through to macOS voice if Chatterbox fails

        # Fallback to macOS 'say' command
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
def speak(text: str, voice: str | None = None, speed: float = 1.0) -> str:
    """
    Queue text to speak without waiting. Returns immediately.
    Use this for natural flowing speech - queue multiple messages that play smoothly.

    Args:
        text: The text to speak
        voice: Voice to use. Options:
               - None or "chatterbox": Neural TTS (Chatterbox, natural sounding)
               - "Samantha": macOS female voice (fallback)
               - Any other macOS voice name
        speed: Speech speed (0.5 = slow, 1.0 = normal, 2.0 = fast)
               Note: speed only applies to macOS voices; neural TTS uses natural pacing.

    Returns:
        Confirmation that text was queued
    """
    ensure_worker_running()
    rate = int(speed * 175)  # 175 words/min = normal speed

    # Determine if we should use neural TTS
    use_neural = voice is None or voice.lower() == "chatterbox"
    macos_voice = None if use_neural else voice

    # Add trailing silence so the last word is fully heard (for macOS voices)
    text_with_silence = f"{text} [[slnc {TRAILING_SILENCE_MS}]]"

    speech_queue.put((text_with_silence, macos_voice, rate, use_neural))

    return "Queued (neural TTS)" if use_neural else f"Queued ({voice})"


@mcp.tool()
def speak_and_wait(text: str, voice: str | None = None, speed: float = 1.1) -> str:
    """
    Speak text and wait until speech is finished before returning.
    Use this instead of speak() + polling queue_status() to reduce API round trips.

    Args:
        text: The text to speak
        voice: Voice to use. Options:
               - None or "chatterbox": Neural TTS (Chatterbox, natural sounding)
               - "Samantha": macOS female voice (fallback)
               - Any other macOS voice name
        speed: Speech speed (0.5 = slow, 1.0 = normal, 1.1 = default, 2.0 = fast)
               Note: speed only applies to macOS voices; neural TTS uses natural pacing.

    Returns:
        Confirmation that speech has completed
    """
    ensure_worker_running()
    rate = int(speed * 175)  # 175 words/min = normal speed

    # Determine if we should use neural TTS
    use_neural = voice is None or voice.lower() == "chatterbox"
    macos_voice = None if use_neural else voice

    # Add trailing silence so the last word is fully heard (for macOS voices)
    text_with_silence = f"{text} [[slnc {TRAILING_SILENCE_MS}]]"

    speech_queue.put((text_with_silence, macos_voice, rate, use_neural))

    # Wait for the queue to be processed
    speech_queue.join()

    # Clear any segments recorded during TTS (feedback loop prevention)
    clear_listen_segments()

    # Play ready sound to indicate listening is active
    play_ready_sound()

    return "Speech completed (neural TTS)" if use_neural else f"Speech completed ({voice})"


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

    # Stop Chatterbox playback (only if enabled)
    if USE_CHATTERBOX:
        stop_chatterbox()

    # Stop macOS say process
    with process_lock:
        if current_process and current_process.poll() is None:
            current_process.terminate()
            current_process = None
            return f"Stopped. {items_cleared} message(s) cleared from queue."

    return f"Nothing playing. {items_cleared} message(s) cleared from queue."


if __name__ == "__main__":
    mcp.run()
