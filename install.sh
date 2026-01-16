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
REPO_URL="https://github.com/alamparelli/mcp-claude-say.git"

# Installation mode (set by menu or argument)
INSTALL_MODE=""  # tts-only, parakeet, speechanalyzer

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}    mcp-claude-say Installer${NC}"
echo -e "${BLUE}    Voice for Claude Code (macOS)${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

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

echo ""
echo -e "Installing: ${CYAN}$INSTALL_MODE${NC}"
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

# Create install directory
echo -e "${GREEN}[2/6]${NC} Setting up installation directory..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/bin"

# Copy TTS files (always needed)
cp "$SOURCE_DIR/mcp_server.py" "$INSTALL_DIR/"
cp -r "$SOURCE_DIR/shared" "$INSTALL_DIR/" 2>/dev/null || true

# Copy requirements
cp "$SOURCE_DIR/requirements-base.txt" "$INSTALL_DIR/"

# Copy STT files based on mode
if [[ "$INSTALL_MODE" != "tts-only" ]]; then
    mkdir -p "$INSTALL_DIR/listen"

    # Copy common listen files
    cp "$SOURCE_DIR/listen/__init__.py" "$INSTALL_DIR/listen/" 2>/dev/null || echo "" > "$INSTALL_DIR/listen/__init__.py"
    cp "$SOURCE_DIR/listen/audio.py" "$INSTALL_DIR/listen/"
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
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r "$REQUIREMENTS_FILE"

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

# Install skills
echo -e "${GREEN}[5/6]${NC} Installing Claude Code skills..."

# Install speak skill (always)
mkdir -p "$SKILL_DIR"
if [[ -f "$SOURCE_DIR/skill/SKILL.md" ]]; then
    cp "$SOURCE_DIR/skill/SKILL.md" "$SKILL_DIR/"
    echo -e "       ${GREEN}Installed /speak skill${NC}"
fi

# Install conversation skill (only if STT enabled)
if [[ "$INSTALL_MODE" != "tts-only" ]]; then
    mkdir -p "$SKILL_CONVERSATION_DIR"
    if [[ -f "$SOURCE_DIR/skill/conversation/SKILL.md" ]]; then
        cp "$SOURCE_DIR/skill/conversation/SKILL.md" "$SKILL_CONVERSATION_DIR/"
        echo -e "       ${GREEN}Installed /conversation skill${NC}"
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
echo -e "Mode:         ${CYAN}$INSTALL_MODE${NC}"
echo -e "Installed to: ${BLUE}$INSTALL_DIR${NC}"
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
        echo -e "  Default key: ${BLUE}Left Cmd + S${NC}"
        echo -e "  Press once to start, press again to stop"
        ;;
esac

echo ""
