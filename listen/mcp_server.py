#!/usr/bin/env python3
"""
Claude-Listen MCP Server - Simplified PTT Mode
Speech-to-Text for Claude Code using simple Push-to-Talk.

Two modes available:
1. Synchronous (blocking): start_ptt_mode() + get_segment_transcription()
2. Background (non-blocking): start_ptt_background() + check_transcription()

Simple operation:
- start_ptt(key): Start listening for hotkey
- Press hotkey to start recording
- Press hotkey again to stop and transcribe
- get_transcription(): Get the transcribed text
"""

import os
import json
import threading
import subprocess
from typing import Optional
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from .simple_ptt import SimplePTTRecorder, get_simple_ptt, destroy_simple_ptt
from .ptt_controller import (
    PTTController, PTTConfig, PTTState,
    get_ptt_controller, create_ptt_controller, destroy_ptt_controller
)

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.coordination import signal_stop_speaking

mcp = FastMCP("claude-listen")

# Background process state
_background_process: Optional[subprocess.Popen] = None
_background_output_file = Path("/tmp/claude-ptt/transcriptions.jsonl")
_last_read_count = 0

# State
_transcription_ready = threading.Event()
_last_transcription: Optional[str] = None


def _on_transcription_ready(text: str) -> None:
    """Callback when transcription is ready."""
    global _last_transcription
    _last_transcription = text
    _transcription_ready.set()


def _ptt_start_recording() -> None:
    """Called when PTT key pressed - start recording."""
    signal_stop_speaking()  # Stop any TTS
    recorder = get_simple_ptt(on_transcription_ready=_on_transcription_ready)
    recorder.start()


def _ptt_stop_recording() -> None:
    """Called when PTT key pressed again - stop and transcribe."""
    recorder = get_simple_ptt()
    recorder.stop()


@mcp.tool()
def start_ptt_mode(key: str = "cmd_l+s") -> str:
    """
    Start Push-to-Talk mode with global hotkey detection.

    In PTT mode:
    - Press the hotkey combo to START recording
    - Press again to STOP recording and transcribe

    Available keys: cmd_r, cmd_l, alt_r, alt_l, ctrl_r, ctrl_l,
                   shift_r, shift_l, f13, f14, f15, space
    Combos supported: cmd_r+m, ctrl_l+r, etc.

    Args:
        key: The key combo to use for PTT toggle (default: cmd_l+s = Left Command + S)

    Returns:
        Confirmation message
    """
    try:
        existing = get_ptt_controller()
        if existing is not None and existing.is_active:
            return f"PTT mode already active (state: {existing.state.value})"

        config = PTTConfig(
            key=key,
            on_start_recording=_ptt_start_recording,
            on_stop_recording=_ptt_stop_recording,
        )

        controller = create_ptt_controller(config)
        controller.start()

        # Format key name nicely
        if "+" in key:
            parts = key.split("+")
            key_name = parts[0].replace("_", " ").title() + " + " + parts[1].upper()
        else:
            key_name = key.replace("_", " ").title()

        return f"PTT mode activated. Press {key_name} to toggle recording."

    except Exception as e:
        return f"Error starting PTT mode: {e}"


@mcp.tool()
def stop_ptt_mode() -> str:
    """
    Stop Push-to-Talk mode.

    This will also stop any active recording.

    Returns:
        Summary of PTT session
    """
    controller = get_ptt_controller()
    if controller is None or not controller.is_active:
        return "PTT mode not active."

    destroy_ptt_controller()
    destroy_simple_ptt()

    return "PTT mode deactivated."


@mcp.tool()
def get_ptt_status() -> str:
    """
    Get current Push-to-Talk status.

    Returns:
        PTT state and recording status
    """
    controller = get_ptt_controller()

    if controller is None or not controller.is_active:
        return "PTT mode: inactive"

    state = controller.state.value
    is_recording = controller.is_recording

    recorder = get_simple_ptt()
    recording_status = "recording" if recorder.is_recording else "waiting"

    return f"PTT mode: {state}, {recording_status}"


@mcp.tool()
def get_segment_transcription(wait: bool = True, timeout: float = 30.0) -> str:
    """
    Get the latest segment transcription.

    In segmented mode, this returns transcriptions as they become available.
    Use this in a loop to get real-time transcription feedback.

    Args:
        wait: If True, wait for a new segment transcription
        timeout: Maximum time to wait in seconds

    Returns:
        Latest segment transcription or status message
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

    if _last_transcription is None:
        return "[No transcription available yet]"

    result = _last_transcription
    return result


# =============================================================================
# BACKGROUND MODE TOOLS (non-blocking)
# =============================================================================

@mcp.tool()
def start_ptt_background(key: str = "cmd_l+s") -> str:
    """
    Start PTT in background mode (non-blocking).

    This launches a separate process that handles PTT and writes
    transcriptions to a file. Claude can check for new transcriptions
    without blocking using check_transcription().

    Args:
        key: The key combo to use for PTT (default: cmd_l+s)

    Returns:
        Status message with output file path
    """
    global _background_process, _last_read_count

    # Check if already running
    if _background_process is not None and _background_process.poll() is None:
        return "Background PTT already running. Use stop_ptt_background() first."

    # Clear previous state
    _last_read_count = 0
    if _background_output_file.exists():
        _background_output_file.unlink()

    # Launch background process
    script_path = Path(__file__).parent / "background_ptt.py"

    _background_process = subprocess.Popen(
        [
            sys.executable,
            str(script_path),
            "--key", key,
            "--output", str(_background_output_file)
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    return f"Background PTT started (PID: {_background_process.pid}). Output: {_background_output_file}"


@mcp.tool()
def check_transcription() -> str:
    """
    Check for new transcriptions from background PTT (non-blocking).

    Reads the output file and returns any new transcriptions since
    the last check. Returns immediately without waiting.

    Returns:
        Latest transcription or status message
    """
    global _last_read_count

    if _background_process is None:
        return "[Background PTT not started. Use start_ptt_background() first.]"

    if not _background_output_file.exists():
        return "[Waiting for PTT to initialize...]"

    # Read all lines from file
    try:
        with open(_background_output_file, "r") as f:
            lines = f.readlines()
    except Exception as e:
        return f"[Error reading transcriptions: {e}]"

    if len(lines) == 0:
        return "[No activity yet. Press hotkey to record.]"

    # Find new transcriptions since last check
    new_transcriptions = []
    for i, line in enumerate(lines):
        if i < _last_read_count:
            continue
        try:
            data = json.loads(line.strip())
            if data.get("status") == "transcription":
                new_transcriptions.append(data.get("transcription", ""))
        except json.JSONDecodeError:
            continue

    _last_read_count = len(lines)

    if new_transcriptions:
        # Return the latest transcription
        return new_transcriptions[-1]

    # Return current status from last line
    try:
        last_data = json.loads(lines[-1].strip())
        status = last_data.get("status", "unknown")
        if status == "ready":
            return "[Ready. Press hotkey to record.]"
        elif status == "recording_start":
            return "[Recording...]"
        elif status == "recording_stop":
            return "[Transcribing...]"
        else:
            return f"[Status: {status}]"
    except:
        return "[Waiting...]"


@mcp.tool()
def stop_ptt_background() -> str:
    """
    Stop background PTT process.

    Returns:
        Summary of session
    """
    global _background_process, _last_read_count

    if _background_process is None:
        return "Background PTT not running."

    if _background_process.poll() is None:
        _background_process.terminate()
        try:
            _background_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _background_process.kill()

    pid = _background_process.pid
    _background_process = None
    _last_read_count = 0

    return f"Background PTT stopped (PID: {pid})."


if __name__ == "__main__":
    mcp.run()
