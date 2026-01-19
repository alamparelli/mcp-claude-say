#!/usr/bin/env python3
"""
Chatterbox TTS FastAPI Service
Provides a local HTTP API for text-to-speech using Chatterbox.
Keeps the model loaded in memory for fast inference.
Supports voice cloning from reference audio samples.
"""

import os
import tempfile
import subprocess
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Optional
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chatterbox-tts")

# Configuration (env-configurable)
VOICES_DIR = Path(os.getenv("VOICES_DIR", Path(__file__).parent / "voices"))
VOICES_DIR.mkdir(exist_ok=True)
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "2000"))
TTS_PORT = int(os.getenv("TTS_PORT", "8123"))

# Temp file prefix for targeted cleanup
TEMP_PREFIX = "chatterbox_tts_"

# Global model instance (loaded once at startup)
tts_model = None
model_load_error: str | None = None

# Track active playback processes for targeted stop
active_processes: list[subprocess.Popen] = []
process_lock = threading.Lock()

# Thread pool for async playback (bounded to prevent thread pile-up)
playback_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tts_playback")


class TTSRequest(BaseModel):
    text: str
    speed: float = 1.0  # Note: speed is ignored for neural TTS (uses natural pacing)
    voice: Optional[str] = None  # Name of voice sample file (without .wav extension)


class TTSResponse(BaseModel):
    status: str
    message: str


def get_voice_path(voice_name: Optional[str]) -> Optional[str]:
    """Get the path to a voice sample file."""
    if not voice_name:
        return None

    # Check in voices directory
    voice_path = VOICES_DIR / f"{voice_name}.wav"
    if voice_path.exists():
        return str(voice_path)

    # Check if it's an absolute path
    if os.path.exists(voice_name):
        return voice_name

    return None


def get_device() -> str:
    """Determine the best device for inference."""
    try:
        import torch
        if torch.backends.mps.is_available():
            return "mps"
        logger.warning("Torch MPS unavailable, falling back to CPU")
    except Exception as e:
        logger.warning(f"Torch not available ({e}), falling back to CPU")
    return "cpu"


def load_model():
    """Load Chatterbox model into memory."""
    global tts_model, model_load_error
    if tts_model is None:
        try:
            logger.info("Loading Chatterbox TTS model...")
            from chatterbox.tts import ChatterboxTTS
            device = get_device()
            logger.info(f"Using device: {device}")
            tts_model = ChatterboxTTS.from_pretrained(device=device)
            logger.info("Model loaded successfully!")
            model_load_error = None
        except Exception as e:
            model_load_error = str(e)
            raise
    return tts_model


def generate_speech(text: str, voice_path: Optional[str] = None):
    """Generate speech audio (blocking, CPU/GPU intensive)."""
    global tts_model
    if tts_model is None:
        load_model()

    if voice_path:
        return tts_model.generate(text, audio_prompt_path=voice_path)
    else:
        return tts_model.generate(text)


def play_audio_blocking(temp_path: str):
    """Play audio and clean up afterward (blocking)."""
    try:
        subprocess.run(["afplay", temp_path], check=True)
    finally:
        try:
            os.unlink(temp_path)
        except:
            pass


def play_audio_async(temp_path: str):
    """Play audio in thread pool with cleanup."""
    def _play():
        proc = None
        try:
            proc = subprocess.Popen(
                ["afplay", temp_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            with process_lock:
                active_processes.append(proc)
            try:
                proc.wait()
            except Exception:
                # Process may have been terminated by /stop
                pass
            with process_lock:
                if proc in active_processes:
                    active_processes.remove(proc)
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass

    playback_executor.submit(_play)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: load model
    try:
        load_model()
    except Exception as e:
        logger.warning(f"Failed to load model at startup: {e}")
        logger.info("Model will be loaded on first request.")
    yield
    # Shutdown: nothing to clean up


app = FastAPI(title="Chatterbox TTS Service", lifespan=lifespan)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    response = {"status": "ok", "model_loaded": tts_model is not None}
    if model_load_error:
        response["status"] = "degraded"
        response["error"] = model_load_error
    return response


@app.get("/voices")
async def list_voices():
    """List available voice samples."""
    voices = [f.stem for f in VOICES_DIR.glob("*.wav")]
    return {"voices": voices, "voices_dir": str(VOICES_DIR)}


@app.post("/speak", response_model=TTSResponse)
async def speak(request: TTSRequest):
    """
    Generate speech from text and play it immediately.
    Optionally clone a voice from a reference audio sample.

    Note: speed parameter is accepted for API compatibility but ignored
    for neural TTS (uses natural pacing).
    """
    # Input validation
    if len(request.text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Text too long. Maximum {MAX_TEXT_LENGTH} characters allowed."
        )

    try:
        # Get voice sample path for cloning
        voice_path = get_voice_path(request.voice)

        # Generate audio in thread pool to avoid blocking event loop
        wav = await run_in_threadpool(generate_speech, request.text, voice_path)

        # Save to temp file with identifiable prefix
        import torchaudio
        with tempfile.NamedTemporaryFile(
            prefix=TEMP_PREFIX, suffix=".wav", delete=False
        ) as f:
            temp_path = f.name
            torchaudio.save(temp_path, wav.cpu(), 24000)

        # Play the audio (blocking) in thread pool
        await run_in_threadpool(play_audio_blocking, temp_path)

        voice_info = f" (voice: {request.voice})" if request.voice else ""
        return TTSResponse(status="ok", message=f"Speech completed{voice_info}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Speech generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/speak_async", response_model=TTSResponse)
async def speak_async(request: TTSRequest):
    """
    Generate speech from text and play it without blocking.
    Returns immediately after starting playback.
    Optionally clone a voice from a reference audio sample.

    Note: speed parameter is accepted for API compatibility but ignored
    for neural TTS (uses natural pacing).
    """
    # Input validation
    if len(request.text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Text too long. Maximum {MAX_TEXT_LENGTH} characters allowed."
        )

    try:
        # Get voice sample path for cloning
        voice_path = get_voice_path(request.voice)

        # Generate audio in thread pool to avoid blocking event loop
        wav = await run_in_threadpool(generate_speech, request.text, voice_path)

        # Save to temp file with identifiable prefix
        import torchaudio
        with tempfile.NamedTemporaryFile(
            prefix=TEMP_PREFIX, suffix=".wav", delete=False
        ) as f:
            temp_path = f.name
            torchaudio.save(temp_path, wav.cpu(), 24000)

        # Play the audio (non-blocking) with proper cleanup
        play_audio_async(temp_path)

        voice_info = f" (voice: {request.voice})" if request.voice else ""
        return TTSResponse(status="ok", message=f"Speech started{voice_info}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Speech generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/stop")
async def stop_speaking():
    """Stop any currently playing audio spawned by this service."""
    stopped = 0
    with process_lock:
        for proc in active_processes[:]:  # Copy list to avoid mutation during iteration
            try:
                proc.terminate()
                stopped += 1
            except:
                pass
        active_processes.clear()

    # Also clean up any orphaned temp files
    try:
        import glob
        for f in glob.glob(f"/tmp/{TEMP_PREFIX}*.wav"):
            try:
                os.unlink(f)
            except:
                pass
    except:
        pass

    return {"status": "ok", "message": f"Stopped {stopped} process(es)"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=TTS_PORT, log_level="info")
