"""
Coordination module for claude-say and claude-listen.
Handles communication between TTS and STT servers.
"""

import subprocess
from pathlib import Path
from typing import Optional
import os
import sys

# Add listen module to path for logger
_listen_path = Path(__file__).parent.parent / "listen"
if str(_listen_path) not in sys.path:
    sys.path.insert(0, str(_listen_path))

try:
    from logger import get_logger
    log = get_logger("coordination")
except ImportError:
    # Fallback if logger not available (e.g., called from say server)
    import logging
    log = logging.getLogger("coordination")
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s'))
        log.addHandler(handler)
        log.setLevel(logging.DEBUG)


# Signal files for coordination
STOP_SIGNAL_FILE = Path("/tmp/claude-voice-stop")
TTS_COMPLETE_SIGNAL_FILE = Path("/tmp/claude-tts-complete")


def force_stop_tts() -> bool:
    """
    Force stop all TTS playback immediately.

    Kills say/afplay processes directly (immediate) + sets signal file (clears queue).
    This is the preferred method for barge-in as it's instantaneous.

    Returns:
        True if any process was killed or signal was sent
    """
    log.info("force_stop_tts() called - killing TTS processes")

    killed = False

    # Kill macOS say process
    try:
        result = subprocess.run(["pkill", "-x", "say"], capture_output=True)
        if result.returncode == 0:
            killed = True
            log.info("Killed 'say' process")
    except Exception as e:
        log.debug(f"Error killing say: {e}")

    # Kill afplay process (used by Kokoro/Google TTS)
    try:
        result = subprocess.run(["pkill", "-x", "afplay"], capture_output=True)
        if result.returncode == 0:
            killed = True
            log.info("Killed 'afplay' process")
    except Exception as e:
        log.debug(f"Error killing afplay: {e}")

    # Also set signal file to clear the queue in speech_worker
    STOP_SIGNAL_FILE.touch()
    log.info("Stop signal file created (queue will be cleared)")

    return killed or True  # Always return True since signal file is set


def signal_stop_speaking() -> bool:
    """
    Signal claude-say to stop speaking.

    This is called by claude-listen when speech is detected,
    to interrupt the TTS output.

    NOTE: For immediate barge-in, use force_stop_tts() instead.

    Returns:
        True if signal was sent successfully
    """
    log.info("signal_stop_speaking() called")

    try:
        # Method 1: Use the MCP tool directly if in same process
        # This requires importing the say module
        try:
            say_path = Path(__file__).parent.parent
            if str(say_path) not in sys.path:
                sys.path.insert(0, str(say_path))

            # Try to import and call stop_speaking directly
            # This works if both servers run in same process or share state
            from mcp_server import stop_speaking
            log.info("Direct import of stop_speaking succeeded, calling it...")
            stop_speaking()
            log.info("stop_speaking() called successfully via direct import")
            return True
        except ImportError as e:
            log.debug(f"Direct import failed (expected in separate processes): {e}")

        # Method 2: Use signal file
        log.info(f"Using signal file method: touching {STOP_SIGNAL_FILE}")
        STOP_SIGNAL_FILE.touch()
        log.info("Signal file created successfully")
        return True

    except Exception as e:
        log.error(f"Error signaling stop: {e}")
        return False


def check_stop_signal() -> bool:
    """
    Check if a stop signal has been sent.

    Called by claude-say to check if it should stop.

    Returns:
        True if stop signal is present
    """
    if STOP_SIGNAL_FILE.exists():
        log.info("Stop signal detected! Clearing signal file and returning True")
        STOP_SIGNAL_FILE.unlink()  # Clear the signal
        return True
    return False


# Cache for is_speaking() to avoid spawning subprocess on every audio chunk
_is_speaking_cache = {"value": False, "timestamp": 0.0}
_IS_SPEAKING_CACHE_TTL = 0.3  # Check every 300ms


def is_speaking() -> bool:
    """
    Check if claude-say is currently speaking.

    Uses caching to avoid spawning a subprocess on every audio chunk.
    The cache is refreshed every 300ms.

    Returns:
        True if TTS is active
    """
    import time

    now = time.time()

    # Return cached value if still valid
    if now - _is_speaking_cache["timestamp"] < _IS_SPEAKING_CACHE_TTL:
        return _is_speaking_cache["value"]

    # Refresh cache
    try:
        # Check if macOS 'say' process is running
        result = subprocess.run(
            ["pgrep", "-x", "say"],
            capture_output=True,
            text=True
        )
        is_active = result.returncode == 0
        _is_speaking_cache["value"] = is_active
        _is_speaking_cache["timestamp"] = now
        return is_active
    except Exception:
        _is_speaking_cache["value"] = False
        _is_speaking_cache["timestamp"] = now
        return False


def clear_stop_signal() -> None:
    """Clear any pending stop signal."""
    if STOP_SIGNAL_FILE.exists():
        try:
            STOP_SIGNAL_FILE.unlink()
        except Exception:
            pass


# ============================================================================
# Phase 2: TTS Completion Signaling (Auto-Start after TTS)
# ============================================================================

def signal_tts_complete() -> bool:
    """
    Signal that TTS has completed speaking.

    Called by claude-say when speak_and_wait() finishes.
    Claude-listen monitors this signal to auto-start recording.

    Returns:
        True if signal was sent successfully
    """
    log.info("signal_tts_complete() called")
    try:
        TTS_COMPLETE_SIGNAL_FILE.touch()
        log.info(f"TTS complete signal created: {TTS_COMPLETE_SIGNAL_FILE}")
        return True
    except Exception as e:
        log.error(f"Error creating TTS complete signal: {e}")
        return False


def wait_for_tts_complete(timeout: float = 30.0) -> bool:
    """
    Wait for TTS completion signal.

    Called by claude-listen when auto_start is enabled.
    Blocks until signal is received or timeout.

    Args:
        timeout: Maximum time to wait in seconds

    Returns:
        True if signal received, False on timeout
    """
    import time

    log.info(f"Waiting for TTS complete signal (timeout={timeout}s)...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        if TTS_COMPLETE_SIGNAL_FILE.exists():
            log.info("TTS complete signal received!")
            # Clear the signal
            try:
                TTS_COMPLETE_SIGNAL_FILE.unlink()
            except Exception:
                pass
            return True
        time.sleep(0.05)  # Poll every 50ms

    log.warning(f"Timeout waiting for TTS complete signal after {timeout}s")
    return False


def clear_tts_complete_signal() -> None:
    """Clear any pending TTS complete signal."""
    if TTS_COMPLETE_SIGNAL_FILE.exists():
        try:
            TTS_COMPLETE_SIGNAL_FILE.unlink()
            log.debug("Cleared stale TTS complete signal")
        except Exception:
            pass


class VoiceCoordinator:
    """
    Coordinates between TTS and STT.

    Ensures that:
    - STT can interrupt TTS when user speaks
    - No feedback loop (not listening to TTS output)
    """

    def __init__(self):
        self._listening = False
        self._speaking = False

    def start_listening(self) -> None:
        """Mark that STT is active."""
        self._listening = True

    def stop_listening(self) -> None:
        """Mark that STT is inactive."""
        self._listening = False

    def start_speaking(self) -> None:
        """Mark that TTS is active."""
        self._speaking = True

    def stop_speaking(self) -> None:
        """Mark that TTS is inactive."""
        self._speaking = False

    @property
    def is_listening(self) -> bool:
        return self._listening

    @property
    def is_speaking(self) -> bool:
        return self._speaking or is_speaking()

    def on_speech_detected(self) -> None:
        """Called when VAD detects speech - interrupts TTS."""
        if self.is_speaking:
            signal_stop_speaking()


# Global coordinator instance
_coordinator: Optional[VoiceCoordinator] = None


def get_coordinator() -> VoiceCoordinator:
    """Get or create the global VoiceCoordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = VoiceCoordinator()
    return _coordinator
