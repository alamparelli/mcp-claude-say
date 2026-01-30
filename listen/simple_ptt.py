"""
Simple Push-to-Talk Recorder with optional VAD auto-stop.

Press key to start recording, press again to stop and transcribe.
With auto_stop=True, recording stops automatically when silence is detected.

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

# VAD configuration defaults
DEFAULT_VAD_SILENCE_MS = 1500  # 1.5s silence = end of utterance
DEFAULT_VAD_THRESHOLD = 0.3  # Speech probability threshold (0.3 is more sensitive than 0.5)


class SimplePTTRecorder:
    """
    Simple PTT recorder with optional VAD auto-stop.

    Records continuously while active, transcribes on stop.
    With auto_stop=True, uses VAD to detect end of speech and stops automatically.

    CRITICAL: Call destroy() when done to release the microphone
    and turn off the macOS orange mic indicator.
    """

    def __init__(
        self,
        output_dir: Path = Path("/tmp/claude-ptt"),
        on_transcription_ready: Optional[Callable[[str], None]] = None,
        auto_stop: bool = False,
        vad_silence_ms: int = DEFAULT_VAD_SILENCE_MS,
        vad_threshold: float = DEFAULT_VAD_THRESHOLD,
    ):
        """
        Initialize simple PTT recorder.

        Args:
            output_dir: Directory to save recordings
            on_transcription_ready: Callback when transcription is done
            auto_stop: If True, use VAD to automatically stop when speech ends
            vad_silence_ms: Silence duration (ms) to trigger auto-stop
            vad_threshold: Speech probability threshold for VAD
        """
        log.info(f"Initializing SimplePTTRecorder (auto_stop={auto_stop})...")
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.on_transcription_ready = on_transcription_ready
        self.auto_stop = auto_stop
        self.vad_silence_ms = vad_silence_ms
        self.vad_threshold = vad_threshold

        self._audio = AudioCapture()
        self._is_recording = False
        self._transcriber = None
        self._vad = None
        self._last_transcription: Optional[str] = None
        self._last_audio_path: Optional[Path] = None
        self._lock = threading.Lock()
        self._auto_stop_triggered = threading.Event()
        log.info(f"SimplePTTRecorder initialized, output_dir={output_dir}, auto_stop={auto_stop}")

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

    def _get_vad(self):
        """Lazy load VAD if auto_stop is enabled."""
        if not self.auto_stop:
            return None

        if self._vad is None:
            try:
                from .vad import SileroVAD, is_silero_available

                if not is_silero_available():
                    log.warning("Silero VAD not available, auto_stop disabled")
                    self.auto_stop = False
                    return None

                self._vad = SileroVAD(
                    speech_threshold=self.vad_threshold,
                    silence_duration_ms=self.vad_silence_ms,
                    on_speech_end=self._on_vad_speech_end,
                )
                log.info(f"VAD initialized: silence={self.vad_silence_ms}ms, threshold={self.vad_threshold}")
            except Exception as e:
                log.error(f"Failed to initialize VAD: {e}")
                self.auto_stop = False
                return None

        return self._vad

    def _on_vad_speech_end(self):
        """Callback when VAD detects end of speech."""
        log.info("VAD detected end of speech - triggering auto-stop")
        self._auto_stop_triggered.set()

    def _audio_callback(self, audio_chunk: np.ndarray):
        """Process audio chunk through VAD if enabled."""
        if self._vad is not None and self._vad.is_running:
            result = self._vad.process_audio(audio_chunk)
            # Debug: log every 2 seconds approximately (16000 samples / 512 = ~31 chunks per second)
            if hasattr(self, '_vad_chunk_count'):
                self._vad_chunk_count += 1
            else:
                self._vad_chunk_count = 1

            if self._vad_chunk_count % 62 == 0:  # Every ~2 seconds
                log.debug(f"VAD status: is_speaking={self._vad.is_speaking}, chunks={self._vad_chunk_count}")

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

            # Reset auto-stop event
            self._auto_stop_triggered.clear()

            # Initialize VAD if auto_stop enabled
            vad = self._get_vad()
            if vad:
                vad.start()
                # Set audio callback for VAD processing
                self._audio.on_audio = self._audio_callback
                log.info("VAD started for auto-stop detection")

            self._audio.clear_buffer()
            self._audio.start()
            self._is_recording = True
            log.info(f"🎤 Recording started (auto_stop={self.auto_stop})")

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

            # Stop VAD if running
            if self._vad is not None:
                self._vad.stop()
                log.debug("VAD stopped")

            # Clear audio callback
            self._audio.on_audio = None

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

    def wait_for_auto_stop(self, timeout: float = 120.0) -> bool:
        """
        Wait for VAD to detect end of speech (auto_stop mode only).

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if auto-stop was triggered, False on timeout
        """
        if not self.auto_stop:
            log.warning("wait_for_auto_stop called but auto_stop is disabled")
            return False

        log.info(f"Waiting for VAD auto-stop (timeout={timeout}s)...")
        triggered = self._auto_stop_triggered.wait(timeout=timeout)

        if triggered:
            log.info("Auto-stop triggered, stopping recording")
            self.stop()
        else:
            log.warning("Auto-stop timeout, stopping recording anyway")
            self.stop()

        return triggered

    def clear(self) -> None:
        """Clear last recording and transcription."""
        self._last_transcription = None
        if self._last_audio_path and self._last_audio_path.exists():
            self._last_audio_path.unlink()
            self._last_audio_path = None


# Global instance
_simple_ptt: Optional[SimplePTTRecorder] = None


def get_simple_ptt(
    on_transcription_ready: Optional[Callable[[str], None]] = None,
    auto_stop: bool = False,
    vad_silence_ms: int = DEFAULT_VAD_SILENCE_MS,
    vad_threshold: float = DEFAULT_VAD_THRESHOLD,
) -> SimplePTTRecorder:
    """
    Get or create global SimplePTTRecorder.

    Args:
        on_transcription_ready: Callback when transcription is done
        auto_stop: If True, use VAD to automatically stop when speech ends
        vad_silence_ms: Silence duration (ms) to trigger auto-stop
        vad_threshold: Speech probability threshold for VAD
    """
    global _simple_ptt
    if _simple_ptt is None:
        _simple_ptt = SimplePTTRecorder(
            on_transcription_ready=on_transcription_ready,
            auto_stop=auto_stop,
            vad_silence_ms=vad_silence_ms,
            vad_threshold=vad_threshold,
        )
    elif auto_stop != _simple_ptt.auto_stop:
        # If auto_stop setting changed, recreate the recorder
        log.info(f"auto_stop changed from {_simple_ptt.auto_stop} to {auto_stop}, recreating recorder")
        destroy_simple_ptt()
        _simple_ptt = SimplePTTRecorder(
            on_transcription_ready=on_transcription_ready,
            auto_stop=auto_stop,
            vad_silence_ms=vad_silence_ms,
            vad_threshold=vad_threshold,
        )

    # Always update callback (important for auto-start to work correctly)
    if on_transcription_ready is not None:
        _simple_ptt.on_transcription_ready = on_transcription_ready

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

        # Destroy VAD if present
        if _simple_ptt._vad is not None:
            from .vad import destroy_vad
            destroy_vad()

        # CRITICAL: Also destroy the AudioCapture singleton to fully release mic
        destroy_capture()

        _simple_ptt = None
        log.info("Global PTT recorder destroyed, mic released")
    else:
        log.debug("No PTT recorder to destroy")
