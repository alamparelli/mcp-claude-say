#!/bin/bash
#
# mcp-claude-say installer
# One-line install: curl -sSL https://raw.githubusercontent.com/USER/mcp-claude-say/main/install.sh | bash
#
# Includes:
# - claude-say (TTS) - Text-to-Speech via macOS 'say'
# - claude-listen (STT) - Speech-to-Text with Parakeet-MLX (fast, Apple Silicon optimized)
# - Simple PTT mode - Push-to-Talk without VAD
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="$HOME/.mcp-claude-say"
SKILL_DIR="$HOME/.claude/skills/speak"
SKILL_CONVERSATION_DIR="$HOME/.claude/skills/conversation"
CLAUDE_SETTINGS="$HOME/.claude.json"
REPO_URL="https://github.com/alamparelli/mcp-claude-say.git"
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}    mcp-claude-say Installer${NC}"
echo -e "${BLUE}    TTS + STT for Claude Code (macOS)${NC}"
echo -e "${BLUE}    Simple PTT + Parakeet-MLX${NC}"
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

echo -e "${GREEN}[1/5]${NC} Creating installation directory..."

# Determine source directory (local or need to clone)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/mcp_server.py" ]]; then
    # Running from local repo
    SOURCE_DIR="$SCRIPT_DIR"
    echo -e "       Using local source: $SOURCE_DIR"
else
    # Need to clone from GitHub
    echo -e "       Cloning from GitHub..."
    if [[ -d "$INSTALL_DIR" ]]; then
        rm -rf "$INSTALL_DIR"
    fi
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" 2>/dev/null || {
        echo -e "${RED}Error: Failed to clone repository${NC}"
        echo -e "${YELLOW}If running locally, make sure install.sh is in the repo directory${NC}"
        exit 1
    }
    SOURCE_DIR="$INSTALL_DIR"
fi

# Create install directory if different from source
if [[ "$SOURCE_DIR" != "$INSTALL_DIR" ]]; then
    mkdir -p "$INSTALL_DIR"
    cp "$SOURCE_DIR/mcp_server.py" "$INSTALL_DIR/"
    cp "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/"
    # Copy listen module
    if [[ -d "$SOURCE_DIR/listen" ]]; then
        cp -r "$SOURCE_DIR/listen" "$INSTALL_DIR/"
    fi
    # Copy shared module
    if [[ -d "$SOURCE_DIR/shared" ]]; then
        cp -r "$SOURCE_DIR/shared" "$INSTALL_DIR/"
    fi
fi

echo -e "${GREEN}[2/5]${NC} Setting up Python virtual environment..."

cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo -e "${GREEN}[3/5]${NC} Installing Claude Code skills..."

# Install speak skill
mkdir -p "$SKILL_DIR"
if [[ -f "$SOURCE_DIR/skill/SKILL.md" ]]; then
    cp "$SOURCE_DIR/skill/SKILL.md" "$SKILL_DIR/"
    echo -e "       ${GREEN}Installed /speak skill${NC}"
else
    echo -e "${YELLOW}       Warning: speak SKILL.md not found${NC}"
fi

# Install conversation skill
mkdir -p "$SKILL_CONVERSATION_DIR"
if [[ -f "$SOURCE_DIR/skill/conversation/SKILL.md" ]]; then
    cp "$SOURCE_DIR/skill/conversation/SKILL.md" "$SKILL_CONVERSATION_DIR/"
    echo -e "       ${GREEN}Installed /conversation skill${NC}"
else
    echo -e "${YELLOW}       Warning: conversation SKILL.md not found${NC}"
fi

echo -e "${GREEN}[4/5]${NC} Configuring Claude Code MCP servers..."

# Create settings.json if it doesn't exist
mkdir -p "$(dirname "$CLAUDE_SETTINGS")"
if [[ ! -f "$CLAUDE_SETTINGS" ]]; then
    echo '{}' > "$CLAUDE_SETTINGS"
fi

# Check if jq is available
if command -v jq &> /dev/null; then
    # Use jq to safely modify JSON - add both claude-say and claude-listen
    TEMP_FILE=$(mktemp)
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
else
    echo -e "${YELLOW}       Warning: jq not installed, please manually add MCP config${NC}"
    echo -e "${YELLOW}       Install jq with: brew install jq${NC}"
    echo ""
    echo -e "       Add this to $CLAUDE_SETTINGS:"
    echo -e "       ${BLUE}\"mcpServers\": {"
    echo -e "         \"claude-say\": {"
    echo -e "           \"command\": \"$INSTALL_DIR/venv/bin/python\","
    echo -e "           \"args\": [\"$INSTALL_DIR/mcp_server.py\"]"
    echo -e "         },"
    echo -e "         \"claude-listen\": {"
    echo -e "           \"command\": \"$INSTALL_DIR/venv/bin/python\","
    echo -e "           \"args\": [\"-m\", \"listen.mcp_server\"],"
    echo -e "           \"cwd\": \"$INSTALL_DIR\","
    echo -e "           \"env\": { \"PYTHONPATH\": \"$INSTALL_DIR\" }"
    echo -e "         }"
    echo -e "       }${NC}"
fi

echo -e "${GREEN}[5/5]${NC} Testing installation..."

# Quick test - MCP
"$INSTALL_DIR/venv/bin/python" -c "from mcp.server.fastmcp import FastMCP; print('MCP module OK')" 2>/dev/null && {
    echo -e "       ${GREEN}MCP server ready${NC}"
} || {
    echo -e "       ${RED}MCP module import failed${NC}"
    exit 1
}

# Test say command
say -v "?" | head -1 > /dev/null 2>&1 && {
    echo -e "       ${GREEN}macOS speech synthesis ready${NC}"
}

# Test Parakeet-MLX
"$INSTALL_DIR/venv/bin/python" -c "from parakeet_mlx import from_pretrained; print('Parakeet-MLX OK')" 2>/dev/null && {
    echo -e "       ${GREEN}Parakeet-MLX ready (fast STT)${NC}"
} || {
    echo -e "${YELLOW}       Warning: parakeet-mlx not installed${NC}"
}

# Test audio capture
"$INSTALL_DIR/venv/bin/python" -c "import sounddevice; import numpy; print('Audio OK')" 2>/dev/null && {
    echo -e "       ${GREEN}Audio capture ready${NC}"
} || {
    echo -e "${YELLOW}       Warning: sounddevice may need manual installation${NC}"
}

# Test pynput (for Push-to-Talk)
"$INSTALL_DIR/venv/bin/python" -c "from pynput import keyboard; print('pynput OK')" 2>/dev/null && {
    echo -e "       ${GREEN}Push-to-Talk ready (pynput)${NC}"
} || {
    echo -e "${YELLOW}       Warning: pynput not installed - PTT mode unavailable${NC}"
}

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}    Installation complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "Installed to: ${BLUE}$INSTALL_DIR${NC}"
echo -e "Skills at:    ${BLUE}$SKILL_DIR${NC}"
echo -e "              ${BLUE}$SKILL_CONVERSATION_DIR${NC}"
echo ""
echo -e "${YELLOW}MCP Servers installed:${NC}"
echo -e "  - ${GREEN}claude-say${NC}    - Text-to-Speech (TTS)"
echo -e "  - ${GREEN}claude-listen${NC} - Speech-to-Text (STT)"
echo ""
echo -e "${YELLOW}Usage:${NC}"
echo -e "  1. Restart Claude Code (or start a new session)"
echo -e "  2. Type ${BLUE}/speak${NC} to activate voice mode (TTS only)"
echo -e "  3. Type ${BLUE}/conversation${NC} for full voice loop (TTS + STT)"
echo ""
echo -e "${YELLOW}Push-to-Talk Mode:${NC}"
echo -e "  Default key: ${BLUE}Left Cmd + S${NC} (configurable)"
echo -e "  Press once to start recording"
echo -e "  Press again to stop and transcribe"
echo ""
