#!/usr/bin/env python3
"""
MLX-Audio TTS Benchmark Script
Phase 1: Evaluation of MLX-Audio for TTS vs macOS say

Tests:
1. Latency (time to first audio byte)
2. Total generation time
3. RAM/GPU consumption
4. Voice quality (generates samples for manual comparison)
"""

import os
import time
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
import json

# Benchmark configuration
TEST_TEXTS = {
    "short": "Hello, this is a test.",
    "medium": "The quick brown fox jumps over the lazy dog. This sentence contains every letter of the alphabet.",
    "long": """Welcome to the MLX Audio benchmark. This is a longer piece of text designed to test
    the performance of text-to-speech systems on more substantial content. We will measure
    latency, throughput, and resource consumption across multiple TTS backends."""
}

# Output directory for samples
OUTPUT_DIR = Path(__file__).parent / "samples"

# MLX-Audio voices to test (American English)
MLX_VOICES = [
    ("af_heart", "Heart (Female)"),
    ("am_adam", "Adam (Male)"),
    ("af_bella", "Bella (Female)"),
    ("am_echo", "Echo (Male)"),
]

# macOS say voices to compare
MACOS_VOICES = [
    ("Samantha", "Samantha (Female)"),
    ("Alex", "Alex (Male)"),
]


def get_ram_usage_mb() -> float:
    """Get current process RAM usage in MB."""
    import psutil
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


def measure_macos_say(text: str, voice: str, output_path: Path) -> Dict[str, Any]:
    """Measure macOS say command performance."""
    start_time = time.perf_counter()

    # Generate audio with say command
    aiff_path = output_path.with_suffix('.aiff')
    cmd = ["say", "-v", voice, "-o", str(aiff_path), text]

    subprocess.run(cmd, check=True, capture_output=True)

    end_time = time.perf_counter()

    # Convert to WAV for comparison
    wav_path = output_path.with_suffix('.wav')
    subprocess.run(
        ["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff_path), str(wav_path)],
        check=True, capture_output=True
    )

    # Clean up AIFF
    aiff_path.unlink()

    file_size = wav_path.stat().st_size

    return {
        "backend": "macos_say",
        "voice": voice,
        "total_time_s": end_time - start_time,
        "output_file": str(wav_path),
        "file_size_kb": file_size / 1024,
    }


def measure_mlx_audio(text: str, voice: str, output_path: Path) -> Dict[str, Any]:
    """Measure MLX-Audio performance."""
    from mlx_audio.tts.generate import generate_audio
    import soundfile as sf

    ram_before = get_ram_usage_mb()

    # Measure generation time
    start_time = time.perf_counter()

    # Generate audio
    generate_audio(
        text=text,
        model_path="prince-canuma/Kokoro-82M",
        voice=voice,
        speed=1.0,
        lang_code="a",  # American English
        file_prefix=str(output_path.with_suffix('')),
        audio_format="wav",
        sample_rate=24000,
        join_audio=True,
        verbose=False
    )

    end_time = time.perf_counter()
    ram_after = get_ram_usage_mb()

    # Find the generated file
    wav_path = output_path.with_suffix('.wav')
    if not wav_path.exists():
        # Try with _full suffix
        wav_path = Path(str(output_path.with_suffix('')) + "_full.wav")

    file_size = wav_path.stat().st_size if wav_path.exists() else 0

    return {
        "backend": "mlx_audio",
        "voice": voice,
        "model": "Kokoro-82M",
        "total_time_s": end_time - start_time,
        "output_file": str(wav_path) if wav_path.exists() else None,
        "file_size_kb": file_size / 1024,
        "ram_delta_mb": ram_after - ram_before,
        "ram_total_mb": ram_after,
    }


def measure_mlx_audio_streaming(text: str, voice: str) -> Dict[str, Any]:
    """Measure MLX-Audio with streaming (time to first chunk)."""
    try:
        from mlx_audio.tts.models.kokoro import KokoroPipeline
        from mlx_audio.tts.utils import load_model
    except ImportError as e:
        print(f"    WARNING: Missing dependency for streaming test: {e}")
        return {
            "backend": "mlx_audio_streaming",
            "voice": voice,
            "error": f"Missing dependency: {e}",
        }

    ram_before = get_ram_usage_mb()

    # Load model
    model_load_start = time.perf_counter()
    model_id = 'prince-canuma/Kokoro-82M'
    model = load_model(model_id)
    pipeline = KokoroPipeline(lang_code='a', model=model, repo_id=model_id)
    model_load_time = time.perf_counter() - model_load_start

    ram_after_model = get_ram_usage_mb()

    # Generate with streaming
    gen_start = time.perf_counter()
    first_chunk_time = None
    chunk_count = 0

    for _, _, audio in pipeline(text, voice=voice, speed=1.0, split_pattern=r'\n+'):
        if first_chunk_time is None:
            first_chunk_time = time.perf_counter() - gen_start
        chunk_count += 1

    total_gen_time = time.perf_counter() - gen_start
    ram_after_gen = get_ram_usage_mb()

    return {
        "backend": "mlx_audio_streaming",
        "voice": voice,
        "model": "Kokoro-82M",
        "model_load_time_s": model_load_time,
        "first_chunk_time_s": first_chunk_time,
        "total_gen_time_s": total_gen_time,
        "chunk_count": chunk_count,
        "ram_model_mb": ram_after_model - ram_before,
        "ram_generation_mb": ram_after_gen - ram_after_model,
        "ram_total_mb": ram_after_gen,
    }


def run_benchmark():
    """Run the complete benchmark suite."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tests": []
    }

    print("=" * 60)
    print("MLX-Audio TTS Benchmark - Phase 1 Evaluation")
    print("=" * 60)

    # Test 1: Streaming latency (time to first chunk)
    print("\n[1/4] Testing MLX-Audio Streaming Latency...")
    print("-" * 40)

    for voice_id, voice_name in MLX_VOICES[:2]:  # Test 2 voices
        print(f"  Voice: {voice_name}")
        result = measure_mlx_audio_streaming(TEST_TEXTS["medium"], voice_id)
        results["tests"].append({
            "test_type": "streaming_latency",
            **result
        })
        if "error" not in result:
            print(f"    Model load: {result['model_load_time_s']:.2f}s")
            print(f"    First chunk: {result['first_chunk_time_s']:.3f}s")
            print(f"    Total: {result['total_gen_time_s']:.2f}s")
            print(f"    RAM: {result['ram_total_mb']:.0f} MB")
        else:
            print(f"    Skipped: {result['error']}")

    # Test 2: MLX-Audio generation (all voices)
    print("\n[2/4] Testing MLX-Audio Generation...")
    print("-" * 40)

    for text_name, text in TEST_TEXTS.items():
        for voice_id, voice_name in MLX_VOICES:
            output_path = OUTPUT_DIR / f"mlx_{voice_id}_{text_name}"
            print(f"  {voice_name} - {text_name}: ", end="", flush=True)

            try:
                result = measure_mlx_audio(text, voice_id, output_path)
                results["tests"].append({
                    "test_type": "generation",
                    "text_type": text_name,
                    "text_length": len(text),
                    **result
                })
                print(f"{result['total_time_s']:.2f}s ({result['file_size_kb']:.0f} KB)")
            except Exception as e:
                print(f"ERROR: {e}")
                results["tests"].append({
                    "test_type": "generation",
                    "text_type": text_name,
                    "voice": voice_id,
                    "error": str(e)
                })

    # Test 3: macOS say comparison
    print("\n[3/4] Testing macOS say (baseline)...")
    print("-" * 40)

    for text_name, text in TEST_TEXTS.items():
        for voice_id, voice_name in MACOS_VOICES:
            output_path = OUTPUT_DIR / f"macos_{voice_id}_{text_name}"
            print(f"  {voice_name} - {text_name}: ", end="", flush=True)

            try:
                result = measure_macos_say(text, voice_id, output_path)
                results["tests"].append({
                    "test_type": "generation",
                    "text_type": text_name,
                    "text_length": len(text),
                    **result
                })
                print(f"{result['total_time_s']:.2f}s ({result['file_size_kb']:.0f} KB)")
            except Exception as e:
                print(f"ERROR: {e}")

    # Test 4: RAM baseline measurement
    print("\n[4/4] Measuring RAM Consumption...")
    print("-" * 40)

    import psutil
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()

    results["ram_summary"] = {
        "current_rss_mb": mem_info.rss / 1024 / 1024,
        "current_vms_mb": mem_info.vms / 1024 / 1024,
    }

    print(f"  Process RSS: {results['ram_summary']['current_rss_mb']:.0f} MB")
    print(f"  Process VMS: {results['ram_summary']['current_vms_mb']:.0f} MB")

    # Save results
    results_path = OUTPUT_DIR / "benchmark_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    # Generate summary report
    print("\n" + "=" * 60)
    print("SUMMARY REPORT")
    print("=" * 60)

    generate_summary(results)

    print(f"\n[OK] Results saved to: {results_path}")
    print(f"[OK] Audio samples saved to: {OUTPUT_DIR}")

    return results


def generate_summary(results: dict):
    """Generate a summary comparison report."""

    # Extract generation tests
    gen_tests = [t for t in results["tests"] if t.get("test_type") == "generation"]

    # Group by backend
    mlx_tests = [t for t in gen_tests if t.get("backend") == "mlx_audio"]
    macos_tests = [t for t in gen_tests if t.get("backend") == "macos_say"]

    if mlx_tests and macos_tests:
        # Calculate averages for medium text
        mlx_medium = [t for t in mlx_tests if t.get("text_type") == "medium"]
        macos_medium = [t for t in macos_tests if t.get("text_type") == "medium"]

        if mlx_medium and macos_medium:
            mlx_avg = sum(t["total_time_s"] for t in mlx_medium) / len(mlx_medium)
            macos_avg = sum(t["total_time_s"] for t in macos_medium) / len(macos_medium)

            print(f"\nGeneration Time (medium text):")
            print(f"  MLX-Audio avg: {mlx_avg:.2f}s")
            print(f"  macOS say avg: {macos_avg:.2f}s")
            print(f"  Difference: {mlx_avg - macos_avg:+.2f}s")

    # Streaming latency
    streaming_tests = [t for t in results["tests"] if t.get("test_type") == "streaming_latency"]
    if streaming_tests:
        avg_first_chunk = sum(t["first_chunk_time_s"] for t in streaming_tests) / len(streaming_tests)
        avg_model_load = sum(t["model_load_time_s"] for t in streaming_tests) / len(streaming_tests)

        print(f"\nMLX-Audio Streaming:")
        print(f"  Model load (cached): {avg_model_load:.2f}s")
        print(f"  First chunk latency: {avg_first_chunk:.3f}s")

    # RAM usage
    if "ram_summary" in results:
        print(f"\nRAM Usage:")
        print(f"  After model load: {results['ram_summary']['current_rss_mb']:.0f} MB")

    # Quality evaluation note
    print(f"\n[NOTE] Audio samples generated in: {OUTPUT_DIR}")
    print("  Compare the WAV files manually to evaluate voice quality.")
    print("  MLX-Audio uses neural synthesis vs macOS say's concatenative synthesis.")


if __name__ == "__main__":
    # Check for psutil
    try:
        import psutil
    except ImportError:
        print("Installing psutil for RAM measurement...")
        subprocess.run(["pip", "install", "psutil"], check=True)
        import psutil

    run_benchmark()
