#!/usr/bin/env python3
"""
Claude-Listen MCP Server - Simple PTT Mode
Speech-to-Text for Claude Code using Push-to-Talk.

Simple operation:
- start_ptt_mode(key): Start listening for hotkey
- Press hotkey to start recording
- Press hotkey again to stop and transcribe
- get_segment_transcription(): Get the transcribed text

Logs go to:
- stderr (visible in Claude Code's MCP console)
- /tmp/claude-listen.log (file for debugging)
"""

import threading
from typing import Optional
from pathlib import Path
import sys

# Import logger first - it initializes logging
from .logger import get_logger, LOG_FILE
log = get_logger("server")

log.info("MCP Server starting...")

from mcp.server.fastmcp import FastMCP
log.debug("FastMCP imported")

from .simple_ptt import SimplePTTRecorder, get_simple_ptt, destroy_simple_ptt
log.debug("simple_ptt imported")

from .ptt_controller import (
    PTTController, PTTConfig, PTTState,
    get_ptt_controller, create_ptt_controller, destroy_ptt_controller
)
log.debug("ptt_controller imported")

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.coordination import signal_stop_speaking
log.debug("shared.coordination imported")

mcp = FastMCP("claude-listen")
log.info(f"FastMCP instance created - logs at {LOG_FILE}")

# State
_transcription_ready = threading.Event()
_last_transcription: Optional[str] = None
_current_status: str = "ready"  # ready, recording, transcribing


def _on_transcription_ready(text: str) -> None:
    """Callback when transcription is ready."""
    global _last_transcription, _current_status
    log.info(f"Transcription ready: {text[:50]}...")
    _last_transcription = text
    _current_status = "ready"
    _transcription_ready.set()


def _ptt_start_recording() -> None:
    """Called when PTT key pressed - start recording."""
    global _current_status
    log.info("_ptt_start_recording callback triggered")
    signal_stop_speaking()  # Stop any TTS
    _current_status = "recording"
    recorder = get_simple_ptt(on_transcription_ready=_on_transcription_ready)
    recorder.start()
    log.info("Recording started via PTT callback")


def _ptt_stop_recording() -> None:
    """Called when PTT key pressed again - stop and transcribe."""
    global _current_status
    log.info("_ptt_stop_recording callback triggered")
    _current_status = "transcribing"
    recorder = get_simple_ptt()
    recorder.stop()
    log.info("Recording stopped, transcription in progress")


@mcp.tool()
def start_ptt_mode(key: str = "cmd_r") -> str:
    """
    Start Push-to-Talk mode with global hotkey detection.

    In PTT mode:
    - Press the hotkey to START recording
    - Press again to STOP recording and transcribe

    Available keys: cmd_r (Right Command - default), cmd_l, alt_r, alt_l, ctrl_r, ctrl_l,
                   shift_r, shift_l, f13, f14, f15, space
    Combos supported: cmd_l+s, cmd_r+m, ctrl_l+r, etc.

    Args:
        key: The key to use for PTT toggle (default: cmd_r = Right Command)

    Returns:
        Confirmation message
    """
    log.info(f"start_ptt_mode called with key={key}")

    try:
        existing = get_ptt_controller()
        if existing is not None and existing.is_active:
            msg = f"PTT mode already active (state: {existing.state.value})"
            log.info(msg)
            return msg

        log.info(f"Creating PTT controller with key={key}")
        config = PTTConfig(
            key=key,
            on_start_recording=_ptt_start_recording,
            on_stop_recording=_ptt_stop_recording,
        )

        controller = create_ptt_controller(config)
        log.info("PTT controller created, starting...")
        controller.start()

        msg = f"PTT mode activated. Press {key.replace('_', ' ').title()} to toggle recording."
        log.info(msg)
        return msg

    except Exception as e:
        log.error(f"ERROR starting PTT mode: {e}", exc_info=True)
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
    log.info("stop_ptt_mode called")

    controller = get_ptt_controller()
    if controller is None or not controller.is_active:
        log.info("PTT mode not active, nothing to stop")
        return "PTT mode not active."

    log.info("Destroying PTT controller...")
    destroy_ptt_controller()

    log.info("Destroying SimplePTT (releases mic)...")
    destroy_simple_ptt()

    log.info("PTT mode fully deactivated, mic released")
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
def interrupt_conversation(reason: str = "typed_input") -> str:
    """
    Interrupt conversation mode cleanly.

    Call this when typed input arrives during voice conversation.
    This will:
    1. Stop any TTS speech immediately
    2. Stop PTT recording if active
    3. Release the microphone
    4. Clear pending transcription states

    After calling this, voice mode is fully stopped.
    User must explicitly restart voice mode if desired.

    This function is idempotent - safe to call multiple times.

    Args:
        reason: Why the interruption occurred (for logging).
                Values: "typed_input", "explicit_stop", "ui_cancel", etc.

    Returns:
        Confirmation message

    Future enhancement (not yet implemented):
        A "soft" interrupt mode could preserve voice session for quick resume.
        See: interrupt_conversation(mode="soft") + resume_voice()
    """
    global _current_status, _last_transcription

    # Idempotency: early-exit if already idle
    controller = get_ptt_controller()
    if _current_status == "ready" and (controller is None or not controller.is_active):
        log.info(f"Interrupt called but system already idle (reason={reason})")
        return "Conversation already idle."

    log.info(f"Conversation interrupted (reason={reason})")

    # 1. Signal TTS to stop (backend-agnostic)
    signal_stop_speaking()

    # 2. Stop PTT and release mic
    if controller is not None and controller.is_active:
        log.info("Stopping PTT controller...")
        destroy_ptt_controller()
        destroy_simple_ptt()

    # 3. Clear pending transcription states
    _current_status = "ready"
    _transcription_ready.set()  # Unblock any waiting calls

    log.info("Conversation interrupted - system idle")
    return "Conversation interrupted. Voice mode stopped."


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
    log.info("Starting MCP server via mcp.run()...")
    log.info("Available tools: start_ptt_mode, stop_ptt_mode, get_ptt_status, get_segment_transcription, interrupt_conversation")
    mcp.run()
