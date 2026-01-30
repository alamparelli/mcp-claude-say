"""
Parakeet MLX transcriber for Apple Silicon.
Fast speech-to-text using NVIDIA's Parakeet models via MLX.

Memory optimization: Model auto-unloads after IDLE_TIMEOUT_SECONDS of inactivity.
"""

import numpy as np
from typing import Optional
import tempfile
import os
import gc
import time
import threading

from .transcriber_base import BaseTranscriber, TranscriptionResult
from .logger import get_logger

log = get_logger("parakeet")

# Memory optimization: unload model after this many seconds of inactivity
IDLE_TIMEOUT_SECONDS = 1800  # 30 minutes


class ParakeetTranscriber(BaseTranscriber):
    """
    Speech-to-text transcription using Parakeet MLX.

    Optimized for Apple Silicon, significantly faster than Whisper.

    Memory optimization: Model is lazily loaded on first use and auto-unloads
    after IDLE_TIMEOUT_SECONDS of inactivity to free ~2GB of RAM.
    """

    DEFAULT_MODEL = "mlx-community/parakeet-tdt-0.6b-v3"

    def __init__(
        self,
        model_name: Optional[str] = None,
    ):
        """
        Initialize Parakeet transcriber.

        Args:
            model_name: HuggingFace model name. Defaults to parakeet-tdt-0.6b-v3
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self._model = None
        self._last_use_time: float = 0
        self._lock = threading.Lock()
        # Lazy loading: don't load model in __init__, wait for first transcribe()

    def _load_model(self) -> None:
        """Load the Parakeet model (~2GB RAM)."""
        with self._lock:
            if self._model is not None:
                return  # Already loaded

            try:
                from parakeet_mlx import from_pretrained

                log.info(f"Loading Parakeet model: {self.model_name} (~2GB RAM)")
                self._model = from_pretrained(self.model_name)
                self._last_use_time = time.time()
                log.info("Parakeet model loaded successfully")

            except ImportError:
                raise ImportError(
                    "parakeet-mlx not installed. Run: pip install parakeet-mlx"
                )

    def _unload_model(self) -> None:
        """Unload the model to free ~2GB RAM."""
        with self._lock:
            if self._model is None:
                return

            log.info("Unloading Parakeet model to free memory...")
            self._model = None
            gc.collect()
            log.info("Parakeet model unloaded, memory freed")

    def _ensure_model_loaded(self) -> None:
        """Ensure model is loaded, loading it if necessary."""
        if self._model is None:
            self._load_model()
        self._last_use_time = time.time()

    def transcribe(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio to text using Parakeet.

        Args:
            audio: Audio data (float32, 16kHz, mono)
            language: Not used by Parakeet (auto-detects)

        Returns:
            TranscriptionResult with text, detected language, and confidence
        """
        if len(audio) == 0:
            return TranscriptionResult(text="", language="", confidence=0.0)

        # Ensure model is loaded (lazy loading)
        self._ensure_model_loaded()

        # Ensure correct dtype
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Normalize if needed
        if np.abs(audio).max() > 1.0:
            audio = audio / np.abs(audio).max()

        # Parakeet requires a file path - save to temp file
        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            sf.write(temp_path, audio, self.SAMPLE_RATE)
            result = self._model.transcribe(temp_path)
            # Extract text from AlignedResult
            text = result.text if hasattr(result, 'text') else str(result)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            # Memory optimization: trigger garbage collection after transcription
            # to free intermediate buffers created by MLX/NumPy
            gc.collect()

        return TranscriptionResult(
            text=text.strip(),
            language="auto",  # Parakeet auto-detects
            confidence=0.95,  # Parakeet doesn't provide confidence scores
        )

    def transcribe_streaming(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Fast streaming transcription.

        Parakeet is fast enough that we can use full transcription.
        """
        return self.transcribe(audio, language)

    @property
    def name(self) -> str:
        return "parakeet-mlx"

    @property
    def supports_streaming(self) -> bool:
        return True


# Singleton instance
_transcriber: Optional[ParakeetTranscriber] = None
_idle_checker_started: bool = False


def _start_idle_checker() -> None:
    """Start background thread that unloads model after idle timeout."""
    global _idle_checker_started
    if _idle_checker_started:
        return
    _idle_checker_started = True

    def idle_checker():
        while True:
            time.sleep(60)  # Check every minute
            if _transcriber is not None and _transcriber._model is not None:
                idle_time = time.time() - _transcriber._last_use_time
                if idle_time > IDLE_TIMEOUT_SECONDS:
                    log.info(f"Model idle for {idle_time:.0f}s, unloading to free memory")
                    _transcriber._unload_model()

    thread = threading.Thread(target=idle_checker, daemon=True, name="parakeet-idle-checker")
    thread.start()
    log.info(f"Idle checker started (timeout: {IDLE_TIMEOUT_SECONDS}s)")


def get_parakeet_transcriber() -> ParakeetTranscriber:
    """Get or create the global ParakeetTranscriber instance."""
    global _transcriber
    if _transcriber is None:
        _transcriber = ParakeetTranscriber()
        _start_idle_checker()
    return _transcriber


def unload_parakeet_model() -> None:
    """Manually unload the Parakeet model to free ~2GB RAM."""
    if _transcriber is not None:
        _transcriber._unload_model()
