# Quick Start Guide

Get Tmux Builder running in 5 minutes.

## Prerequisites Check

```bash
# Check Python
python3 --version  # Need 3.8+

# Check Node.js
node --version     # Need 16+

# Check tmux
tmux -V            # Need tmux installed

# Check Claude CLI
claude --version   # Need Claude CLI configured

# Check Python websockets
python3 -c "import websockets; print('OK')"  # Need websockets package
```

## Setup

### 1. Install Dependencies

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend (in new terminal)
cd frontend
npm install
```

### 2. Start Backend Server

```bash
cd backend
source venv/bin/activate
python main.py
```

**Expected output:**
```
============================================================
TMUX BUILDER BACKEND SERVER
============================================================
Starting API on 0.0.0.0:8000
Starting Progress WebSocket server on port 8001
Frontend CORS: http://localhost:5173
============================================================

INFO:     Started server process
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 3. Start Frontend Dev Server

```bash
cd frontend
npm run dev
```

### 4. Access the Application

Open browser: **http://localhost:5173**

## Using the Application

1. **Create Session**: Click "Create Session" button
   - Creates a tmux session with Claude CLI
   - Generates `notify.sh` script for progress updates
   - Wait for "Session ready" status

2. **Send Messages**: Type message and press Enter
   - Watch the Activity Log panel (right side) for real-time progress
   - See updates: `ACK`, `STATUS`, `WORKING`, `DONE`, etc.

3. **Monitor Progress**:
   - Channel 1 (Port 8000): Chat messages
   - Channel 2 (Port 8001): Real-time activity updates

## Architecture Overview

```
Browser (React UI)
    │
    ├──[Port 8000]──► FastAPI Backend
    │                     │
    │                     ├──► tmux session ──► Claude CLI
    │                     │
    │                     └──► generates notify.sh
    │
    └──[Port 8001]──► Progress WebSocket Server (real-time updates)

Claude CLI ──► ./notify.sh ──► WebSocket Server ──► UI
```

## Troubleshooting

### "notify.sh not working"

```bash
# Check notify.sh exists and has correct GUID
cat sessions/<guid>/notify.sh | grep GUID

# Test manually
cd sessions/<guid>
./notify.sh test "hello"

# Check websockets installed
python3 -c "import websockets; print('OK')"
```

### "Session creation times out"

```bash
# Check backend is running
curl http://localhost:8000/

# Check WebSocket server is running (see logs)

# View tmux session
tmux list-sessions
tmux attach -t tmux_builder_*
```

### "Port already in use"

```bash
# Kill existing processes
lsof -i :8000  # Backend
lsof -i :8001  # Progress WebSocket

# Restart backend
```

## Project Structure

```
tmux-builder/
├── backend/
│   ├── main.py                    # FastAPI server
│   ├── ws_server.py               # Progress WebSocket server
│   ├── system_prompt_generator.py # Generate system_prompt.txt
│   ├── notify_generator.py        # Generate notify.sh from template
│   ├── scripts/
│   │   └── notify_template.sh     # Template with {{GUID}} placeholder
│   ├── session_controller.py      # Message orchestration
│   └── tmux_helper.py             # TMUX operations
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── SplitChatView.jsx  # Main UI with dual panels
│       │   └── McpToolsLog.jsx    # Activity log panel
│       └── hooks/
│           └── useProgressSocket.js  # Progress WebSocket hook
├── sessions/
│   └── <guid>/
│       ├── system_prompt.txt      # Autonomous agent instructions
│       ├── notify.sh              # Generated script (GUID baked in)
│       ├── prompt.txt             # User task
│       ├── tmp/                   # Scratch work
│       ├── code/                  # Application code
│       ├── infrastructure/        # IaC files
│       └── docs/                  # Documentation
└── docs/
    └── architecture/
        └── ARCHITECTURE.md        # Full architecture details
```

## Next Steps

- Read [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) for full technical details
- Read [SETUP.md](SETUP.md) for detailed setup instructions
