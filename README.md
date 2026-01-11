# mcp-claude-say

Text-to-Speech MCP server for Claude Code on macOS. Claude speaks its responses using the native `say` command.

## Features

- **Voice responses** - Claude speaks key information aloud
- **Three expressive modes** - Brief, brainstorming, and complete
- **Queue management** - Multiple messages are queued and spoken sequentially
- **Multilingual** - Speaks in the user's language (French, English, etc.)
- **Lightweight** - Uses native macOS speech synthesis, no external APIs

## One-Line Installation

```bash
git clone https://github.com/alamparelli/mcp-claude-say.git && cd mcp-claude-say && ./install.sh
```

Or if you've already cloned the repo:

```bash
./install.sh
```

### What the installer does

1. Creates a Python virtual environment in `~/.mcp-claude-say/`
2. Installs the MCP dependency
3. Copies the skill to `~/.claude/skills/speak/`
4. Configures the MCP server in `~/.claude/settings.json`

## Usage

After installation, restart Claude Code and:

```
/speak
```

Or simply say "speak", "parle", or "voice mode" in your conversation.

### Voice Commands

| Command | Action |
|---------|--------|
| `/speak` | Activate voice mode |
| `stop` / `tais-toi` | Stop speaking immediately |
| `skip` / `next` | Skip to next message |
| `vocal off` | Disable voice mode |

### Expressive Modes

| Mode | Activation | Style |
|------|------------|-------|
| **Brief** (default) | "brief mode" / "mode bref" | 1-3 sentences, direct |
| **Brainstorming** | "brainstorming mode" | Creative, exploratory, questions |
| **Complete** | "complete mode" / "mode complet" | Detailed, structured, pedagogical |

## Requirements

- **macOS** (uses native `say` command)
- **Python 3.9+**
- **Claude Code** CLI
- **jq** (optional, for automatic config) - `brew install jq`

## Manual Configuration

If the installer couldn't configure Claude Code automatically, add this to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "claude-say": {
      "command": "/Users/YOUR_USERNAME/.mcp-claude-say/venv/bin/python",
      "args": ["/Users/YOUR_USERNAME/.mcp-claude-say/mcp_server.py"]
    }
  }
}
```

## MCP Tools

The server exposes these tools:

| Tool | Description |
|------|-------------|
| `speak(text, voice?, speed?)` | Add text to speech queue |
| `stop_speaking()` | Stop and clear queue |
| `skip()` | Skip current message |
| `list_voices()` | List available voices |
| `queue_status()` | Get queue status |

## File Structure

```
~/.mcp-claude-say/
├── mcp_server.py      # MCP server
├── requirements.txt   # Python dependencies
└── venv/              # Python virtual environment

~/.claude/skills/speak/
└── SKILL.md           # Claude skill definition
```

## Uninstallation

```bash
./uninstall.sh
```

Or manually:

```bash
rm -rf ~/.mcp-claude-say
rm -rf ~/.claude/skills/speak
# Remove "claude-say" from mcpServers in ~/.claude/settings.json
```

## Troubleshooting

### No sound

```bash
# Test macOS speech
say "Hello world"

# Check MCP server
~/.mcp-claude-say/venv/bin/python ~/.mcp-claude-say/mcp_server.py
```

### MCP not connecting

1. Restart Claude Code
2. Check `~/.claude/settings.json` has the correct paths
3. Verify the virtual environment: `~/.mcp-claude-say/venv/bin/pip list | grep mcp`

### Change voice

Use `list_voices` in Claude to see available voices, then specify in the `speak()` call:

```
speak("Hello", voice="Samantha")
```

## License

MIT

---

**Enjoy your talking AI assistant!**
