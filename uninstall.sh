#!/bin/bash
#
# mcp-claude-say uninstaller
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

INSTALL_DIR="$HOME/.mcp-claude-say"
SKILL_SPEAK_DIR="$HOME/.claude/skills/speak"
SKILL_CONVERSATION_DIR="$HOME/.claude/skills/conversation"
CLAUDE_SETTINGS="$HOME/.claude.json"
PARAKEET_CACHE="$HOME/.cache/huggingface/hub/models--mlx-community--parakeet-tdt-0.6b-v3"
KOKORO_CACHE="$HOME/.cache/huggingface/hub/models--prince-canuma--Kokoro-82M"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}    mcp-claude-say Uninstaller${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if models exist
PARAKEET_SIZE=""
KOKORO_SIZE=""
if [[ -d "$PARAKEET_CACHE" ]]; then
    PARAKEET_SIZE=$(du -sh "$PARAKEET_CACHE" 2>/dev/null | cut -f1)
fi
if [[ -d "$KOKORO_CACHE" ]]; then
    KOKORO_SIZE=$(du -sh "$KOKORO_CACHE" 2>/dev/null | cut -f1)
fi

# Ask about model cleanup
CLEANUP_MODELS=false
if [[ -n "$PARAKEET_SIZE" || -n "$KOKORO_SIZE" ]]; then
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  Cached Models Cleanup${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    [[ -n "$PARAKEET_SIZE" ]] && echo -e "Found Parakeet-MLX model cache: ${YELLOW}$PARAKEET_SIZE${NC}"
    [[ -n "$KOKORO_SIZE" ]] && echo -e "Found Kokoro TTS model cache:   ${YELLOW}$KOKORO_SIZE${NC}"
    echo ""
    echo -e "  ${GREEN}1)${NC} Keep models (faster reinstall later)"
    echo -e "  ${GREEN}2)${NC} Remove everything (free up disk space)"
    echo ""
    read -p "Enter choice [1-2] (default: 1): " cleanup_choice

    if [[ "$cleanup_choice" == "2" ]]; then
        CLEANUP_MODELS=true
    fi
    echo ""
fi

# Remove MCP server config from claude.json
if [[ -f "$CLAUDE_SETTINGS" ]] && command -v jq &> /dev/null; then
    echo -e "${GREEN}[1/5]${NC} Removing MCP server configuration..."
    TEMP_FILE=$(mktemp)
    jq 'del(.mcpServers["claude-say"]) | del(.mcpServers["claude-listen"])' "$CLAUDE_SETTINGS" > "$TEMP_FILE" && mv "$TEMP_FILE" "$CLAUDE_SETTINGS"
    echo -e "       Removed claude-say and claude-listen from mcpServers"
else
    echo -e "${YELLOW}[1/5]${NC} Please manually remove 'claude-say' and 'claude-listen' from mcpServers in $CLAUDE_SETTINGS"
fi

# Remove speak skill
if [[ -d "$SKILL_SPEAK_DIR" ]]; then
    echo -e "${GREEN}[2/5]${NC} Removing speak skill..."
    rm -rf "$SKILL_SPEAK_DIR"
else
    echo -e "${YELLOW}[2/5]${NC} Speak skill not found, skipping"
fi

# Remove conversation skill
if [[ -d "$SKILL_CONVERSATION_DIR" ]]; then
    echo -e "${GREEN}[3/5]${NC} Removing conversation skill..."
    rm -rf "$SKILL_CONVERSATION_DIR"
else
    echo -e "${YELLOW}[3/5]${NC} Conversation skill not found, skipping"
fi

# Remove installation directory
if [[ -d "$INSTALL_DIR" ]]; then
    echo -e "${GREEN}[4/5]${NC} Removing installation directory..."
    rm -rf "$INSTALL_DIR"
else
    echo -e "${YELLOW}[4/5]${NC} Installation directory not found, skipping"
fi

# Remove cached models if requested
if [[ "$CLEANUP_MODELS" == true ]]; then
    echo -e "${GREEN}[5/5]${NC} Removing cached models..."
    if [[ -d "$PARAKEET_CACHE" ]]; then
        rm -rf "$PARAKEET_CACHE"
        echo -e "       ${GREEN}Removed Parakeet-MLX cache ($PARAKEET_SIZE freed)${NC}"
    fi
    if [[ -d "$KOKORO_CACHE" ]]; then
        rm -rf "$KOKORO_CACHE"
        echo -e "       ${GREEN}Removed Kokoro TTS cache ($KOKORO_SIZE freed)${NC}"
    fi
else
    echo -e "${YELLOW}[5/5]${NC} Keeping cached models"
    [[ -n "$PARAKEET_SIZE" ]] && echo -e "       Parakeet-MLX cache preserved at: $PARAKEET_CACHE"
    [[ -n "$KOKORO_SIZE" ]] && echo -e "       Kokoro TTS cache preserved at: $KOKORO_CACHE"
fi

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}    Uninstallation complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "Restart Claude Code to apply changes."
echo ""
