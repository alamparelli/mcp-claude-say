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


# Signal file for stop communication
STOP_SIGNAL_FILE = Path("/tmp/claude-voice-stop")


def signal_stop_speaking() -> bool:
    """
    Signal claude-say to stop speaking.

    This is called by claude-listen when speech is detected,
    to interrupt the TTS output.

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
