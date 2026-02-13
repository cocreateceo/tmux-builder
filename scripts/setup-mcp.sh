#!/bin/bash
# Setup MCP server registration for Claude CLI
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PATH="$SCRIPT_DIR/../backend/mcp_server/server.py"

echo "=== MCP Server Registration ==="
echo "Server path: $SERVER_PATH"

# Verify server exists
if [ ! -f "$SERVER_PATH" ]; then
    echo "ERROR: MCP server not found at $SERVER_PATH"
    exit 1
fi

# Remove existing registration (ignore errors if not exists)
echo "Removing existing tmux-progress registration..."
claude mcp remove tmux-progress 2>/dev/null || true

# Register MCP server
echo "Registering MCP server..."
claude mcp add tmux-progress -- python3 "$SERVER_PATH"

# Verify registration
echo ""
echo "=== Registered MCP Servers ==="
claude mcp list

echo ""
echo "Setup complete! MCP server registered as 'tmux-progress'"
