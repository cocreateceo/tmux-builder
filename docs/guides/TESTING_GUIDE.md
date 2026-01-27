# Testing Guide - Tmux Builder UI

Testing the dual-channel MCP architecture.

## Prerequisites

- Python 3.8+ installed
- Node.js 16+ installed
- tmux installed
- Claude CLI installed and configured
- **MCP server registered at user scope** (see Setup section)

## Setup

### Register MCP Server (One Time)

```bash
cd /mnt/c/Development/Builder-CLI/tmux-builder

# Register MCP server at user scope
claude mcp add --scope user tmux-progress -- python3 $(pwd)/backend/mcp_server/server.py

# Verify
claude mcp list
# Should show: tmux-progress    user    python3 ...
```

## Quick Start

### Terminal 1 - Backend Server

```bash
cd /mnt/c/Development/Builder-CLI/tmux-builder
./start-backend.sh
```

**Expected Output:**
```
============================================================
TMUX BUILDER BACKEND SERVER
============================================================
Starting API on 0.0.0.0:8000
Starting MCP WebSocket server on port 8001
Frontend CORS: http://localhost:5173
============================================================

INFO:     Started server process [xxxxx]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Terminal 2 - Frontend Dev Server

```bash
cd /mnt/c/Development/Builder-CLI/tmux-builder
./start-frontend.sh
```

**Expected Output:**
```
  VITE v5.0.8  ready in 350 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### Browser

1. Open: **http://localhost:5173**
2. Click **"Create Session"** button
3. Wait for MCP health check (ack) to complete
4. Type a message in the input box
5. Watch the MCP Tools Log panel (right side) for real-time progress
6. See response appear in chat panel (left side)

## What You'll See

### UI Split View

```
┌─────────────────────────────┬─────────────────────────────┐
│      Chat Panel             │    MCP Tools Log Panel      │
│      (Channel 1)            │    (Channel 2)              │
│                             │                             │
│  User: Hello Claude!        │  [12:01:00] notify_ack      │
│                             │    guid: abc123             │
│  Claude: Hello! How can     │                             │
│  I help you today?          │  [12:01:02] send_progress   │
│                             │    guid: abc123, percent: 50│
│                             │                             │
│                             │  [12:01:05] send_response   │
│                             │    guid: abc123             │
│                             │    content: Hello! How...   │
│                             │                             │
│                             │  [12:01:05] notify_complete │
│                             │    guid: abc123, success:true│
└─────────────────────────────┴─────────────────────────────┘
```

### Backend Logs (Terminal 1)

When you click "Create Session":
```
INFO - === CREATE SESSION REQUEST ===
INFO - Creating tmux session: tmux_builder_abc123
INFO - Registering session with MCP server...
INFO - Sending health check instruction...
INFO - Waiting for MCP ack (timeout: 30s)...
INFO - MCP ack received - Claude CLI is alive and ready
INFO - Session initialization complete
```

When you send a message:
```
INFO - === SEND MESSAGE REQUEST ===
INFO - Writing prompt to /path/to/sessions/abc123/prompt.txt
INFO - Sending instruction to Claude CLI...
INFO - Waiting for MCP response (timeout: 300s)...
INFO - MCP response received
INFO - Response: Hello! How can I help you today?
```

### Frontend Console (Browser F12)

```
[MCP-WS] Connecting to ws://localhost:8001/ws/abc123...
[MCP-WS] Connected to MCP progress server
[MCP-WS] Received: ack {guid: "abc123", timestamp: "..."}
[MCP-WS] Received: progress {guid: "abc123", percent: 50, ...}
[MCP-WS] Received: response {guid: "abc123", content: "Hello!...", ...}
[MCP-WS] Received: complete {guid: "abc123", success: true, ...}
```

## Test Scenarios

### 1. Session Creation Test

1. Open browser to http://localhost:5173
2. Click "Create Session"
3. Verify:
   - Backend logs show MCP ack received
   - UI shows session ready status
   - MCP Tools Log shows connection established

### 2. Message Send/Receive Test

1. Type message: "Hello Claude!"
2. Press Enter
3. Verify:
   - User message appears in chat panel
   - MCP Tools Log shows `notify_ack`
   - Progress updates appear (if Claude reports them)
   - Response appears in chat panel
   - `notify_complete` appears in MCP log

### 3. MCP WebSocket Connection Test

1. Open browser console (F12)
2. Watch for `[MCP-WS]` log messages
3. Verify:
   - Connection to port 8001 succeeds
   - Messages received in real-time

### 4. Bridge Mode Test

1. Attach to tmux session: `tmux attach -t tmux_builder_*`
2. In Claude CLI, press `/` to open menu
3. Select "mcp"
4. Verify:
   - `tmux-progress` shows "connected"
   - Tools are listed (notify_ack, send_progress, etc.)

## Troubleshooting

### MCP Tools Not Available

**Symptoms:** Claude shows `tmux-progress` connected but "Capabilities: none"

**Solution:**
```bash
# Re-register with user scope
claude mcp remove tmux-progress
claude mcp add --scope user tmux-progress -- python3 /path/to/backend/mcp_server/server.py
```

### Session Creation Times Out

**Symptoms:** "Timeout waiting for MCP ack"

**Check:**
1. MCP server registered at user scope: `claude mcp list`
2. Backend running on port 8000: `curl http://localhost:8000/`
3. Attach to tmux session: `tmux attach -t tmux_builder_*`

### WebSocket Connection Fails

**Symptoms:** UI shows disconnected status, browser console shows WebSocket errors

**Check:**
1. MCP WebSocket server running on port 8001
2. Backend logs show "Starting MCP WebSocket server"
3. No firewall blocking port 8001

### Tool Calls Not Reaching UI

**Symptoms:** Claude works but UI doesn't show progress

**Check:**
1. Browser connected to WebSocket (check console)
2. `/api/mcp/tool-call` endpoint accessible:
   ```bash
   curl -X POST http://localhost:8000/api/mcp/tool-call \
     -H "Content-Type: application/json" \
     -d '{"tool": "notify_ack", "arguments": {"guid": "test"}}'
   ```

## Debugging Commands

### Check Backend Status
```bash
# Is backend running?
ps aux | grep "python3 main.py"

# Test backend
curl http://localhost:8000/

# Test MCP tool call endpoint
curl -X POST http://localhost:8000/api/mcp/tool-call \
  -H "Content-Type: application/json" \
  -d '{"tool": "notify_ack", "arguments": {"guid": "test-guid"}}'
```

### Check TMUX Sessions
```bash
# List sessions
tmux list-sessions

# Attach to Claude session
tmux attach -t tmux_builder_*

# Detach: Ctrl+B then D

# Capture pane output
tmux capture-pane -t tmux_builder_* -p | tail -50
```

### Check MCP Registration
```bash
# List MCP servers
claude mcp list

# Should show:
# Name            Scope    Command
# tmux-progress   user     python3 /path/to/backend/mcp_server/server.py
```

### Check Ports
```bash
# Backend port
lsof -i :8000

# MCP WebSocket port
lsof -i :8001

# Frontend port
lsof -i :5173
```

### Clean Up
```bash
# Stop backend
pkill -f "python3 main.py"

# Stop frontend
pkill -f "vite"

# Kill tmux sessions
tmux kill-server

# Clean session data
rm -rf ~/tmux-builder/sessions/active/*
```

## Success Indicators

- Backend shows: `INFO: Uvicorn running on http://0.0.0.0:8000`
- Backend shows: `Starting MCP WebSocket server on port 8001`
- Frontend shows: `Local: http://localhost:5173/`
- Browser loads split-view UI
- MCP connection status shows green/connected
- "Create Session" completes successfully
- MCP Tools Log shows tool calls in real-time
- Messages send and receive responses

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| MCP tools unavailable | Wrong scope | Re-register with `--scope user` |
| Session timeout | MCP bridge not working | Check backend port 8000 |
| No progress updates | WebSocket disconnect | Check port 8001 |
| CORS errors | Wrong frontend URL | Check backend CORS settings |
| Port already in use | Previous instance | Kill process |

## Architecture Verification

### Verify Bridge Mode

When Claude CLI spawns the MCP server, it runs in bridge mode. Verify by:

1. Start a session
2. Check backend logs for: `Tool call forwarded: notify_ack(...)`
3. This confirms MCP server is forwarding to FastAPI

### Verify Dual Channels

1. Channel 1 (Port 8000): Chat API
   - Test: `curl http://localhost:8000/api/status`

2. Channel 2 (Port 8001): MCP WebSocket
   - Test: Check browser console for WebSocket connection

### Verify End-to-End Flow

```
1. User sends message (UI)
      ↓
2. HTTP POST to /api/chat (Port 8000)
      ↓
3. Backend writes prompt.txt, sends tmux instruction
      ↓
4. Claude CLI reads prompt, calls MCP tools
      ↓
5. MCP Bridge forwards to /api/mcp/tool-call (Port 8000)
      ↓
6. Backend updates registry, broadcasts via WebSocket (Port 8001)
      ↓
7. UI receives progress on Channel 2
      ↓
8. Backend returns final response on Channel 1
      ↓
9. UI displays response
```
