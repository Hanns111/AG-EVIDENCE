#!/bin/bash
# Setup Ollama server and pull qwen2.5vl:7b
export LD_LIBRARY_PATH=/home/hans/ollama/lib/ollama:/usr/lib/wsl/lib:$LD_LIBRARY_PATH
export OLLAMA_MODELS=/home/hans/.ollama/models

OLLAMA=/home/hans/ollama/bin/ollama

# Kill any existing ollama
pkill -f "ollama serve" 2>/dev/null
sleep 1

# Start server
echo "Starting Ollama server..."
$OLLAMA serve &
SERVE_PID=$!
sleep 3

# Verify
if curl -s http://localhost:11434/ | grep -q "Ollama"; then
    echo "Server running (PID $SERVE_PID)"
else
    echo "ERROR: Server failed to start"
    exit 1
fi

# Pull model
echo "Pulling qwen2.5vl:7b..."
$OLLAMA pull qwen2.5vl:7b

echo ""
echo "=== Models available ==="
$OLLAMA list

echo ""
echo "Server still running (PID $SERVE_PID). Ready for inference."
echo "To stop: kill $SERVE_PID"

# Keep server running - wait for it
wait $SERVE_PID
