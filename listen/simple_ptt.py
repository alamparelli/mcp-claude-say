"""
Simple Push-to-Talk Recorder - No VAD, just record and transcribe.

Press key to start recording, press again to stop and transcribe.
No automatic segmentation - captures everything between start/stop.
"""

import numpy as np
import soundfile as sf
import tempfile
import os
import threading
from typing import Optional, Callable
from pathlib import Path
from datetime import datetime

from .audio import AudioCapture


class SimplePTTRecorder:
    """
    Simple PTT recorder without VAD.

    Records continuously while active, transcribes on stop.
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
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.on_transcription_ready = on_transcription_ready

        self._audio = AudioCapture()
        self._is_recording = False
        self._transcriber = None
        self._last_transcription: Optional[str] = None
        self._last_audio_path: Optional[Path] = None
        self._lock = threading.Lock()

    def _get_transcriber(self):
        """Lazy load transcriber."""
        if self._transcriber is None:
            from .parakeet_transcriber import get_parakeet_transcriber
            self._transcriber = get_parakeet_transcriber()
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
        with self._lock:
            if self._is_recording:
                return

            self._audio.clear_buffer()
            self._audio.start()
            self._is_recording = True
            print("🎤 Recording started...")

    def stop(self) -> Optional[str]:
        """
        Stop recording and transcribe.

        Returns:
            Transcription text or None if no audio
        """
        with self._lock:
            if not self._is_recording:
                return None

            self._is_recording = False

            # Get recorded audio
            audio = self._audio.get_buffer()
            self._audio.stop()

            if len(audio) == 0:
                print("⚠️ No audio recorded")
                return None

            duration = len(audio) / AudioCapture.SAMPLE_RATE
            print(f"⏹️ Recording stopped ({duration:.1f}s)")

            # Save audio file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_path = self.output_dir / f"ptt_{timestamp}.flac"
            sf.write(str(audio_path), audio, AudioCapture.SAMPLE_RATE)
            self._last_audio_path = audio_path
            print(f"💾 Saved to {audio_path}")

            # Transcribe
            print("📝 Transcribing...")
            transcriber = self._get_transcriber()
            result = transcriber.transcribe(audio)

            self._last_transcription = result.text
            print(f"✅ Transcription: {result.text}")

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
    """Destroy global SimplePTTRecorder."""
    global _simple_ptt
    if _simple_ptt is not None:
        if _simple_ptt.is_recording:
            _simple_ptt.stop()
        _simple_ptt = None
