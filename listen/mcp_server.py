#!/usr/bin/env python3
"""
Claude-Listen MCP Server
Speech-to-Text server for Claude Code with VAD and Whisper.
"""

import threading
from typing import Optional
import numpy as np
from mcp.server.fastmcp import FastMCP

from .audio import AudioCapture, get_capture
from .vad import SileroVAD, get_vad
from .transcriber import WhisperTranscriber, get_transcriber, TranscriptionResult

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.coordination import signal_stop_speaking, get_coordinator

mcp = FastMCP("claude-listen")

# Global state
_is_listening = False
_audio_buffer: list[np.ndarray] = []
_last_transcription: Optional[TranscriptionResult] = None
_transcription_ready = threading.Event()
_buffer_lock = threading.Lock()

# Components (lazy loaded)
_audio: Optional[AudioCapture] = None
_vad: Optional[SileroVAD] = None
_transcriber: Optional[WhisperTranscriber] = None


def _on_audio_chunk(chunk: np.ndarray) -> None:
    """Called for each audio chunk from microphone."""
    global _audio_buffer, _vad

    if not _is_listening or _vad is None:
        return

    # Add to buffer
    with _buffer_lock:
        _audio_buffer.append(chunk)

    # Process with VAD
    _vad.process_audio(chunk)


def _on_speech_start() -> None:
    """Called when VAD detects speech starting."""
    global _audio_buffer

    # Clear any old buffer
    with _buffer_lock:
        _audio_buffer = []

    # Signal TTS to stop (interrupt)
    signal_stop_speaking()
    get_coordinator().on_speech_detected()


def _on_speech_end() -> None:
    """Called when VAD detects speech ending (after silence timeout)."""
    global _last_transcription, _audio_buffer

    # Get buffered audio
    with _buffer_lock:
        if not _audio_buffer:
            return
        audio = np.concatenate(_audio_buffer)
        _audio_buffer = []

    # Transcribe
    if _transcriber is not None and len(audio) > 0:
        _last_transcription = _transcriber.transcribe(audio)
        _transcription_ready.set()


def _initialize_components() -> None:
    """Initialize audio, VAD, and transcriber components."""
    global _audio, _vad, _transcriber

    if _audio is None:
        _audio = AudioCapture(on_audio=_on_audio_chunk)

    if _vad is None:
        _vad = SileroVAD(
            silence_timeout=2.0,
            on_speech_start=_on_speech_start,
            on_speech_end=_on_speech_end,
        )

    if _transcriber is None:
        _transcriber = WhisperTranscriber()


@mcp.tool()
def start_listening() -> str:
    """
    Start continuous listening mode.

    Activates microphone capture with VAD. When speech is detected,
    it will automatically interrupt any TTS output. After 2 seconds
    of silence, the speech is transcribed.

    Returns:
        Confirmation message
    """
    global _is_listening

    if _is_listening:
        return "Already listening."

    try:
        _initialize_components()

        _is_listening = True
        _transcription_ready.clear()

        if _audio:
            _audio.start()

        get_coordinator().start_listening()

        return "Listening started. Speak now - I'll transcribe after 2s of silence."

    except Exception as e:
        _is_listening = False
        return f"Error starting listening: {e}"


@mcp.tool()
def stop_listening() -> str:
    """
    Stop listening mode.

    Stops microphone capture and VAD processing.

    Returns:
        Confirmation message
    """
    global _is_listening

    if not _is_listening:
        return "Not currently listening."

    _is_listening = False

    if _audio:
        _audio.stop()

    if _vad:
        _vad.reset()

    get_coordinator().stop_listening()

    return "Listening stopped."


@mcp.tool()
def get_transcription(wait: bool = True, timeout: float = 30.0) -> str:
    """
    Get the last transcription result.

    Args:
        wait: If True, wait for a new transcription. If False, return immediately.
        timeout: Maximum time to wait in seconds (default 30s)

    Returns:
        Transcribed text, or status message if no transcription available
    """
    global _last_transcription

    if wait:
        # Wait for new transcription
        _transcription_ready.clear()
        got_result = _transcription_ready.wait(timeout=timeout)

        if not got_result:
            return "[Timeout: No speech detected]"

    if _last_transcription is None:
        return "[No transcription available]"

    result = _last_transcription
    return f"{result.text}"


@mcp.tool()
def listening_status() -> str:
    """
    Get current listening status.

    Returns:
        Status information including listening state and VAD state
    """
    coordinator = get_coordinator()

    status_parts = [
        f"Listening: {'Yes' if _is_listening else 'No'}",
        f"Speaking (TTS): {'Yes' if coordinator.is_speaking else 'No'}",
    ]

    if _vad:
        status_parts.append(f"Speech detected: {'Yes' if _vad.is_speaking else 'No'}")

    if _last_transcription:
        preview = _last_transcription.text[:50]
        if len(_last_transcription.text) > 50:
            preview += "..."
        status_parts.append(f"Last transcription: \"{preview}\"")
        status_parts.append(f"Language: {_last_transcription.language}")

    return "\n".join(status_parts)


@mcp.tool()
def transcribe_now() -> str:
    """
    Immediately transcribe any buffered audio.

    Use this to force transcription without waiting for silence timeout.

    Returns:
        Transcribed text
    """
    global _last_transcription, _audio_buffer

    with _buffer_lock:
        if not _audio_buffer:
            return "[No audio buffered]"
        audio = np.concatenate(_audio_buffer)
        _audio_buffer = []

    if _transcriber is None:
        _initialize_components()

    if _transcriber and len(audio) > 0:
        _last_transcription = _transcriber.transcribe(audio)
        return _last_transcription.text

    return "[Transcription failed]"


if __name__ == "__main__":
    mcp.run()
