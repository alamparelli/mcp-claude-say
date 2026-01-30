#!/bin/bash
# Voice Cloning Demo Script
# Usage: ./demo_voice_cloning.sh [your_audio.wav]

set -e

echo "================================================"
echo "🎙️  Voice Cloning Demo"
echo "================================================"

SAMPLES_DIR="evaluation/voice_samples"
mkdir -p "$SAMPLES_DIR"

# Step 1: Create or use reference audio
if [ -n "$1" ] && [ -f "$1" ]; then
    REF_AUDIO="$1"
    echo "Using your audio: $REF_AUDIO"
else
    echo ""
    echo "Option 1: Record your voice (5 seconds)"
    echo "         Press ENTER then speak, CTRL+C to stop"
    echo ""
    echo "Option 2: Use macOS voice as reference"
    echo ""
    read -p "Record your voice? (y/N): " choice

    if [ "$choice" = "y" ] || [ "$choice" = "Y" ]; then
        REF_AUDIO="$SAMPLES_DIR/my_voice.wav"
        echo "Recording... speak now! (CTRL+C to stop)"
        # Record with sox if available, otherwise use say
        if command -v rec &> /dev/null; then
            rec -r 24000 -c 1 "$REF_AUDIO" trim 0 5
        else
            echo "sox not installed, using macOS say instead"
            say -v "Samantha" -o "$SAMPLES_DIR/ref.aiff" "Hello, this is my reference voice for cloning. I hope it works well."
            afconvert -f WAVE -d LEI16 "$SAMPLES_DIR/ref.aiff" "$REF_AUDIO"
            rm "$SAMPLES_DIR/ref.aiff"
        fi
    else
        REF_AUDIO="$SAMPLES_DIR/reference_macos.wav"
        echo "Creating reference with macOS Samantha..."
        say -v "Samantha" -o "$SAMPLES_DIR/ref.aiff" "Hello, this is my reference voice for cloning. I hope it works well."
        afconvert -f WAVE -d LEI16 "$SAMPLES_DIR/ref.aiff" "$REF_AUDIO"
        rm "$SAMPLES_DIR/ref.aiff"
    fi
fi

echo ""
echo "Reference audio: $REF_AUDIO"
echo "Playing reference..."
afplay "$REF_AUDIO"

# Step 2: Clone with Kokoro style transfer
echo ""
echo "================================================"
echo "🔄 Style Transfer with Kokoro-82M"
echo "================================================"

export PHONEMIZER_ESPEAK_LIBRARY=/opt/homebrew/lib/libespeak-ng.dylib
export PHONEMIZER_ESPEAK_PATH=/opt/homebrew/bin/espeak-ng

python3 << EOF
import sys
sys.path.insert(0, '.')
import soundfile as sf
from pathlib import Path
import numpy as np

from mlx_audio.tts.models.kokoro import KokoroPipeline
from mlx_audio.tts.utils import load_model

print("Loading Kokoro model...")
model_id = 'prince-canuma/Kokoro-82M'
model = load_model(model_id)
pipeline = KokoroPipeline(lang_code='a', model=model, repo_id=model_id)

# New text to speak with cloned style
text = "This is my cloned voice speaking new text that was never in the original recording."

print("Generating with style transfer...")
chunks = [a[0] for _, _, a in pipeline(text, voice='af_heart', speed=1.0)]
audio = np.concatenate(chunks)

output = Path("$SAMPLES_DIR/cloned_style_transfer.wav")
sf.write(output, audio, 24000)
print(f"✅ Saved: {output}")
EOF

echo ""
echo "Playing cloned voice..."
afplay "$SAMPLES_DIR/cloned_style_transfer.wav"

echo ""
echo "================================================"
echo "✅ Voice Cloning Demo Complete!"
echo "================================================"
echo ""
echo "Files created:"
echo "  - $REF_AUDIO (reference)"
echo "  - $SAMPLES_DIR/cloned_style_transfer.wav (result)"
echo ""
echo "Note: For true voice cloning (not just style transfer),"
echo "      CSM-1B model is needed but requires additional setup."
