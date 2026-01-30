"""
MLX-Audio TTS Backend for claude-say

Provides high-quality neural text-to-speech synthesis using Kokoro-82M model
optimized for Apple Silicon (MLX framework).

Supports 54 voices across 9 languages:
- American English (a): 20 voices
- British English (b): 8 voices
- Spanish (e): 3 voices
- French (f): 1 voice (ff_siwis)
- Hindi (h): 4 voices
- Italian (i): 2 voices
- Portuguese Brazilian (p): 3 voices
- Japanese (j): 5 voices
- Mandarin Chinese (z): 8 voices

Usage:
    from mlx_audio_tts import MLXAudioTTS

    tts = MLXAudioTTS(voice="ff_siwis", speed=1.0)  # French voice
    audio_array, sr = tts.synthesize("Bonjour le monde")
    tts.play(audio_array, sr)
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

try:
    from mlx_audio.tts.generate import generate_audio
    from mlx_audio.tts.utils import load_model
    try:
        from mlx_audio.tts.models.kokoro import KokoroPipeline
    except ImportError:
        # KokoroPipeline might not be available if misaki is missing
        KokoroPipeline = None
    HAS_MLX_AUDIO = True
except ImportError:
    HAS_MLX_AUDIO = False
    KokoroPipeline = None


class MLXAudioTTS:
    """MLX-Audio Text-to-Speech backend with multilingual Kokoro support."""

    # Language codes and their descriptions
    LANGUAGES = {
        "a": "American English",
        "b": "British English",
        "e": "Spanish",
        "f": "French",
        "h": "Hindi",
        "i": "Italian",
        "p": "Portuguese (Brazilian)",
        "j": "Japanese",
        "z": "Mandarin Chinese",
    }

    # All available voices organized by language
    VOICES_BY_LANGUAGE = {
        # American English (20 voices)
        "a": {
            "af_heart": "Heart (Female)",
            "af_alloy": "Alloy (Female)",
            "af_aoede": "Aoede (Female)",
            "af_bella": "Bella (Female)",
            "af_jessica": "Jessica (Female)",
            "af_kore": "Kore (Female)",
            "af_nicole": "Nicole (Female)",
            "af_nova": "Nova (Female)",
            "af_river": "River (Female)",
            "af_sarah": "Sarah (Female)",
            "af_sky": "Sky (Female)",
            "am_adam": "Adam (Male)",
            "am_echo": "Echo (Male)",
            "am_eric": "Eric (Male)",
            "am_fenrir": "Fenrir (Male)",
            "am_liam": "Liam (Male)",
            "am_michael": "Michael (Male)",
            "am_onyx": "Onyx (Male)",
            "am_puck": "Puck (Male)",
            "am_santa": "Santa (Male)",
        },
        # British English (8 voices)
        "b": {
            "bf_alice": "Alice (Female)",
            "bf_emma": "Emma (Female)",
            "bf_isabella": "Isabella (Female)",
            "bf_lily": "Lily (Female)",
            "bm_daniel": "Daniel (Male)",
            "bm_fable": "Fable (Male)",
            "bm_george": "George (Male)",
            "bm_lewis": "Lewis (Male)",
        },
        # Spanish (3 voices)
        "e": {
            "ef_dora": "Dora (Female)",
            "em_alex": "Alex (Male)",
            "em_santa": "Santa (Male)",
        },
        # French (1 voice)
        "f": {
            "ff_siwis": "Siwis (Female)",
        },
        # Hindi (4 voices)
        "h": {
            "hf_alpha": "Alpha (Female)",
            "hf_beta": "Beta (Female)",
            "hm_omega": "Omega (Male)",
            "hm_psi": "Psi (Male)",
        },
        # Italian (2 voices)
        "i": {
            "if_sara": "Sara (Female)",
            "im_nicola": "Nicola (Male)",
        },
        # Portuguese Brazilian (3 voices)
        "p": {
            "pf_dora": "Dora (Female)",
            "pm_alex": "Alex (Male)",
            "pm_santa": "Santa (Male)",
        },
        # Japanese (5 voices)
        "j": {
            "jf_alpha": "Alpha (Female)",
            "jf_gongitsune": "Gongitsune (Female)",
            "jf_nezumi": "Nezumi (Female)",
            "jf_tebukuro": "Tebukuro (Female)",
            "jm_kumo": "Kumo (Male)",
        },
        # Mandarin Chinese (8 voices)
        "z": {
            "zf_xiaobei": "Xiaobei (Female)",
            "zf_xiaoni": "Xiaoni (Female)",
            "zf_xiaoxiao": "Xiaoxiao (Female)",
            "zf_xiaoyi": "Xiaoyi (Female)",
            "zm_yunjian": "Yunjian (Male)",
            "zm_yunxi": "Yunxi (Male)",
            "zm_yunxia": "Yunxia (Male)",
            "zm_yunyang": "Yunyang (Male)",
        },
    }

    # Flat dict of all voices for quick lookup
    VOICES = {}
    for lang_voices in VOICES_BY_LANGUAGE.values():
        VOICES.update(lang_voices)

    # Default voices per language
    DEFAULT_VOICES = {
        "a": "af_heart",
        "b": "bf_emma",
        "e": "ef_dora",
        "f": "ff_siwis",
        "h": "hf_alpha",
        "i": "if_sara",
        "p": "pf_dora",
        "j": "jf_alpha",
        "z": "zf_xiaoxiao",
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
            voice: Voice ID (e.g., "af_heart" for American, "ff_siwis" for French)
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
        self._current_lang = None

    @staticmethod
    def get_language_from_voice(voice_id: str) -> str:
        """Extract language code from voice ID (first character)."""
        if not voice_id:
            return "a"
        return voice_id[0]

    def _load_model(self, lang_code: str = None):
        """Load and cache the model for the specified language."""
        if lang_code is None:
            lang_code = self.get_language_from_voice(self.voice)

        # Reload if language changed
        if self._pipeline is None or self._current_lang != lang_code:
            self._model = load_model(self.model_id)
            self._pipeline = KokoroPipeline(
                lang_code=lang_code,
                model=self._model,
                repo_id=self.model_id,
            )
            self._current_lang = lang_code
        return self._pipeline

    def synthesize(self, text: str, voice: str = None) -> Tuple[np.ndarray, int]:
        """
        Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice: Optional voice override (uses instance voice if not specified)

        Returns:
            Tuple of (audio_array, sample_rate)
            audio_array: numpy array of audio samples
            sample_rate: 24000 Hz for Kokoro-82M
        """
        voice = voice or self.voice
        lang_code = self.get_language_from_voice(voice)
        pipeline = self._load_model(lang_code)

        # Collect all audio chunks
        audio_chunks = []
        for _, _, audio in pipeline(
            text, voice=voice, speed=self.speed, split_pattern=r'\n+'
        ):
            # audio is (1, num_samples) array
            audio_chunks.append(audio[0])

        if not audio_chunks:
            raise RuntimeError(f"Failed to synthesize: {text}")

        # Concatenate all chunks
        audio_array = np.concatenate(audio_chunks)

        return audio_array, 24000

    def synthesize_to_file(
        self, text: str, output_path: Path, format: str = "wav", voice: str = None
    ) -> Path:
        """
        Synthesize text and save to file.

        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            format: Audio format (wav, mp3, etc.)
            voice: Optional voice override

        Returns:
            Path to generated file
        """
        import soundfile as sf

        audio_array, sr = self.synthesize(text, voice)
        sf.write(output_path, audio_array, sr)

        return output_path

    def play(self, audio_array: np.ndarray, sample_rate: int = 24000):
        """
        Play audio using macOS afplay.

        Args:
            audio_array: numpy array of audio samples
            sample_rate: sample rate (default: 24000)
        """
        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio_array, sample_rate)
            subprocess.run(["afplay", f.name], check=True)

    def speak(self, text: str, voice: str = None, blocking: bool = True) -> bool:
        """
        Synthesize and play text.

        Args:
            text: Text to speak
            voice: Optional voice override
            blocking: Wait for playback to complete (default: True)

        Returns:
            True if successful
        """
        import soundfile as sf

        try:
            audio_array, sr = self.synthesize(text, voice)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                sf.write(f.name, audio_array, sr)
                if blocking:
                    subprocess.run(["afplay", f.name], check=True)
                else:
                    subprocess.Popen(
                        ["afplay", f.name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            return True
        except Exception as e:
            print(f"Kokoro TTS error: {e}")
            return False

    def unload_model(self):
        """Unload model from memory to free RAM."""
        self._model = None
        self._pipeline = None
        self._current_lang = None

    @staticmethod
    def get_voice_name(voice_id: str) -> str:
        """Get human-readable voice name."""
        return MLXAudioTTS.VOICES.get(voice_id, voice_id)

    @staticmethod
    def list_voices(language: str = None) -> dict:
        """
        Return available voices, optionally filtered by language.

        Args:
            language: Language code (a, b, e, f, h, i, p, j, z) or None for all

        Returns:
            Dict of voice_id -> voice_name
        """
        if language:
            return MLXAudioTTS.VOICES_BY_LANGUAGE.get(language, {}).copy()
        return MLXAudioTTS.VOICES.copy()

    @staticmethod
    def list_languages() -> dict:
        """Return available languages."""
        return MLXAudioTTS.LANGUAGES.copy()

    @staticmethod
    def get_default_voice(language: str) -> str:
        """Get default voice for a language."""
        return MLXAudioTTS.DEFAULT_VOICES.get(language, "af_heart")


# Quick test
if __name__ == "__main__":
    if not HAS_MLX_AUDIO:
        print("Installing mlx-audio...")
        import subprocess
        subprocess.run(["pip", "install", "mlx-audio"], check=True)

    print("Available languages:")
    for code, name in MLXAudioTTS.list_languages().items():
        voices = MLXAudioTTS.list_voices(code)
        print(f"  {code}: {name} ({len(voices)} voices)")

    # Test French voice
    print("\nTesting French voice (ff_siwis)...")
    tts = MLXAudioTTS(voice="ff_siwis")
    text_fr = "Bonjour, je suis Siwis, une voix de synthèse en français."
    print(f"Synthesizing: {text_fr}")

    audio, sr = tts.synthesize(text_fr)
    print(f"Generated {len(audio) / sr:.2f}s of audio at {sr} Hz")

    # Play if running interactively
    response = input("Play audio? (y/n): ")
    if response.lower() == "y":
        tts.play(audio, sr)

    # Test English voice
    print("\nTesting English voice (af_heart)...")
    text_en = "Hello, I'm Heart, testing MLX Audio text to speech synthesis."
    audio, sr = tts.synthesize(text_en, voice="af_heart")
    print(f"Generated {len(audio) / sr:.2f}s of audio at {sr} Hz")
