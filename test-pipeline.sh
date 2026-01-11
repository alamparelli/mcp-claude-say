#!/bin/bash
#
# Test Pipeline for mcp-claude-say
# Performs clean uninstall, copies fresh source, and reinstalls
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ORIGINAL_DIR="$HOME/mcp-claude-say-original"
TEMP_DIR="/tmp/test-install"
VENV_DIR="$HOME/.claude-say-venv"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   MCP Claude-Say Test Pipeline${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Uninstall
echo -e "${YELLOW}[1/4] Uninstalling previous installation...${NC}"
if [ -f "$ORIGINAL_DIR/uninstall.sh" ]; then
    bash "$ORIGINAL_DIR/uninstall.sh" 2>/dev/null || true
    echo -e "${GREEN}  ✓ Uninstall script executed${NC}"
else
    echo -e "${YELLOW}  ⚠ No uninstall.sh found, skipping${NC}"
fi

# Also clean up venv if it exists
if [ -d "$VENV_DIR" ]; then
    echo -e "  Removing virtual environment..."
    rm -rf "$VENV_DIR"
    echo -e "${GREEN}  ✓ Virtual environment removed${NC}"
fi

# Step 2: Remove temp directory
echo ""
echo -e "${YELLOW}[2/4] Cleaning temp directory...${NC}"
if [ -d "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR"
    echo -e "${GREEN}  ✓ Removed $TEMP_DIR${NC}"
else
    echo -e "${GREEN}  ✓ Temp directory already clean${NC}"
fi

# Step 3: Copy original to temp
echo ""
echo -e "${YELLOW}[3/4] Copying source to temp...${NC}"
if [ -d "$ORIGINAL_DIR" ]; then
    # Create temp dir and copy (excluding .git for speed)
    mkdir -p "$TEMP_DIR"
    rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
          "$ORIGINAL_DIR/" "$TEMP_DIR/"
    echo -e "${GREEN}  ✓ Copied to $TEMP_DIR${NC}"

    # Show what was copied
    echo -e "  Files copied:"
    ls -la "$TEMP_DIR" | head -15
else
    echo -e "${RED}  ✗ Original directory not found: $ORIGINAL_DIR${NC}"
    exit 1
fi

# Step 4: Install
echo ""
echo -e "${YELLOW}[4/4] Installing from temp directory...${NC}"
cd "$TEMP_DIR"

if [ -f "install.sh" ]; then
    echo -e "  Running install.sh..."
    bash install.sh
    echo -e "${GREEN}  ✓ Installation complete${NC}"
else
    echo -e "${RED}  ✗ install.sh not found in $TEMP_DIR${NC}"
    exit 1
fi

# Summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}   Pipeline Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Source:      $ORIGINAL_DIR"
echo -e "Test dir:    $TEMP_DIR"
echo -e "Venv:        $VENV_DIR"
echo ""
echo -e "${YELLOW}To test the installation:${NC}"
echo -e "  1. Restart Claude Code"
echo -e "  2. Run: /conversation"
echo -e "  3. Say something, then say 'stop' to test trigger word"
echo ""
echo -e "${YELLOW}Environment variables (optional):${NC}"
echo -e "  CLAUDE_LISTEN_TRANSCRIBER=parakeet     # or whisper, auto"
echo -e "  CLAUDE_LISTEN_SILENCE_TIMEOUT=1.5      # seconds (default: 1.5)"
echo -e "  CLAUDE_LISTEN_SPEECH_THRESHOLD=0.5     # Silero probability 0.0-1.0"
echo -e "  CLAUDE_LISTEN_USE_COREML=true          # Use Neural Engine (default: true)"
