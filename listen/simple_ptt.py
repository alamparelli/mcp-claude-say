"""
Simple Push-to-Talk Recorder - No VAD, just record and transcribe.

Press key to start recording, press again to stop and transcribe.
No automatic segmentation - captures everything between start/stop.

IMPORTANT: This module must properly release the microphone when done
to turn off the macOS orange mic indicator.
"""

import numpy as np
import soundfile as sf
import tempfile
import os
import threading
import sys
from typing import Optional, Callable
from pathlib import Path
from datetime import datetime

from .audio import AudioCapture, destroy_capture


class SimplePTTRecorder:
    """
    Simple PTT recorder without VAD.

    Records continuously while active, transcribes on stop.

    CRITICAL: Call destroy() when done to release the microphone
    and turn off the macOS orange mic indicator.
    """

    def __init__(
        self,
        output_dir: Path = Path("/tmp/claude-ptt"),
        on_transcription_ready: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize simple PTT recorder.

        Args:
            output_dir: Directory to save recordings
            on_transcription_ready: Callback when transcription is done
        """
        print("[SimplePTTRecorder] Initializing...", file=sys.stderr)
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.on_transcription_ready = on_transcription_ready

        self._audio = AudioCapture()
        self._is_recording = False
        self._transcriber = None
        self._last_transcription: Optional[str] = None
        self._last_audio_path: Optional[Path] = None
        self._lock = threading.Lock()
        print("[SimplePTTRecorder] Initialized", file=sys.stderr)

    def _get_transcriber(self):
        """
        Lazy load transcriber.

        Tries to load in order:
        1. Parakeet-MLX (recommended, if installed)
        2. SpeechAnalyzer (if available on macOS 26+)
        3. Raises error if none available
        """
        if self._transcriber is None:
            # Try Parakeet-MLX first (recommended)
            try:
                from .parakeet_transcriber import get_parakeet_transcriber
                self._transcriber = get_parakeet_transcriber()
                print("🎯 Using Parakeet-MLX")
                return self._transcriber
            except ImportError:
                pass

            # Try SpeechAnalyzer (experimental, macOS 26+)
            try:
                from .speechanalyzer_transcriber import (
                    is_speechanalyzer_available,
                    get_speechanalyzer_transcriber
                )
                if is_speechanalyzer_available():
                    self._transcriber = get_speechanalyzer_transcriber()
                    print("🎯 Using SpeechAnalyzer (Apple native)")
                    return self._transcriber
            except ImportError:
                pass

            # No transcriber available
            raise RuntimeError(
                "No STT transcriber available. Install with:\n"
                "  - Parakeet (recommended): pip install parakeet-mlx\n"
                "  - SpeechAnalyzer: Requires macOS 26+ and CLI build"
            )

        return self._transcriber

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording

    @property
    def last_transcription(self) -> Optional[str]:
        """Get the last transcription result."""
        return self._last_transcription

    def start(self) -> None:
        """Start recording audio."""
        print("[SimplePTTRecorder] start() called", file=sys.stderr)
        with self._lock:
            if self._is_recording:
                print("[SimplePTTRecorder] Already recording, skipping", file=sys.stderr)
                return

            self._audio.clear_buffer()
            self._audio.start()
            self._is_recording = True
            print("🎤 Recording started...", file=sys.stderr)

    def stop(self) -> Optional[str]:
        """
        Stop recording and transcribe.

        Returns:
            Transcription text or None if no audio
        """
        print("[SimplePTTRecorder] stop() called", file=sys.stderr)
        with self._lock:
            if not self._is_recording:
                print("[SimplePTTRecorder] Not recording, skipping stop", file=sys.stderr)
                return None

            self._is_recording = False

            # Get recorded audio BEFORE stopping (to capture buffer)
            audio = self._audio.get_buffer()

            # CRITICAL: Stop and release the microphone
            self._audio.stop()
            print("[SimplePTTRecorder] Audio capture stopped, mic released", file=sys.stderr)

            if len(audio) == 0:
                print("⚠️ No audio recorded", file=sys.stderr)
                return None

            duration = len(audio) / AudioCapture.SAMPLE_RATE
            print(f"⏹️ Recording stopped ({duration:.1f}s)", file=sys.stderr)

            # Save audio file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_path = self.output_dir / f"ptt_{timestamp}.flac"
            sf.write(str(audio_path), audio, AudioCapture.SAMPLE_RATE)
            self._last_audio_path = audio_path
            print(f"💾 Saved to {audio_path}", file=sys.stderr)

            # Transcribe
            print("📝 Transcribing...", file=sys.stderr)
            transcriber = self._get_transcriber()
            result = transcriber.transcribe(audio)

            self._last_transcription = result.text
            print(f"✅ Transcription: {result.text}", file=sys.stderr)

            # Callback
            if self.on_transcription_ready:
                self.on_transcription_ready(result.text)

            return result.text

    def clear(self) -> None:
        """Clear last recording and transcription."""
        self._last_transcription = None
        if self._last_audio_path and self._last_audio_path.exists():
            self._last_audio_path.unlink()
            self._last_audio_path = None


# Global instance
_simple_ptt: Optional[SimplePTTRecorder] = None


def get_simple_ptt(
    on_transcription_ready: Optional[Callable[[str], None]] = None
) -> SimplePTTRecorder:
    """Get or create global SimplePTTRecorder."""
    global _simple_ptt
    if _simple_ptt is None:
        _simple_ptt = SimplePTTRecorder(on_transcription_ready=on_transcription_ready)
    return _simple_ptt


def destroy_simple_ptt() -> None:
    """
    Destroy global SimplePTTRecorder and RELEASE the microphone.

    CRITICAL: This must be called to turn off the macOS orange mic indicator.
    """
    global _simple_ptt
    print("[SimplePTTRecorder] destroy_simple_ptt() called", file=sys.stderr)
    if _simple_ptt is not None:
        if _simple_ptt.is_recording:
            print("[SimplePTTRecorder] Still recording, stopping first", file=sys.stderr)
            _simple_ptt.stop()

        # CRITICAL: Also destroy the AudioCapture singleton to fully release mic
        destroy_capture()

        _simple_ptt = None
        print("[SimplePTTRecorder] Global PTT recorder destroyed, mic released", file=sys.stderr)
    else:
        print("[SimplePTTRecorder] No PTT recorder to destroy", file=sys.stderr)
