"""
Parakeet MLX transcriber for Apple Silicon.
Fast speech-to-text using NVIDIA's Parakeet models via MLX.
"""

import numpy as np
from typing import Optional
import tempfile
import os

from .transcriber_base import BaseTranscriber, TranscriptionResult


class ParakeetTranscriber(BaseTranscriber):
    """
    Speech-to-text transcription using Parakeet MLX.

    Optimized for Apple Silicon, significantly faster than Whisper.
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
        self._processor = None
        self._load_model()

    def _load_model(self) -> None:
        """Load the Parakeet model."""
        try:
            from parakeet_mlx import load_model, transcribe

            # Store transcribe function for later use
            self._transcribe_fn = transcribe

            # Load model (will download if needed)
            self._model, self._processor = load_model(self.model_name)

        except ImportError:
            raise ImportError(
                "parakeet-mlx not installed. Run: pip install parakeet-mlx"
            )

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

        # Ensure correct dtype
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Normalize if needed
        if np.abs(audio).max() > 1.0:
            audio = audio / np.abs(audio).max()

        # Parakeet expects a file path, so we need to save temporarily
        # or use the direct numpy interface if available
        try:
            # Try direct transcription first (newer versions)
            from parakeet_mlx import transcribe_array
            result = transcribe_array(
                audio,
                sample_rate=self.SAMPLE_RATE,
                model=self._model,
                processor=self._processor,
            )
            text = result.get("text", "") if isinstance(result, dict) else str(result)

        except (ImportError, AttributeError):
            # Fallback: save to temp file
            import soundfile as sf

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name

            try:
                sf.write(temp_path, audio, self.SAMPLE_RATE)
                result = self._transcribe_fn(
                    temp_path,
                    model=self._model,
                    processor=self._processor,
                )
                text = result.get("text", "") if isinstance(result, dict) else str(result)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

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


def get_parakeet_transcriber() -> ParakeetTranscriber:
    """Get or create the global ParakeetTranscriber instance."""
    global _transcriber
    if _transcriber is None:
        _transcriber = ParakeetTranscriber()
    return _transcriber
