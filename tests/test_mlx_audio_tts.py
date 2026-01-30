"""
Tests for MLX-Audio TTS Backend

Requirements:
- pytest
- mlx-audio

Run: pytest tests/test_mlx_audio_tts.py -v
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

# Skip tests if mlx-audio not installed
pytest.importorskip("mlx_audio")

from say.mlx_audio_tts import MLXAudioTTS, HAS_MLX_AUDIO


class TestMLXAudioTTSInit:
    """Test MLXAudioTTS initialization."""

    def test_init_default_voice(self):
        """Test initialization with default voice."""
        tts = MLXAudioTTS()
        assert tts.voice == "af_heart"
        assert tts.speed == 1.0

    def test_init_custom_voice(self):
        """Test initialization with custom voice."""
        tts = MLXAudioTTS(voice="am_adam", speed=1.5)
        assert tts.voice == "am_adam"
        assert tts.speed == 1.5

    def test_init_invalid_voice(self):
        """Test that invalid voice raises ValueError."""
        with pytest.raises(ValueError, match="Voice.*not supported"):
            MLXAudioTTS(voice="invalid_voice")

    def test_init_invalid_speed_too_low(self):
        """Test that speed < 0.5 raises ValueError."""
        with pytest.raises(ValueError, match="Speed must be between"):
            MLXAudioTTS(speed=0.3)

    def test_init_invalid_speed_too_high(self):
        """Test that speed > 2.0 raises ValueError."""
        with pytest.raises(ValueError, match="Speed must be between"):
            MLXAudioTTS(speed=2.5)

    def test_init_valid_speeds(self):
        """Test valid speed range."""
        for speed in [0.5, 1.0, 1.5, 2.0]:
            tts = MLXAudioTTS(speed=speed)
            assert tts.speed == speed


class TestMLXAudioTTSVoices:
    """Test voice management."""

    def test_list_voices(self):
        """Test listing available voices."""
        voices = MLXAudioTTS.list_voices()
        assert isinstance(voices, dict)
        assert len(voices) > 0
        assert "af_heart" in voices
        assert "am_adam" in voices

    def test_get_voice_name(self):
        """Test getting voice display name."""
        name = MLXAudioTTS.get_voice_name("af_heart")
        assert isinstance(name, str)
        assert len(name) > 0

    def test_get_voice_name_invalid(self):
        """Test getting name for invalid voice."""
        name = MLXAudioTTS.get_voice_name("invalid")
        assert name == "invalid"  # Returns input if not found


class TestMLXAudioTTSSynthesis:
    """Test text synthesis functionality."""

    def test_synthesize_short_text(self):
        """Test synthesizing short text."""
        tts = MLXAudioTTS()
        text = "Hello world"

        audio, sr = tts.synthesize(text)

        assert isinstance(audio, np.ndarray)
        assert audio.ndim == 1  # 1D array
        assert len(audio) > 0
        assert sr == 24000  # Kokoro-82M uses 24kHz

    def test_synthesize_medium_text(self):
        """Test synthesizing medium-length text."""
        tts = MLXAudioTTS()
        text = "The quick brown fox jumps over the lazy dog. This is a longer sentence."

        audio, sr = tts.synthesize(text)

        assert len(audio) > 0
        assert sr == 24000

    def test_synthesize_with_newlines(self):
        """Test that newlines are handled correctly."""
        tts = MLXAudioTTS()
        text = "First sentence.\nSecond sentence."

        audio, sr = tts.synthesize(text)

        assert len(audio) > 0

    def test_synthesize_empty_text_fails(self):
        """Test that empty text raises error."""
        tts = MLXAudioTTS()

        with pytest.raises(RuntimeError):
            tts.synthesize("")

    def test_synthesize_different_speeds(self):
        """Test synthesis with different speeds."""
        text = "Hello world"

        # Slower speech should produce longer audio
        tts_slow = MLXAudioTTS(speed=0.5)
        audio_slow, _ = tts_slow.synthesize(text)

        # Normal speed
        tts_normal = MLXAudioTTS(speed=1.0)
        audio_normal, _ = tts_normal.synthesize(text)

        # Faster speech should produce shorter audio
        tts_fast = MLXAudioTTS(speed=2.0)
        audio_fast, _ = tts_fast.synthesize(text)

        # Check approximate relationship (with tolerance for model variation)
        assert len(audio_slow) > len(audio_normal) * 0.8
        assert len(audio_fast) < len(audio_normal) * 1.2

    def test_synthesize_different_voices(self):
        """Test synthesis with different voices."""
        text = "Hello world"

        tts_f = MLXAudioTTS(voice="af_heart")
        audio_f, _ = tts_f.synthesize(text)

        tts_m = MLXAudioTTS(voice="am_adam")
        audio_m, _ = tts_m.synthesize(text)

        # Both should produce valid audio
        assert len(audio_f) > 0
        assert len(audio_m) > 0

        # Audio characteristics will differ
        assert not np.allclose(audio_f, audio_m)


class TestMLXAudioTTSFileOutput:
    """Test file output functionality."""

    def test_synthesize_to_file_wav(self):
        """Test saving synthesis to WAV file."""
        tts = MLXAudioTTS()
        text = "Hello world"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.wav"

            result_path = tts.synthesize_to_file(text, output_path, format="wav")

            assert result_path == output_path
            assert output_path.exists()
            assert output_path.stat().st_size > 0

    def test_synthesize_to_file_creates_parent_dirs(self):
        """Test that parent directories are created if needed."""
        tts = MLXAudioTTS()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir1" / "subdir2" / "audio.wav"

            # Parent directories should be created by soundfile
            result_path = tts.synthesize_to_file("Hello", output_path)

            assert result_path.parent.exists()


class TestMLXAudioTTSModelManagement:
    """Test model loading and caching."""

    def test_model_lazy_loading(self):
        """Test that model is only loaded when needed."""
        tts = MLXAudioTTS(cache_model=True)

        # Model should be None initially
        assert tts._model is None
        assert tts._pipeline is None

        # Model should be loaded after first synthesis
        tts.synthesize("Hello")
        assert tts._model is not None
        assert tts._pipeline is not None

    def test_unload_model(self):
        """Test unloading model to free memory."""
        tts = MLXAudioTTS(cache_model=True)

        # Load model
        tts.synthesize("Hello")
        assert tts._model is not None

        # Unload
        tts.unload_model()
        assert tts._model is None
        assert tts._pipeline is None

    def test_model_reuse_for_multiple_syntheses(self):
        """Test that model is reused for multiple syntheses."""
        tts = MLXAudioTTS(cache_model=True)

        # First synthesis
        audio1, _ = tts.synthesize("Hello")
        model1 = tts._model

        # Second synthesis
        audio2, _ = tts.synthesize("World")
        model2 = tts._model

        # Same model should be used
        assert model1 is model2
        assert len(audio1) > 0
        assert len(audio2) > 0


class TestMLXAudioTTSIntegration:
    """Integration tests."""

    def test_full_workflow(self):
        """Test complete workflow: init -> synthesize -> save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize
            tts = MLXAudioTTS(voice="af_heart", speed=1.0)

            # Synthesize
            text = "Integration test for MLX-Audio TTS"
            audio, sr = tts.synthesize(text)

            # Save to file
            output_path = Path(tmpdir) / "integration_test.wav"
            tts.synthesize_to_file(text, output_path)

            # Verify
            assert output_path.exists()
            assert output_path.stat().st_size > 0
            assert len(audio) > 0
            assert sr == 24000

            # Cleanup
            tts.unload_model()

    @pytest.mark.skip(reason="Time-intensive, run manually for performance testing")
    def test_performance_multiple_syntheses(self):
        """Test performance with multiple synthesis calls."""
        import time

        tts = MLXAudioTTS()

        texts = [
            "First test",
            "Second test",
            "Third test",
            "Fourth test",
            "Fifth test",
        ]

        start = time.perf_counter()
        for text in texts:
            tts.synthesize(text)
        elapsed = time.perf_counter() - start

        # Should complete in reasonable time
        assert elapsed < 60, f"Synthesis took {elapsed}s for 5 texts"

        tts.unload_model()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
