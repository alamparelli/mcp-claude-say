#!/usr/bin/env python3
"""
Chatterbox TTS FastAPI Service
Provides a local HTTP API for text-to-speech using Chatterbox.
Keeps the model loaded in memory for fast inference.
Supports voice cloning from reference audio samples.
"""

import io
import os
import tempfile
import subprocess
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="Chatterbox TTS Service")

# Global model instance (loaded once at startup)
tts_model = None

# Voice samples directory
VOICES_DIR = Path(__file__).parent / "voices"
VOICES_DIR.mkdir(exist_ok=True)

class TTSRequest(BaseModel):
    text: str
    speed: float = 1.0
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

def load_model():
    """Load Chatterbox model into memory."""
    global tts_model
    if tts_model is None:
        print("Loading Chatterbox TTS model...")
        from chatterbox.tts import ChatterboxTTS
        tts_model = ChatterboxTTS.from_pretrained(device="mps")  # Apple Silicon GPU
        print("Model loaded successfully!")
    return tts_model

@app.on_event("startup")
async def startup_event():
    """Load model when service starts."""
    try:
        load_model()
    except Exception as e:
        print(f"Warning: Failed to load model at startup: {e}")
        print("Model will be loaded on first request.")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "model_loaded": tts_model is not None}

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
    """
    global tts_model

    try:
        # Ensure model is loaded
        if tts_model is None:
            load_model()

        # Get voice sample path for cloning
        voice_path = get_voice_path(request.voice)

        # Generate audio (with optional voice cloning)
        if voice_path:
            wav = tts_model.generate(request.text, audio_prompt_path=voice_path)
        else:
            wav = tts_model.generate(request.text)

        # Save to temp file and play with afplay
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            # ChatterboxTTS returns a tensor, need to save it properly
            import torchaudio
            # Ensure proper sample rate (Chatterbox uses 24kHz)
            torchaudio.save(temp_path, wav.cpu(), 24000)

        # Play the audio (blocking)
        subprocess.run(["afplay", temp_path], check=True)

        # Cleanup
        os.unlink(temp_path)

        voice_info = f" (voice: {request.voice})" if request.voice else ""
        return TTSResponse(status="ok", message=f"Speech completed{voice_info}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/speak_async", response_model=TTSResponse)
async def speak_async(request: TTSRequest):
    """
    Generate speech from text and play it without blocking.
    Returns immediately after starting playback.
    Optionally clone a voice from a reference audio sample.
    """
    global tts_model

    try:
        # Ensure model is loaded
        if tts_model is None:
            load_model()

        # Get voice sample path for cloning
        voice_path = get_voice_path(request.voice)

        # Generate audio (with optional voice cloning)
        if voice_path:
            wav = tts_model.generate(request.text, audio_prompt_path=voice_path)
        else:
            wav = tts_model.generate(request.text)

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            import torchaudio
            torchaudio.save(temp_path, wav.cpu(), 24000)

        # Play the audio (non-blocking) - cleanup handled by shell
        subprocess.Popen(
            f'afplay "{temp_path}" && rm "{temp_path}"',
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        voice_info = f" (voice: {request.voice})" if request.voice else ""
        return TTSResponse(status="ok", message=f"Speech started{voice_info}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop")
async def stop_speaking():
    """Stop any currently playing audio."""
    # Kill any running afplay processes
    subprocess.run(["pkill", "-f", "afplay"], capture_output=True)
    return {"status": "ok", "message": "Stopped"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8123, log_level="info")
