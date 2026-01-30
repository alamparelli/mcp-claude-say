"""
Voice Activity Detection (VAD) for claude-listen.

Uses Silero VAD for robust end-of-speech detection.
Silero VAD is a lightweight, accurate model that runs on CPU.

Key features:
- Detects speech vs silence in real-time
- Configurable silence threshold for end-of-utterance detection
- Low latency (~30ms per chunk)
"""

import numpy as np
import threading
import time
from typing import Optional, Callable
from pathlib import Path

from .logger import get_logger

log = get_logger("vad")

# Silero VAD constants
SILERO_SAMPLE_RATE = 16000  # Silero expects 16kHz
SILERO_CHUNK_MS = 32  # Process 32ms chunks (512 samples at 16kHz)
SILERO_CHUNK_SAMPLES = int(SILERO_SAMPLE_RATE * SILERO_CHUNK_MS / 1000)

# Default thresholds
DEFAULT_SPEECH_THRESHOLD = 0.3  # Probability threshold for speech detection (lower = more sensitive)
DEFAULT_SILENCE_DURATION_MS = 1500  # 1.5s silence = end of utterance
MIN_SPEECH_DURATION_MS = 300  # Minimum speech before considering silence


class SileroVAD:
    """
    Silero VAD wrapper for end-of-speech detection.

    Usage:
        vad = SileroVAD(on_speech_end=my_callback)
        vad.start()
        # Feed audio chunks via process_audio()
        vad.stop()
    """

    def __init__(
        self,
        speech_threshold: float = DEFAULT_SPEECH_THRESHOLD,
        silence_duration_ms: int = DEFAULT_SILENCE_DURATION_MS,
        min_speech_duration_ms: int = MIN_SPEECH_DURATION_MS,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize Silero VAD.

        Args:
            speech_threshold: Probability threshold (0-1) for speech detection
            silence_duration_ms: Silence duration to trigger end-of-speech
            min_speech_duration_ms: Minimum speech duration before silence detection
            on_speech_start: Callback when speech starts
            on_speech_end: Callback when speech ends (after silence threshold)
        """
        self.speech_threshold = speech_threshold
        self.silence_duration_ms = silence_duration_ms
        self.min_speech_duration_ms = min_speech_duration_ms
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end

        self._model = None
        self._is_running = False
        self._is_speaking = False
        self._speech_start_time: Optional[float] = None
        self._last_speech_time: Optional[float] = None
        self._lock = threading.Lock()

        # Audio buffer for resampling if needed
        self._audio_buffer = np.array([], dtype=np.float32)

        log.info(f"SileroVAD initialized: threshold={speech_threshold}, "
                 f"silence={silence_duration_ms}ms, min_speech={min_speech_duration_ms}ms")

    def _load_model(self):
        """Lazy-load Silero VAD model."""
        if self._model is not None:
            return

        try:
            import torch
            log.info("Loading Silero VAD model...")

            # Load from torch hub (will cache locally)
            self._model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False,  # Use PyTorch for Apple Silicon optimization
                trust_repo=True
            )

            # Get the VAD iterator function
            (self._get_speech_timestamps,
             self._save_audio,
             self._read_audio,
             self._VADIterator,
             self._collect_chunks) = utils

            log.info("Silero VAD model loaded successfully")

        except ImportError as e:
            log.error(f"Failed to import torch/torchaudio: {e}")
            raise RuntimeError(
                "Silero VAD requires PyTorch + torchaudio. Install with: pip install torch torchaudio"
            ) from e
        except Exception as e:
            log.error(f"Failed to load Silero VAD: {e}")
            raise

    def start(self) -> None:
        """Start VAD processing."""
        with self._lock:
            if self._is_running:
                return

            self._load_model()
            self._is_running = True
            self._is_speaking = False
            self._speech_start_time = None
            self._last_speech_time = None
            self._audio_buffer = np.array([], dtype=np.float32)

            # Reset model state
            if self._model is not None:
                self._model.reset_states()

            log.info("VAD started")

    def stop(self) -> None:
        """Stop VAD processing."""
        with self._lock:
            if not self._is_running:
                return

            self._is_running = False
            self._is_speaking = False
            log.info("VAD stopped")

    def process_audio(self, audio_chunk: np.ndarray) -> bool:
        """
        Process an audio chunk and detect speech.

        Args:
            audio_chunk: Audio samples (float32, 16kHz expected)

        Returns:
            True if speech is detected, False otherwise
        """
        if not self._is_running or self._model is None:
            return False

        import torch

        # Add to buffer
        self._audio_buffer = np.concatenate([self._audio_buffer, audio_chunk])

        # Process in SILERO_CHUNK_SAMPLES chunks
        speech_detected = False

        while len(self._audio_buffer) >= SILERO_CHUNK_SAMPLES:
            chunk = self._audio_buffer[:SILERO_CHUNK_SAMPLES]
            self._audio_buffer = self._audio_buffer[SILERO_CHUNK_SAMPLES:]

            # Convert to torch tensor
            tensor = torch.from_numpy(chunk).float()

            # Get speech probability
            with torch.no_grad():
                speech_prob = self._model(tensor, SILERO_SAMPLE_RATE).item()

            is_speech = speech_prob >= self.speech_threshold
            current_time = time.time()

            if is_speech:
                speech_detected = True
                self._last_speech_time = current_time

                if not self._is_speaking:
                    # Speech just started
                    self._is_speaking = True
                    self._speech_start_time = current_time
                    log.debug(f"Speech started (prob={speech_prob:.2f})")

                    if self.on_speech_start:
                        self.on_speech_start()

            else:
                # Check for end of speech
                if self._is_speaking and self._last_speech_time is not None:
                    silence_duration = (current_time - self._last_speech_time) * 1000
                    speech_duration = (current_time - self._speech_start_time) * 1000 if self._speech_start_time else 0

                    # Only trigger end-of-speech if:
                    # 1. Silence duration exceeds threshold
                    # 2. There was enough speech before the silence
                    if (silence_duration >= self.silence_duration_ms and
                        speech_duration >= self.min_speech_duration_ms):

                        log.info(f"End of speech detected: {speech_duration:.0f}ms speech, "
                                f"{silence_duration:.0f}ms silence")

                        self._is_speaking = False
                        self._speech_start_time = None

                        if self.on_speech_end:
                            self.on_speech_end()

        return speech_detected

    @property
    def is_speaking(self) -> bool:
        """Check if speech is currently detected."""
        return self._is_speaking

    @property
    def is_running(self) -> bool:
        """Check if VAD is active."""
        return self._is_running


# Global instance
_vad: Optional[SileroVAD] = None


def get_vad(
    speech_threshold: float = DEFAULT_SPEECH_THRESHOLD,
    silence_duration_ms: int = DEFAULT_SILENCE_DURATION_MS,
    on_speech_start: Optional[Callable[[], None]] = None,
    on_speech_end: Optional[Callable[[], None]] = None,
) -> SileroVAD:
    """Get or create global VAD instance."""
    global _vad
    if _vad is None:
        _vad = SileroVAD(
            speech_threshold=speech_threshold,
            silence_duration_ms=silence_duration_ms,
            on_speech_start=on_speech_start,
            on_speech_end=on_speech_end,
        )
    return _vad


def destroy_vad() -> None:
    """Destroy global VAD instance."""
    global _vad
    if _vad is not None:
        _vad.stop()
        _vad = None
        log.info("Global VAD destroyed")


def is_silero_available() -> bool:
    """Check if Silero VAD dependencies are available."""
    try:
        import torch
        import torchaudio
        return True
    except ImportError:
        return False
