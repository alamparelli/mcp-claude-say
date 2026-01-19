"""
Logging configuration for claude-listen.

Logs to both:
- stderr (visible in Claude Code MCP console)
- /tmp/claude-listen.log (file for easier debugging)
"""

import logging
import sys
from pathlib import Path

LOG_FILE = Path("/tmp/claude-listen.log")

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger that outputs to both stderr and file.

    Args:
        name: Logger name (typically module name like "audio" or "ptt")

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(f"claude-listen.{name}")

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # Format with timestamp for file, simpler for stderr
        file_formatter = logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        stderr_formatter = logging.Formatter('[%(name)s] %(message)s')

        # File handler - append mode, DEBUG level
        file_handler = logging.FileHandler(LOG_FILE, mode='a')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Stderr handler - INFO level (less verbose)
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.INFO)
        stderr_handler.setFormatter(stderr_formatter)
        logger.addHandler(stderr_handler)

        # Don't propagate to root logger
        logger.propagate = False

    return logger


def clear_log():
    """Clear the log file (useful at startup)."""
    if LOG_FILE.exists():
        LOG_FILE.unlink()


# Initialize on import - clear old logs and log startup
clear_log()
_startup_logger = get_logger("startup")
_startup_logger.info(f"=== claude-listen logging initialized ===")
_startup_logger.info(f"Log file: {LOG_FILE}")
