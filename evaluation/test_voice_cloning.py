#!/usr/bin/env python3
"""
MLX-Audio Voice Cloning (Speech-to-Speech) Demonstration

Tests voice cloning capabilities using:
1. CSM-1B model: Voice cloning from reference audio
2. Kokoro-82M: Style transfer with reference audio

Usage:
    python3 test_voice_cloning.py --input reference_audio.wav --text "Hello world"
"""

import argparse
import tempfile
from pathlib import Path
import numpy as np
from typing import Optional, Tuple

try:
    from mlx_audio.tts.generate import generate_audio
    from mlx_audio.tts.models.csm import CSMPipeline
    from mlx_audio.tts.utils import load_model
    import soundfile as sf
    HAS_MLX_AUDIO = True
except ImportError as e:
    print(f"Error: {e}")
    HAS_MLX_AUDIO = False


def get_voice_characteristics(audio_path: Path) -> dict:
    """
    Analyze reference audio characteristics.

    Returns:
        Dictionary with audio properties
    """
    audio, sr = sf.read(audio_path)

    # Basic analysis
    duration = len(audio) / sr
    rms = np.sqrt(np.mean(audio ** 2))
    peak = np.max(np.abs(audio))

    return {
        "duration_s": duration,
        "sample_rate": sr,
        "channels": audio.ndim,
        "rms_level": rms,
        "peak_level": peak,
        "bit_depth": 16 if audio.dtype == np.int16 else 24,
    }


def test_csm_voice_cloning(
    text: str,
    reference_audio: Path,
    output_dir: Optional[Path] = None,
) -> Tuple[str, dict]:
    """
    Test voice cloning with CSM-1B model.

    CSM (Conversational Speech Model) supports voice cloning from reference audio.

    Args:
        text: Text to synthesize
        reference_audio: Path to reference audio file
        output_dir: Directory to save output (optional)

    Returns:
        Tuple of (output_file, metadata)
    """
    print("\n[CSM-1B] Voice Cloning Test")
    print("-" * 50)

    if not reference_audio.exists():
        raise FileNotFoundError(f"Reference audio not found: {reference_audio}")

    # Analyze reference
    ref_char = get_voice_characteristics(reference_audio)
    print(f"Reference Audio Characteristics:")
    print(f"  Duration: {ref_char['duration_s']:.2f}s")
    print(f"  Sample Rate: {ref_char['sample_rate']} Hz")
    print(f"  RMS Level: {ref_char['rms_level']:.4f}")

    # Output directory
    if output_dir is None:
        output_dir = Path(tempfile.gettempdir())
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "csm_cloned.wav"

    print(f"\nGenerating with reference audio...")
    print(f"Text: {text}")

    try:
        # CSM-1B supports voice cloning
        generate_audio(
            text=text,
            model_path="mlx-community/csm-1b",
            file_prefix=str(output_file.with_suffix('')),
            audio_format="wav",
            sample_rate=24000,
            ref_audio=str(reference_audio),  # Reference for voice cloning
            verbose=False
        )

        if not output_file.exists():
            # Try alternative naming
            alt_file = Path(str(output_file.with_suffix('')) + "_full.wav")
            if alt_file.exists():
                alt_file.rename(output_file)

        if output_file.exists():
            out_char = get_voice_characteristics(output_file)
            print(f"\n✅ Generated successfully!")
            print(f"  Output: {output_file}")
            print(f"  Duration: {out_char['duration_s']:.2f}s")
            print(f"  Size: {output_file.stat().st_size / 1024:.1f} KB")

            return str(output_file), {
                "model": "CSM-1B",
                "method": "voice_cloning",
                "reference_duration_s": ref_char['duration_s'],
                "output_duration_s": out_char['duration_s'],
            }
        else:
            print(f"⚠️  No output file generated")
            return None, {}

    except Exception as e:
        print(f"❌ CSM-1B cloning failed: {e}")
        return None, {"error": str(e)}


def test_kokoro_style_transfer(
    text: str,
    reference_audio: Path,
    voice_id: str = "af_heart",
    output_dir: Optional[Path] = None,
) -> Tuple[str, dict]:
    """
    Test style transfer with Kokoro-82M model.

    Kokoro uses reference audio for style transfer (pitch, prosody, emotion).

    Args:
        text: Text to synthesize
        reference_audio: Path to reference audio for style
        voice_id: Base voice to use
        output_dir: Directory to save output (optional)

    Returns:
        Tuple of (output_file, metadata)
    """
    print("\n[Kokoro-82M] Style Transfer Test")
    print("-" * 50)

    if not reference_audio.exists():
        raise FileNotFoundError(f"Reference audio not found: {reference_audio}")

    ref_char = get_voice_characteristics(reference_audio)
    print(f"Reference Audio Characteristics:")
    print(f"  Duration: {ref_char['duration_s']:.2f}s")
    print(f"  Sample Rate: {ref_char['sample_rate']} Hz")
    print(f"  Voice Base: {voice_id}")

    if output_dir is None:
        output_dir = Path(tempfile.gettempdir())
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "kokoro_styled.wav"

    print(f"\nGenerating with style transfer...")
    print(f"Text: {text}")

    try:
        # Kokoro with reference for style transfer
        generate_audio(
            text=text,
            model_path="prince-canuma/Kokoro-82M",
            voice=voice_id,
            file_prefix=str(output_file.with_suffix('')),
            audio_format="wav",
            sample_rate=24000,
            ref_audio=str(reference_audio),  # Reference for style
            verbose=False
        )

        if not output_file.exists():
            alt_file = Path(str(output_file.with_suffix('')) + "_full.wav")
            if alt_file.exists():
                alt_file.rename(output_file)

        if output_file.exists():
            out_char = get_voice_characteristics(output_file)
            print(f"\n✅ Generated successfully!")
            print(f"  Output: {output_file}")
            print(f"  Duration: {out_char['duration_s']:.2f}s")
            print(f"  Size: {output_file.stat().st_size / 1024:.1f} KB")

            return str(output_file), {
                "model": "Kokoro-82M",
                "method": "style_transfer",
                "voice": voice_id,
                "reference_duration_s": ref_char['duration_s'],
                "output_duration_s": out_char['duration_s'],
            }
        else:
            print(f"⚠️  No output file generated")
            return None, {}

    except Exception as e:
        print(f"❌ Kokoro style transfer failed: {e}")
        return None, {"error": str(e)}


def compare_voices(original_path: Path, cloned_paths: dict):
    """
    Print comparison between original and cloned voices.
    """
    print("\n" + "=" * 60)
    print("VOICE COMPARISON SUMMARY")
    print("=" * 60)

    orig_char = get_voice_characteristics(original_path)
    print(f"\nOriginal Voice:")
    print(f"  File: {original_path.name}")
    print(f"  Duration: {orig_char['duration_s']:.2f}s")
    print(f"  RMS Level: {orig_char['rms_level']:.4f}")

    for name, path in cloned_paths.items():
        if path and Path(path).exists():
            char = get_voice_characteristics(Path(path))
            print(f"\n{name}:")
            print(f"  File: {Path(path).name}")
            print(f"  Duration: {char['duration_s']:.2f}s")
            print(f"  RMS Level: {char['rms_level']:.4f}")
            print(f"  Size: {Path(path).stat().st_size / 1024:.1f} KB")


def main():
    parser = argparse.ArgumentParser(
        description="Test MLX-Audio voice cloning capabilities"
    )
    parser.add_argument(
        "--ref-audio",
        type=Path,
        default=None,
        help="Path to reference audio file (default: generate test audio)",
    )
    parser.add_argument(
        "--text",
        type=str,
        default="The quick brown fox jumps over the lazy dog.",
        help="Text to synthesize",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default="af_heart",
        help="Base voice for Kokoro (default: af_heart)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to save outputs (default: temp)",
    )

    args = parser.parse_args()

    if not HAS_MLX_AUDIO:
        print("Error: mlx-audio not installed")
        print("Install with: pip install mlx-audio")
        return

    # Use reference audio or create test audio
    if args.ref_audio:
        ref_audio = args.ref_audio
    else:
        # Generate reference using macOS say
        print("Generating reference audio with macOS say...")
        ref_audio = Path(tempfile.gettempdir()) / "reference.wav"
        import subprocess
        aiff_path = ref_audio.with_suffix('.aiff')
        subprocess.run(
            ["say", "-v", "Samantha", "-o", str(aiff_path), "The quick brown fox"],
            check=True
        )
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff_path), str(ref_audio)],
            check=True
        )
        aiff_path.unlink()
        print(f"✅ Reference audio created: {ref_audio}")

    # Test voice cloning
    print("\n" + "=" * 60)
    print("MLX-Audio Voice Cloning Tests")
    print("=" * 60)

    results = {}

    # CSM-1B cloning
    csm_output, csm_meta = test_csm_voice_cloning(
        args.text,
        ref_audio,
        args.output_dir
    )
    if csm_output:
        results["CSM-1B (Voice Cloning)"] = csm_output

    # Kokoro style transfer
    kokoro_output, kokoro_meta = test_kokoro_style_transfer(
        args.text,
        ref_audio,
        args.voice,
        args.output_dir
    )
    if kokoro_output:
        results["Kokoro-82M (Style Transfer)"] = kokoro_output

    # Summary
    if results:
        compare_voices(ref_audio, results)

        print("\n" + "=" * 60)
        print("Generated Audio Files:")
        print("=" * 60)
        for name, path in results.items():
            print(f"✅ {name}: {path}")
    else:
        print("\n❌ No output files generated")


if __name__ == "__main__":
    main()
