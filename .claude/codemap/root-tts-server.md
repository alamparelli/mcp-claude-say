# Module: Root TTS Server
Last scanned: 2026-01-30T14:30:00Z
Source files: 1 (mcp_server.py)

## Main Server

### FastMCP("claude-say") - mcp_server.py:98
Main TTS MCP server with multi-backend support (macOS, Kokoro MLX, Google Cloud, Chatterbox) and queue management.

#### Global State
- `speech_queue` :101 - Queue for TTS requests
- `current_process` :102 - Active macOS say process
- `current_afplay` :103 - Active Google/Kokoro TTS playback process
- `process_lock` :104 - Thread lock for process control
- `worker_thread` :105 - Background TTS processor
- `TTS_BACKEND` :109 - Backend selection from env (macos/kokoro/google/chatterbox)
- `KOKORO_VOICE` :112 - Default Kokoro voice ID
- `KOKORO_SPEED` :113 - Default Kokoro speed
- `_kokoro_tts` :126 - Lazy-loaded Kokoro instance
- `_kokoro_lock` :127 - Thread lock for Kokoro singleton

## Configuration Functions

### load_env_file() - mcp_server.py:42
Loads config from ~/.mcp-claude-say/.env without requiring python-dotenv. Parses KEY=value format.

### _configure_espeak() - mcp_server.py:23
Configures espeak-ng library path for French/multilingual phonemization on macOS.

### check_and_clear_stop_signal() - mcp_server.py:87
Checks and clears /tmp/claude-voice-stop signal file for coordination with claude-listen.

## TTS Backend Functions

### chatterbox_available() - mcp_server.py:144
Checks if Chatterbox TTS service is running with health check caching (TTL: 2 seconds).

### speak_with_chatterbox(text, blocking, voice) - mcp_server.py:166
Sends TTS request to local Chatterbox neural TTS service via HTTP endpoint.

### stop_chatterbox() - mcp_server.py:187
Stops Chatterbox playback via HTTP POST to /stop endpoint.

### google_tts_available() - mcp_server.py:200
Validates Google Cloud TTS configuration and API key presence.

### speak_with_google(text, blocking) - mcp_server.py:316
Synthesizes speech using Google Cloud TTS API, decodes audio, plays with afplay.

## Kokoro MLX Functions (NEW)

### kokoro_available() - mcp_server.py:205
Checks if Kokoro MLX TTS backend is available and configured as TTS_BACKEND.

### get_kokoro_tts() - mcp_server.py:216
Gets or creates singleton Kokoro TTS instance. Validates voice, logs initialization.

### speak_with_kokoro(text, blocking, voice) - mcp_server.py:238
Synthesizes and plays audio via Kokoro MLX. Supports voice override. Thread-safe with process_lock.

#### Features
- Validates voice against MLXAudioTTS.VOICES
- Temp file generation and cleanup
- Stop signal polling during blocking playback
- Error logging and return boolean status

### stop_kokoro() - mcp_server.py:305
Stops active Kokoro playback by terminating afplay process.

## Utility Functions

### play_ready_sound() - mcp_server.py:399
Plays macOS Pop.aiff system sound to indicate ready/listening state.

### clear_listen_segments() - mcp_server.py:409
Clears /tmp/claude-segments to prevent TTS feedback loop during recording.

### speech_worker() - mcp_server.py:420
Background thread processing TTS queue sequentially. Routes to Kokoro→Google→Chatterbox→macOS fallback chain.

#### Processing Logic
1. Dequeues TTS request (text, voice, rate, use_neural flag)
2. Checks/clears stop signal
3. Attempts Kokoro MLX if use_neural and available
4. Attempts Google Cloud if use_neural and available
5. Attempts Chatterbox if use_neural and available
6. Falls back to macOS say command
7. Polls stop signal during playback
8. Marks task complete

### ensure_worker_running() - mcp_server.py:502
Starts worker thread if not running or dead. Thread-safe via _worker_lock.

## MCP Tools

### speak(text, voice, speed) - mcp_server.py:521
Queues TTS without waiting. Detects Kokoro voice IDs and routes appropriately.

#### Voice Detection
- None or explicit "kokoro"/"google"/"chatterbox" → use neural backend
- Voice format `[a-z]f_[name]` (e.g., af_heart, ff_siwis) → identified as Kokoro
- Otherwise → macOS voice

#### Behavior
- Adds trailing silence markup for macOS voices
- Queues request with neural/macOS flag
- Returns immediately with backend name

### speak_and_wait(text, voice, speed) - mcp_server.py:546
Speaks and waits for completion. Clears segments, plays ready sound after speech finishes.

#### Additional Behavior
- Waits for speech_queue.join() before returning
- Clears /tmp/claude-segments
- Plays ready sound (Pop.aiff)
- Blocking mode, recommended for user prompts

### stop_speaking() - mcp_server.py:582
Stops current TTS across all backends and clears queue.

#### Actions
- Clears speech_queue
- Stops Chatterbox (if enabled)
- Stops Kokoro (if backend)
- Terminates afplay (Google/Kokoro)
- Terminates macOS say process
- Returns status with items cleared count

## Configuration

### Environment Variables
- `TTS_BACKEND` - Backend selection (default: macos)
  - `macos` - Native macOS say command
  - `kokoro` - Kokoro MLX (54 voices, 9 languages)
  - `google` - Google Cloud TTS (requires API key)
  - `chatterbox` - Local Chatterbox service
- `KOKORO_VOICE` - Default Kokoro voice ID (default: af_heart)
- `KOKORO_SPEED` - Default speed 0.5-2.0 (default: 1.0)
- `GOOGLE_CLOUD_API_KEY` - Google Cloud API key
- `GOOGLE_VOICE` - Google voice name (default: en-US-Neural2-F)
- `GOOGLE_LANGUAGE` - Google language code (default: en-US)
- `CHATTERBOX_URL` - Chatterbox service URL (default: http://127.0.0.1:8123)
- `PHONEMIZER_ESPEAK_LIBRARY` - espeak-ng library path for multilingual support
- `TTS_LOG_LEVEL` - Logging level (default: WARNING)

### Default Settings
- `TRAILING_SILENCE_MS` :517 - 300ms silence at end of macOS speech
- `READY_SOUND` :141 - Pop.aiff from macOS system sounds
- `HEALTH_CHECK_TTL` :138 - 2 second cache for backend health checks

## Thread Safety
- `process_lock` - Protects current_process and current_afplay
- `_worker_lock` - Protects worker_thread creation
- `_kokoro_lock` - Protects Kokoro singleton instantiation
- `_health_lock` - Protects health check cache

## Signal Files
- `/tmp/claude-voice-stop` - Stop signal for inter-process communication
- `/tmp/claude-segments` - STT recordings directory

## Backend Priority Chain
When use_neural=True, the worker attempts backends in this order:
1. Kokoro MLX (if TTS_BACKEND=kokoro)
2. Google Cloud (if API key configured)
3. Chatterbox (if enabled and available)
4. macOS say (fallback, always available)
