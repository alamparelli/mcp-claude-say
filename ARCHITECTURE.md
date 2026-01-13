# Claude Voice - Architecture

## Overview

This repository contains two complementary MCP servers for creating a complete voice loop with Claude Code:

- **claude-say** (TTS): Speech synthesis - Claude speaks
- **claude-listen** (STT): Speech recognition - Claude listens

## Global Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code                              │
│                            ↑ ↓                                  │
├─────────────────────────────────────────────────────────────────┤
│                      MCP Protocol                               │
│                       ↑       ↓                                 │
├───────────────────────┴───────┴─────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐              ┌──────────────────┐        │
│  │   claude-listen  │   [stop]     │    claude-say    │        │
│  │      (STT)       │ ──────────→  │      (TTS)       │        │
│  │                  │              │                  │        │
│  │  - Parakeet MLX  │              │  - macOS say     │        │
│  │  - Push-to-Talk  │              │  - Queue         │        │
│  └────────┬─────────┘              └────────┬─────────┘        │
│           │                                 │                  │
│           ↓                                 ↓                  │
│      [Microphone]                      [Speakers]              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## claude-say (TTS)

### MCP Tools

| Tool | Description |
|------|-------------|
| `speak(text, voice?, speed?)` | Queue text to speak, returns immediately |
| `speak_and_wait(text, voice?, speed?)` | Speak and wait for completion |
| `stop_speaking()` | Stop immediately and clear queue |

### How it works

1. Text is added to a queue
2. Worker thread processes queue sequentially
3. Uses macOS native `say` command
4. Supports voice selection and speed control

## claude-listen (STT)

### Components

| Component | Technology | Role |
|-----------|------------|------|
| STT | Parakeet MLX | Fast transcription (Apple Silicon optimized) |
| Audio | sounddevice | Microphone capture |
| Hotkey | pynput | Global Push-to-Talk detection |

### MCP Tools

| Tool | Description |
|------|-------------|
| `start_ptt_mode(key?)` | Start PTT mode (default: `cmd_l+s`) |
| `stop_ptt_mode()` | Stop PTT mode |
| `get_ptt_status()` | Get current status |
| `get_segment_transcription(wait?, timeout?)` | Get transcribed text |

### Push-to-Talk Flow

```
1. start_ptt_mode() called
2. User presses hotkey (Left Cmd + S)
   → Recording starts
3. User presses hotkey again
   → Recording stops
   → Parakeet MLX transcribes audio
4. get_segment_transcription() returns text
5. Loop continues until stop_ptt_mode()
```

### Available PTT Keys

| Key | Description |
|-----|-------------|
| `cmd_l+s` | Left Command + S (default) |
| `cmd_r+m` | Right Command + M |
| `cmd_l`, `cmd_r` | Command keys alone |
| `alt_l`, `alt_r` | Option keys |
| `ctrl_l`, `ctrl_r` | Control keys |
| `f13`, `f14`, `f15` | Function keys |
| `space` | Space bar |

## Inter-server Coordination

When PTT recording starts, claude-listen signals claude-say to stop speaking via a shared coordination module (`shared/coordination.py`).

## Repository Structure

```
mcp-claude-say/
├── mcp_server.py              # TTS MCP server (claude-say)
├── requirements.txt           # Python dependencies
├── install.sh                 # Installation script
├── uninstall.sh               # Uninstallation script
│
├── listen/                    # STT module (claude-listen)
│   ├── __init__.py
│   ├── mcp_server.py          # STT MCP server
│   ├── simple_ptt.py          # PTT recorder
│   ├── ptt_controller.py      # Hotkey detection
│   ├── parakeet_transcriber.py # Parakeet MLX wrapper
│   ├── transcriber_base.py    # Base transcriber interface
│   └── audio.py               # Audio capture
│
├── shared/                    # Shared utilities
│   ├── __init__.py
│   └── coordination.py        # TTS ↔ STT coordination
│
└── skill/                     # Claude Code skills
    ├── SKILL.md               # /speak skill
    └── conversation/
        └── SKILL.md           # /conversation skill
```

## Installation

The `install.sh` script:

1. Creates Python virtual environment (`~/.mcp-claude-say/`)
2. Installs dependencies (mcp, parakeet-mlx, sounddevice, pynput)
3. Copies skills to `~/.claude/skills/`
4. Configures MCP servers in Claude Code settings

## Dependencies

### Python packages
- `mcp` - MCP server framework
- `parakeet-mlx` - Fast STT for Apple Silicon
- `sounddevice` - Audio capture
- `soundfile` - Audio file handling
- `numpy` - Audio processing
- `pynput` - Global hotkey detection

### System requirements
- macOS (uses native `say` command)
- Apple Silicon recommended for fast STT
- Python 3.9+
- Microphone access permission
- Accessibility permission (for global hotkeys)

## Performance

| Metric | Value |
|--------|-------|
| STT Speed | ~60x real-time |
| STT RAM | ~2 GB |
| TTS Latency | < 100ms |

## Skills

### /speak
Activates TTS-only mode. Claude speaks responses aloud.

### /conversation
Activates full voice loop (TTS + STT). Push-to-Talk for input, voice for output.

## Future Improvements

1. **Streaming TTS** - Send to TTS phrase by phrase during generation
2. **Wake word** - "Hey Claude" activation without skill
3. **Voice Activity Detection** - Optional automatic recording start/stop
