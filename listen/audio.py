"""
Audio capture module for claude-listen.
Captures audio from microphone using sounddevice.
"""

import numpy as np
import sounddevice as sd
from typing import Callable, Optional
import threading
from queue import Queue


class AudioCapture:
    """Captures audio from microphone in real-time."""

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

    def _audio_callback(self, indata: np.ndarray, frames: int,
                        time_info: dict, status: sd.CallbackFlags) -> None:
        """Called by sounddevice for each audio block."""
        if status:
            print(f"Audio status: {status}")

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
            return

        self._is_running = True
        self._buffer = []

        self._stream = sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            channels=self.CHANNELS,
            dtype=self.DTYPE,
            blocksize=self.BLOCK_SIZE,
            callback=self._audio_callback
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop capturing audio."""
        if not self._is_running:
            return

        self._is_running = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

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
