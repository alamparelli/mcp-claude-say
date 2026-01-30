#!/bin/bash
#
# mcp-claude-say installer
# One-line install: curl -sSL https://raw.githubusercontent.com/USER/mcp-claude-say/main/install.sh | bash
#
# Installation modes:
# 1. TTS only (claude-say) - Text-to-Speech only, minimal
# 2. TTS + STT Parakeet - Full voice with Parakeet-MLX (~2.3GB model)
# 3. TTS + STT SpeechAnalyzer - Full voice with Apple native (macOS 26+, 0 extra)
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="$HOME/.mcp-claude-say"
SKILL_DIR="$HOME/.claude/skills/speak"
SKILL_CONVERSATION_DIR="$HOME/.claude/skills/conversation"
CLAUDE_SETTINGS="$HOME/.claude.json"
ENV_FILE="$INSTALL_DIR/.env"
REPO_URL="https://github.com/alamparelli/mcp-claude-say.git"

# Installation mode (set by menu or argument)
INSTALL_MODE=""  # tts-only, parakeet, speechanalyzer

# TTS configuration (set by menu)
TTS_BACKEND="macos"
GOOGLE_API_KEY=""
GOOGLE_VOICE="en-US-Neural2-F"
GOOGLE_LANGUAGE="en-US"
KOKORO_VOICE="af_heart"
KOKORO_SPEED="1.0"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}    mcp-claude-say Installer${NC}"
echo -e "${BLUE}    Voice for Claude Code (macOS)${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if already installed
UPDATE_MODE=false
if [[ -d "$INSTALL_DIR" && -f "$INSTALL_DIR/mcp_server.py" ]]; then
    echo -e "${YELLOW}mcp-claude-say is already installed.${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC} Update (keep settings, refresh code)"
    echo -e "  ${GREEN}2)${NC} Fresh install (remove everything and reinstall)"
    echo -e "  ${GREEN}3)${NC} Cancel"
    echo ""
    read -p "Enter choice [1-3]: " update_choice

    case $update_choice in
        1)
            UPDATE_MODE=true
            # Load existing settings
            if [[ -f "$ENV_FILE" ]]; then
                source "$ENV_FILE" 2>/dev/null || true
                echo -e "${GREEN}Loaded existing configuration${NC}"
            fi
            ;;
        2)
            echo -e "${YELLOW}Removing existing installation...${NC}"
            rm -rf "$INSTALL_DIR"
            ;;
        3)
            echo -e "Installation cancelled."
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac
    echo ""
fi

# Check macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}Error: This tool only works on macOS${NC}"
    exit 1
fi

# Check if 'say' command exists
if ! command -v say &> /dev/null; then
    echo -e "${RED}Error: 'say' command not found. Are you on macOS?${NC}"
    exit 1
fi

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required${NC}"
    exit 1
fi

# Check macOS version for SpeechAnalyzer
check_macos_26() {
    local version=$(sw_vers -productVersion 2>/dev/null | cut -d. -f1)
    [[ "$version" -ge 26 ]] && return 0 || return 1
}

# Check Swift for SpeechAnalyzer
check_swift() {
    command -v swift &> /dev/null && return 0 || return 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --tts-only)
            INSTALL_MODE="tts-only"
            shift
            ;;
        --parakeet)
            INSTALL_MODE="parakeet"
            shift
            ;;
        --speechanalyzer)
            INSTALL_MODE="speechanalyzer"
            shift
            ;;
        --tts-macos)
            TTS_BACKEND="macos"
            shift
            ;;
        --tts-google)
            TTS_BACKEND="google"
            shift
            ;;
        --tts-kokoro)
            TTS_BACKEND="kokoro"
            shift
            ;;
        --kokoro-voice)
            KOKORO_VOICE="$2"
            shift 2
            ;;
        --google-api-key)
            GOOGLE_API_KEY="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Interactive menu if no mode specified
if [[ -z "$INSTALL_MODE" ]]; then
    echo -e "${CYAN}Select installation mode:${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC} TTS only (claude-say)"
    echo -e "     ${YELLOW}Minimal - Text-to-Speech only${NC}"
    echo ""
    echo -e "  ${GREEN}2)${NC} TTS + STT with Parakeet-MLX ${GREEN}(Recommended)${NC}"
    echo -e "     ${YELLOW}Full voice - Downloads ~2.3GB model on first use${NC}"
    echo ""

    if check_macos_26; then
        echo -e "  ${GREEN}3)${NC} TTS + STT with Apple SpeechAnalyzer"
        echo -e "     ${YELLOW}Full voice - Uses macOS 26 native STT, no extra download (experimental)${NC}"
        echo ""
    else
        echo -e "  ${RED}3)${NC} TTS + STT with Apple SpeechAnalyzer"
        echo -e "     ${RED}Requires macOS 26+ (you have $(sw_vers -productVersion))${NC}"
        echo ""
    fi

    read -p "Enter choice [1-3]: " choice

    case $choice in
        1)
            INSTALL_MODE="tts-only"
            ;;
        2)
            INSTALL_MODE="parakeet"
            ;;
        3)
            if check_macos_26; then
                INSTALL_MODE="speechanalyzer"
            else
                echo -e "${RED}Error: macOS 26+ required for SpeechAnalyzer${NC}"
                exit 1
            fi
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac
fi

# ============================================
# TTS Backend Selection
# ============================================
select_tts_backend() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  Select TTS Backend${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC} macOS say ${GREEN}(default)${NC}"
    echo -e "     ${YELLOW}Native, instant, unlimited, offline${NC}"
    echo ""
    echo -e "  ${GREEN}2)${NC} Kokoro MLX ${GREEN}(Recommended for Apple Silicon)${NC}"
    echo -e "     ${YELLOW}54 voices, 9 languages (EN/FR/ES/IT/PT/JA/ZH/HI), neural quality${NC}"
    echo -e "     ${YELLOW}~500MB model, runs locally on M1/M2/M3${NC}"
    echo ""
    echo -e "  ${GREEN}3)${NC} Google Cloud TTS"
    echo -e "     ${YELLOW}Neural voices, ~0.5s latency, free tier 1M chars/month${NC}"
    echo ""
    read -p "Enter choice [1-3] (default: 1): " tts_choice

    case $tts_choice in
        2)
            TTS_BACKEND="kokoro"
            setup_kokoro_tts
            ;;
        3)
            TTS_BACKEND="google"
            setup_google_tts
            ;;
        *)
            TTS_BACKEND="macos"
            ;;
    esac
}

# Kokoro MLX TTS setup wizard
setup_kokoro_tts() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  Kokoro TTS Voice Selection${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}Languages: American EN, British EN, French, Spanish, Italian,${NC}"
    echo -e "${YELLOW}           Portuguese, Japanese, Chinese, Hindi${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC} af_heart - Heart (American Female) ${GREEN}(default)${NC}"
    echo -e "  ${GREEN}2)${NC} am_adam - Adam (American Male)"
    echo -e "  ${GREEN}3)${NC} bf_emma - Emma (British Female)"
    echo -e "  ${GREEN}4)${NC} bm_george - George (British Male)"
    echo -e "  ${GREEN}5)${NC} ff_siwis - Siwis (French Female)"
    echo -e "  ${GREEN}6)${NC} ef_dora - Dora (Spanish Female)"
    echo -e "  ${GREEN}7)${NC} if_sara - Sara (Italian Female)"
    echo -e "  ${GREEN}8)${NC} jf_alpha - Alpha (Japanese Female)"
    echo -e "  ${GREEN}9)${NC} zf_xiaoxiao - Xiaoxiao (Chinese Female)"
    echo -e "  ${GREEN}0)${NC} Other (enter voice ID manually)"
    echo ""
    echo -e "Full list: https://github.com/Blaizzy/mlx-audio"
    echo ""
    read -p "Enter choice [0-9] (default: 1): " voice_choice

    case $voice_choice in
        2) KOKORO_VOICE="am_adam" ;;
        3) KOKORO_VOICE="bf_emma" ;;
        4) KOKORO_VOICE="bm_george" ;;
        5) KOKORO_VOICE="ff_siwis" ;;
        6) KOKORO_VOICE="ef_dora" ;;
        7) KOKORO_VOICE="if_sara" ;;
        8) KOKORO_VOICE="jf_alpha" ;;
        9) KOKORO_VOICE="zf_xiaoxiao" ;;
        0)
            read -p "Enter Kokoro voice ID (e.g., af_nova, pm_alex): " custom_voice
            if [[ -n "$custom_voice" ]]; then
                KOKORO_VOICE="$custom_voice"
            fi
            ;;
        *) KOKORO_VOICE="af_heart" ;;
    esac

    echo ""
    echo -e "Selected voice: ${CYAN}$KOKORO_VOICE${NC}"
    echo ""
    echo -e "${YELLOW}Note: The Kokoro model (~500MB) will download on first use.${NC}"
}

# Google Cloud TTS setup wizard
setup_google_tts() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  Google Cloud TTS Setup${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "To get your free API key:"
    echo -e "  1. Go to: ${BLUE}https://console.cloud.google.com${NC}"
    echo -e "  2. Enable: ${YELLOW}Cloud Text-to-Speech API${NC}"
    echo -e "  3. Create: ${YELLOW}API key in Credentials${NC}"
    echo ""
    echo -e "Free tier: ${GREEN}1M chars/month${NC} (~150h conversation)"
    echo ""
    read -p "Enter API key (or Enter to skip and configure later): " api_key

    if [[ -n "$api_key" ]]; then
        GOOGLE_API_KEY="$api_key"
        select_google_voice
    else
        echo -e "${YELLOW}Note: Configure API key later in ~/.mcp-claude-say/.env${NC}"
    fi
}

# Google voice selection
select_google_voice() {
    echo ""
    echo -e "${CYAN}Select voice:${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC} English US - Neural2-F (female) ${GREEN}(default)${NC}"
    echo -e "  ${GREEN}2)${NC} English US - Neural2-D (male)"
    echo -e "  ${GREEN}3)${NC} French - Neural2-A (female)"
    echo -e "  ${GREEN}4)${NC} French - Neural2-B (male)"
    echo -e "  ${GREEN}5)${NC} Spanish - Neural2-A (female)"
    echo -e "  ${GREEN}6)${NC} Other (configure manually in .env)"
    echo ""
    read -p "Enter choice [1-6] (default: 1): " voice_choice

    case $voice_choice in
        2)
            GOOGLE_VOICE="en-US-Neural2-D"
            GOOGLE_LANGUAGE="en-US"
            ;;
        3)
            GOOGLE_VOICE="fr-FR-Neural2-A"
            GOOGLE_LANGUAGE="fr-FR"
            ;;
        4)
            GOOGLE_VOICE="fr-FR-Neural2-B"
            GOOGLE_LANGUAGE="fr-FR"
            ;;
        5)
            GOOGLE_VOICE="es-ES-Neural2-A"
            GOOGLE_LANGUAGE="es-ES"
            ;;
        6)
            echo -e "${YELLOW}Edit ~/.mcp-claude-say/.env to set GOOGLE_VOICE and GOOGLE_LANGUAGE${NC}"
            ;;
        *)
            GOOGLE_VOICE="en-US-Neural2-F"
            GOOGLE_LANGUAGE="en-US"
            ;;
    esac
}

# Create .env configuration file
create_env_file() {
    mkdir -p "$INSTALL_DIR"

    # Detect espeak library path for French/multilingual
    ESPEAK_LIB=""
    if [[ -f "/opt/homebrew/lib/libespeak-ng.dylib" ]]; then
        ESPEAK_LIB="/opt/homebrew/lib/libespeak-ng.dylib"
    elif [[ -f "/usr/local/lib/libespeak-ng.dylib" ]]; then
        ESPEAK_LIB="/usr/local/lib/libespeak-ng.dylib"
    fi

    cat > "$ENV_FILE" << EOF
# mcp-claude-say Configuration
# Generated by installer on $(date +%Y-%m-%d)

# TTS Backend: macos, kokoro, google
TTS_BACKEND=$TTS_BACKEND

# Kokoro MLX TTS settings (only used if TTS_BACKEND=kokoro)
# Voice IDs: af_heart, am_adam, bf_emma, ff_siwis, ef_dora, if_sara, jf_alpha, zf_xiaoxiao, etc.
# Full list: https://github.com/Blaizzy/mlx-audio
KOKORO_VOICE=$KOKORO_VOICE
KOKORO_SPEED=$KOKORO_SPEED

# espeak library for French/multilingual phonemization (auto-detected)
PHONEMIZER_ESPEAK_LIBRARY=$ESPEAK_LIB

# Google Cloud TTS settings (only used if TTS_BACKEND=google)
GOOGLE_CLOUD_API_KEY=$GOOGLE_API_KEY
GOOGLE_VOICE=$GOOGLE_VOICE
GOOGLE_LANGUAGE=$GOOGLE_LANGUAGE
EOF
    echo -e "       ${GREEN}Created config: $ENV_FILE${NC}"
}

# Run TTS backend selection if not set via arguments (skip if updating)
if [[ "$UPDATE_MODE" == false && "$TTS_BACKEND" == "macos" && -z "$GOOGLE_API_KEY" ]]; then
    select_tts_backend
fi

echo ""
echo -e "Installing: ${CYAN}$INSTALL_MODE${NC} with TTS backend: ${CYAN}$TTS_BACKEND${NC}"
echo ""

# Determine source directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/mcp_server.py" ]]; then
    SOURCE_DIR="$SCRIPT_DIR"
    echo -e "${GREEN}[1/6]${NC} Using local source: $SOURCE_DIR"
else
    echo -e "${GREEN}[1/6]${NC} Cloning from GitHub..."
    if [[ -d "$INSTALL_DIR" ]]; then
        rm -rf "$INSTALL_DIR"
    fi
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" 2>/dev/null || {
        echo -e "${RED}Error: Failed to clone repository${NC}"
        exit 1
    }
    SOURCE_DIR="$INSTALL_DIR"
fi

# Create install directory and config
echo -e "${GREEN}[2/6]${NC} Setting up installation directory..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/bin"
create_env_file

# Copy TTS files (always needed)
cp "$SOURCE_DIR/mcp_server.py" "$INSTALL_DIR/"
cp -r "$SOURCE_DIR/shared" "$INSTALL_DIR/" 2>/dev/null || true
cp -r "$SOURCE_DIR/say" "$INSTALL_DIR/" 2>/dev/null || true

# Copy requirements
cp "$SOURCE_DIR/requirements-base.txt" "$INSTALL_DIR/"
cp "$SOURCE_DIR/requirements-mlx-audio.txt" "$INSTALL_DIR/" 2>/dev/null || true

# Copy STT files based on mode
if [[ "$INSTALL_MODE" != "tts-only" ]]; then
    mkdir -p "$INSTALL_DIR/listen"

    # Copy common listen files
    cp "$SOURCE_DIR/listen/__init__.py" "$INSTALL_DIR/listen/" 2>/dev/null || echo "" > "$INSTALL_DIR/listen/__init__.py"
    cp "$SOURCE_DIR/listen/audio.py" "$INSTALL_DIR/listen/"
    cp "$SOURCE_DIR/listen/logger.py" "$INSTALL_DIR/listen/"
    cp "$SOURCE_DIR/listen/simple_ptt.py" "$INSTALL_DIR/listen/"
    cp "$SOURCE_DIR/listen/ptt_controller.py" "$INSTALL_DIR/listen/"
    cp "$SOURCE_DIR/listen/transcriber_base.py" "$INSTALL_DIR/listen/"
    cp "$SOURCE_DIR/listen/mcp_server.py" "$INSTALL_DIR/listen/"

    if [[ "$INSTALL_MODE" == "parakeet" ]]; then
        # Copy Parakeet transcriber only
        cp "$SOURCE_DIR/listen/parakeet_transcriber.py" "$INSTALL_DIR/listen/"
        cp "$SOURCE_DIR/requirements-parakeet.txt" "$INSTALL_DIR/"
        REQUIREMENTS_FILE="requirements-parakeet.txt"
    else
        # Copy SpeechAnalyzer transcriber only
        cp "$SOURCE_DIR/listen/speechanalyzer_transcriber.py" "$INSTALL_DIR/listen/"
        cp "$SOURCE_DIR/requirements-speechanalyzer.txt" "$INSTALL_DIR/"
        REQUIREMENTS_FILE="requirements-speechanalyzer.txt"
    fi
else
    # TTS only - just base requirements
    REQUIREMENTS_FILE="requirements-base.txt"
fi

# Setup Python virtual environment
echo -e "${GREEN}[3/6]${NC} Setting up Python virtual environment..."
cd "$INSTALL_DIR"

# Create venv if not exists or not in update mode
if [[ ! -d "venv" ]] || [[ "$UPDATE_MODE" == false ]]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r "$REQUIREMENTS_FILE"

# Install mlx-audio if Kokoro backend is selected
if [[ "$TTS_BACKEND" == "kokoro" ]]; then
    echo -e "       ${CYAN}Installing mlx-audio + dependencies for Kokoro TTS...${NC}"

    # Install espeak-ng for non-English phonemization (French, etc.)
    if ! command -v espeak-ng &> /dev/null; then
        echo -e "       ${CYAN}Installing espeak-ng (required for French/multilingual)...${NC}"
        brew install espeak-ng 2>/dev/null || echo -e "       ${YELLOW}Warning: Install espeak-ng manually for French support${NC}"
    fi

    # Create espeak symlink if needed (phonemizer looks for 'espeak')
    if command -v espeak-ng &> /dev/null && ! command -v espeak &> /dev/null; then
        sudo ln -sf "$(which espeak-ng)" /usr/local/bin/espeak 2>/dev/null || true
    fi

    pip install --quiet -r "$INSTALL_DIR/requirements-mlx-audio.txt"
fi

# Build SpeechAnalyzer CLI if needed
if [[ "$INSTALL_MODE" == "speechanalyzer" ]]; then
    echo -e "${GREEN}[4/6]${NC} Building SpeechAnalyzer CLI..."

    if ! check_swift; then
        echo -e "${RED}Error: Swift not found. Install Xcode Command Line Tools.${NC}"
        exit 1
    fi

    # Copy Swift source
    cp -r "$SOURCE_DIR/speechanalyzer-cli" "$INSTALL_DIR/"

    # Build
    cd "$INSTALL_DIR/speechanalyzer-cli"
    swift build -c release 2>&1 | grep -v "^Build" || true

    # Copy binary
    cp ".build/release/apple-speechanalyzer-cli" "$INSTALL_DIR/bin/"

    if [[ -f "$INSTALL_DIR/bin/apple-speechanalyzer-cli" ]]; then
        echo -e "       ${GREEN}SpeechAnalyzer CLI built successfully${NC}"
    else
        echo -e "${RED}Error: Failed to build SpeechAnalyzer CLI${NC}"
        exit 1
    fi

    cd "$INSTALL_DIR"
else
    echo -e "${GREEN}[4/6]${NC} Skipping SpeechAnalyzer CLI (not needed)"
fi

# Install skills (symlinked so updates auto-propagate)
echo -e "${GREEN}[5/6]${NC} Installing Claude Code skills..."

# Install speak skill (always)
mkdir -p "$SKILL_DIR"
if [[ -f "$SOURCE_DIR/skill/SKILL.md" ]]; then
    ln -sf "$SOURCE_DIR/skill/SKILL.md" "$SKILL_DIR/SKILL.md"
    echo -e "       ${GREEN}Installed /speak skill (symlinked)${NC}"
fi

# Install conversation skill (only if STT enabled)
if [[ "$INSTALL_MODE" != "tts-only" ]]; then
    mkdir -p "$SKILL_CONVERSATION_DIR"
    if [[ -f "$SOURCE_DIR/skill/conversation/SKILL.md" ]]; then
        ln -sf "$SOURCE_DIR/skill/conversation/SKILL.md" "$SKILL_CONVERSATION_DIR/SKILL.md"
        echo -e "       ${GREEN}Installed /conversation skill (symlinked)${NC}"
    fi
else
    echo -e "       ${YELLOW}Skipping /conversation skill (TTS only mode)${NC}"
fi

# Configure MCP servers
echo -e "${GREEN}[6/6]${NC} Configuring Claude Code MCP servers..."

mkdir -p "$(dirname "$CLAUDE_SETTINGS")"
if [[ ! -f "$CLAUDE_SETTINGS" ]]; then
    echo '{}' > "$CLAUDE_SETTINGS"
fi

if command -v jq &> /dev/null; then
    TEMP_FILE=$(mktemp)

    if [[ "$INSTALL_MODE" == "tts-only" ]]; then
        # TTS only - just claude-say
        jq --arg dir "$INSTALL_DIR" '
            .mcpServers["claude-say"] = {
                "type": "stdio",
                "command": ($dir + "/venv/bin/python"),
                "args": [($dir + "/mcp_server.py")],
                "env": {}
            }
        ' "$CLAUDE_SETTINGS" > "$TEMP_FILE" && mv "$TEMP_FILE" "$CLAUDE_SETTINGS"
    else
        # Full - claude-say + claude-listen
        jq --arg dir "$INSTALL_DIR" '
            .mcpServers["claude-say"] = {
                "type": "stdio",
                "command": ($dir + "/venv/bin/python"),
                "args": [($dir + "/mcp_server.py")],
                "env": {}
            } |
            .mcpServers["claude-listen"] = {
                "type": "stdio",
                "command": ($dir + "/venv/bin/python"),
                "args": ["-m", "listen.mcp_server"],
                "cwd": $dir,
                "env": {
                    "PYTHONPATH": $dir
                }
            }
        ' "$CLAUDE_SETTINGS" > "$TEMP_FILE" && mv "$TEMP_FILE" "$CLAUDE_SETTINGS"
    fi
else
    echo -e "${YELLOW}       Warning: jq not installed, please manually configure MCP${NC}"
    echo -e "${YELLOW}       Install jq with: brew install jq${NC}"
fi

# Final tests
echo ""
echo -e "${CYAN}Testing installation...${NC}"

# Test MCP
"$INSTALL_DIR/venv/bin/python" -c "from mcp.server.fastmcp import FastMCP; print('OK')" 2>/dev/null && {
    echo -e "  ${GREEN}✓${NC} MCP server ready"
} || {
    echo -e "  ${RED}✗${NC} MCP module failed"
}

# Test say
say -v "?" | head -1 > /dev/null 2>&1 && {
    echo -e "  ${GREEN}✓${NC} macOS speech synthesis ready"
}

if [[ "$INSTALL_MODE" == "parakeet" ]]; then
    "$INSTALL_DIR/venv/bin/python" -c "from parakeet_mlx import from_pretrained; print('OK')" 2>/dev/null && {
        echo -e "  ${GREEN}✓${NC} Parakeet-MLX ready"
    } || {
        echo -e "  ${YELLOW}!${NC} Parakeet-MLX will download on first use (~2.3GB)"
    }
fi

if [[ "$TTS_BACKEND" == "kokoro" ]]; then
    "$INSTALL_DIR/venv/bin/python" -c "from mlx_audio.tts.utils import load_model; print('OK')" 2>/dev/null && {
        echo -e "  ${GREEN}✓${NC} Kokoro MLX TTS ready (voice: $KOKORO_VOICE)"
    } || {
        echo -e "  ${YELLOW}!${NC} Kokoro model will download on first use (~500MB)"
    }
fi

if [[ "$INSTALL_MODE" == "speechanalyzer" ]]; then
    [[ -x "$INSTALL_DIR/bin/apple-speechanalyzer-cli" ]] && {
        echo -e "  ${GREEN}✓${NC} SpeechAnalyzer CLI ready"
    }
fi

if [[ "$INSTALL_MODE" != "tts-only" ]]; then
    "$INSTALL_DIR/venv/bin/python" -c "import sounddevice; import pynput; print('OK')" 2>/dev/null && {
        echo -e "  ${GREEN}✓${NC} Audio capture & PTT ready"
    }
fi

# Summary
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}    Installation complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "STT Mode:     ${CYAN}$INSTALL_MODE${NC}"
echo -e "TTS Backend:  ${CYAN}$TTS_BACKEND${NC}"
if [[ "$TTS_BACKEND" == "kokoro" ]]; then
    echo -e "Voice:        ${CYAN}$KOKORO_VOICE${NC}"
    echo -e "${YELLOW}              (Model downloads on first use ~500MB)${NC}"
elif [[ "$TTS_BACKEND" == "google" ]]; then
    echo -e "Voice:        ${CYAN}$GOOGLE_VOICE${NC}"
    if [[ -z "$GOOGLE_API_KEY" ]]; then
        echo -e "${YELLOW}              (API key not configured - will fallback to macOS)${NC}"
    fi
fi
echo -e "Installed to: ${BLUE}$INSTALL_DIR${NC}"
echo -e "Config file:  ${BLUE}$ENV_FILE${NC}"
echo ""

case $INSTALL_MODE in
    tts-only)
        echo -e "${YELLOW}MCP Servers:${NC}"
        echo -e "  - ${GREEN}claude-say${NC} - Text-to-Speech"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo -e "  1. Restart Claude Code"
        echo -e "  2. Type ${BLUE}/speak${NC} to activate voice mode"
        ;;
    parakeet|speechanalyzer)
        echo -e "${YELLOW}MCP Servers:${NC}"
        echo -e "  - ${GREEN}claude-say${NC}    - Text-to-Speech"
        echo -e "  - ${GREEN}claude-listen${NC} - Speech-to-Text ($INSTALL_MODE)"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo -e "  1. Restart Claude Code"
        echo -e "  2. Type ${BLUE}/speak${NC} for TTS only"
        echo -e "  3. Type ${BLUE}/conversation${NC} for full voice loop"
        echo ""
        echo -e "${YELLOW}Push-to-Talk:${NC}"
        echo -e "  Default key: ${BLUE}Right Command${NC}"
        echo -e "  Press once to start, press again to stop"
        ;;
esac

echo ""
echo -e "${YELLOW}To change TTS settings:${NC} edit ${BLUE}$ENV_FILE${NC} then restart Claude Code"
echo ""
