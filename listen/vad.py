"""
Voice Activity Detection module using Silero VAD.
Detects when speech starts and ends in audio stream.
Supports trigger words for immediate transcription.
"""

import numpy as np
import torch
from typing import Callable, Optional, List
import threading
import time


# Default trigger words that signal end of speech
DEFAULT_TRIGGER_WORDS = [
    "stop", "terminé", "fini", "ok", "c'est tout",
    "that's it", "done", "end", "over", "go",
]


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
        quick_check_timeout: float = 0.5,
        speech_threshold: float = 0.5,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[], None]] = None,
        on_quick_check: Optional[Callable[[], Optional[str]]] = None,
        trigger_words: Optional[List[str]] = None,
    ):
        """
        Initialize Silero VAD.

        Args:
            silence_timeout: Seconds of silence before speech is considered ended
            quick_check_timeout: Seconds before quick transcription check for trigger words
            speech_threshold: VAD probability threshold (0-1)
            on_speech_start: Callback when speech starts
            on_speech_end: Callback when speech ends (after silence_timeout)
            on_quick_check: Callback for quick transcription, returns text or None
            trigger_words: List of words that trigger immediate transcription
        """
        self.silence_timeout = silence_timeout
        self.quick_check_timeout = quick_check_timeout
        self.speech_threshold = speech_threshold
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end
        self.on_quick_check = on_quick_check
        self.trigger_words = trigger_words or DEFAULT_TRIGGER_WORDS

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
        self._quick_check_timer: Optional[threading.Timer] = None
        self._quick_check_done = False
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

                # Cancel any pending timers
                if self._silence_timer:
                    self._silence_timer.cancel()
                    self._silence_timer = None
                if self._quick_check_timer:
                    self._quick_check_timer.cancel()
                    self._quick_check_timer = None
                self._quick_check_done = False

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
                else:
                    # Start quick check timer if not done yet
                    if not self._quick_check_done and not self._quick_check_timer and \
                       silence_duration >= self.quick_check_timeout:
                        self._do_quick_check()
                    elif not self._quick_check_timer and not self._quick_check_done and \
                         silence_duration < self.quick_check_timeout:
                        # Start timer for quick check
                        remaining = self.quick_check_timeout - silence_duration
                        self._quick_check_timer = threading.Timer(
                            remaining, self._do_quick_check
                        )
                        self._quick_check_timer.start()

                    # Start silence timer if not already running
                    if not self._silence_timer:
                        remaining = self.silence_timeout - silence_duration
                        self._silence_timer = threading.Timer(
                            remaining, self._check_silence_timeout
                        )
                        self._silence_timer.start()

        return is_speech

    def _do_quick_check(self) -> None:
        """Perform quick transcription check for trigger words."""
        with self._lock:
            if not self._is_speaking or self._quick_check_done:
                return
            self._quick_check_done = True
            self._quick_check_timer = None

        # Call the quick check callback
        if self.on_quick_check:
            try:
                text = self.on_quick_check()
                if text and self._has_trigger_word(text):
                    # Trigger word found - immediately end speech
                    with self._lock:
                        if self._silence_timer:
                            self._silence_timer.cancel()
                            self._silence_timer = None
                    self._trigger_speech_end()
            except Exception:
                pass  # Ignore errors in quick check

    def _has_trigger_word(self, text: str) -> bool:
        """Check if text ends with a trigger word."""
        text_lower = text.lower().strip()
        # Remove punctuation from end
        text_clean = text_lower.rstrip(".,!?;:")

        for word in self.trigger_words:
            word_lower = word.lower()
            if text_clean.endswith(word_lower):
                return True
            # Also check last word
            words = text_clean.split()
            if words and words[-1] == word_lower:
                return True
        return False

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
            self._quick_check_done = False
            if self._silence_timer:
                self._silence_timer.cancel()
                self._silence_timer = None
            if self._quick_check_timer:
                self._quick_check_timer.cancel()
                self._quick_check_timer = None

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
    quick_check_timeout: float = 0.5,
    on_speech_start: Optional[Callable[[], None]] = None,
    on_speech_end: Optional[Callable[[], None]] = None,
    on_quick_check: Optional[Callable[[], Optional[str]]] = None,
    trigger_words: Optional[List[str]] = None,
) -> SileroVAD:
    """Get or create the global SileroVAD instance."""
    global _vad
    if _vad is None:
        _vad = SileroVAD(
            silence_timeout=silence_timeout,
            quick_check_timeout=quick_check_timeout,
            on_speech_start=on_speech_start,
            on_speech_end=on_speech_end,
            on_quick_check=on_quick_check,
            trigger_words=trigger_words,
        )
    return _vad
