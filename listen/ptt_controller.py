"""
Push-to-Talk Controller with Global Hotkey Detection.

Uses pynput to detect global key events for PTT functionality.
Hybrid mode: PTT controls session start/stop, VAD segments long recordings.

IMPORTANT: pynput requires Accessibility permissions on macOS.
Go to System Settings → Privacy & Security → Accessibility and enable
the app running this code (Terminal, Cursor, VS Code, etc.)
"""

import threading
import sys
from typing import Optional, Callable
from enum import Enum
from dataclasses import dataclass

print("[PTTController] Loading module...", file=sys.stderr)

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
    print("[PTTController] pynput loaded successfully", file=sys.stderr)
except ImportError as e:
    PYNPUT_AVAILABLE = False
    print(f"[PTTController] WARNING: pynput not installed. PTT will not work. Error: {e}", file=sys.stderr)


class PTTState(Enum):
    """Push-to-talk state."""
    IDLE = "idle"           # PTT not active, not listening for key
    LISTENING = "listening"  # PTT active, waiting for key press
    RECORDING = "recording"  # Currently recording


@dataclass
class PTTConfig:
    """Configuration for push-to-talk."""
    # Key to use for PTT (default: left command + s)
    key: str = "cmd_l+s"

    # Callback functions
    on_start_recording: Optional[Callable[[], None]] = None
    on_stop_recording: Optional[Callable[[], None]] = None
    on_state_change: Optional[Callable[[PTTState], None]] = None


# Key mapping for pynput
KEY_MAP = {
    "cmd_r": keyboard.Key.cmd_r if PYNPUT_AVAILABLE else None,
    "cmd_l": keyboard.Key.cmd_l if PYNPUT_AVAILABLE else None,
    "alt_r": keyboard.Key.alt_r if PYNPUT_AVAILABLE else None,
    "alt_l": keyboard.Key.alt_l if PYNPUT_AVAILABLE else None,
    "ctrl_r": keyboard.Key.ctrl_r if PYNPUT_AVAILABLE else None,
    "ctrl_l": keyboard.Key.ctrl_l if PYNPUT_AVAILABLE else None,
    "shift_r": keyboard.Key.shift_r if PYNPUT_AVAILABLE else None,
    "shift_l": keyboard.Key.shift_l if PYNPUT_AVAILABLE else None,
    "f13": keyboard.Key.f13 if PYNPUT_AVAILABLE else None,
    "f14": keyboard.Key.f14 if PYNPUT_AVAILABLE else None,
    "f15": keyboard.Key.f15 if PYNPUT_AVAILABLE else None,
    "space": keyboard.Key.space if PYNPUT_AVAILABLE else None,
}

# Combo key support - format: "modifier+key"
def parse_combo_key(key_string: str):
    """Parse a key combo string like 'cmd_r+m' into component parts."""
    if "+" in key_string:
        parts = key_string.split("+")
        modifier = KEY_MAP.get(parts[0])
        # For letter keys, we just store the character
        char_key = parts[1].lower() if len(parts[1]) == 1 else None
        return (modifier, char_key)
    else:
        return (KEY_MAP.get(key_string), None)


class PTTController:
    """
    Push-to-Talk controller with global hotkey detection.

    Toggle mode: Press key once to start recording, press again to stop.
    Integrates with segmented recorder for hybrid VAD mode.

    Usage:
        controller = PTTController(config)
        controller.start()  # Start listening for hotkey

        # ... user presses Right Cmd to toggle recording ...

        controller.stop()   # Stop listening
    """

    def __init__(self, config: Optional[PTTConfig] = None):
        """
        Initialize PTT controller.

        Args:
            config: PTT configuration with callbacks
        """
        print(f"[PTTController] Initializing with config key: {config.key if config else 'default'}", file=sys.stderr)

        if not PYNPUT_AVAILABLE:
            print("[PTTController] ERROR: pynput not available!", file=sys.stderr)
            raise RuntimeError("pynput is required for PTT. Install with: pip install pynput")

        self.config = config or PTTConfig()
        self._state = PTTState.IDLE
        self._listener: Optional[keyboard.Listener] = None
        self._lock = threading.Lock()

        # Track currently pressed keys for combo detection
        self._pressed_keys = set()
        self._combo_triggered = False

        # Parse key config - supports combos like "cmd_r+m"
        self._modifier_key, self._char_key = parse_combo_key(self.config.key)
        self._is_combo = self._char_key is not None

        print(f"[PTTController] Parsed key: modifier={self._modifier_key}, char={self._char_key}, is_combo={self._is_combo}", file=sys.stderr)

        if self._modifier_key is None:
            print(f"[PTTController] ERROR: Unknown key: {self.config.key}", file=sys.stderr)
            raise ValueError(f"Unknown key: {self.config.key}. Available: {list(KEY_MAP.keys())} or combos like 'cmd_r+m'")

        print("[PTTController] Initialized successfully", file=sys.stderr)

    @property
    def state(self) -> PTTState:
        """Get current PTT state."""
        return self._state

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._state == PTTState.RECORDING

    @property
    def is_active(self) -> bool:
        """Check if PTT is active (listening or recording)."""
        return self._state != PTTState.IDLE

    def _set_state(self, new_state: PTTState) -> None:
        """Update state and trigger callback."""
        old_state = self._state
        self._state = new_state

        if old_state != new_state and self.config.on_state_change:
            try:
                self.config.on_state_change(new_state)
            except Exception as e:
                print(f"Error in state change callback: {e}")

    def _get_key_char(self, key) -> Optional[str]:
        """Extract character from key if it's a character key."""
        try:
            return key.char.lower() if hasattr(key, 'char') and key.char else None
        except AttributeError:
            return None

    def _check_combo(self) -> bool:
        """Check if the required combo keys are pressed."""
        if not self._is_combo:
            return self._modifier_key in self._pressed_keys

        # For combo: check modifier is pressed AND char key is pressed
        modifier_pressed = self._modifier_key in self._pressed_keys
        char_pressed = self._char_key in self._pressed_keys
        return modifier_pressed and char_pressed

    def _on_key_press(self, key) -> None:
        """Handle key press event."""
        # Log all key presses for debugging (only when not combo triggered to reduce noise)
        if not self._combo_triggered:
            print(f"[PTTController] Key press detected: {key}", file=sys.stderr)

        # Track this key
        if key == self._modifier_key:
            self._pressed_keys.add(self._modifier_key)
            print(f"[PTTController] Modifier key pressed: {key}", file=sys.stderr)
        else:
            char = self._get_key_char(key)
            if char and char == self._char_key:
                self._pressed_keys.add(char)
                print(f"[PTTController] Char key pressed: {char}", file=sys.stderr)

        # Check if combo is complete
        if not self._check_combo():
            return

        # Prevent re-triggering while keys still held
        if self._combo_triggered:
            return
        self._combo_triggered = True

        print(f"[PTTController] Combo triggered! State: {self._state.value}", file=sys.stderr)

        with self._lock:
            if self._state == PTTState.LISTENING:
                # Start recording
                self._set_state(PTTState.RECORDING)
                print(f"🎤 PTT: Recording started", file=sys.stderr)

                if self.config.on_start_recording:
                    try:
                        print("[PTTController] Calling on_start_recording callback", file=sys.stderr)
                        self.config.on_start_recording()
                    except Exception as e:
                        print(f"[PTTController] Error in start recording callback: {e}", file=sys.stderr)

            elif self._state == PTTState.RECORDING:
                # Stop recording
                self._set_state(PTTState.LISTENING)
                print(f"⏹️  PTT: Recording stopped", file=sys.stderr)

                if self.config.on_stop_recording:
                    try:
                        print("[PTTController] Calling on_stop_recording callback", file=sys.stderr)
                        self.config.on_stop_recording()
                    except Exception as e:
                        print(f"[PTTController] Error in stop recording callback: {e}", file=sys.stderr)

    def _on_key_release(self, key) -> None:
        """Handle key release event - reset combo trigger."""
        # Remove key from pressed set
        if key == self._modifier_key:
            self._pressed_keys.discard(self._modifier_key)
        else:
            char = self._get_key_char(key)
            if char:
                self._pressed_keys.discard(char)

        # Reset combo trigger when any combo key is released
        if not self._check_combo():
            self._combo_triggered = False

    def start(self) -> None:
        """Start listening for PTT hotkey."""
        print("[PTTController] start() called", file=sys.stderr)

        if self._listener is not None:
            print("[PTTController] Listener already exists, PTT already active", file=sys.stderr)
            return

        self._set_state(PTTState.LISTENING)

        print("[PTTController] Creating keyboard.Listener...", file=sys.stderr)
        try:
            self._listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release
            )
            self._listener.start()
            print(f"[PTTController] Keyboard listener started (thread alive: {self._listener.is_alive()})", file=sys.stderr)
        except Exception as e:
            print(f"[PTTController] ERROR: Failed to start keyboard listener: {e}", file=sys.stderr)
            raise

        key_name = self.config.key.replace("_", " ").title()
        print(f"🎯 PTT mode active - Press {key_name} to toggle recording", file=sys.stderr)
        print(f"[PTTController] Waiting for key: {key_name} (modifier={self._modifier_key})", file=sys.stderr)

    def stop(self) -> None:
        """Stop listening for PTT hotkey."""
        print("[PTTController] stop() called", file=sys.stderr)

        if self._listener is None:
            print("[PTTController] No listener to stop", file=sys.stderr)
            return

        # If recording, stop it first
        if self._state == PTTState.RECORDING and self.config.on_stop_recording:
            print("[PTTController] Was recording, calling stop callback", file=sys.stderr)
            try:
                self.config.on_stop_recording()
            except Exception as e:
                print(f"[PTTController] Error stopping recording: {e}", file=sys.stderr)

        print("[PTTController] Stopping keyboard listener...", file=sys.stderr)
        self._listener.stop()
        self._listener = None
        self._set_state(PTTState.IDLE)

        print("🛑 PTT mode deactivated", file=sys.stderr)
        print("[PTTController] PTT controller stopped", file=sys.stderr)

    def force_stop_recording(self) -> None:
        """Force stop recording without stopping PTT mode."""
        with self._lock:
            if self._state == PTTState.RECORDING:
                self._set_state(PTTState.LISTENING)

                if self.config.on_stop_recording:
                    try:
                        self.config.on_stop_recording()
                    except Exception as e:
                        print(f"Error in stop recording callback: {e}")


# Global PTT instance for MCP server
_ptt_controller: Optional[PTTController] = None


def get_ptt_controller() -> Optional[PTTController]:
    """Get the global PTT controller instance."""
    return _ptt_controller


def create_ptt_controller(config: Optional[PTTConfig] = None) -> PTTController:
    """Create and set the global PTT controller."""
    global _ptt_controller
    _ptt_controller = PTTController(config)
    return _ptt_controller


def destroy_ptt_controller() -> None:
    """Stop and destroy the global PTT controller."""
    global _ptt_controller
    if _ptt_controller is not None:
        _ptt_controller.stop()
        _ptt_controller = None
