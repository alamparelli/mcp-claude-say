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
SKILL_DIR="$HOME/.claude/skills/speak"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"

echo -e "${BLUE}mcp-claude-say Uninstaller${NC}"
echo ""

# Remove MCP server config from settings.json
if [[ -f "$CLAUDE_SETTINGS" ]] && command -v jq &> /dev/null; then
    echo -e "${GREEN}[1/3]${NC} Removing MCP server configuration..."
    TEMP_FILE=$(mktemp)
    jq 'del(.mcpServers["claude-say"])' "$CLAUDE_SETTINGS" > "$TEMP_FILE" && mv "$TEMP_FILE" "$CLAUDE_SETTINGS"
else
    echo -e "${YELLOW}[1/3]${NC} Please manually remove 'claude-say' from mcpServers in $CLAUDE_SETTINGS"
fi

# Remove skill
if [[ -d "$SKILL_DIR" ]]; then
    echo -e "${GREEN}[2/3]${NC} Removing skill..."
    rm -rf "$SKILL_DIR"
else
    echo -e "${YELLOW}[2/3]${NC} Skill directory not found, skipping"
fi

# Remove installation directory
if [[ -d "$INSTALL_DIR" ]]; then
    echo -e "${GREEN}[3/3]${NC} Removing installation directory..."
    rm -rf "$INSTALL_DIR"
else
    echo -e "${YELLOW}[3/3]${NC} Installation directory not found, skipping"
fi

echo ""
echo -e "${GREEN}Uninstallation complete!${NC}"
echo -e "Restart Claude Code to apply changes."
