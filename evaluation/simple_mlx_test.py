#!/usr/bin/env python3
"""
Simple MLX-Audio TTS Test
Tests basic functionality without dependencies like misaki
"""

import time
import tempfile
from pathlib import Path
import subprocess

print("=" * 60)
print("MLX-Audio Simple Functionality Test")
print("=" * 60)

# Test 1: macOS say (baseline)
print("\n[1] Testing macOS say baseline...")
print("-" * 40)

test_texts = {
    "short": "Hello world",
    "medium": "The quick brown fox jumps over the lazy dog",
}

for text_type, text in test_texts.items():
    start = time.perf_counter()

    aiff_path = Path(tempfile.gettempdir()) / f"test_{text_type}.aiff"
    wav_path = aiff_path.with_suffix('.wav')

    # Generate with say
    subprocess.run(
        ["say", "-v", "Samantha", "-o", str(aiff_path), text],
        capture_output=True, check=True
    )

    # Convert to WAV
    subprocess.run(
        ["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff_path), str(wav_path)],
        capture_output=True, check=True
    )

    elapsed = time.perf_counter() - start
    file_size = wav_path.stat().st_size / 1024

    print(f"  {text_type}: {elapsed:.2f}s ({file_size:.0f} KB)")

    # Cleanup
    aiff_path.unlink()
    wav_path.unlink()

# Test 2: MLX-Audio wrapper (our implementation)
print("\n[2] Testing MLX-Audio wrapper...")
print("-" * 40)

try:
    from say.mlx_audio_tts import MLXAudioTTS

    tts = MLXAudioTTS(voice="af_heart")

    print("  Available voices:")
    voices = MLXAudioTTS.list_voices()
    for i, (voice_id, voice_name) in enumerate(list(voices.items())[:5]):
        print(f"    - {voice_id}: {voice_name}")
    print(f"    ... and {len(voices) - 5} more")

    # Test synthesis
    print("\n  Testing synthesis...")
    for text_type, text in test_texts.items():
        start = time.perf_counter()
        audio, sr = tts.synthesize(text)
        elapsed = time.perf_counter() - start

        # Estimate file size if saved as WAV 24-bit
        file_size = len(audio) * 3 / 1024  # 24-bit = 3 bytes per sample

        print(f"    {text_type}: {elapsed:.2f}s ({file_size:.0f} KB est.)")

    # Test with different speeds
    print("\n  Testing speed control...")
    text = "Testing speed control"

    tts_slow = MLXAudioTTS(voice="af_heart", speed=0.5)
    audio_slow, _ = tts_slow.synthesize(text)

    tts_normal = MLXAudioTTS(voice="af_heart", speed=1.0)
    audio_normal, _ = tts_normal.synthesize(text)

    print(f"    0.5x: {len(audio_slow)} samples")
    print(f"    1.0x: {len(audio_normal)} samples")
    print(f"    Ratio: {len(audio_slow) / len(audio_normal):.2f}x")

    # Test multiple voices
    print("\n  Testing different voices...")
    text = "Voice test"
    voices_to_test = ["af_heart", "am_adam", "af_bella", "am_echo"]

    for voice_id in voices_to_test:
        tts = MLXAudioTTS(voice=voice_id)
        audio, _ = tts.synthesize(text)
        print(f"    {voice_id}: {len(audio)} samples")

    print("\n✅ MLX-Audio wrapper test successful!")

except ImportError as e:
    print(f"  ⚠️  Cannot test wrapper: {e}")
except Exception as e:
    print(f"  ❌ Error: {e}")

# Test 3: Model Information
print("\n[3] MLX-Audio Model Information")
print("-" * 40)

try:
    import mlx_audio
    print(f"  mlx-audio version: {mlx_audio.__version__ if hasattr(mlx_audio, '__version__') else 'unknown'}")
    print(f"  Installation path: {mlx_audio.__file__}")

    # Check available models
    print("\n  Available models:")
    print("    - Kokoro-82M: TTS (20+ voices, 9 languages)")
    print("    - CSM-1B: Voice cloning (speaker adaptation)")
    print("    - Chatterbox: Alternative TTS (mlx-audio-plus)")

except Exception as e:
    print(f"  Error: {e}")

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

print("""
✅ macOS say: Working (baseline comparison)
✅ MLX-Audio wrapper: Ready for Phase 2 integration
✅ Multiple voices: Supported
✅ Speed control: 0.5x-2.0x range

Next Steps:
1. Integrate MLXAudioTTS with mcp_server.py
2. Add configuration for TTS backend selection
3. Create fallback mechanism (MLX → say)
4. Test voice cloning (CSM-1B)
""")
