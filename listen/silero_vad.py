"""
Silero Voice Activity Detection using ONNX Runtime.
Pure numpy implementation with CoreML support for Apple Silicon.

No PyTorch dependency - uses ONNX Runtime with CoreML Execution Provider
for hardware acceleration on Apple Neural Engine.
"""

import numpy as np
import os
from typing import Callable, Optional
import threading
import time
from pathlib import Path

# Try to import onnxruntime with CoreML support
try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False
    ort = None


class SileroVAD:
    """
    Voice Activity Detection using Silero VAD ONNX model.

    Uses ONNX Runtime with CoreML Execution Provider for
    hardware acceleration on Apple Silicon (Neural Engine).

    Model processes 512 samples (32ms at 16kHz) and returns
    speech probability 0.0-1.0.
    """

    SAMPLE_RATE = 16000
    CHUNK_SIZE = 512  # 32ms at 16kHz (Silero expects 512 for 16kHz)
    CONTEXT_SIZE = 64  # Context samples prepended to each chunk

    def __init__(
        self,
        model_path: Optional[str] = None,
        silence_timeout: float = 1.5,  # Ported from Bun: 1500ms
        speech_threshold: float = 0.5,  # Probability threshold
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[], None]] = None,
        min_speech_frames: int = 1,  # Reduced for more sensitivity
        use_coreml: bool = True,
    ):
        """
        Initialize Silero VAD with ONNX Runtime.

        Args:
            model_path: Path to silero_vad.onnx model file
            silence_timeout: Seconds of silence before speech ends (default 1.5s from Bun)
            speech_threshold: Speech probability threshold 0.0-1.0
            on_speech_start: Callback when speech starts
            on_speech_end: Callback when speech ends
            min_speech_frames: Minimum frames to confirm speech start
            use_coreml: Use CoreML EP for Apple Silicon acceleration
        """
        if not HAS_ONNX:
            raise ImportError("onnxruntime not installed. Run: pip install onnxruntime-coreml")

        self.silence_timeout = silence_timeout
        self.speech_threshold = speech_threshold
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end
        self.min_speech_frames = min_speech_frames

        # Find model path
        if model_path is None:
            model_path = self._find_model()

        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Silero VAD model not found at {model_path}. "
                "Download with: wget https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
            )

        # Initialize ONNX Runtime session
        self.session = self._create_session(model_path, use_coreml)

        # Model state (RNN hidden state)
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, self.CONTEXT_SIZE), dtype=np.float32)
        self._sr = np.array(self.SAMPLE_RATE, dtype=np.int64)

        # VAD state
        self._is_speaking = False
        self._speech_frame_count = 0
        self._last_speech_time: Optional[float] = None
        self._silence_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

        # Audio buffer for accumulating chunks
        self._audio_buffer = np.array([], dtype=np.float32)

    def _find_model(self) -> str:
        """Find the Silero VAD model file."""
        # Check common locations
        locations = [
            Path(__file__).parent / "data" / "silero_vad.onnx",
            Path(__file__).parent / "silero_vad.onnx",
            Path.home() / ".cache" / "silero_vad" / "silero_vad.onnx",
            Path("/tmp") / "silero_vad.onnx",
        ]

        for loc in locations:
            if loc.exists():
                return str(loc)

        # Default to data directory
        return str(Path(__file__).parent / "data" / "silero_vad.onnx")

    def _create_session(self, model_path: str, use_coreml: bool) -> "ort.InferenceSession":
        """Create ONNX Runtime session with appropriate providers."""
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1

        # Try CoreML first for Apple Silicon, fallback to CPU
        available_providers = ort.get_available_providers()

        if use_coreml and 'CoreMLExecutionProvider' in available_providers:
            providers = [
                ('CoreMLExecutionProvider', {
                    'MLComputeUnits': 'ALL',  # Use ANE + GPU + CPU
                }),
                'CPUExecutionProvider'
            ]
            print("[SileroVAD] Using CoreML Execution Provider (Neural Engine)")
        else:
            providers = ['CPUExecutionProvider']
            if use_coreml:
                print("[SileroVAD] CoreML not available, using CPU")
            else:
                print("[SileroVAD] Using CPU Execution Provider")

        return ort.InferenceSession(model_path, providers=providers, sess_options=opts)

    def _run_inference(self, audio_chunk: np.ndarray) -> float:
        """
        Run VAD inference on a single chunk.

        Args:
            audio_chunk: Audio data, shape (512,) float32

        Returns:
            Speech probability 0.0-1.0
        """
        # Ensure correct shape
        if audio_chunk.shape[0] != self.CHUNK_SIZE:
            raise ValueError(f"Expected {self.CHUNK_SIZE} samples, got {audio_chunk.shape[0]}")

        # Reshape to (1, chunk_size)
        x = audio_chunk.reshape(1, -1).astype(np.float32)

        # Prepend context
        x = np.concatenate([self._context, x], axis=1)

        # Run inference
        ort_inputs = {
            'input': x,
            'state': self._state,
            'sr': self._sr
        }

        out, new_state = self.session.run(None, ort_inputs)

        # Update state
        self._state = new_state
        self._context = x[:, -self.CONTEXT_SIZE:]

        # Return speech probability
        return float(out[0, 0])

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

        # Process complete chunks (512 samples = 32ms)
        while len(self._audio_buffer) >= self.CHUNK_SIZE:
            chunk = self._audio_buffer[:self.CHUNK_SIZE]
            self._audio_buffer = self._audio_buffer[self.CHUNK_SIZE:]

            # Get speech probability
            prob = self._run_inference(chunk)
            is_speech = prob >= self.speech_threshold

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

            # Reset model state
            self._state = np.zeros((2, 1, 128), dtype=np.float32)
            self._context = np.zeros((1, self.CONTEXT_SIZE), dtype=np.float32)

            if self._silence_timer:
                self._silence_timer.cancel()
                self._silence_timer = None

    @property
    def is_speaking(self) -> bool:
        """Check if speech is currently detected."""
        with self._lock:
            return self._is_speaking


# Singleton instance
_vad: Optional[SileroVAD] = None


def get_silero_vad(
    silence_timeout: float = 1.5,
    speech_threshold: float = 0.5,
    on_speech_start: Optional[Callable[[], None]] = None,
    on_speech_end: Optional[Callable[[], None]] = None,
    use_coreml: bool = True,
) -> SileroVAD:
    """Get or create the global SileroVAD instance."""
    global _vad
    if _vad is None:
        _vad = SileroVAD(
            silence_timeout=silence_timeout,
            speech_threshold=speech_threshold,
            on_speech_start=on_speech_start,
            on_speech_end=on_speech_end,
            use_coreml=use_coreml,
        )
    return _vad
