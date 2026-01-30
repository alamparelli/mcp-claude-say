"""
MLX-Audio TTS Backend for claude-say

Provides high-quality neural text-to-speech synthesis using Kokoro-82M model
optimized for Apple Silicon (MLX framework).

Usage:
    from mlx_audio_tts import MLXAudioTTS

    tts = MLXAudioTTS(voice="af_heart", speed=1.0)
    audio_array, sr = tts.synthesize("Hello world")
    tts.play(audio_array, sr)
"""

import tempfile
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

try:
    from mlx_audio.tts.generate import generate_audio
    from mlx_audio.tts.models.kokoro import KokoroPipeline
    from mlx_audio.tts.utils import load_model
    HAS_MLX_AUDIO = True
except ImportError:
    HAS_MLX_AUDIO = False


class MLXAudioTTS:
    """MLX-Audio Text-to-Speech backend."""

    # Available voices for Kokoro-82M (American English)
    VOICES = {
        # Female voices
        "af_heart": "Heart (Female)",
        "af_alloy": "Alloy (Female)",
        "af_bella": "Bella (Female)",
        "af_jessica": "Jessica (Female)",
        "af_nova": "Nova (Female)",
        "af_sarah": "Sarah (Female)",
        "af_sky": "Sky (Female)",
        # Male voices
        "am_adam": "Adam (Male)",
        "am_echo": "Echo (Male)",
        "am_eric": "Eric (Male)",
        "am_liam": "Liam (Male)",
        "am_michael": "Michael (Male)",
        "am_onyx": "Onyx (Male)",
    }

    def __init__(
        self,
        voice: str = "af_heart",
        speed: float = 1.0,
        model_id: str = "prince-canuma/Kokoro-82M",
        cache_model: bool = True,
    ):
        """
        Initialize MLX-Audio TTS backend.

        Args:
            voice: Voice ID from VOICES dict (default: af_heart)
            speed: Speaking speed 0.5-2.0 (default: 1.0)
            model_id: HuggingFace model ID (default: Kokoro-82M)
            cache_model: Keep model in memory for faster synthesis (default: True)
        """
        if not HAS_MLX_AUDIO:
            raise ImportError(
                "mlx-audio is not installed. Install with: pip install mlx-audio"
            )

        if voice not in self.VOICES:
            raise ValueError(
                f"Voice '{voice}' not supported. Available: {list(self.VOICES.keys())}"
            )

        if not (0.5 <= speed <= 2.0):
            raise ValueError(f"Speed must be between 0.5 and 2.0, got {speed}")

        self.voice = voice
        self.speed = speed
        self.model_id = model_id
        self.cache_model = cache_model
        self._model = None
        self._pipeline = None

    def _load_model(self) -> KokoroPipeline:
        """Load and cache the model."""
        if self._pipeline is None:
            self._model = load_model(self.model_id)
            self._pipeline = KokoroPipeline(
                lang_code="a",  # American English
                model=self._model,
                repo_id=self.model_id,
            )
        return self._pipeline

    def synthesize(self, text: str) -> Tuple[np.ndarray, int]:
        """
        Synthesize text to speech.

        Args:
            text: Text to synthesize

        Returns:
            Tuple of (audio_array, sample_rate)
            audio_array: numpy array of audio samples
            sample_rate: 24000 Hz for Kokoro-82M
        """
        pipeline = self._load_model()

        # Collect all audio chunks
        audio_chunks = []
        for _, _, audio in pipeline(
            text, voice=self.voice, speed=self.speed, split_pattern=r'\n+'
        ):
            # audio is (1, num_samples) array
            audio_chunks.append(audio[0])

        if not audio_chunks:
            raise RuntimeError(f"Failed to synthesize: {text}")

        # Concatenate all chunks
        audio_array = np.concatenate(audio_chunks)

        return audio_array, 24000

    def synthesize_to_file(
        self, text: str, output_path: Path, format: str = "wav"
    ) -> Path:
        """
        Synthesize text and save to file.

        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            format: Audio format (wav, mp3, etc.)

        Returns:
            Path to generated file
        """
        import soundfile as sf

        audio_array, sr = self.synthesize(text)
        sf.write(output_path, audio_array, sr)

        return output_path

    def unload_model(self):
        """Unload model from memory to free RAM."""
        self._model = None
        self._pipeline = None

    @staticmethod
    def get_voice_name(voice_id: str) -> str:
        """Get human-readable voice name."""
        return MLXAudioTTS.VOICES.get(voice_id, voice_id)

    @staticmethod
    def list_voices() -> dict:
        """Return available voices."""
        return MLXAudioTTS.VOICES.copy()


# Quick test
if __name__ == "__main__":
    if not HAS_MLX_AUDIO:
        print("Installing mlx-audio...")
        import subprocess
        subprocess.run(["pip", "install", "mlx-audio"], check=True)

    tts = MLXAudioTTS(voice="af_heart")

    # Test synthesis
    text = "Hello, I'm testing MLX Audio text to speech synthesis."
    print(f"Synthesizing: {text}")

    audio, sr = tts.synthesize(text)
    print(f"Generated {len(audio) / sr:.2f}s of audio at {sr} Hz")

    # Test file output
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test.wav"
        tts.synthesize_to_file(text, output_path)
        print(f"Saved to: {output_path}")
        print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")
