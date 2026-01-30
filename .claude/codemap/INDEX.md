# MCP Claude-Say Codemap
Generated: 2026-01-30T14:30:00Z
Project: Voice interaction system for Claude Code (TTS + STT)

## Overview
MCP servers providing Text-to-Speech and Speech-to-Text functionality for Claude Code voice interactions on macOS. Features multi-backend TTS including new Kokoro MLX neural synthesis with 54 voices across 9 languages.

## Architecture
- **TTS Server**: claude-say (mcp_server.py) - Multi-backend text-to-speech with Kokoro MLX integration
- **Kokoro Backend**: say/mlx_audio_tts.py - Neural TTS with 54 multilingual voices
- **STT Module**: claude-listen (listen/) - Push-to-Talk speech recognition
- **Coordination**: shared/ - Inter-server communication
- **Installation**: Shell scripts for setup/teardown
- **Skills**: Claude Code skill integrations (/speak, /conversation)

## Module Index

| Module | Files | Last Scanned | Description |
|--------|-------|--------------|-------------|
| [Root TTS Server](root-tts-server.md) | 1 | 2026-01-30 | Main TTS server with Kokoro, Google, Chatterbox, macOS backends |
| [Kokoro TTS Backend](kokoro-tts-backend.md) | 2 | 2026-01-30 | Kokoro MLX neural TTS with 54 voices, 9 languages |
| [Listen STT Module](listen-stt-module.md) | 8 | 2026-01-29 | Speech-to-text with PTT control (Parakeet/SpeechAnalyzer) |
| [Shared Coordination](shared-coordination.md) | 1 | 2026-01-29 | Inter-server communication (TTS/STT synchronization) |
| [Installation Scripts](installation-scripts.md) | 3 | 2026-01-29 | Setup, teardown and testing |
| [Claude Skills](claude-skills.md) | 2 | 2026-01-30 | Voice mode integrations (/speak and /conversation) |

## Quick Reference

### Main MCP Tools

**claude-say (TTS)**:
- `speak(text, voice?, speed?)` - Queue TTS without blocking
- `speak_and_wait(text, voice?, speed?)` - Speak and wait for completion
- `stop_speaking()` - Stop current TTS and clear queue

**claude-listen (STT)**:
- `start_ptt_mode(key?)` - Start push-to-talk (default: cmd_r / Right Command)
- `stop_ptt_mode()` - Stop PTT and release microphone
- `get_ppt_status()` - Get current PTT state
- `get_segment_transcription(wait?, timeout?)` - Get user speech (default timeout: 120s)
- `interrupt_conversation(reason?)` - Stop TTS+PTT cleanly (idempotent for typed input)

### Key Classes

**TTS**:
- `FastMCP("claude-say")` - Main TTS MCP server
- `MLXAudioTTS` - Kokoro neural TTS engine (54 voices, 9 languages)

**STT**:
- `FastMCP("claude-listen")` - Main STT MCP server
- `SimplePTTRecorder` - Core recording without VAD
- `PTTController` - Global hotkey detection with pynput
- `AudioCapture` - Microphone input with sounddevice
- `BaseTranscriber` - STT engine interface
- `ParakeetTranscriber` - MLX-optimized STT (recommended, 2.3GB model)
- `SpeechAnalyzerTranscriber` - Apple native STT (experimental, macOS 26+)

**Coordination**:
- `VoiceCoordinator` - TTS/STT synchronization

### TTS Backends

| Backend | Description | Model Size | Quality | Voices |
|---------|-------------|-----------|---------|--------|
| `kokoro` | Kokoro MLX (NEW) | 82M | Excellent neural | 54 (9 languages) |
| `google` | Google Cloud TTS | N/A (cloud) | Excellent neural | Many (requires API key) |
| `chatterbox` | Local neural | 11GB | Good | Limited |
| `macos` | Built-in say | N/A (system) | Good | System voices |

### Kokoro Voice Examples (NEW)

**American English** (20 voices):
- Female: `af_heart` (default), `af_nova`, `af_bella`, `af_jessica`, etc.
- Male: `am_adam`, `am_echo`, `am_liam`, `am_michael`, etc.

**British English** (8 voices):
- Female: `bf_emma`, `bf_alice`, `bf_isabella`, `bf_lily`
- Male: `bm_daniel`, `bm_fable`, `bm_george`, `bm_lewis`

**French** (1 voice):
- `ff_siwis` - Native French female voice

**Other Languages**:
- Spanish: `ef_dora`, `em_alex`
- Italian: `if_sara`, `im_nicola`
- Portuguese: `pf_dora`, `pm_alex`
- Japanese: `jf_alpha`, `jm_kumo`
- Chinese: `zf_xiaoxiao`, `zm_yunxi`
- Hindi: `hf_alpha`, `hm_omega`

### Installation Modes

1. **TTS-only**: claude-say server only (minimal, ~10MB)
2. **Kokoro**: TTS + STT with Kokoro MLX (~2.3GB model, excellent accuracy)
3. **SpeechAnalyzer**: TTS + STT with Apple native (macOS 26+, no download, less reliable)

### Configuration

**Environment File**: `~/.mcp-claude-say/.env`

**Key Variables**:
```
TTS_BACKEND=kokoro          # or: macos (default), google, chatterbox
KOKORO_VOICE=ff_siwis       # Default voice (french example)
KOKORO_SPEED=1.0            # Speed 0.5-2.0
GOOGLE_CLOUD_API_KEY=...    # Google Cloud TTS API key
PHONEMIZER_ESPEAK_LIBRARY=... # Path to espeak-ng for multilingual
```

### Claude Skills

**`/speak` Skill**:
- One-way TTS mode - Claude speaks aloud while user types
- Three expressive modes: brief (default), brainstorming, complete
- No microphone interaction
- Supports all TTS backends and voices

**`/conversation` Skill**:
- Bidirectional voice conversation with Push-to-Talk
- User speaks → Claude responds vocally
- Simple PTT mode (press key to start/stop recording)
- Integrated TTS + STT for natural dialog loops

### Status Messages

`get_segment_transcription()` returns status to help identify state:
- `[Ready]` - Waiting for user to start recording
- `[Recording...]` - Currently recording audio
- `[Transcribing...]` - Processing audio to text
- `[Timeout: No transcription received]` - Wait timed out
- Otherwise: The actual transcription text

### Default PTT Key
**Right Command** (`cmd_r`) - Recommended, no conflicts

### Thread Safety
- `process_lock` - Protects TTS process/afplay
- `_worker_lock` - Protects speech worker thread
- `_kokoro_lock` - Protects Kokoro singleton (NEW)
- `_health_lock` - Protects backend health checks

### Signal Files
- `/tmp/claude-voice-stop` - Stop signal for inter-process communication
- `/tmp/claude-segments` - STT recordings directory

### Dependencies Summary

**Core**:
- mcp>=1.0.0
- sounddevice, numpy, soundfile
- pynput (for PTT hotkey detection)

**TTS Backends**:
- `mlx-audio` (Kokoro MLX - NEW)
- `mlx` (Apple Silicon ML framework)
- `parakeet-mlx` (Parakeet STT - recommended)

**Optional**:
- `espeak-ng` (multilingual phonemization via homebrew)
- Google Cloud SDK (for Google TTS)
- Swift/Xcode (for Apple SpeechAnalyzer)

## Recent Changes (Kokoro Integration)

### New Modules
- `kokoro-tts-backend.md` - Comprehensive Kokoro documentation
- `claude-skills.md` - Expanded skill documentation

### Updated Modules
- `root-tts-server.md` - Added Kokoro functions and configuration
- Backend priority chain: Kokoro → Google → Chatterbox → macOS
- New environment variables: TTS_BACKEND=kokoro, KOKORO_VOICE, KOKORO_SPEED

### New Functionality
- `MLXAudioTTS` class with 54 voices across 9 languages
- `kokoro_available()` - Check Kokoro availability
- `get_kokoro_tts()` - Lazy-load Kokoro singleton
- `speak_with_kokoro()` - Kokoro synthesis and playback
- `stop_kokoro()` - Stop Kokoro playback
- Voice detection logic in `speak()` and `speak_and_wait()`
- Multilingual support with espeak-ng integration

## Key Architectural Patterns

### Queue-Based TTS
- `speak()` returns immediately, queues request
- Background worker thread processes queue sequentially
- Stop signal polling during playback for responsive interruption

### Lazy Loading
- Kokoro model loads on first use, cached for performance
- Parakeet model auto-unloads after 30 minutes inactivity (2GB RAM)
- Health checks cached to avoid blocking

### Signal File Communication
- `/tmp/claude-voice-stop` - Cross-process stop signaling
- Avoids IPC complexity while supporting separate processes

### Backend Fallback Chain
When `use_neural=True`:
1. Try Kokoro MLX (if TTS_BACKEND=kokoro)
2. Try Google Cloud (if API key configured)
3. Try Chatterbox (if enabled and available)
4. Fallback to macOS `say` command (always available)

## Scanning Strategy

This codemap covers:
- All Python source files in main directories
- All MCP tool definitions and backends
- All class and function definitions with line numbers
- Voice and language specifications
- Configuration patterns and defaults
- Thread safety mechanisms
- Skill definitions and usage patterns

See individual module files for detailed symbol documentation.
