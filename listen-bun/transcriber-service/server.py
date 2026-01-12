#!/usr/bin/env python3
"""
Parakeet MLX Transcriber Microservice.
Fast speech-to-text HTTP server for claude-listen-bun.
"""

import base64
import json
import struct
import numpy as np
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
import os
import sys

# Add parent directory for shared modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Configuration
HOST = os.environ.get("TRANSCRIBER_HOST", "localhost")
PORT = int(os.environ.get("TRANSCRIBER_PORT", "8765"))


class ParakeetTranscriber:
    """Parakeet MLX transcriber wrapper."""

    DEFAULT_MODEL = "mlx-community/parakeet-tdt-0.6b-v3"
    SAMPLE_RATE = 16000

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or self.DEFAULT_MODEL
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        """Load the Parakeet model."""
        try:
            from parakeet_mlx import from_pretrained

            print(f"[Transcriber] Loading model: {self.model_name}", file=sys.stderr)
            self._model = from_pretrained(self.model_name)
            print("[Transcriber] Model loaded successfully", file=sys.stderr)

        except ImportError:
            print("[Transcriber] parakeet-mlx not installed. Falling back to whisper.", file=sys.stderr)
            self._use_whisper_fallback()

    def _use_whisper_fallback(self) -> None:
        """Use faster-whisper as fallback."""
        from faster_whisper import WhisperModel

        print("[Transcriber] Loading whisper model...", file=sys.stderr)
        self._model = WhisperModel("large-v3-turbo", device="cpu", compute_type="float32")
        self._is_whisper = True
        print("[Transcriber] Whisper model loaded", file=sys.stderr)

    def transcribe(self, audio: np.ndarray) -> dict:
        """Transcribe audio to text."""
        if len(audio) == 0:
            return {"text": "", "language": "", "confidence": 0.0}

        # Ensure correct dtype
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Normalize
        if np.abs(audio).max() > 1.0:
            audio = audio / np.abs(audio).max()

        if hasattr(self, "_is_whisper") and self._is_whisper:
            return self._transcribe_whisper(audio)

        return self._transcribe_parakeet(audio)

    def _transcribe_parakeet(self, audio: np.ndarray) -> dict:
        """Transcribe using Parakeet MLX."""
        import tempfile
        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            sf.write(temp_path, audio, self.SAMPLE_RATE)
            result = self._model.transcribe(temp_path)
            text = result.text if hasattr(result, "text") else str(result)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        return {
            "text": text.strip(),
            "language": "auto",
            "confidence": 0.95,
        }

    def _transcribe_whisper(self, audio: np.ndarray) -> dict:
        """Transcribe using faster-whisper."""
        segments, info = self._model.transcribe(
            audio,
            language=None,
            beam_size=1,  # Fast mode
            vad_filter=False,
        )

        text_parts = [segment.text.strip() for segment in segments]

        return {
            "text": " ".join(text_parts).strip(),
            "language": info.language,
            "confidence": info.language_probability,
        }


# Global transcriber instance (lazy loaded)
_transcriber: Optional[ParakeetTranscriber] = None


def get_transcriber() -> ParakeetTranscriber:
    """Get or create transcriber instance."""
    global _transcriber
    if _transcriber is None:
        _transcriber = ParakeetTranscriber()
    return _transcriber


class TranscriberHandler(BaseHTTPRequestHandler):
    """HTTP request handler for transcription."""

    def log_message(self, format, *args):
        """Log to stderr."""
        print(f"[HTTP] {format % args}", file=sys.stderr)

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_error(404)

    def do_POST(self):
        """Handle POST requests."""
        if self.path == "/transcribe":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                data = json.loads(body)
                audio_b64 = data.get("audio", "")
                sample_rate = data.get("sample_rate", 16000)

                # Decode base64 audio
                audio_bytes = base64.b64decode(audio_b64)

                # Convert bytes to float32 array
                # The Bun client sends Float32Array as raw bytes
                audio = np.frombuffer(audio_bytes, dtype=np.float32)

                # Resample if needed
                if sample_rate != 16000:
                    # Simple resampling (could use librosa for better quality)
                    ratio = 16000 / sample_rate
                    audio = np.interp(
                        np.arange(0, len(audio) * ratio) / ratio,
                        np.arange(len(audio)),
                        audio,
                    ).astype(np.float32)

                # Transcribe
                transcriber = get_transcriber()
                result = transcriber.transcribe(audio)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())

            except Exception as e:
                print(f"[Error] Transcription failed: {e}", file=sys.stderr)
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_error(404)


def main():
    """Start the transcriber server."""
    print(f"[Transcriber] Starting server on {HOST}:{PORT}", file=sys.stderr)

    # Pre-load the model
    get_transcriber()

    server = HTTPServer((HOST, PORT), TranscriberHandler)
    print(f"[Transcriber] Server ready at http://{HOST}:{PORT}", file=sys.stderr)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Transcriber] Shutting down...", file=sys.stderr)
        server.shutdown()


if __name__ == "__main__":
    main()
