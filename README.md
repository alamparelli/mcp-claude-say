# mcp-claude-say

> **macOS only** - Uses native macOS speech synthesis and Parakeet MLX for STT

Voice interaction MCP servers for Claude Code. Includes both Text-to-Speech (TTS) and Speech-to-Text (STT) for a complete voice conversation experience.

## Features

- **Voice responses** - Claude speaks its responses aloud
- **Voice input** - Talk to Claude using Push-to-Talk (PTT)
- **Full conversation mode** - Complete voice loop with `/conversation`
- **Fast local STT** - Uses Parakeet MLX (optimized for Apple Silicon)
- **Multilingual** - Speaks and understands multiple languages
- **Lightweight** - Uses native macOS speech synthesis by default, no external APIs

## TTS Backend Options

Choose your TTS backend based on your needs:

| Backend | Quality | Storage | Latency | Free Tier |
|---------|---------|---------|---------|-----------|
| **macOS** (default) | Basic | 0 | Instant | Unlimited |
| **Google Cloud** | Good | 0 | ~0.5s | 1M chars/mo |
| **Chatterbox** | Excellent | 11GB | ~0.3s | Unlimited |

### Option 1: macOS (Default)

No setup required. Uses the native `say` command. Voice is robotic but works everywhere.

### Option 2: Google Cloud TTS (Recommended)

Natural-sounding Neural2 voices with zero storage footprint. 1M characters/month free (~10K sentences).

**Setup:**

1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the [Text-to-Speech API](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
3. Create an API key at [APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials)

**Configure:**

Add to your shell profile (`~/.zshrc` or `~/.bashrc`):

```bash
export TTS_BACKEND="google"
export GOOGLE_CLOUD_API_KEY="your-api-key-here"
# Optional: change voice (default: en-US-Neural2-F)
export GOOGLE_VOICE="en-US-Neural2-D"  # Male voice
```

Then restart Claude Code or run `source ~/.zshrc`.

**Available Voices:**

| Voice | Description |
|-------|-------------|
| `en-US-Neural2-F` | Female (default) |
| `en-US-Neural2-H` | Female, warm |
| `en-US-Neural2-D` | Male |
| `en-US-Neural2-J` | Male, casual |

See [all voices](https://cloud.google.com/text-to-speech/docs/voices) for more options.

### Option 3: Chatterbox (Local Neural TTS)

Highest quality, runs 100% locally, but requires 11GB storage for model weights.

**Setup:**

```bash
# Requires Python 3.11 (Chatterbox doesn't support 3.12+)
python3.11 -m venv ~/.mcp-claude-say/venv-tts
source ~/.mcp-claude-say/venv-tts/bin/activate
pip install chatterbox-tts uvicorn fastapi torchaudio

# Add a voice sample (5-10 seconds of clear speech, 24kHz WAV)
mkdir -p ~/.mcp-claude-say/voices
# Copy your sample to voices/female_voice.wav
```

**Configure:**

```bash
export TTS_BACKEND="chatterbox"
```

**Usage:**

The Chatterbox service must be started manually:

```bash
# Start the service (~5-10 sec to load model)
~/.mcp-claude-say/start_tts_service.sh

# Verify it's running
curl http://127.0.0.1:8123/health

# Stop when done (frees ~1.5GB RAM)
~/.mcp-claude-say/stop_tts_service.sh
```

| Factor | Impact |
|--------|--------|
| Storage | ~11GB for model weights |
| RAM | ~1.5GB when running |
| First load | 5-10 seconds |

If the service isn't running, TTS falls back to macOS `say`.

## One-Line Installation

```bash
git clone https://github.com/alamparelli/mcp-claude-say.git && cd mcp-claude-say && ./install.sh
```

Or if you've already cloned the repo:

```bash
./install.sh
```

### What the installer does

1. Creates a Python virtual environment
2. Installs dependencies (MCP, Parakeet MLX, sounddevice, pynput)
3. Installs two skills: `/speak` and `/conversation`
4. Configures both MCP servers in Claude Code settings

## Usage

After installation, restart Claude Code.

### Voice Mode (TTS only)

```
/speak
```

Claude will speak its responses aloud.

### Conversation Mode (TTS + STT)

```
/conversation
```

Full voice loop:
1. Press **Left Cmd + S** to start recording
2. Speak your message
3. Press **Left Cmd + S** again to stop
4. Claude transcribes and responds vocally
5. Repeat!

Say **"fin de session"** to end the conversation.

## Push-to-Talk Keys

| Key | Description |
|-----|-------------|
| `cmd_l+s` | Left Command + S (default) |
| `cmd_r` | Right Command (recommended for MacBooks) |
| `cmd_r+m` | Right Command + M |
| `alt_l`, `alt_r` | Option keys |
| `f13`, `f14`, `f15` | Function keys |

### MacBook Hotkey Notes

Some hotkeys don't work well on MacBooks:

| Hotkey | Issue |
|--------|-------|
| `alt_l+c` | ❌ Produces `ç` character on macOS |
| `f13`, `f14`, `f15` | ❌ MacBooks don't have these keys |
| `ctrl_r` | ❌ MacBooks don't have Right Control |
| `cmd_l+s` | ⚠️ Conflicts with Save in most apps |
| `cmd_r` | ✅ Right Command alone - no conflicts, works everywhere |

**Recommendation:** Use `cmd_r` (Right Command) for PTT on MacBooks.

## Requirements

- **macOS** (uses native `say` command + Parakeet MLX)
- **Apple Silicon** recommended for fast STT
- **Python 3.9+**
- **Claude Code** CLI

## MCP Servers

The installer configures two MCP servers:

### claude-say (TTS)

| Tool | Description |
|------|-------------|
| `speak(text, voice?, speed?)` | Queue text to speak |
| `speak_and_wait(text, voice?, speed?)` | Speak and wait for completion |
| `stop_speaking()` | Stop and clear queue |

### claude-listen (STT)

| Tool | Description |
|------|-------------|
| `start_ptt_mode(key?)` | Start Push-to-Talk mode |
| `stop_ptt_mode()` | Stop PTT mode |
| `get_ptt_status()` | Get current status |
| `get_segment_transcription()` | Get transcribed text |

## File Structure

```
~/.mcp-claude-say/
├── mcp_server.py          # TTS server
├── listen/                # STT module
│   ├── mcp_server.py      # STT server
│   ├── parakeet_transcriber.py
│   └── ptt_controller.py
├── shared/                # Coordination
└── venv/                  # Python environment

~/.claude/skills/
├── speak/                 # /speak skill
│   └── SKILL.md
└── conversation/          # /conversation skill
    └── SKILL.md
```

## Uninstallation

```bash
./uninstall.sh
```

## Troubleshooting

### No sound

```bash
# Test macOS speech
say "Hello world"
```

### STT not working

```bash
# Check Parakeet MLX
~/.mcp-claude-say/venv/bin/python -c "import parakeet_mlx; print('OK')"

# Check audio capture
~/.mcp-claude-say/venv/bin/python -c "import sounddevice; print(sounddevice.query_devices())"
```

### PTT key not detected

Make sure Claude Code (or Terminal) has Accessibility permissions in System Settings > Privacy & Security > Accessibility.

## Performance

| Metric | Value |
|--------|-------|
| STT Speed | ~60x real-time (Parakeet MLX) |
| STT RAM | ~2 GB |
| TTS Latency | < 100ms |

> **Note:** The first transcription is slow (~10-15 seconds) as the Parakeet MLX model loads into memory. Subsequent transcriptions are near-instant.

## License

MIT

---

**Enjoy your voice-enabled AI assistant!**
