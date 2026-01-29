#!/usr/bin/env python3
"""Claude-Say: TTS with queue. Backends: google, chatterbox, macos (default)."""

import subprocess
import threading
import os
import time
import tempfile
import base64
import urllib.request
import json
from queue import Queue, Empty
from pathlib import Path
from mcp.server.fastmcp import FastMCP


def load_env_file():
    """Load configuration from ~/.mcp-claude-say/.env file.

    This allows centralized config without requiring python-dotenv.
    Only sets env vars if not already set (os.environ.setdefault).
    """
    env_path = Path.home() / ".mcp-claude-say" / ".env"
    if not env_path.exists():
        return

    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            # Parse KEY=value (handle values with = in them)
            if '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()
                # Remove surrounding quotes if present
                if val and len(val) >= 2:
                    if (val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'"):
                        val = val[1:-1]
                # Only set if not already in environment
                os.environ.setdefault(key, val)
    except Exception:
        pass  # Silently ignore errors - fall back to defaults


# Load .env file before any env var reads
load_env_file()

# Signal file for stop communication (shared with claude-listen)
STOP_SIGNAL_FILE = Path("/tmp/claude-voice-stop")


def check_and_clear_stop_signal() -> bool:
    """Check if stop signal exists and clear it. Returns True if signal was present."""
    if STOP_SIGNAL_FILE.exists():
        try:
            STOP_SIGNAL_FILE.unlink()
        except:
            pass
        return True
    return False


mcp = FastMCP("claude-say")

# Global state
speech_queue: Queue = Queue()
current_process: subprocess.Popen | None = None
current_afplay: subprocess.Popen | None = None  # Tracks afplay for Google TTS
process_lock = threading.Lock()
worker_thread: threading.Thread | None = None

# TTS Backend selection (env-configurable)
# Options: "chatterbox" (local neural, 11GB), "google" (cloud, needs API key), "macos" (built-in)
TTS_BACKEND = os.getenv("TTS_BACKEND", "macos").lower()

# Chatterbox configuration (for TTS_BACKEND=chatterbox)
CHATTERBOX_URL = os.getenv("CHATTERBOX_URL", "http://127.0.0.1:8123")
USE_CHATTERBOX = TTS_BACKEND == "chatterbox" or os.getenv("USE_CHATTERBOX", "0") == "1"
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "female_voice")

# Google Cloud TTS configuration (for TTS_BACKEND=google)
GOOGLE_CLOUD_API_KEY = os.getenv("GOOGLE_CLOUD_API_KEY", "")
GOOGLE_VOICE = os.getenv("GOOGLE_VOICE", "en-US-Neural2-F")  # Neural2 voices are in free tier
GOOGLE_LANGUAGE = os.getenv("GOOGLE_LANGUAGE", "en-US")

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


def google_tts_available() -> bool:
    """Check if Google Cloud TTS is configured."""
    return bool(GOOGLE_CLOUD_API_KEY) and TTS_BACKEND == "google"


def speak_with_google(text: str, blocking: bool = True) -> bool:
    """
    Speak using Google Cloud Text-to-Speech API.
    Returns True if successful, False on error.
    """
    global current_afplay
    if not GOOGLE_CLOUD_API_KEY:
        return False

    try:
        # Build the API request (use header for API key - more secure than URL param)
        url = "https://texttospeech.googleapis.com/v1/text:synthesize"
        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": GOOGLE_LANGUAGE,
                "name": GOOGLE_VOICE
            },
            "audioConfig": {
                "audioEncoding": "MP3",
                "speakingRate": 1.0
            }
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": GOOGLE_CLOUD_API_KEY
            },
            method="POST"
        )
        response = urllib.request.urlopen(req, timeout=30)
        result = json.loads(response.read().decode())

        # Decode the audio content
        audio_content = base64.b64decode(result["audioContent"])

        # Save to temp file and play
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False, prefix="google_tts_") as f:
            f.write(audio_content)
            temp_path = f.name

        try:
            # Clear stale stop signals before starting playback
            check_and_clear_stop_signal()

            if blocking:
                with process_lock:
                    current_afplay = subprocess.Popen(
                        ["afplay", temp_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                # Poll for completion while checking stop signal
                while current_afplay.poll() is None:
                    if check_and_clear_stop_signal():
                        current_afplay.terminate()
                        break
                    time.sleep(0.05)  # Check every 50ms
                with process_lock:
                    current_afplay = None
            else:
                subprocess.Popen(
                    ["afplay", temp_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        finally:
            if blocking:
                try:
                    os.unlink(temp_path)
                except:
                    pass
            # For non-blocking, file cleanup happens when afplay finishes (not ideal but acceptable)

        return True
    except Exception as e:
        # Log error but don't crash - will fallback to macOS
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

        # Check for stop signal - if present, clear queue and skip this item
        if check_and_clear_stop_signal():
            # Clear all remaining items in queue
            while not speech_queue.empty():
                try:
                    speech_queue.get_nowait()
                    speech_queue.task_done()
                except Empty:
                    break
            speech_queue.task_done()  # Mark current item as done
            continue  # Skip to next iteration (queue is now empty)

        text, voice, rate, use_neural = item
        # Remove macOS-specific silence markup for neural backends
        clean_text = text.replace(f" [[slnc {TRAILING_SILENCE_MS}]]", "")

        # Try Google Cloud TTS (if configured)
        if use_neural and google_tts_available():
            if speak_with_google(clean_text, blocking=True):
                speech_queue.task_done()
                continue
            # Fall through to other backends if Google fails

        # Try Chatterbox for neural TTS (if enabled)
        if use_neural and USE_CHATTERBOX and chatterbox_available():
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

        # Poll for completion while checking stop signal
        while current_process.poll() is None:
            if check_and_clear_stop_signal():
                current_process.terminate()
                break
            time.sleep(0.05)  # Check every 50ms

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
    """Queue TTS without waiting. Args: text, voice, speed (1.0=normal)"""
    ensure_worker_running()
    rate = int(speed * 175)  # 175 words/min = normal speed

    # Determine if we should use neural TTS (default backend or explicit request)
    use_neural = voice is None or voice.lower() in ("chatterbox", "google")
    macos_voice = None if use_neural else voice

    # Add trailing silence so the last word is fully heard (for macOS voices)
    text_with_silence = f"{text} [[slnc {TRAILING_SILENCE_MS}]]"

    speech_queue.put((text_with_silence, macos_voice, rate, use_neural))

    backend_name = TTS_BACKEND if use_neural else voice
    return f"Queued ({backend_name})"


@mcp.tool()
def speak_and_wait(text: str, voice: str | None = None, speed: float = 1.1) -> str:
    """Speak and wait for completion. Args: text, voice, speed (1.1=default)"""
    ensure_worker_running()
    rate = int(speed * 175)  # 175 words/min = normal speed

    # Determine if we should use neural TTS (default backend or explicit request)
    use_neural = voice is None or voice.lower() in ("chatterbox", "google")
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

    backend_name = TTS_BACKEND if use_neural else voice
    return f"Speech completed ({backend_name})"


@mcp.tool()
def stop_speaking() -> str:
    """Stop current TTS and clear queue."""
    global current_process, current_afplay

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

    stopped = False
    with process_lock:
        # Stop Google TTS afplay process
        if current_afplay and current_afplay.poll() is None:
            current_afplay.terminate()
            current_afplay = None
            stopped = True

        # Stop macOS say process
        if current_process and current_process.poll() is None:
            current_process.terminate()
            current_process = None
            stopped = True

    if stopped:
        return f"Stopped. {items_cleared} message(s) cleared from queue."

    return f"Nothing playing. {items_cleared} message(s) cleared from queue."


if __name__ == "__main__":
    mcp.run()
