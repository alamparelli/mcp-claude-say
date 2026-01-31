#!/usr/bin/env python3
"""Claude-Listen: STT via PTT hotkey. Logs: stderr + /tmp/claude-listen.log"""

import threading
import gc
from typing import Optional
from pathlib import Path
import sys

# Import logger first - it initializes logging
from .logger import get_logger, LOG_FILE
log = get_logger("server")

log.info("MCP Server starting...")

from mcp.server.fastmcp import FastMCP
log.debug("FastMCP imported")

from .simple_ptt import (
    SimplePTTRecorder, get_simple_ptt, destroy_simple_ptt,
    DEFAULT_VAD_SILENCE_MS, DEFAULT_VAD_THRESHOLD
)
log.debug("simple_ptt imported")

from .ptt_controller import (
    PTTController, PTTConfig, PTTState,
    get_ptt_controller, create_ptt_controller, destroy_ptt_controller
)
log.debug("ptt_controller imported")

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.coordination import (
    signal_stop_speaking, is_speaking, force_stop_tts,
    wait_for_tts_complete, clear_tts_complete_signal, clear_barge_in_signal
)
log.debug("shared.coordination imported")


mcp = FastMCP("claude-listen")
log.info(f"FastMCP instance created - logs at {LOG_FILE}")

# Phase 2 defaults
DEFAULT_ECHO_DELAY_MS = 400  # Delay after TTS before starting recording (echo prevention)

# State
_transcription_ready = threading.Event()
_last_transcription: Optional[str] = None
_current_status: str = "ready"  # ready, recording, transcribing
_auto_stop_enabled: bool = False  # Track if auto_stop mode is active
_auto_start_enabled: bool = False  # Track if auto_start mode is active (Phase 2)
_auto_start_thread: Optional[threading.Thread] = None  # Thread waiting for TTS completion
_echo_delay_ms: int = DEFAULT_ECHO_DELAY_MS


def _on_transcription_ready(text: str) -> None:
    """Callback when transcription is ready."""
    global _last_transcription, _current_status
    log.info(f"Transcription ready: {text[:50]}...")
    _last_transcription = text
    _current_status = "ready"

    # Clear barge-in signal to allow speak_and_wait to work again
    # This marks the end of the interruption - Claude can speak again
    clear_barge_in_signal()

    _transcription_ready.set()


def _ptt_start_recording() -> None:
    """Called when PTT key pressed - start recording (barge-in if TTS playing)."""
    global _current_status, _auto_stop_enabled
    log.info(f"_ptt_start_recording callback triggered (auto_stop={_auto_stop_enabled})")

    # BARGE-IN: Force stop TTS immediately + clear queue
    # Always call force_stop_tts() to ensure queue is cleared even if not currently speaking
    if is_speaking():
        log.info("🔇 BARGE-IN: TTS is speaking, force stopping + clearing queue")
        force_stop_tts()
    else:
        log.debug("TTS not speaking, no barge-in needed")

    _current_status = "recording"
    recorder = get_simple_ptt(
        on_transcription_ready=_on_transcription_ready,
        auto_stop=_auto_stop_enabled,
    )
    recorder.start()
    log.info(f"Recording started via PTT callback (auto_stop={_auto_stop_enabled})")

    # If auto_stop is enabled, start a background thread to wait for VAD
    if _auto_stop_enabled:
        def auto_stop_waiter():
            log.info("Auto-stop waiter thread started")
            # The recorder will call stop() internally when VAD triggers
            # This also triggers transcription and callback which sets _current_status
            triggered = recorder.wait_for_auto_stop(timeout=120.0)
            if triggered:
                log.info("Auto-stop completed successfully (transcription done via callback)")
            else:
                log.warning("Auto-stop timed out")
            # NOTE: Don't set _current_status here - callback already handles it

        waiter_thread = threading.Thread(target=auto_stop_waiter, daemon=True)
        waiter_thread.start()


def _ptt_stop_recording() -> None:
    """Called when PTT key pressed again - stop and transcribe."""
    global _current_status, _auto_stop_enabled
    log.info(f"_ptt_stop_recording callback triggered (auto_stop={_auto_stop_enabled})")

    # In auto_stop mode, the VAD waiter thread handles stopping
    # But if user presses key again manually, we should still stop
    recorder = get_simple_ptt()

    if recorder.is_recording:
        _current_status = "transcribing"
        recorder.stop()
        log.info("Recording stopped manually, transcription in progress")
    else:
        log.info("Recording already stopped (likely by VAD auto-stop)")


def _auto_start_waiter():
    """
    Background thread that waits for TTS completion signal and auto-starts recording.

    This implements Phase 2: Auto-start listening after TTS completes.
    """
    import time
    global _current_status, _auto_start_enabled

    log.info("Auto-start waiter thread started")

    while _auto_start_enabled:
        # Wait for TTS completion signal
        if wait_for_tts_complete(timeout=5.0):
            log.info(f"TTS complete! Waiting {_echo_delay_ms}ms for echo prevention...")

            # Echo prevention delay
            time.sleep(_echo_delay_ms / 1000.0)

            # Check if still in auto-start mode (user might have stopped PTT)
            if not _auto_start_enabled:
                log.info("Auto-start disabled during echo delay, skipping")
                continue

            # Check if already recording (user might have manually started)
            recorder = get_simple_ptt(auto_stop=_auto_stop_enabled)
            if recorder.is_recording:
                log.info("Already recording, skipping auto-start")
                continue

            # Auto-start recording
            log.info("Auto-starting recording after TTS completion")
            _ptt_start_recording()

    log.info("Auto-start waiter thread exiting")


@mcp.tool()
def start_ptt_mode(
    key: str = "cmd_r",
    auto_stop: bool = False,
    vad_silence_ms: int = DEFAULT_VAD_SILENCE_MS,
    auto_start: bool = False,
    echo_delay_ms: int = DEFAULT_ECHO_DELAY_MS,
) -> str:
    """Start PTT with hotkey toggle. Set auto_stop=True for VAD-based automatic stop when speech ends.

    Args:
        key: Hotkey to toggle recording. Keys: cmd/alt/ctrl/shift(_l/_r), f13-f15, space. Combos: mod+key
        auto_stop: If True, recording stops automatically when silence is detected (VAD)
        vad_silence_ms: Silence duration in ms to trigger auto-stop (default: 1500ms)
        auto_start: If True, recording starts automatically after TTS completion (Phase 2)
        echo_delay_ms: Delay in ms after TTS before starting recording (echo prevention, default: 400ms)
    """
    global _auto_stop_enabled, _auto_start_enabled, _auto_start_thread, _echo_delay_ms
    log.info(f"start_ptt_mode called with key={key}, auto_stop={auto_stop}, vad_silence_ms={vad_silence_ms}, auto_start={auto_start}, echo_delay_ms={echo_delay_ms}")

    try:
        existing = get_ptt_controller()
        if existing is not None and existing.is_active:
            msg = f"PTT mode already active (state: {existing.state.value})"
            log.info(msg)
            return msg

        # Store settings for use in callbacks
        _auto_stop_enabled = auto_stop
        _auto_start_enabled = auto_start
        _echo_delay_ms = echo_delay_ms

        # Clear any stale TTS complete signal
        clear_tts_complete_signal()

        log.info(f"Creating PTT controller with key={key}")
        config = PTTConfig(
            key=key,
            on_start_recording=_ptt_start_recording,
            on_stop_recording=_ptt_stop_recording,
        )

        controller = create_ptt_controller(config)
        log.info("PTT controller created, starting...")
        controller.start()

        # Phase 2: Start auto-start waiter thread if enabled
        if auto_start:
            _auto_start_thread = threading.Thread(target=_auto_start_waiter, daemon=True)
            _auto_start_thread.start()
            log.info("Auto-start waiter thread launched")

        key_display = key.replace('_', ' ').title()

        # Build mode description
        mode_parts = []
        if auto_stop:
            mode_parts.append(f"auto-stop (VAD: {vad_silence_ms}ms)")
        if auto_start:
            mode_parts.append(f"auto-start (delay: {echo_delay_ms}ms)")
        mode_desc = ", ".join(mode_parts) if mode_parts else "manual mode"

        if auto_start and auto_stop:
            instruction = f"Press {key_display} to START first recording. After that, conversation flows automatically!"
        elif auto_stop:
            instruction = f"Press {key_display} to START recording. Recording will STOP AUTOMATICALLY when you stop speaking."
        else:
            instruction = f"Press {key_display} to toggle recording on/off."

        msg = f"""PTT mode activated ({mode_desc}).
{instruction}

⚠️ Keys not working? Grant Accessibility permission:
   System Settings → Privacy & Security → Accessibility → Enable your terminal app (VSCode, Terminal, Cursor, etc.)
   Then restart the app."""

        log.info(f"PTT mode activated: key={key}, auto_stop={auto_stop}, auto_start={auto_start}")
        return msg

    except Exception as e:
        log.error(f"ERROR starting PTT mode: {e}", exc_info=True)
        return f"Error starting PTT mode: {e}"


@mcp.tool()
def stop_ptt_mode() -> str:
    """Stop PTT and active recording."""
    global _auto_stop_enabled, _auto_start_enabled, _auto_start_thread
    log.info("stop_ptt_mode called")

    controller = get_ptt_controller()
    if controller is None or not controller.is_active:
        log.info("PTT mode not active, nothing to stop")
        return "PTT mode not active."

    log.info("Destroying PTT controller...")
    destroy_ptt_controller()

    log.info("Destroying SimplePTT (releases mic)...")
    destroy_simple_ptt()

    # Reset auto_stop and auto_start state
    _auto_stop_enabled = False
    _auto_start_enabled = False  # This will cause the waiter thread to exit
    _auto_start_thread = None

    # Clear any pending TTS complete signal
    clear_tts_complete_signal()

    # Memory optimization: force garbage collection to free buffers
    gc.collect()

    log.info("PTT mode fully deactivated, mic released")
    return "PTT mode deactivated. Microphone released."


@mcp.tool()
def get_ptt_status() -> str:
    """Get PTT status: inactive/ready/recording/transcribing. Includes auto_stop/auto_start indicators if enabled."""
    global _auto_stop_enabled, _auto_start_enabled
    controller = get_ptt_controller()

    if controller is None or not controller.is_active:
        return "inactive"

    status = _current_status
    modes = []
    if _auto_stop_enabled:
        modes.append("auto_stop")
    if _auto_start_enabled:
        modes.append("auto_start")

    if modes:
        status = f"{status} ({', '.join(modes)})"

    return status


@mcp.tool()
def interrupt_conversation(reason: str = "typed_input") -> str:
    """Stop TTS + PTT cleanly (idempotent). Call on typed input during voice conversation."""
    global _current_status, _last_transcription, _auto_stop_enabled, _auto_start_enabled, _auto_start_thread

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
    _auto_stop_enabled = False
    _auto_start_enabled = False  # Stop auto-start waiter thread
    _auto_start_thread = None
    _transcription_ready.set()  # Unblock any waiting calls

    # 4. Clear any pending TTS complete signal
    clear_tts_complete_signal()

    log.info("Conversation interrupted - system idle")
    return "Conversation interrupted. Voice mode stopped."


@mcp.tool()
def get_segment_transcription(wait: bool = True, timeout: float = 120.0) -> str:
    """Get transcription. Args: wait, timeout(s). Returns: text or [Ready|Recording...|Transcribing...|Timeout]"""
    global _last_transcription

    controller = get_ptt_controller()
    if controller is None or not controller.is_active:
        return "[PTT mode not active. Use start_ptt_mode() first.]"

    # Auto-restart recording if not active and auto_start is enabled
    # This handles the case where get_segment_transcription is called twice
    # and the auto-start signal was missed
    if _auto_start_enabled and _current_status == "ready":
        recorder = get_simple_ptt(auto_stop=_auto_stop_enabled)
        if not recorder.is_recording:
            log.info("get_segment_transcription: auto-restarting recording (fallback)")
            _ptt_start_recording()

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
    log.info("Available tools: start_ptt_mode (with auto_stop/auto_start), stop_ptt_mode, get_ptt_status, get_segment_transcription, interrupt_conversation")
    log.info("Phase 1 - VAD auto-stop: Use start_ptt_mode(auto_stop=True) to enable automatic end-of-speech detection")
    log.info("Phase 2 - Auto-start: Use start_ptt_mode(auto_start=True) to auto-start recording after TTS completes")
    mcp.run()
