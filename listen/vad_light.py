"""
Lightweight Voice Activity Detection using WebRTC VAD.
Ultra-fast, C-based, no PyTorch dependency.
"""

import numpy as np
import webrtcvad
from typing import Callable, Optional, List
import threading
import time


# Default trigger words that signal end of speech
DEFAULT_TRIGGER_WORDS = [
    "stop", "terminé", "fini", "ok", "c'est tout",
    "that's it", "done", "end", "over", "go",
]


class WebRTCVAD:
    """
    Voice Activity Detection using WebRTC VAD.

    Ultra-lightweight alternative to Silero VAD.
    No PyTorch, pure C implementation.
    """

    SAMPLE_RATE = 16000
    FRAME_DURATION_MS = 30  # WebRTC VAD supports 10, 20, or 30 ms
    FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # 480 samples

    def __init__(
        self,
        silence_timeout: float = 1.5,
        speech_threshold: int = 3,  # VAD aggressiveness 0-3 (3 = most aggressive)
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[], None]] = None,
        trigger_words: Optional[List[str]] = None,
        min_speech_frames: int = 3,  # Minimum frames to confirm speech
    ):
        """
        Initialize WebRTC VAD.

        Args:
            silence_timeout: Seconds of silence before speech is considered ended
            speech_threshold: VAD aggressiveness (0-3, higher = more aggressive filtering)
            on_speech_start: Callback when speech starts
            on_speech_end: Callback when speech ends
            trigger_words: List of words that trigger immediate transcription
            min_speech_frames: Minimum consecutive speech frames to confirm speech start
        """
        self.silence_timeout = silence_timeout
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end
        self.trigger_words = trigger_words or DEFAULT_TRIGGER_WORDS
        self.min_speech_frames = min_speech_frames

        # Initialize WebRTC VAD
        self._vad = webrtcvad.Vad(speech_threshold)

        # State
        self._is_speaking = False
        self._speech_frame_count = 0
        self._last_speech_time: Optional[float] = None
        self._silence_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

        # Buffer for accumulating audio to frame size
        self._audio_buffer = np.array([], dtype=np.float32)

    def process_audio(self, audio_chunk: np.ndarray) -> bool:
        """
        Process an audio chunk and detect speech.

        Args:
            audio_chunk: Audio data (float32, 16kHz, mono)

        Returns:
            True if speech is detected in this chunk
        """
        # Accumulate audio in buffer
        self._audio_buffer = np.concatenate([self._audio_buffer, audio_chunk])

        is_speech_detected = False

        # Process complete frames
        while len(self._audio_buffer) >= self.FRAME_SIZE:
            frame = self._audio_buffer[:self.FRAME_SIZE]
            self._audio_buffer = self._audio_buffer[self.FRAME_SIZE:]

            # Convert float32 [-1, 1] to int16 for WebRTC VAD
            frame_int16 = (frame * 32767).astype(np.int16)
            frame_bytes = frame_int16.tobytes()

            # Check if frame contains speech
            try:
                is_speech = self._vad.is_speech(frame_bytes, self.SAMPLE_RATE)
            except Exception:
                is_speech = False

            if is_speech:
                is_speech_detected = True
                self._handle_speech_detected()
            else:
                self._handle_silence_detected()

        return is_speech_detected

    def _handle_speech_detected(self) -> None:
        """Handle speech detection in a frame."""
        with self._lock:
            self._last_speech_time = time.time()
            self._speech_frame_count += 1

            # Cancel silence timer
            if self._silence_timer:
                self._silence_timer.cancel()
                self._silence_timer = None

            # Confirm speech start after min_speech_frames
            if not self._is_speaking and self._speech_frame_count >= self.min_speech_frames:
                self._is_speaking = True
                if self.on_speech_start:
                    threading.Thread(target=self.on_speech_start, daemon=True).start()

    def _handle_silence_detected(self) -> None:
        """Handle silence detection in a frame."""
        with self._lock:
            # Reset speech frame count
            self._speech_frame_count = 0

            if self._is_speaking and self._last_speech_time:
                silence_duration = time.time() - self._last_speech_time

                if silence_duration >= self.silence_timeout:
                    self._trigger_speech_end()
                elif not self._silence_timer:
                    # Start timer for remaining silence
                    remaining = self.silence_timeout - silence_duration
                    self._silence_timer = threading.Timer(
                        remaining, self._check_silence_timeout
                    )
                    self._silence_timer.start()

    def _check_silence_timeout(self) -> None:
        """Called by timer to check if silence timeout reached."""
        with self._lock:
            if self._is_speaking and self._last_speech_time:
                silence_duration = time.time() - self._last_speech_time
                if silence_duration >= self.silence_timeout:
                    self._trigger_speech_end()

    def _trigger_speech_end(self) -> None:
        """Trigger speech end event."""
        self._is_speaking = False
        self._silence_timer = None
        self._speech_frame_count = 0

        if self.on_speech_end:
            threading.Thread(target=self.on_speech_end, daemon=True).start()

    def reset(self) -> None:
        """Reset VAD state."""
        with self._lock:
            self._is_speaking = False
            self._last_speech_time = None
            self._speech_frame_count = 0
            self._audio_buffer = np.array([], dtype=np.float32)
            if self._silence_timer:
                self._silence_timer.cancel()
                self._silence_timer = None

    @property
    def is_speaking(self) -> bool:
        """Check if speech is currently detected."""
        with self._lock:
            return self._is_speaking


# Singleton instance
_vad: Optional[WebRTCVAD] = None


def get_vad(
    silence_timeout: float = 1.5,
    on_speech_start: Optional[Callable[[], None]] = None,
    on_speech_end: Optional[Callable[[], None]] = None,
    trigger_words: Optional[List[str]] = None,
) -> WebRTCVAD:
    """Get or create the global WebRTCVAD instance."""
    global _vad
    if _vad is None:
        _vad = WebRTCVAD(
            silence_timeout=silence_timeout,
            on_speech_start=on_speech_start,
            on_speech_end=on_speech_end,
            trigger_words=trigger_words,
        )
    return _vad
