"""
Coordination module for claude-say and claude-listen.
Handles communication between TTS and STT servers.
"""

import subprocess
from pathlib import Path
from typing import Optional
import os


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
    try:
        # Method 1: Use the MCP tool directly if in same process
        # This requires importing the say module
        try:
            import sys
            say_path = Path(__file__).parent.parent
            if str(say_path) not in sys.path:
                sys.path.insert(0, str(say_path))

            # Try to import and call stop_speaking directly
            # This works if both servers run in same process or share state
            from mcp_server import stop_speaking
            stop_speaking()
            return True
        except ImportError:
            pass

        # Method 2: Use signal file
        STOP_SIGNAL_FILE.touch()
        return True

    except Exception as e:
        print(f"Error signaling stop: {e}")
        return False


def check_stop_signal() -> bool:
    """
    Check if a stop signal has been sent.

    Called by claude-say to check if it should stop.

    Returns:
        True if stop signal is present
    """
    if STOP_SIGNAL_FILE.exists():
        STOP_SIGNAL_FILE.unlink()  # Clear the signal
        return True
    return False


def is_speaking() -> bool:
    """
    Check if claude-say is currently speaking.

    Returns:
        True if TTS is active
    """
    try:
        # Check if macOS 'say' process is running
        result = subprocess.run(
            ["pgrep", "-x", "say"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
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
