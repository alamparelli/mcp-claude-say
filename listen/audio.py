"""
Audio capture module for claude-listen.
Captures audio from microphone using sounddevice.

IMPORTANT: macOS mic indicators are handle-based, not activity-based.
If any process holds an open audio input stream, the indicator stays on.
We MUST fully close and release the stream when done recording.
"""

import numpy as np
import sounddevice as sd
from typing import Callable, Optional
import threading
from queue import Queue
import sys


class AudioCapture:
    """
    Captures audio from microphone in real-time.

    CRITICAL: Call close() or destroy() when done to release the microphone.
    macOS will show the orange mic indicator until the stream is fully released.
    """

    SAMPLE_RATE = 16000  # Whisper expects 16kHz
    CHANNELS = 1  # Mono
    DTYPE = np.float32
    BLOCK_SIZE = 512  # ~32ms at 16kHz

    def __init__(self, on_audio: Optional[Callable[[np.ndarray], None]] = None):
        """
        Initialize audio capture.

        Args:
            on_audio: Callback function called with each audio chunk
        """
        self.on_audio = on_audio
        self._stream: Optional[sd.InputStream] = None
        self._is_running = False
        self._audio_queue: Queue = Queue()
        self._buffer: list[np.ndarray] = []
        self._lock = threading.Lock()
        print("[AudioCapture] Initialized", file=sys.stderr)

    def __del__(self):
        """Ensure stream is closed on garbage collection."""
        self._force_close_stream()

    def _force_close_stream(self) -> None:
        """Force close the audio stream - releases mic to OS."""
        try:
            if self._stream is not None:
                try:
                    self._stream.stop()
                except Exception:
                    pass  # May already be stopped
                try:
                    self._stream.close()
                except Exception:
                    pass  # May already be closed
                self._stream = None
                print("[AudioCapture] Stream force-closed, mic released", file=sys.stderr)
        except Exception as e:
            print(f"[AudioCapture] Error in _force_close_stream: {e}", file=sys.stderr)

    def _audio_callback(self, indata: np.ndarray, frames: int,
                        time_info: dict, status: sd.CallbackFlags) -> None:
        """Called by sounddevice for each audio block."""
        if status:
            print(f"[AudioCapture] Audio status: {status}", file=sys.stderr)

        # Copy data to avoid issues with buffer reuse
        audio_chunk = indata.copy().flatten()

        # Add to buffer
        with self._lock:
            self._buffer.append(audio_chunk)

        # Call callback if set
        if self.on_audio:
            self.on_audio(audio_chunk)

        # Also put in queue for get_audio()
        self._audio_queue.put(audio_chunk)

    def start(self) -> None:
        """Start capturing audio from microphone."""
        if self._is_running:
            print("[AudioCapture] Already running, skipping start", file=sys.stderr)
            return

        print("[AudioCapture] Starting audio capture...", file=sys.stderr)
        self._is_running = True
        self._buffer = []

        try:
            self._stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype=self.DTYPE,
                blocksize=self.BLOCK_SIZE,
                callback=self._audio_callback
            )
            self._stream.start()
            print("[AudioCapture] Stream started, mic is now active (orange dot)", file=sys.stderr)
        except Exception as e:
            print(f"[AudioCapture] Failed to start stream: {e}", file=sys.stderr)
            self._is_running = False
            self._force_close_stream()
            raise

    def stop(self) -> None:
        """
        Stop capturing audio and RELEASE the microphone.

        This MUST be called to turn off the macOS mic indicator.
        """
        if not self._is_running:
            print("[AudioCapture] Not running, skipping stop", file=sys.stderr)
            return

        print("[AudioCapture] Stopping audio capture...", file=sys.stderr)
        self._is_running = False

        # CRITICAL: Fully close the stream to release mic
        self._force_close_stream()
        print("[AudioCapture] Audio capture stopped, mic should be released", file=sys.stderr)

    def get_buffer(self) -> np.ndarray:
        """
        Get all buffered audio and clear the buffer.

        Returns:
            Concatenated audio data as numpy array
        """
        with self._lock:
            if not self._buffer:
                return np.array([], dtype=self.DTYPE)

            audio = np.concatenate(self._buffer)
            self._buffer = []
            return audio

    def clear_buffer(self) -> None:
        """Clear the audio buffer."""
        with self._lock:
            self._buffer = []

        # Also clear the queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except:
                break

    @property
    def is_running(self) -> bool:
        """Check if audio capture is active."""
        return self._is_running

    def restart(self) -> None:
        """Restart audio capture to handle device changes."""
        was_running = self._is_running
        self.stop()
        if was_running:
            self.start()

    @staticmethod
    def list_devices() -> list[dict]:
        """List available audio input devices."""
        devices = sd.query_devices()
        input_devices = []

        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append({
                    'id': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'],
                    'sample_rate': device['default_samplerate']
                })

        return input_devices


# Singleton instance for easy access
_capture: Optional[AudioCapture] = None


def get_capture() -> AudioCapture:
    """Get or create the global AudioCapture instance."""
    global _capture
    if _capture is None:
        _capture = AudioCapture()
    return _capture


def destroy_capture() -> None:
    """
    Destroy the global AudioCapture instance and release the microphone.

    CRITICAL: Call this when PTT mode ends to turn off the mic indicator.
    """
    global _capture
    if _capture is not None:
        print("[AudioCapture] Destroying global capture instance", file=sys.stderr)
        _capture.stop()
        _capture = None
        print("[AudioCapture] Global capture destroyed", file=sys.stderr)
