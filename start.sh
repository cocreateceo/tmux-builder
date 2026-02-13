#!/bin/bash
set -e

echo "============================================"
echo "Starting tmux-builder services..."
echo "============================================"

# Activate Python venv
cd /app/backend
source venv/bin/activate

# Export AWS credentials if provided
if [ ! -z "$AWS_ACCESS_KEY_ID" ]; then
    export AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
    export AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
    export AWS_DEFAULT_REGION=${AWS_REGION:-us-east-1}
    echo "✓ AWS credentials configured"
fi

# Export Anthropic API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY environment variable not set"
    exit 1
fi
echo "✓ Anthropic API key configured"

# Start services
echo ""
echo "Starting FastAPI backend on port 8080..."
uvicorn main:app --host 0.0.0.0 --port 8080 --log-level info &
BACKEND_PID=$!

# Wait for backend to start
sleep 5

# Check if backend is running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "ERROR: Backend failed to start"
    exit 1
fi

echo "✓ Backend started (PID: $BACKEND_PID)"
echo ""
echo "============================================"
echo "All services running!"
echo "Backend: http://0.0.0.0:8080"
echo "WebSocket: ws://0.0.0.0:8082"
echo "Health: http://0.0.0.0:8080/health"
echo "============================================"

# Keep container running and forward signals
trap "echo 'Shutting down...'; kill $BACKEND_PID 2>/dev/null || true; exit 0" SIGTERM SIGINT

wait $BACKEND_PID
EXIT_CODE=$?

echo "Backend exited with code $EXIT_CODE"
exit $EXIT_CODE
