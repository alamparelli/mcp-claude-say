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

Natural-sounding voices with zero storage footprint.

**Pricing Tiers:**

| Tier | Quality | Price |
|------|---------|-------|
| Neural2 | Good | Free (1M chars/mo) |
| Studio | Better | $0.16/1M chars |
| Journey | Conversational | $0.30/1M chars |
| Chirp3-HD | Best (Gemini) | $0.30/1M chars |

**Setup:**

1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the [Text-to-Speech API](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
3. Create an API key at [APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials)

**Configure via installer (recommended):**

Run `./install.sh` and select "Google Cloud TTS" when prompted. The installer will guide you through entering your API key and selecting a voice.

**Or configure manually:**

Edit `~/.mcp-claude-say/.env`:

```bash
TTS_BACKEND=google
GOOGLE_CLOUD_API_KEY=your-api-key-here
GOOGLE_VOICE=en-US-Neural2-F
GOOGLE_LANGUAGE=en-US
```

Then restart Claude Code.

**Example Voices:**

| Voice | Tier | Description |
|-------|------|-------------|
| `en-US-Neural2-F` | Free | US female (default) |
| `en-US-Journey-O` | Paid | US female, conversational |
| `en-GB-Chirp3-HD-Erinome` | Paid | British female |
| `en-GB-Chirp3-HD-Aoede` | Paid | British female |
| `en-US-Neural2-D` | Free | US male |

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

The interactive installer will guide you through:
1. **STT backend selection** - Parakeet MLX or Apple SpeechAnalyzer
2. **TTS backend selection** - macOS say or Google Cloud TTS
3. **Google Cloud setup** (if selected) - API key and voice selection

### What the installer does

1. Creates a Python virtual environment
2. Installs dependencies (MCP, Parakeet MLX, sounddevice, pynput)
3. **Creates `~/.mcp-claude-say/.env`** with your TTS configuration
4. Installs two skills: `/speak` and `/conversation`
5. Configures both MCP servers in Claude Code settings

### Configuration File

After installation, your TTS settings are stored in `~/.mcp-claude-say/.env`:

```bash
# TTS Backend: macos, google
TTS_BACKEND=macos

# Google Cloud TTS settings (only used if TTS_BACKEND=google)
GOOGLE_CLOUD_API_KEY=your-api-key
GOOGLE_VOICE=en-US-Neural2-F
GOOGLE_LANGUAGE=en-US
```

Edit this file and restart Claude Code to change settings. See `env.template` for all options.

### CLI Options

For scripted/automated installation:

```bash
# Install with macOS TTS (default)
./install.sh --parakeet --tts-macos

# Install with Google Cloud TTS
./install.sh --parakeet --tts-google --google-api-key "YOUR_API_KEY"

# TTS only mode (no STT)
./install.sh --tts-only --tts-google
```

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

Full voice loop with automatic turn-taking:
1. Press **Right Command** to start recording
2. Speak your message
3. Recording stops automatically when you finish speaking (VAD)
4. Claude transcribes and responds vocally
5. Recording restarts automatically after Claude finishes
6. Continue the conversation naturally!

**Barge-in:** Press **Right Command** anytime to interrupt Claude mid-sentence.

Say **"fin de session"** to end the conversation.

## Push-to-Talk Keys

| Key | Description |
|-----|-------------|
| `cmd_r` | Right Command (default, recommended) |
| `cmd_l+s` | Left Command + S |
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
├── .env                   # TTS configuration (TTS_BACKEND, GOOGLE_CLOUD_API_KEY, etc.)
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

The uninstaller will ask if you want to remove cached models (Parakeet MLX ~2.3GB). Choose "Keep models" for faster reinstallation later, or "Remove everything" to free up disk space.

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

### PTT key not detected (especially in VSCode)

The PTT hotkey uses `pynput` which requires **Accessibility permissions** on macOS. Without these permissions, the keyboard listener starts successfully but never receives key events.

**To fix:**

1. Open **System Settings** → **Privacy & Security** → **Accessibility**
2. Click the **+** button (unlock with your password if needed)
3. Add your terminal application:
   - For VSCode: `/Applications/Visual Studio Code.app`
   - For Cursor: `/Applications/Cursor.app`
   - For Terminal: `/Applications/Utilities/Terminal.app`
   - For iTerm2: `/Applications/iTerm.app`
4. **Enable the checkbox** next to the app
5. **Restart the application completely** (quit and reopen)

**Still not working?**

- Try a different hotkey: `start_ptt_mode("f13")` or `start_ptt_mode("alt_r")`
- Check logs: `tail -f /tmp/claude-listen.log`
- Verify pynput works: Run a simple pynput test script outside of Claude Code

**Note:** Some keys may work without Accessibility permissions (like function keys F13-F15), but modifier keys (Cmd, Alt, Ctrl) always require permissions.

## Performance

| Metric | Value |
|--------|-------|
| STT Speed | ~60x real-time (Parakeet MLX) |
| STT RAM | ~2 GB |
| TTS Latency | < 100ms |

> **Note:** The first transcription is slow (~10-15 seconds) as the Parakeet MLX model loads into memory. Subsequent transcriptions are near-instant.

## Tested Environments

| Environment | Status | Notes |
|-------------|--------|-------|
| **Terminal** (macOS native) | ✅ Works | |
| **iTerm2** | ✅ Works | |
| **Cursor** | ⚠️ Should work | Not yet tested |
| **VSCode Terminal** + Claude Code CLI | ✅ Works | |
| **VSCode** + Claude Code GUI extension | ❌ Not working | Conversation mode not stable |

> **Help wanted!** If you test mcp-claude-say in other environments, please [open an issue](https://github.com/alamparelli/mcp-claude-say/issues) to report your results.

## Changelog

### v0.3.0 - Voice Conversation Mode (Jan 2026)

**Kokoro TTS Backend** (PR #9)
- New `kokoro` TTS backend using MLX-Audio with 54 voices across 9 languages
- Supports English, Spanish, French, Italian, Portuguese, Japanese, Chinese, Hindi
- Configure with `TTS_BACKEND=kokoro` and `KOKORO_VOICE=af_heart`

**Seamless Conversation Flow**
- **VAD auto-stop**: Recording stops automatically when you finish speaking
- **Auto-start**: Recording restarts automatically after Claude responds
- **Barge-in**: Press PTT to interrupt Claude mid-sentence
- Press PTT once to start, then conversation flows naturally

### v0.2.0 - TTS Configuration (Jan 2026)

**Installer Improvements** (PR #7)
- Interactive TTS backend selection (macOS, Google Cloud, Kokoro)
- Google Cloud TTS setup wizard with API key and voice selection
- Centralized configuration via `~/.mcp-claude-say/.env`
- Model cache cleanup option during uninstall

## License

MIT

---

**Enjoy your voice-enabled AI assistant!**
