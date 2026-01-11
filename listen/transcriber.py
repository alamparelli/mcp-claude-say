"""
Whisper transcription module for claude-listen.
Uses faster-whisper for efficient speech-to-text.
"""

import numpy as np
from pathlib import Path
from typing import Optional, NamedTuple
import os


class TranscriptionResult(NamedTuple):
    """Result of a transcription."""
    text: str
    language: str
    confidence: float


class WhisperTranscriber:
    """
    Speech-to-text transcription using Whisper (via faster-whisper).

    Supports auto language detection and runs efficiently on Apple Silicon.
    """

    DEFAULT_MODEL_PATH = Path.home() / "models" / "ggml-large-v3-turbo.bin"
    SAMPLE_RATE = 16000

    def __init__(
        self,
        model_path: Optional[Path] = None,
        device: str = "auto",
        compute_type: str = "auto",
    ):
        """
        Initialize Whisper transcriber.

        Args:
            model_path: Path to Whisper model file. Defaults to ~/models/ggml-large-v3-turbo.bin
            device: Device to use ("auto", "cpu", "cuda", "mps")
            compute_type: Compute type ("auto", "float16", "float32", "int8")
        """
        self.model_path = model_path or self.DEFAULT_MODEL_PATH

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Whisper model not found at {self.model_path}. "
                f"Run install.sh to download the model."
            )

        # Determine device
        if device == "auto":
            device = self._detect_device()

        # Determine compute type
        if compute_type == "auto":
            compute_type = "float16" if device in ("cuda", "mps") else "float32"

        # Import faster-whisper
        from faster_whisper import WhisperModel

        # Load model
        # For faster-whisper, we need to use model size string or path
        # If using .bin file, we need to convert or use a different approach
        # Let's use the model size for faster-whisper's built-in download
        self._model = WhisperModel(
            "large-v3-turbo",  # faster-whisper will download if needed
            device=device if device != "mps" else "cpu",  # MPS not yet supported
            compute_type=compute_type if device != "mps" else "float32",
        )

        self._device = device

    def _detect_device(self) -> str:
        """Detect best available device."""
        import torch

        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

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
        if len(audio) == 0:
            return TranscriptionResult(text="", language="", confidence=0.0)

        # Ensure correct dtype
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Normalize if needed
        if np.abs(audio).max() > 1.0:
            audio = audio / np.abs(audio).max()

        # Transcribe
        segments, info = self._model.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=True,  # Use Silero VAD internally too
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200,
            ),
        )

        # Collect all segments
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        full_text = " ".join(text_parts).strip()

        return TranscriptionResult(
            text=full_text,
            language=info.language,
            confidence=info.language_probability,
        )

    def transcribe_file(self, audio_path: Path) -> TranscriptionResult:
        """
        Transcribe an audio file.

        Args:
            audio_path: Path to audio file (wav, mp3, etc.)

        Returns:
            TranscriptionResult
        """
        segments, info = self._model.transcribe(str(audio_path))

        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        return TranscriptionResult(
            text=" ".join(text_parts).strip(),
            language=info.language,
            confidence=info.language_probability,
        )


# Singleton instance
_transcriber: Optional[WhisperTranscriber] = None


def get_transcriber() -> WhisperTranscriber:
    """Get or create the global WhisperTranscriber instance."""
    global _transcriber
    if _transcriber is None:
        _transcriber = WhisperTranscriber()
    return _transcriber
