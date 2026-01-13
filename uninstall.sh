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
NC='\033[0m'

INSTALL_DIR="$HOME/.mcp-claude-say"
SKILL_SPEAK_DIR="$HOME/.claude/skills/speak"
SKILL_CONVERSATION_DIR="$HOME/.claude/skills/conversation"
CLAUDE_SETTINGS="$HOME/.claude.json"

echo -e "${BLUE}mcp-claude-say Uninstaller${NC}"
echo ""

# Remove MCP server config from claude.json
if [[ -f "$CLAUDE_SETTINGS" ]] && command -v jq &> /dev/null; then
    echo -e "${GREEN}[1/4]${NC} Removing MCP server configuration..."
    TEMP_FILE=$(mktemp)
    jq 'del(.mcpServers["claude-say"]) | del(.mcpServers["claude-listen"])' "$CLAUDE_SETTINGS" > "$TEMP_FILE" && mv "$TEMP_FILE" "$CLAUDE_SETTINGS"
    echo -e "       Removed claude-say and claude-listen from mcpServers"
else
    echo -e "${YELLOW}[1/4]${NC} Please manually remove 'claude-say' and 'claude-listen' from mcpServers in $CLAUDE_SETTINGS"
fi

# Remove speak skill
if [[ -d "$SKILL_SPEAK_DIR" ]]; then
    echo -e "${GREEN}[2/4]${NC} Removing speak skill..."
    rm -rf "$SKILL_SPEAK_DIR"
else
    echo -e "${YELLOW}[2/4]${NC} Speak skill not found, skipping"
fi

# Remove conversation skill
if [[ -d "$SKILL_CONVERSATION_DIR" ]]; then
    echo -e "${GREEN}[3/4]${NC} Removing conversation skill..."
    rm -rf "$SKILL_CONVERSATION_DIR"
else
    echo -e "${YELLOW}[3/4]${NC} Conversation skill not found, skipping"
fi

# Remove installation directory
if [[ -d "$INSTALL_DIR" ]]; then
    echo -e "${GREEN}[4/4]${NC} Removing installation directory..."
    rm -rf "$INSTALL_DIR"
else
    echo -e "${YELLOW}[4/4]${NC} Installation directory not found, skipping"
fi

echo ""
echo -e "${GREEN}Uninstallation complete!${NC}"
echo -e "Restart Claude Code to apply changes."
echo ""
echo -e "${YELLOW}Note:${NC} Parakeet-MLX model cache (~2.3GB) is preserved at:"
echo -e "  ~/.cache/huggingface/hub/models--mlx-community--parakeet-tdt-0.6b-v3"
echo -e "Remove manually if you want to free up disk space."
