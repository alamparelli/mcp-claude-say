# MCP Claude-Say Project Instructions

## Overview
MCP servers for Claude Code voice interaction:
- **claude-say**: Text-to-Speech (TTS) via macOS `say` command
- **claude-listen**: Speech-to-Text (STT) with simple PTT mode and Parakeet-MLX

## Architecture

### Listen Module (Simple PTT)
```
listen/
├── audio.py              # Audio capture with sounddevice
├── simple_ptt.py         # Simple PTT recorder (no VAD)
├── ptt_controller.py     # Hotkey detection with pynput
├── parakeet_transcriber.py  # STT with Parakeet-MLX
├── transcriber_base.py   # Base transcriber interface
└── mcp_server.py         # MCP tools (4 tools only)
```

### MCP Tools (claude-listen)
| Tool | Description |
|------|-------------|
| `start_ptt_mode(key?)` | Start PTT (default: cmd_l+s) |
| `stop_ptt_mode()` | Stop PTT mode |
| `get_ptt_status()` | Get current status |
| `get_segment_transcription(wait?, timeout?)` | Get transcription |

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
**Left Command + S** (`cmd_l+s`)

## Dependencies
- mcp>=1.0.0
- sounddevice, numpy, soundfile
- parakeet-mlx
- pynput

## Testing
After `test-pipeline.sh`:
1. Restart Claude Code
2. Run `/conversation`
3. Press Left Cmd + S to record
4. Press again to stop and transcribe
