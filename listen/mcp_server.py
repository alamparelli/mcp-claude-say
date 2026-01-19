#!/usr/bin/env python3
"""
Claude-Listen MCP Server - Simple PTT Mode
Speech-to-Text for Claude Code using Push-to-Talk.

Simple operation:
- start_ptt_mode(key): Start listening for hotkey
- Press hotkey to start recording
- Press hotkey again to stop and transcribe
- get_segment_transcription(): Get the transcribed text

DEBUG: Logs go to stderr (visible in Claude Code's MCP console)
"""

import subprocess
import threading
import sys
from typing import Optional
from pathlib import Path

print("[claude-listen] MCP Server starting...", file=sys.stderr)

from mcp.server.fastmcp import FastMCP
print("[claude-listen] FastMCP imported", file=sys.stderr)

from .simple_ptt import SimplePTTRecorder, get_simple_ptt, destroy_simple_ptt
print("[claude-listen] simple_ptt imported", file=sys.stderr)

from .ptt_controller import (
    PTTController, PTTConfig, PTTState,
    get_ptt_controller, create_ptt_controller, destroy_ptt_controller
)
print("[claude-listen] ptt_controller imported", file=sys.stderr)

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.coordination import signal_stop_speaking
print("[claude-listen] shared.coordination imported", file=sys.stderr)

mcp = FastMCP("claude-listen")
print("[claude-listen] FastMCP instance created", file=sys.stderr)

# State
_transcription_ready = threading.Event()
_last_transcription: Optional[str] = None
_current_status: str = "ready"  # ready, recording, transcribing


def _on_transcription_ready(text: str) -> None:
    """Callback when transcription is ready."""
    global _last_transcription, _current_status
    print(f"[claude-listen] Transcription ready: {text[:50]}...", file=sys.stderr)
    _last_transcription = text
    _current_status = "ready"
    _transcription_ready.set()


def _ptt_start_recording() -> None:
    """Called when PTT key pressed - start recording."""
    global _current_status
    print("[claude-listen] _ptt_start_recording callback triggered", file=sys.stderr)
    # Stop any TTS playback immediately (afplay is used by claude-say)
    subprocess.run(["pkill", "-9", "afplay"], capture_output=True)
    _current_status = "recording"
    recorder = get_simple_ptt(on_transcription_ready=_on_transcription_ready)
    recorder.start()
    print("[claude-listen] Recording started via callback", file=sys.stderr)


def _ptt_stop_recording() -> None:
    """Called when PTT key pressed again - stop and transcribe."""
    global _current_status
    print("[claude-listen] _ptt_stop_recording callback triggered", file=sys.stderr)
    _current_status = "transcribing"
    recorder = get_simple_ptt()
    recorder.stop()
    print("[claude-listen] Recording stopped, transcription in progress", file=sys.stderr)


@mcp.tool()
def start_ptt_mode(key: str = "cmd_r") -> str:
    """
    Start Push-to-Talk mode with global hotkey detection.

    In PTT mode:
    - Press the hotkey to START recording
    - Press again to STOP recording and transcribe

    Available keys: cmd_r (Right Command), cmd_l, alt_r, alt_l, ctrl_r, ctrl_l,
                   shift_r, shift_l, f13, f14, f15, space
    Combos supported: cmd_r+m, ctrl_l+r, etc.

    Args:
        key: The key to use for PTT toggle (default: cmd_r = Right Command)

    Returns:
        Confirmation message
    """
    print(f"[claude-listen] start_ptt_mode called with key={key}", file=sys.stderr)

    try:
        existing = get_ptt_controller()
        if existing is not None and existing.is_active:
            msg = f"PTT mode already active (state: {existing.state.value})"
            print(f"[claude-listen] {msg}", file=sys.stderr)
            return msg

        print(f"[claude-listen] Creating PTT controller with key={key}", file=sys.stderr)
        config = PTTConfig(
            key=key,
            on_start_recording=_ptt_start_recording,
            on_stop_recording=_ptt_stop_recording,
        )

        controller = create_ptt_controller(config)
        print("[claude-listen] PTT controller created, starting...", file=sys.stderr)
        controller.start()

        msg = f"PTT mode activated. Press {key.replace('_', ' ').title()} to toggle recording."
        print(f"[claude-listen] {msg}", file=sys.stderr)
        return msg

    except Exception as e:
        print(f"[claude-listen] ERROR starting PTT mode: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return f"Error starting PTT mode: {e}"


@mcp.tool()
def stop_ptt_mode() -> str:
    """
    Stop Push-to-Talk mode and RELEASE the microphone.

    This will also stop any active recording and turn off
    the macOS orange mic indicator.

    Returns:
        Summary of PTT session
    """
    print("[claude-listen] stop_ptt_mode called", file=sys.stderr)

    controller = get_ptt_controller()
    if controller is None or not controller.is_active:
        print("[claude-listen] PTT mode not active, nothing to stop", file=sys.stderr)
        return "PTT mode not active."

    print("[claude-listen] Destroying PTT controller...", file=sys.stderr)
    destroy_ptt_controller()

    print("[claude-listen] Destroying SimplePTT (releases mic)...", file=sys.stderr)
    destroy_simple_ptt()

    print("[claude-listen] PTT mode fully deactivated, mic released", file=sys.stderr)
    return "PTT mode deactivated. Microphone released."


@mcp.tool()
def get_ptt_status() -> str:
    """
    Get current Push-to-Talk status.

    Returns:
        PTT state and recording status
    """
    controller = get_ptt_controller()

    if controller is None or not controller.is_active:
        return "inactive"

    return _current_status


@mcp.tool()
def get_segment_transcription(wait: bool = True, timeout: float = 120.0) -> str:
    """
    Get the latest segment transcription.

    In segmented mode, this returns transcriptions as they become available.
    Use this in a loop to get real-time transcription feedback.

    Args:
        wait: If True, wait for a new segment transcription
        timeout: Maximum time to wait in seconds

    Returns:
        Latest segment transcription or status message:
        - "[Ready]" - Waiting for user to start recording
        - "[Recording...]" - Currently recording audio
        - "[Transcribing...]" - Processing audio to text
        - "[Timeout: No transcription received]" - Wait timed out
        - Otherwise: The actual transcription text
    """
    global _last_transcription

    controller = get_ptt_controller()
    if controller is None or not controller.is_active:
        return "[PTT mode not active. Use start_ptt_mode() first.]"

    if wait:
        _transcription_ready.clear()
        got_result = _transcription_ready.wait(timeout=timeout)

        if not got_result:
            return "[Timeout: No transcription received]"

    # If not waiting or transcription ready, check status
    if _current_status == "recording":
        return "[Recording...]"
    elif _current_status == "transcribing":
        return "[Transcribing...]"
    elif _last_transcription is None:
        return "[Ready]"

    result = _last_transcription
    return result


if __name__ == "__main__":
    print("[claude-listen] Starting MCP server via mcp.run()...", file=sys.stderr)
    print("[claude-listen] Available tools: start_ptt_mode, stop_ptt_mode, get_ptt_status, get_segment_transcription", file=sys.stderr)
    mcp.run()
