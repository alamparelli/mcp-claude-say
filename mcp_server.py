#!/usr/bin/env python3
"""Claude-Say: TTS with queue. Backends: kokoro, google, chatterbox, macos (default)."""

import subprocess
import threading
import os
import sys
import time
import tempfile
import base64
import urllib.request
import json
import logging
from queue import Queue, Empty
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Add say/ and shared/ to path for imports
sys.path.insert(0, str(Path(__file__).parent / "say"))
sys.path.insert(0, str(Path(__file__).parent))

# Import coordination module for Phase 2 auto-start signaling
from shared.coordination import signal_tts_complete

# Configure espeak library path for French/multilingual phonemization (macOS)
# This is set after load_env_file() so .env value takes precedence
def _configure_espeak():
    if "PHONEMIZER_ESPEAK_LIBRARY" in os.environ and os.environ["PHONEMIZER_ESPEAK_LIBRARY"]:
        return  # Already configured via .env
    if sys.platform == "darwin":
        for lib_path in ["/opt/homebrew/lib/libespeak-ng.dylib", "/usr/local/lib/libespeak-ng.dylib"]:
            if Path(lib_path).exists():
                os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = lib_path
                break

# Configure logging to stderr (visible in MCP logs)
LOG_LEVEL = os.getenv("TTS_LOG_LEVEL", "WARNING").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.WARNING),
    format="[claude-say] %(levelname)s: %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("claude-say")


def load_env_file():
    """Load configuration from ~/.mcp-claude-say/.env file.

    This allows centralized config without requiring python-dotenv.
    Only sets env vars if not already set (os.environ.setdefault).
    """
    env_path = Path.home() / ".mcp-claude-say" / ".env"
    if not env_path.exists():
        logger.debug(f"No .env file found at {env_path}")
        return

    try:
        loaded_vars = []
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
                loaded_vars.append(f"{key}={val}")
        logger.debug(f"Loaded from .env: {', '.join(loaded_vars)}")
    except Exception as e:
        logger.warning(f"Error loading .env: {e}")


# Load .env file before any env var reads
load_env_file()

# Configure espeak after loading .env (for French/multilingual)
_configure_espeak()

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
# Options: "kokoro" (local MLX, 82M), "chatterbox" (local neural, 11GB), "google" (cloud, needs API key), "macos" (built-in)
TTS_BACKEND = os.getenv("TTS_BACKEND", "macos").lower()

# Kokoro MLX configuration (for TTS_BACKEND=kokoro)
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")  # Default: American English female
KOKORO_SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))

# Chatterbox configuration (for TTS_BACKEND=chatterbox)
CHATTERBOX_URL = os.getenv("CHATTERBOX_URL", "http://127.0.0.1:8123")
USE_CHATTERBOX = TTS_BACKEND == "chatterbox" or os.getenv("USE_CHATTERBOX", "0") == "1"
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "female_voice")

# Google Cloud TTS configuration (for TTS_BACKEND=google)
GOOGLE_CLOUD_API_KEY = os.getenv("GOOGLE_CLOUD_API_KEY", "")
GOOGLE_VOICE = os.getenv("GOOGLE_VOICE", "en-US-Neural2-F")  # Neural2 voices are in free tier
GOOGLE_LANGUAGE = os.getenv("GOOGLE_LANGUAGE", "en-US")

# Kokoro TTS instance (lazy-loaded)
_kokoro_tts = None
_kokoro_lock = threading.Lock()

# Log configuration at startup
logger.info(f"TTS Backend: {TTS_BACKEND}")
if TTS_BACKEND == "kokoro":
    logger.info(f"Kokoro voice: {KOKORO_VOICE}, speed: {KOKORO_SPEED}")

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


def kokoro_available() -> bool:
    """Check if Kokoro MLX TTS is available."""
    if TTS_BACKEND != "kokoro":
        return False
    try:
        from mlx_audio_tts import HAS_MLX_AUDIO
        return HAS_MLX_AUDIO
    except ImportError:
        return False


def get_kokoro_tts():
    """Get or create Kokoro TTS instance (singleton)."""
    global _kokoro_tts
    with _kokoro_lock:
        if _kokoro_tts is None:
            try:
                from mlx_audio_tts import MLXAudioTTS

                # Validate voice, fallback to default if invalid
                voice_to_use = KOKORO_VOICE
                if voice_to_use not in MLXAudioTTS.VOICES:
                    logger.warning(f"Invalid KOKORO_VOICE '{voice_to_use}', using 'af_heart'")
                    voice_to_use = "af_heart"

                _kokoro_tts = MLXAudioTTS(voice=voice_to_use, speed=KOKORO_SPEED)
                logger.info(f"Kokoro TTS initialized: voice={voice_to_use}, speed={KOKORO_SPEED}")
            except Exception as e:
                logger.error(f"Failed to initialize Kokoro TTS: {e}")
                return None
        return _kokoro_tts


def speak_with_kokoro(text: str, blocking: bool = True, voice: str = None) -> bool:
    """
    Speak using Kokoro MLX TTS.
    Returns True if successful, False if unavailable.
    """
    global current_afplay
    tts = get_kokoro_tts()
    if tts is None:
        return False

    try:
        import soundfile as sf

        # Use specified voice, or configured KOKORO_VOICE, or instance default
        if voice and voice in tts.VOICES:
            use_voice = voice
        else:
            use_voice = KOKORO_VOICE if KOKORO_VOICE in tts.VOICES else tts.voice

        logger.debug(f"Kokoro TTS using voice: {use_voice}")

        # Synthesize audio
        audio_array, sr = tts.synthesize(text, voice=use_voice)

        # Save to temp file and play with afplay
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False, prefix="kokoro_tts_") as f:
            sf.write(f.name, audio_array, sr)
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

        return True
    except Exception as e:
        logger.error(f"Kokoro TTS error: {e}")
        return False


def stop_kokoro():
    """Stop any Kokoro playback (via afplay)."""
    global current_afplay
    with process_lock:
        if current_afplay and current_afplay.poll() is None:
            current_afplay.terminate()
            current_afplay = None
            return True
    return False


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
    logger.info("Speech worker thread started")
    while True:
        try:
            item = speech_queue.get(timeout=1.0)
        except Empty:
            continue

        if item is None:  # Stop signal
            logger.info("Speech worker received stop signal")
            break

        # Check for stop signal - if present, clear queue and skip this item
        if check_and_clear_stop_signal():
            logger.debug("Stop signal detected, clearing queue")
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
        logger.debug(f"Processing speech: {text[:50]}... (neural={use_neural})")
        # Remove macOS-specific silence markup for neural backends
        clean_text = text.replace(f" [[slnc {TRAILING_SILENCE_MS}]]", "")

        # Try Kokoro MLX TTS first (if configured)
        if use_neural and kokoro_available():
            if speak_with_kokoro(clean_text, blocking=True, voice=voice):
                speech_queue.task_done()
                continue
            # Fall through to other backends if Kokoro fails

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


_worker_lock = threading.Lock()


def ensure_worker_running():
    """Ensure the worker thread is running. Thread-safe."""
    global worker_thread
    with _worker_lock:
        if worker_thread is None or not worker_thread.is_alive():
            logger.info("Starting new speech worker thread")
            worker_thread = threading.Thread(target=speech_worker, daemon=True)
            worker_thread.start()
            # Give the thread a moment to start
            time.sleep(0.01)
        else:
            logger.debug(f"Worker thread alive: {worker_thread.is_alive()}")


# Trailing silence in milliseconds to prevent last word from being cut off
TRAILING_SILENCE_MS = 300


@mcp.tool()
def speak(text: str, voice: str | None = None, speed: float = 1.0) -> str:
    """Queue TTS without waiting. Args: text, voice, speed (1.0=normal)"""
    logger.info(f"speak() called: {text[:50]}...")
    ensure_worker_running()
    rate = int(speed * 175)  # 175 words/min = normal speed

    # Determine if we should use neural TTS (default backend or explicit request)
    # Check if voice is a Kokoro voice ID (2-character prefix like af_, bf_, ff_, etc.)
    is_kokoro_voice = voice and len(voice) >= 3 and voice[1] in "mf" and voice[2] == "_"
    use_neural = voice is None or voice.lower() in ("chatterbox", "google", "kokoro") or is_kokoro_voice
    macos_voice = None if use_neural else voice

    # Add trailing silence so the last word is fully heard (for macOS voices)
    text_with_silence = f"{text} [[slnc {TRAILING_SILENCE_MS}]]"

    # Pass Kokoro voice ID if specified
    neural_voice = voice if is_kokoro_voice else None
    speech_queue.put((text_with_silence, neural_voice if use_neural else macos_voice, rate, use_neural))
    logger.debug(f"Queued message, queue size: {speech_queue.qsize()}")

    backend_name = TTS_BACKEND if use_neural else voice
    return f"Queued ({backend_name})"


@mcp.tool()
def speak_and_wait(text: str, voice: str | None = None, speed: float = 1.1) -> str:
    """Speak and wait for completion. Args: text, voice, speed (1.1=default)"""
    logger.info(f"speak_and_wait() called: {text[:50]}...")
    ensure_worker_running()
    rate = int(speed * 175)  # 175 words/min = normal speed

    # Determine if we should use neural TTS (default backend or explicit request)
    # Check if voice is a Kokoro voice ID (2-character prefix like af_, bf_, ff_, etc.)
    is_kokoro_voice = voice and len(voice) >= 3 and voice[1] in "mf" and voice[2] == "_"
    use_neural = voice is None or voice.lower() in ("chatterbox", "google", "kokoro") or is_kokoro_voice
    macos_voice = None if use_neural else voice

    # Add trailing silence so the last word is fully heard (for macOS voices)
    text_with_silence = f"{text} [[slnc {TRAILING_SILENCE_MS}]]"

    # Pass Kokoro voice ID if specified
    neural_voice = voice if is_kokoro_voice else None
    speech_queue.put((text_with_silence, neural_voice if use_neural else macos_voice, rate, use_neural))
    logger.debug(f"Queued message, queue size: {speech_queue.qsize()}")

    # Wait for the queue to be processed
    logger.debug("Waiting for queue to empty...")
    speech_queue.join()
    logger.debug("Queue empty, speech completed")

    # Clear any segments recorded during TTS (feedback loop prevention)
    clear_listen_segments()

    # Play ready sound to indicate listening is active
    play_ready_sound()

    # Phase 2: Signal TTS completion for auto-start listening
    signal_tts_complete()
    logger.debug("TTS complete signal sent")

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

    # Stop Kokoro playback (if enabled)
    if TTS_BACKEND == "kokoro":
        stop_kokoro()

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
