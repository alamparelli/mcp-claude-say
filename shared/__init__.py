"""
Shared utilities for claude-say and claude-listen coordination
"""

from .coordination import signal_stop_speaking, is_speaking

__all__ = ["signal_stop_speaking", "is_speaking"]
