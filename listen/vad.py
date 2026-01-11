"""
Voice Activity Detection module using Silero VAD.
Detects when speech starts and ends in audio stream.
"""

import numpy as np
import torch
from typing import Callable, Optional
import threading
import time


class SileroVAD:
    """
    Voice Activity Detection using Silero VAD model.

    Detects speech in real-time audio stream and triggers callbacks
    for speech start/end events.
    """

    SAMPLE_RATE = 16000
    WINDOW_SIZE = 512  # 32ms at 16kHz - Silero expects 512 samples

    def __init__(
        self,
        silence_timeout: float = 2.0,
        speech_threshold: float = 0.5,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize Silero VAD.

        Args:
            silence_timeout: Seconds of silence before speech is considered ended
            speech_threshold: VAD probability threshold (0-1)
            on_speech_start: Callback when speech starts
            on_speech_end: Callback when speech ends (after silence_timeout)
        """
        self.silence_timeout = silence_timeout
        self.speech_threshold = speech_threshold
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end

        # Load Silero VAD model
        self._model, self._utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        self._model.eval()

        # State
        self._is_speaking = False
        self._last_speech_time: Optional[float] = None
        self._silence_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def process_audio(self, audio_chunk: np.ndarray) -> bool:
        """
        Process an audio chunk and detect speech.

        Args:
            audio_chunk: Audio data (float32, 16kHz, mono)

        Returns:
            True if speech is detected in this chunk
        """
        # Convert to tensor
        if len(audio_chunk) < self.WINDOW_SIZE:
            # Pad if too short
            audio_chunk = np.pad(audio_chunk, (0, self.WINDOW_SIZE - len(audio_chunk)))

        # Take only the window size Silero expects
        audio_tensor = torch.from_numpy(audio_chunk[:self.WINDOW_SIZE]).float()

        # Get speech probability
        with torch.no_grad():
            speech_prob = self._model(audio_tensor, self.SAMPLE_RATE).item()

        is_speech = speech_prob >= self.speech_threshold

        with self._lock:
            if is_speech:
                self._last_speech_time = time.time()

                # Cancel any pending silence timer
                if self._silence_timer:
                    self._silence_timer.cancel()
                    self._silence_timer = None

                # Trigger speech start if not already speaking
                if not self._is_speaking:
                    self._is_speaking = True
                    if self.on_speech_start:
                        # Run callback in separate thread to not block audio
                        threading.Thread(target=self.on_speech_start, daemon=True).start()

            elif self._is_speaking and self._last_speech_time:
                # Check if silence timeout reached
                silence_duration = time.time() - self._last_speech_time

                if silence_duration >= self.silence_timeout:
                    self._trigger_speech_end()
                elif not self._silence_timer:
                    # Start timer for speech end
                    remaining = self.silence_timeout - silence_duration
                    self._silence_timer = threading.Timer(
                        remaining, self._check_silence_timeout
                    )
                    self._silence_timer.start()

        return is_speech

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

        if self.on_speech_end:
            threading.Thread(target=self.on_speech_end, daemon=True).start()

    def reset(self) -> None:
        """Reset VAD state."""
        with self._lock:
            self._is_speaking = False
            self._last_speech_time = None
            if self._silence_timer:
                self._silence_timer.cancel()
                self._silence_timer = None

        # Reset model state
        self._model.reset_states()

    @property
    def is_speaking(self) -> bool:
        """Check if speech is currently detected."""
        with self._lock:
            return self._is_speaking


# Singleton instance
_vad: Optional[SileroVAD] = None


def get_vad(
    silence_timeout: float = 2.0,
    on_speech_start: Optional[Callable[[], None]] = None,
    on_speech_end: Optional[Callable[[], None]] = None,
) -> SileroVAD:
    """Get or create the global SileroVAD instance."""
    global _vad
    if _vad is None:
        _vad = SileroVAD(
            silence_timeout=silence_timeout,
            on_speech_start=on_speech_start,
            on_speech_end=on_speech_end,
        )
    return _vad
