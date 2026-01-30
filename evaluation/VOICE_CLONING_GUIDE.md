# MLX-Audio Voice Cloning & Style Transfer Guide

**Status**: Research & Testing Phase
**Branch**: `experimental/mlx-audio-tts`
**Date**: 2026-01-30

## Overview

MLX-Audio supports two approaches to voice customization:

1. **Voice Cloning (CSM-1B)**: Clone a speaker's unique voice characteristics
2. **Style Transfer (Kokoro-82M)**: Apply prosody, emotion, and intonation from reference audio

## Voice Cloning: CSM-1B Model

### What is CSM?

**CSM-1B** (Conversational Speech Model) is a specialized model for voice cloning. It learns voice characteristics from a reference audio sample and applies them to new text.

### Capabilities

- ✅ Clone any speaker's voice from audio sample
- ✅ Natural prosody and emotion transfer
- ✅ Support for multiple languages (optimized for English)
- ✅ Real-time synthesis (after model load)
- ⚠️ Requires good quality reference audio (>1 second)

### Usage

```python
from mlx_audio.tts.generate import generate_audio

# Clone a voice
generate_audio(
    text="Hello, I'm using your voice",
    model_path="mlx-community/csm-1b",
    ref_audio="speaker.wav",              # Reference audio
    file_prefix="cloned_output",
    audio_format="wav",
)
```

### Command Line

```bash
python -m mlx_audio.tts.generate \
    --model mlx-community/csm-1b \
    --text "Hello world" \
    --ref_audio reference.wav \
    --play
```

### Requirements

- Reference audio file (WAV, MP3, etc.)
- Duration: 2-30 seconds recommended
- Quality: Clear, low background noise
- Sample rate: 16kHz or higher

### Example Workflow

```bash
# 1. Record reference audio (e.g., 10 seconds)
# 2. Use as reference
python test_voice_cloning.py \
    --ref-audio your_voice.wav \
    --text "This is my cloned voice"
```

## Style Transfer: Kokoro-82M

### What is Style Transfer?

Kokoro can modify its base voices using prosody and emotional characteristics from reference audio without fully cloning the speaker's identity.

### Capabilities

- ✅ Apply emotion/prosody from reference
- ✅ Maintain base voice quality
- ✅ 20+ base voices to choose from
- ✅ Language-specific models
- ⚠️ Not true voice cloning (different acoustic space)

### Usage

```python
from mlx_audio.tts.generate import generate_audio

# Style transfer with Kokoro
generate_audio(
    text="Using reference prosody",
    model_path="prince-canuma/Kokoro-82M",
    voice="af_heart",                     # Base voice
    ref_audio="prosody_reference.wav",    # Style reference
    file_prefix="styled_output",
    audio_format="wav",
)
```

### When to Use

- Transfer emotional tone from reference
- Maintain consistent prosody across sentences
- Apply speaker characteristics to predefined voices
- Blend reference characteristics with base voice quality

## Comparison: CSM vs Kokoro for Cloning

| Feature | CSM-1B | Kokoro (with ref) |
|---------|--------|-------------------|
| Voice Cloning | ✅ True Cloning | ⚠️ Style Transfer |
| Quality | High | Very High |
| Voices | Custom (from ref) | 20+ Base Voices |
| Speed | Fast | Fast |
| Naturalness | Excellent | Excellent |
| Emotion Transfer | Yes | Yes |
| Use Case | Clone speaker voice | Enhanced base voice |

## Reference Audio Requirements

### Quality Checklist

```
✅ Clear speech (no heavy accents/slurring)
✅ Minimal background noise
✅ 16kHz+ sample rate
✅ 2-30 seconds duration
✅ Consistent volume level
✅ Normal speaking pace (not too fast/slow)
```

### Good Examples

- Natural conversation audio
- Interview clips (mono or stereo)
- Audiobook narration
- Clear speech recordings

### Bad Examples

- ❌ Heavy background music
- ❌ Multiple speakers overlapping
- ❌ Robotic/synthetic speech
- ❌ Very short clips (<1 second)
- ❌ Extremely high/low pitch distortions

## Testing Voice Cloning

### Quick Test

```bash
# Test with generated reference (macOS say)
python3 evaluation/test_voice_cloning.py

# Test with your own audio
python3 evaluation/test_voice_cloning.py \
    --ref-audio path/to/your/voice.wav \
    --text "Your text here"
```

### Output Files

- `csm_cloned.wav`: CSM-1B voice cloning result
- `kokoro_styled.wav`: Kokoro-82M style transfer result

### Manual Evaluation

Listen to the outputs and compare:

1. **Voice Identity**: Does it sound like the speaker?
2. **Naturalness**: Does the synthesis sound natural?
3. **Prosody**: Is intonation/rhythm preserved?
4. **Clarity**: Is articulation clear?
5. **Artifacts**: Any glitches, stutters, or robotic elements?

## Integration Roadmap (Phase 3+)

### Short Term
- [ ] Test CSM-1B cloning with Claude Code user voice
- [ ] Benchmark cloning latency
- [ ] Create voice profile system

### Medium Term
- [ ] Add voice cloning to `MLXAudioTTS` class
- [ ] Support user voice recording via PTT
- [ ] Store voice profiles for reuse
- [ ] MCP tool for voice cloning

### Long Term
- [ ] Real-time voice cloning in `/conversation` mode
- [ ] Voice-to-voice with Moshi MLX (experimental)
- [ ] Multi-speaker synthesis
- [ ] Voice transformation (emotion, age, gender)

## Known Limitations

### CSM-1B

- Model download: ~2-3 GB
- First load: 10-15 seconds
- Quality depends on reference audio quality
- Best for content that matches reference context

### Kokoro Style Transfer

- Not true speaker cloning
- Limited to 20+ predefined base voices
- Style transfer less effective than CSM

## Technical Details

### Model Comparison

**CSM-1B** (Conversational Speech Model)
- Encoder-Decoder architecture
- Learns speaker embeddings from reference
- Synthesizes from learned representation
- Size: ~2.3 GB (similar to Kokoro)

**Kokoro-82M**
- 82 Million parameter model
- Optimized for Apple Silicon (MLX)
- 20+ voice presets included
- Supports 9 languages

### Audio Specifications

- Sample Rate: 24kHz (Kokoro), 24kHz (CSM-1B)
- Bit Depth: 24-bit
- Duration: Real-time, limited by model throughput
- Supported Formats: WAV, MP3, FLAC

## Troubleshooting

### "Module not found: misaki"

```bash
pip install misaki
```

### "Reference audio too short"

- Use audio at least 2 seconds long
- Ensure clear speech (not music or background noise)

### Quality Issues with Cloned Voice

- Use higher quality reference audio
- Try different reference samples
- Ensure reference matches text language

### Memory Issues

- Unload model after use: `tts.unload_model()`
- Use smaller reference files
- Reduce batch size

## References

- [MLX-Audio Repository](https://github.com/Blaizzy/mlx-audio)
- [CSM-1B Model](https://github.com/Blaizzy/mlx-audio/tree/main/mlx_audio/tts/models/csm)
- [Kokoro-82M Model Card](https://huggingface.co/prince-canuma/Kokoro-82M)
- [MLX Framework](https://github.com/ml-explore/mlx)

## Related Issues

- **#6**: MLX-Audio Integration (Phase 1 - Core TTS)
- **#10**: Add Chatterbox TTS as alternative (Phase 2)
- **(Future) #11**: Voice Cloning Integration (Phase 3)

---

**Next Steps**:
1. Complete Phase 1 benchmark
2. Test cloning with actual user voice samples
3. Design integration for Phase 3
