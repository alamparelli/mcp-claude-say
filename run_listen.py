#!/usr/bin/env python3
"""Wrapper script to run the listen MCP server."""
import sys
from pathlib import Path

# Add parent directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))

from listen.mcp_server import mcp

if __name__ == "__main__":
    mcp.run()
