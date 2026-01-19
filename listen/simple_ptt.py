"""
Simple Push-to-Talk Recorder - No VAD, just record and transcribe.

Press key to start recording, press again to stop and transcribe.
No automatic segmentation - captures everything between start/stop.

IMPORTANT: This module must properly release the microphone when done
to turn off the macOS orange mic indicator.
"""

import numpy as np
import soundfile as sf
import tempfile
import os
import threading
from typing import Optional, Callable
from pathlib import Path
from datetime import datetime

from .audio import AudioCapture, destroy_capture
from .logger import get_logger

log = get_logger("ptt")


class SimplePTTRecorder:
    """
    Simple PTT recorder without VAD.

    Records continuously while active, transcribes on stop.

    CRITICAL: Call destroy() when done to release the microphone
    and turn off the macOS orange mic indicator.
    """

    def __init__(
        self,
        output_dir: Path = Path("/tmp/claude-ptt"),
        on_transcription_ready: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize simple PTT recorder.

        Args:
            output_dir: Directory to save recordings
            on_transcription_ready: Callback when transcription is done
        """
        log.info("Initializing SimplePTTRecorder...")
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.on_transcription_ready = on_transcription_ready

        self._audio = AudioCapture()
        self._is_recording = False
        self._transcriber = None
        self._last_transcription: Optional[str] = None
        self._last_audio_path: Optional[Path] = None
        self._lock = threading.Lock()
        log.info(f"SimplePTTRecorder initialized, output_dir={output_dir}")

    def _get_transcriber(self):
        """
        Lazy load transcriber.

        Tries to load in order:
        1. Parakeet-MLX (recommended, if installed)
        2. SpeechAnalyzer (if available on macOS 26+)
        3. Raises error if none available
        """
        if self._transcriber is None:
            # Try Parakeet-MLX first (recommended)
            try:
                from .parakeet_transcriber import get_parakeet_transcriber
                self._transcriber = get_parakeet_transcriber()
                log.info("Using Parakeet-MLX transcriber")
                return self._transcriber
            except ImportError:
                log.debug("Parakeet-MLX not available")

            # Try SpeechAnalyzer (experimental, macOS 26+)
            try:
                from .speechanalyzer_transcriber import (
                    is_speechanalyzer_available,
                    get_speechanalyzer_transcriber
                )
                if is_speechanalyzer_available():
                    self._transcriber = get_speechanalyzer_transcriber()
                    log.info("Using SpeechAnalyzer (Apple native)")
                    return self._transcriber
            except ImportError:
                log.debug("SpeechAnalyzer not available")

            # No transcriber available
            raise RuntimeError(
                "No STT transcriber available. Install with:\n"
                "  - Parakeet (recommended): pip install parakeet-mlx\n"
                "  - SpeechAnalyzer: Requires macOS 26+ and CLI build"
            )

        return self._transcriber

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    @property
    def last_transcription(self) -> Optional[str]:
        """Get the last transcription result."""
        return self._last_transcription

    def start(self) -> None:
        """Start recording audio."""
        log.info("start() called")
        with self._lock:
            if self._is_recording:
                log.debug("Already recording, skipping")
                return

            self._audio.clear_buffer()
            self._audio.start()
            self._is_recording = True
            log.info("🎤 Recording started")

    def stop(self) -> Optional[str]:
        """
        Stop recording and transcribe.

        Returns:
            Transcription text or None if no audio
        """
        log.info("stop() called")
        with self._lock:
            if not self._is_recording:
                log.debug("Not recording, skipping stop")
                return None

            self._is_recording = False

            # Get recorded audio BEFORE stopping (to capture buffer)
            audio = self._audio.get_buffer()
            buffer_samples = len(audio)
            log.debug(f"Got {buffer_samples} samples from buffer")

            # CRITICAL: Stop and release the microphone
            self._audio.stop()
            log.info("Audio capture stopped, mic released")

            if buffer_samples == 0:
                log.warning("⚠️ No audio recorded - buffer was empty!")
                return None

            duration = buffer_samples / AudioCapture.SAMPLE_RATE
            max_amplitude = float(np.max(np.abs(audio))) if buffer_samples > 0 else 0
            log.info(f"⏹️ Recording stopped: {duration:.1f}s, {buffer_samples} samples, max_amp={max_amplitude:.3f}")

            # Save audio file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_path = self.output_dir / f"ptt_{timestamp}.flac"
            sf.write(str(audio_path), audio, AudioCapture.SAMPLE_RATE)
            self._last_audio_path = audio_path
            log.info(f"💾 Saved audio to {audio_path}")

            # Transcribe
            log.info("📝 Starting transcription...")
            transcriber = self._get_transcriber()
            result = transcriber.transcribe(audio)

            self._last_transcription = result.text
            log.info(f"✅ Transcription complete: {result.text[:100]}...")

            # Callback
            if self.on_transcription_ready:
                self.on_transcription_ready(result.text)

            return result.text

    def clear(self) -> None:
        """Clear last recording and transcription."""
        self._last_transcription = None
        if self._last_audio_path and self._last_audio_path.exists():
            self._last_audio_path.unlink()
            self._last_audio_path = None


# Global instance
_simple_ptt: Optional[SimplePTTRecorder] = None


def get_simple_ptt(
    on_transcription_ready: Optional[Callable[[str], None]] = None
) -> SimplePTTRecorder:
    """Get or create global SimplePTTRecorder."""
    global _simple_ptt
    if _simple_ptt is None:
        _simple_ptt = SimplePTTRecorder(on_transcription_ready=on_transcription_ready)
    return _simple_ptt


def destroy_simple_ptt() -> None:
    """
    Destroy global SimplePTTRecorder and RELEASE the microphone.

    CRITICAL: This must be called to turn off the macOS orange mic indicator.
    """
    global _simple_ptt
    log.info("destroy_simple_ptt() called")
    if _simple_ptt is not None:
        if _simple_ptt.is_recording:
            log.info("Still recording, stopping first")
            _simple_ptt.stop()

        # CRITICAL: Also destroy the AudioCapture singleton to fully release mic
        destroy_capture()

        _simple_ptt = None
        log.info("Global PTT recorder destroyed, mic released")
    else:
        log.debug("No PTT recorder to destroy")
