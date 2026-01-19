#!/bin/bash
# Stop Chatterbox TTS Service

PID_FILE="/tmp/chatterbox_tts.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Stopping TTS service (PID: $PID)..."
        kill "$PID"
        rm -f "$PID_FILE"
        echo "Stopped."
    else
        echo "TTS service not running (stale PID file removed)"
        rm -f "$PID_FILE"
    fi
else
    echo "TTS service not running (no PID file)"
fi
