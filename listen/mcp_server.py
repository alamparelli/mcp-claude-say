#!/usr/bin/env python3
"""Claude-Listen: STT via PTT hotkey."""

import threading
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

# State
_transcription_ready = threading.Event()
_last_transcription: Optional[str] = None
_current_status: str = "ready"  # ready, recording, transcribing


def _on_transcription_ready(text: str) -> None:
    """Callback when transcription is ready."""
    global _last_transcription, _current_status
    _last_transcription = text
    _current_status = "ready"
    _transcription_ready.set()


def _ptt_start_recording() -> None:
    """Called when PTT key pressed - start recording."""
    global _current_status
    signal_stop_speaking()  # Stop any TTS
    _current_status = "recording"
    recorder = get_simple_ptt(on_transcription_ready=_on_transcription_ready)
    recorder.start()


def _ptt_stop_recording() -> None:
    """Called when PTT key pressed again - stop and transcribe."""
    global _current_status
    _current_status = "transcribing"
    recorder = get_simple_ptt()
    recorder.stop()


@mcp.tool()
def start_ptt_mode(key: str = "cmd_l+s") -> str:
    """Start PTT with hotkey toggle. Keys: cmd/alt/ctrl/shift(_l/_r), f13-f15, space. Combos: mod+key"""
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

        return "PTT mode activated."

    except Exception as e:
        return f"Error starting PTT mode: {e}"


@mcp.tool()
def stop_ptt_mode() -> str:
    """Stop PTT and active recording."""
    controller = get_ptt_controller()
    if controller is None or not controller.is_active:
        return "PTT mode not active."

    destroy_ptt_controller()
    destroy_simple_ptt()

    return "PTT mode deactivated."


@mcp.tool()
def get_ptt_status() -> str:
    """Get PTT status: inactive/ready/recording/transcribing"""
    controller = get_ptt_controller()

    if controller is None or not controller.is_active:
        return "inactive"

    return _current_status


@mcp.tool()
def get_segment_transcription(wait: bool = True, timeout: float = 120.0) -> str:
    """Get transcription. Args: wait, timeout(s). Returns: text or [Ready|Recording...|Transcribing...|Timeout]"""
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
    mcp.run()
