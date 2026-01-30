# Module: Installation Scripts
Last scanned: 2026-01-29T14:30:00Z
Source files: 3

## Main Installer

### install.sh - install.sh:1
Interactive installer with TTS backend selection and multiple STT modes.

#### Installation Modes
- `--tts-only` :77 - TTS only (claude-say server)
- `--parakeet` :81 - TTS + STT with Parakeet-MLX (~2.3GB model)
- `--speechanalyzer` :85 - TTS + STT with Apple SpeechAnalyzer (macOS 26+)

#### TTS Backend Selection  
- `--tts-macos` :89 - macOS built-in say command (default)
- `--tts-google` :93 - Google Cloud TTS with API key

#### Key Functions
- `check_macos_26()` :64 - Validates macOS version for SpeechAnalyzer
- `check_swift()` :70 - Validates Swift/Xcode for SpeechAnalyzer build
- `select_tts_backend()` :156 - Interactive TTS backend menu
- `setup_google_tts()` :182 - Google Cloud TTS configuration wizard
- `select_google_voice()` :206 - Google voice selection menu
- `create_env_file()` :247 - Generates ~/.mcp-claude-say/.env config

#### Installation Steps
1. Platform checks (macOS, Python 3, say command) :46-61
2. Mode selection (interactive or argument-based) :108-151  
3. TTS backend configuration :156-267
4. Source detection (local or GitHub clone) :274-289
5. File copying based on mode :297-330
6. Python venv setup and dependency installation :333-339
7. SpeechAnalyzer CLI build (if needed) :341-369
8. Claude Code skill installation :372-390
9. MCP server configuration in ~/.claude.json :393-436
10. Installation verification tests :441-472

#### Configuration Paths
- Install: `$HOME/.mcp-claude-say` :23
- Speak skill: `$HOME/.claude/skills/speak` :24  
- Conversation skill: `$HOME/.claude/skills/conversation` :25
- Claude settings: `$HOME/.claude.json` :26
- Environment: `$HOME/.mcp-claude-say/.env` :27

## Uninstaller

### uninstall.sh - uninstall.sh:1  
Complete removal with optional model cache cleanup.

#### Cleanup Options
- Keep models (faster reinstall) :42
- Remove everything including Parakeet cache (~2.3GB) :47

#### Removal Steps
1. MCP server config removal from ~/.claude.json :54-61
2. Speak skill removal :64-69
3. Conversation skill removal :71-77  
4. Installation directory removal :80-85
5. Optional cached model removal :88-99

#### Paths Cleaned
- `$HOME/.mcp-claude-say` :16 - Main installation
- `$HOME/.claude/skills/speak` :17 - Speak skill
- `$HOME/.claude/skills/conversation` :18 - Conversation skill
- `$HOME/.cache/huggingface/hub/models--mlx-community--parakeet-tdt-0.6b-v3` :20 - Parakeet cache

## Test Pipeline

### test-pipeline.sh - test-pipeline.sh:1
Development testing pipeline for clean reinstall testing.

#### Process
1. Uninstall previous installation :43-49
2. Clean temp directory (/tmp/test-install) :53-63
3. Copy source to temp (excluding .git, __pycache__) :67-81  
4. Run install.sh from temp directory :85-95

#### Configuration
- `ORIGINAL_DIR="$HOME/mcp-claude-say-original"` :24 - Development source
- `TEMP_DIR="/tmp/test-install"` :25 - Testing location

#### Mode Support
- `--tts-only` :29 - TTS only testing
- `--parakeet` :31 - Parakeet STT testing  
- `--speechanalyzer` :33 - SpeechAnalyzer STT testing

#### Usage Pattern
```bash
# From development directory
./test-pipeline.sh --parakeet
# Then restart Claude Code and test /conversation
```
