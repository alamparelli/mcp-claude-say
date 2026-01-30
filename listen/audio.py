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

from .logger import get_logger

log = get_logger("audio")


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

    # Memory optimization: limit buffer to ~10 minutes of audio max
    MAX_BUFFER_CHUNKS = 18750  # ~10 min at 16kHz with 512 block size

    def __init__(self, on_audio: Optional[Callable[[np.ndarray], None]] = None):
        """
        Initialize audio capture.

        Args:
            on_audio: Callback function called with each audio chunk
        """
        self.on_audio = on_audio
        self._stream: Optional[sd.InputStream] = None
        self._is_running = False
        self._buffer: list[np.ndarray] = []
        self._lock = threading.Lock()
        log.info("AudioCapture initialized")

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
                log.info("Stream force-closed, mic released")
        except Exception as e:
            log.error(f"Error in _force_close_stream: {e}")

    def _audio_callback(self, indata: np.ndarray, frames: int,
                        time_info: dict, status: sd.CallbackFlags) -> None:
        """Called by sounddevice for each audio block."""
        if status:
            log.warning(f"Audio callback status: {status}")

        # Copy data to avoid issues with buffer reuse
        audio_chunk = indata.copy().flatten()

        # Add to buffer with size limit (memory optimization)
        with self._lock:
            self._buffer.append(audio_chunk)
            # Trim oldest chunks if buffer exceeds max size
            if len(self._buffer) > self.MAX_BUFFER_CHUNKS:
                self._buffer = self._buffer[-self.MAX_BUFFER_CHUNKS:]

        # Call callback if set
        if self.on_audio:
            self.on_audio(audio_chunk)

    def start(self) -> None:
        """Start capturing audio from microphone."""
        if self._is_running:
            log.debug("Already running, skipping start")
            return

        log.info("Starting audio capture...")
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
            log.info("Stream started - mic is now active (orange dot)")
        except Exception as e:
            log.error(f"Failed to start stream: {e}")
            self._is_running = False
            self._force_close_stream()
            raise

    def stop(self) -> None:
        """
        Stop capturing audio and RELEASE the microphone.

        This MUST be called to turn off the macOS mic indicator.
        """
        if not self._is_running:
            log.debug("Not running, skipping stop")
            return

        log.info("Stopping audio capture...")
        self._is_running = False

        # CRITICAL: Fully close the stream to release mic
        self._force_close_stream()
        log.info("Audio capture stopped, mic released")

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
        log.info("Destroying global capture instance")
        _capture.stop()
        _capture = None
        log.info("Global capture destroyed")
