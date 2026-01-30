# MLX-Audio Phase 1 Testing Guide

## Quick Start

### 1. Test MLXAudioTTS Wrapper (2 minutes)

```bash
# From project root
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from say.mlx_audio_tts import MLXAudioTTS

# Create TTS instance
tts = MLXAudioTTS(voice="af_heart")

# Test synthesis
audio, sr = tts.synthesize("Hello world")
print(f"✅ Generated {len(audio) / sr:.2f}s of audio at {sr} Hz")

# Test different voices
for voice in ["af_heart", "am_adam", "af_bella"]:
    tts = MLXAudioTTS(voice=voice)
    audio, _ = tts.synthesize("Voice test")
    print(f"✅ {voice}: {len(audio)} samples")

# Test speed control
for speed in [0.5, 1.0, 2.0]:
    tts = MLXAudioTTS(speed=speed)
    audio, _ = tts.synthesize("Speed test")
    print(f"✅ {speed}x: {len(audio)} samples")

print("\n✅ All basic tests passed!")
EOF
```

### 2. Run Unit Tests (5 minutes)

```bash
# Install pytest if needed
pip install pytest

# Run all tests
pytest tests/test_mlx_audio_tts.py -v

# Run specific test class
pytest tests/test_mlx_audio_tts.py::TestMLXAudioTTSSynthesis -v

# Run with coverage
pytest tests/test_mlx_audio_tts.py --cov=say.mlx_audio_tts
```

### 3. Test Voice Cloning (10 minutes)

```bash
# Basic test (generates reference audio automatically)
python3 evaluation/test_voice_cloning.py

# Test with your own voice
python3 evaluation/test_voice_cloning.py \
    --ref-audio /path/to/your/voice.wav \
    --text "This is my custom text"

# Custom voice selection
python3 evaluation/test_voice_cloning.py \
    --voice am_michael  # Use male voice base
```

### 4. Run Benchmarks (30 minutes)

```bash
# Simple performance test
python3 evaluation/simple_mlx_test.py

# Full benchmark suite
python3 evaluation/mlx_audio_benchmark.py
```

## Detailed Testing Scenarios

### Scenario 1: Basic Functionality

```bash
python3 << 'EOF'
from say.mlx_audio_tts import MLXAudioTTS

# Test 1: Initialization
print("Test 1: Initialization")
tts = MLXAudioTTS(voice="af_heart", speed=1.0)
print(f"  ✅ TTS initialized")

# Test 2: List voices
print("\nTest 2: Voice enumeration")
voices = MLXAudioTTS.list_voices()
print(f"  ✅ Found {len(voices)} voices")
for v_id, v_name in list(voices.items())[:3]:
    print(f"     - {v_id}: {v_name}")

# Test 3: Synthesis
print("\nTest 3: Text synthesis")
text = "The quick brown fox jumps over the lazy dog"
audio, sr = tts.synthesize(text)
print(f"  ✅ Generated {len(audio) / sr:.2f}s audio")
print(f"     Sample rate: {sr} Hz")
print(f"     Samples: {len(audio)}")

# Test 4: Speed variations
print("\nTest 4: Speed control")
for speed in [0.5, 1.0, 1.5, 2.0]:
    tts_speed = MLXAudioTTS(speed=speed)
    audio, _ = tts_speed.synthesize("Speed test")
    duration = len(audio) / 24000
    print(f"  ✅ {speed}x: {duration:.2f}s")

# Test 5: File output
print("\nTest 5: File output")
import tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as tmpdir:
    output = Path(tmpdir) / "test.wav"
    tts.synthesize_to_file("Hello world", output)
    size = output.stat().st_size / 1024
    print(f"  ✅ Saved {size:.1f} KB to {output.name}")

print("\n✅ All basic tests passed!")
EOF
```

### Scenario 2: Voice Comparison

```bash
python3 << 'EOF'
from say.mlx_audio_tts import MLXAudioTTS

text = "Comparing different voices"

# Female voices
print("Female Voices:")
for voice_id in ["af_heart", "af_bella", "af_jessica", "af_nova"]:
    tts = MLXAudioTTS(voice=voice_id)
    audio, sr = tts.synthesize(text)
    print(f"  {voice_id}: {len(audio) / sr:.2f}s")

# Male voices
print("\nMale Voices:")
for voice_id in ["am_adam", "am_echo", "am_liam", "am_michael"]:
    tts = MLXAudioTTS(voice=voice_id)
    audio, sr = tts.synthesize(text)
    print(f"  {voice_id}: {len(audio) / sr:.2f}s")
EOF
```

### Scenario 3: Memory Management

```bash
python3 << 'EOF'
import psutil
import os
from say.mlx_audio_tts import MLXAudioTTS

def get_rss_mb():
    return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024

print("Memory Profile:")
baseline = get_rss_mb()
print(f"  Baseline: {baseline:.0f} MB")

# Create TTS (model not loaded yet)
tts = MLXAudioTTS()
after_init = get_rss_mb()
print(f"  After init: {after_init:.0f} MB (+{after_init - baseline:.0f})")

# First synthesis (loads model)
audio, _ = tts.synthesize("Hello")
after_load = get_rss_mb()
print(f"  After model load: {after_load:.0f} MB (+{after_load - baseline:.0f})")

# Second synthesis (reuses model)
audio, _ = tts.synthesize("World")
after_reuse = get_rss_mb()
print(f"  After reuse: {after_reuse:.0f} MB (+{after_reuse - baseline:.0f})")

# Unload model
tts.unload_model()
after_unload = get_rss_mb()
print(f"  After unload: {after_unload:.0f} MB (+{after_unload - baseline:.0f})")
EOF
```

### Scenario 4: Error Handling

```bash
python3 << 'EOF'
from say.mlx_audio_tts import MLXAudioTTS

print("Testing error handling:")

# Test 1: Invalid voice
print("\n1. Invalid voice:")
try:
    tts = MLXAudioTTS(voice="invalid_voice")
except ValueError as e:
    print(f"  ✅ Caught: {e}")

# Test 2: Invalid speed (too low)
print("\n2. Speed too low:")
try:
    tts = MLXAudioTTS(speed=0.3)
except ValueError as e:
    print(f"  ✅ Caught: {e}")

# Test 3: Invalid speed (too high)
print("\n3. Speed too high:")
try:
    tts = MLXAudioTTS(speed=2.5)
except ValueError as e:
    print(f"  ✅ Caught: {e}")

print("\n✅ Error handling working correctly!")
EOF
```

### Scenario 5: Comparison with macOS say

```bash
python3 << 'EOF'
import subprocess
import time
import tempfile
from pathlib import Path
from say.mlx_audio_tts import MLXAudioTTS

text = "The quick brown fox jumps over the lazy dog"

# Test macOS say
print("macOS say:")
start = time.perf_counter()
aiff = Path(tempfile.gettempdir()) / "say_test.aiff"
subprocess.run(["say", "-o", str(aiff), text], capture_output=True)
elapsed = time.perf_counter() - start
aiff.unlink()
print(f"  Time: {elapsed:.2f}s")

# Test MLX-Audio
print("\nMLX-Audio (Kokoro):")
tts = MLXAudioTTS()
start = time.perf_counter()
audio, _ = tts.synthesize(text)
elapsed = time.perf_counter() - start
print(f"  Time: {elapsed:.2f}s")

print("\n✅ Comparison complete!")
EOF
```

## Voice Cloning Tests

### Test CSM-1B Voice Cloning

```bash
# Generate reference (5 seconds)
say -v Samantha -o reference.wav "The quick brown fox jumps over the lazy dog plus extra words to make it longer"

# Clone with CSM
python3 << 'EOF'
from evaluation.test_voice_cloning import test_csm_voice_cloning
from pathlib import Path

output, meta = test_csm_voice_cloning(
    "Hello from cloned voice",
    Path("reference.wav")
)

print(f"\n✅ Generated: {output}")
print(f"   Model: {meta['model']}")
print(f"   Method: {meta['method']}")
EOF
```

### Test Style Transfer

```bash
python3 << 'EOF'
from evaluation.test_voice_cloning import test_kokoro_style_transfer
from pathlib import Path

# Use reference for prosody
output, meta = test_kokoro_style_transfer(
    "Applying style from reference",
    Path("reference.wav"),
    voice_id="af_heart"
)

print(f"\n✅ Generated: {output}")
print(f"   Method: {meta['method']}")
EOF
```

## Pytest Test Suites

### Run All Tests

```bash
pytest tests/test_mlx_audio_tts.py -v
```

### Run Specific Test Groups

```bash
# Initialization tests
pytest tests/test_mlx_audio_tts.py::TestMLXAudioTTSInit -v

# Synthesis tests
pytest tests/test_mlx_audio_tts.py::TestMLXAudioTTSSynthesis -v

# Voice management
pytest tests/test_mlx_audio_tts.py::TestMLXAudioTTSVoices -v

# File output
pytest tests/test_mlx_audio_tts.py::TestMLXAudioTTSFileOutput -v

# Integration tests
pytest tests/test_mlx_audio_tts.py::TestMLXAudioTTSIntegration -v
```

### Performance Tests (Optional)

```bash
# Skip time-intensive tests
pytest tests/test_mlx_audio_tts.py -v -m "not slow"

# Run only performance tests
pytest tests/test_mlx_audio_tts.py::TestMLXAudioTTSIntegration::test_performance_multiple_syntheses -v
```

## Troubleshooting

### Issue: "No module named 'misaki'"

```bash
pip install misaki
```

### Issue: "Model download stuck"

```bash
# Use HF token for faster downloads
huggingface-cli login

# Or set token directly
export HF_TOKEN="your-token-here"
```

### Issue: Memory exhausted

```bash
# Unload model immediately after use
tts.unload_model()

# Or reduce concurrent instances
tts1.unload_model()  # before creating tts2
tts2 = MLXAudioTTS()
```

### Issue: Synthesis too slow

- First synthesis includes model load (~10s) - normal
- Subsequent syntheses fast (<1-2s) - use caching
- Model caching is automatic by default

## Validation Checklist

Before Phase 2 integration:

- [ ] Wrapper loads without errors
- [ ] Can synthesize text to audio
- [ ] All voices work
- [ ] Speed control 0.5x-2.0x working
- [ ] Model caching working
- [ ] File output to WAV working
- [ ] Error handling for invalid inputs
- [ ] Memory usage reasonable (<4GB)
- [ ] Voice cloning demos working
- [ ] Unit tests passing

## Next Steps

After validating Phase 1 testing:

1. ✅ Create feature branch for Phase 2
2. ✅ Integrate MLXAudioTTS with mcp_server.py
3. ✅ Add configuration system
4. ✅ Implement fallback to macOS say
5. ✅ Test with real Claude Code environment

---

**Questions?** See `VOICE_CLONING_GUIDE.md` or `PHASE1_COMPLETION.md`
