#!/usr/bin/env python3
"""
Background PTT Runner - Runs PTT in a separate process.

Writes transcriptions to a file for Claude to monitor.
This allows Claude to not block while waiting for speech.

Usage:
    python background_ptt.py [--key cmd_l+s] [--output /tmp/ptt_transcription.txt]
"""

import argparse
import signal
import sys
import time
import json
from pathlib import Path
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from listen.simple_ptt import SimplePTTRecorder
from listen.ptt_controller import PTTController, PTTConfig


class BackgroundPTT:
    """
    Background PTT manager that writes transcriptions to a file.

    Claude can monitor this file instead of blocking on a tool call.
    """

    def __init__(self, output_file: Path, key: str = "cmd_l+s"):
        self.output_file = output_file
        self.key = key
        self.running = True
        self.recorder = None
        self.controller = None
        self.transcription_count = 0

    def _write_status(self, status: str, transcription: str = None) -> None:
        """Write status/transcription to output file as JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "count": self.transcription_count,
        }
        if transcription:
            data["transcription"] = transcription

        # Append to file (one JSON per line)
        with open(self.output_file, "a") as f:
            f.write(json.dumps(data) + "\n")
            f.flush()

        print(f"[{status}] {transcription or ''}")

    def _on_transcription_ready(self, text: str) -> None:
        """Called when transcription is ready."""
        self.transcription_count += 1
        self._write_status("transcription", text)

    def _start_recording(self) -> None:
        """Called when PTT key pressed - start recording."""
        self._write_status("recording_start")
        self.recorder.start()

    def _stop_recording(self) -> None:
        """Called when PTT key released - stop and transcribe."""
        self._write_status("recording_stop")
        self.recorder.stop()

    def run(self) -> None:
        """Run the background PTT loop."""
        # Clear/create output file
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.output_file.write_text("")

        # Setup recorder
        self.recorder = SimplePTTRecorder(
            on_transcription_ready=self._on_transcription_ready
        )

        # Setup PTT controller
        config = PTTConfig(
            key=self.key,
            on_start_recording=self._start_recording,
            on_stop_recording=self._stop_recording,
        )
        self.controller = PTTController(config)

        # Handle signals
        def shutdown(sig, frame):
            print("\nShutting down...")
            self.running = False

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        # Start
        self._write_status("ready")
        self.controller.start()

        print(f"Background PTT active. Key: {self.key}")
        print(f"Output file: {self.output_file}")
        print("Press Ctrl+C or send SIGTERM to stop.")

        # Keep running until signaled
        try:
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self.controller.stop()
            self._write_status("stopped")
            print("Background PTT stopped.")


def main():
    parser = argparse.ArgumentParser(description="Background PTT Runner")
    parser.add_argument(
        "--key",
        default="cmd_l+s",
        help="PTT hotkey (default: cmd_l+s)"
    )
    parser.add_argument(
        "--output",
        default="/tmp/claude-ptt/transcriptions.jsonl",
        help="Output file for transcriptions"
    )

    args = parser.parse_args()

    ptt = BackgroundPTT(
        output_file=Path(args.output),
        key=args.key
    )
    ptt.run()


if __name__ == "__main__":
    main()
