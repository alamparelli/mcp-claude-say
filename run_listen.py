#!/usr/bin/env python3
"""Wrapper script to run the listen MCP server with file logging."""
import sys
import os
from pathlib import Path
from datetime import datetime

# Set up log file BEFORE any imports
LOG_DIR = Path.home() / ".mcp-claude-say" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "claude-listen.log"

class TeeStderr:
    """Write to both stderr and a log file."""
    def __init__(self, log_path: Path):
        self.terminal = sys.__stderr__
        self.log = open(log_path, "a", buffering=1)  # Line buffered
        # Write session start marker
        self.log.write(f"\n{'='*60}\n")
        self.log.write(f"[SESSION START] {datetime.now().isoformat()}\n")
        self.log.write(f"{'='*60}\n")
        self.log.flush()

    def write(self, message):
        if self.terminal:
            self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        if self.terminal:
            self.terminal.flush()
        self.log.flush()

# Redirect stderr to both terminal and file
sys.stderr = TeeStderr(LOG_FILE)
print(f"[run_listen] Log file: {LOG_FILE}", file=sys.stderr)

# Add parent directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent))

from listen.mcp_server import mcp

if __name__ == "__main__":
    mcp.run()
