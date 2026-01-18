#!/bin/bash
# Start Chatterbox TTS Service
# This script starts the FastAPI TTS server that provides neural text-to-speech.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_PATH="$SCRIPT_DIR/venv-tts"
LOG_FILE="/tmp/chatterbox_tts.log"
PID_FILE="/tmp/chatterbox_tts.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "TTS service already running (PID: $PID)"
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# Start the service
echo "Starting Chatterbox TTS service..."
"$VENV_PATH/bin/python" "$SCRIPT_DIR/tts_service.py" > "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

# Wait for startup
echo "Waiting for model to load (this may take 5-10 seconds on first run)..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:8123/health | grep -q '"model_loaded":true'; then
        echo "TTS service started successfully (PID: $PID)"
        exit 0
    fi
    sleep 1
done

echo "Warning: Service started but model may not be loaded yet."
echo "Check logs: tail -f $LOG_FILE"
exit 1
