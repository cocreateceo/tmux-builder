#!/bin/bash

# Build and test Docker image locally before Lightsail deployment
set -e

echo "============================================"
echo "Building tmux-builder Docker image..."
echo "============================================"

# Build image
docker build -t tmux-builder:latest .

echo ""
echo "✓ Image built successfully!"
echo ""
echo "============================================"
echo "Starting container for testing..."
echo "============================================"

# Stop and remove existing test container if it exists
docker stop tmux-builder-test 2>/dev/null || true
docker rm tmux-builder-test 2>/dev/null || true

# Get Anthropic API key from environment or prompt
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY environment variable not set"
    echo "Please set it with: export ANTHROPIC_API_KEY=your-key"
    exit 1
fi

# Run container
docker run -d \
  --name tmux-builder-test \
  -p 8080:8080 \
  -p 8082:8082 \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -e LIGHTSAIL_DEPLOYMENT=true \
  -e AWS_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}" \
  -e AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}" \
  tmux-builder:latest

echo ""
echo "✓ Container started!"
echo ""
echo "Waiting for services to start (40 seconds)..."
sleep 40

echo ""
echo "============================================"
echo "Testing endpoints..."
echo "============================================"

# Test health endpoint
echo -n "Testing health endpoint... "
if curl -f -s http://localhost:8080/health > /dev/null; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
    echo ""
    echo "Container logs:"
    docker logs tmux-builder-test
    exit 1
fi

# Test admin sessions endpoint
echo -n "Testing admin sessions endpoint... "
if curl -f -s http://localhost:8080/api/admin/sessions?filter=all > /dev/null; then
    echo "✓ PASSED"
else
    echo "✗ FAILED"
fi

echo ""
echo "============================================"
echo "Container is running successfully!"
echo "============================================"
echo ""
echo "Backend API:   http://localhost:8080"
echo "Health check:  http://localhost:8080/health"
echo "WebSocket:     ws://localhost:8082"
echo ""
echo "View logs:     docker logs -f tmux-builder-test"
echo "Stop:          docker stop tmux-builder-test"
echo "Remove:        docker rm tmux-builder-test"
echo ""
echo "Press Ctrl+C to stop showing logs (container will keep running)"
echo ""

# Show logs
docker logs -f tmux-builder-test
