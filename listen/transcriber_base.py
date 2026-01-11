"""
Base transcriber interface for speech-to-text engines.
Allows switching between Whisper, Parakeet MLX, etc.
"""

from abc import ABC, abstractmethod
from typing import Optional, NamedTuple
import numpy as np


class TranscriptionResult(NamedTuple):
    """Result of a transcription."""
    text: str
    language: str
    confidence: float


class BaseTranscriber(ABC):
    """Abstract base class for speech-to-text transcribers."""

    SAMPLE_RATE = 16000

    @abstractmethod
    def transcribe(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio to text.

        Args:
            audio: Audio data (float32, 16kHz, mono)
            language: Language code (e.g., "fr", "en") or None for auto-detect

        Returns:
            TranscriptionResult with text, detected language, and confidence
        """
        pass

    @abstractmethod
    def transcribe_streaming(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Fast streaming transcription for keyword detection.
        May be less accurate but faster.

        Args:
            audio: Audio data (float32, 16kHz, mono)
            language: Language code or None for auto-detect

        Returns:
            TranscriptionResult (may be partial)
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the transcriber name."""
        pass

    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether this transcriber supports streaming mode."""
        pass
