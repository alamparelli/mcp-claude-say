# MCP Claude-Say Project Instructions

## Overview
MCP servers for Claude Code voice interaction:
- **claude-say**: Text-to-Speech (TTS) via macOS `say` command
- **claude-listen**: Speech-to-Text (STT) with simple PTT mode

## STT Backends
- **Parakeet-MLX** (Recommended) - Downloads ~2.3GB model, excellent accuracy
- **Apple SpeechAnalyzer** (Experimental) - macOS 26+ native, no download but less reliable

## Architecture

### Listen Module (Simple PTT)
```
listen/
├── audio.py                      # Audio capture with sounddevice
├── simple_ptt.py                 # Simple PTT recorder (no VAD)
├── ptt_controller.py             # Hotkey detection with pynput
├── parakeet_transcriber.py       # STT with Parakeet-MLX (recommended)
├── speechanalyzer_transcriber.py # STT with Apple SpeechAnalyzer (experimental)
├── transcriber_base.py           # Base transcriber interface
└── mcp_server.py                 # MCP tools (4 tools only)
```

### MCP Tools (claude-listen)
| Tool | Description |
|------|-------------|
| `start_ptt_mode(key?)` | Start PTT (default: cmd_r) |
| `stop_ptt_mode()` | Stop PTT mode |
| `get_ptt_status()` | Get current status (ready/recording/transcribing) |
| `get_segment_transcription(wait?, timeout?)` | Get transcription (default timeout: 120s) |
| `interrupt_conversation(reason?)` | Stop TTS + PTT cleanly (idempotent, call on typed input) |

### Status Feedback
`get_segment_transcription()` returns status messages to help identify the current state:
- `[Ready]` - Waiting for user to start recording
- `[Recording...]` - Currently recording audio
- `[Transcribing...]` - Processing audio to text
- `[Timeout: No transcription received]` - Wait timed out
- Otherwise: The actual transcription text

## Development Workflow

**IMPORTANT: Always use test-pipeline.sh after making changes!**

```bash
cd ~/mcp-claude-say-original
bash test-pipeline.sh
```

This script:
1. Uninstalls previous installation
2. Copies source to /tmp/test-install
3. Runs install.sh
4. Verifies installation

After running, restart Claude Code to test changes.

## Key Files

| File | Purpose |
|------|---------|
| `install.sh` | Installation script |
| `uninstall.sh` | Uninstallation script |
| `test-pipeline.sh` | Development testing |
| `requirements.txt` | Python dependencies |
| `skill/conversation/SKILL.md` | /conversation skill |
| `skill/SKILL.md` | /speak skill |

## Default PTT Key
**Right Command** (`cmd_r`)

## Dependencies
- mcp>=1.0.0
- sounddevice, numpy, soundfile
- pynput
- parakeet-mlx (if using Parakeet backend)
- Swift/Xcode (if using SpeechAnalyzer backend)

## Testing
After `test-pipeline.sh`:
1. Restart Claude Code
2. Run `/conversation`
3. Press Right Command to record
4. Press again to stop and transcribe
