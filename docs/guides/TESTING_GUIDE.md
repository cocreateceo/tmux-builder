# Testing Guide - Tmux Builder UI

## Prerequisites

✅ Python 3.8+ installed
✅ Node.js 16+ installed
✅ tmux installed
✅ Claude CLI installed and configured

## Quick Start

### Terminal 1 - Backend Server

```bash
cd /mnt/c/Development/Builder-CLI/tmux-builder
./start-backend.sh
```

**Expected Output:**
```
============================================================
STARTING TMUX BUILDER BACKEND
============================================================

Checking dependencies...
✓ All imports working

Starting backend server...
Press Ctrl+C to stop

============================================================
TMUX BUILDER BACKEND SERVER
============================================================
Starting API on 0.0.0.0:8000
Frontend CORS: http://localhost:5173
Default User: default_user
============================================================

INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
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
============================================================
STARTING TMUX BUILDER FRONTEND
============================================================

Checking node_modules...

Starting frontend dev server...
Press Ctrl+C to stop

  VITE v5.0.8  ready in 350 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

### Browser

1. Open: **http://localhost:5173**
2. Click **"Create Session"** button
3. Wait 10-20 seconds for initialization
4. Type a message in the input box
5. Press Enter or click Send

## What You'll See in Logs

### Backend Logs (Terminal 1)

When you click "Create Session":
```
2026-01-24 12:00:00 - __main__ - INFO - === CREATE SESSION REQUEST ===
2026-01-24 12:00:00 - __main__ - INFO - User: default_user
2026-01-24 12:00:00 - __main__ - INFO - Creating SessionController...
2026-01-24 12:00:00 - session_controller - INFO - Initializing SessionController for user: default_user
2026-01-24 12:00:00 - session_controller - INFO - Session path: /path/to/sessions/default_user
2026-01-24 12:00:00 - session_controller - INFO - Session name: tmux_builder_default_user_1737712800
2026-01-24 12:00:00 - session_controller - INFO - === INITIALIZING SESSION ===
2026-01-24 12:00:00 - session_controller - INFO - Creating tmux session: tmux_builder_default_user_1737712800
2026-01-24 12:00:03 - session_controller - INFO - ✓ Tmux session created
2026-01-24 12:00:03 - session_controller - INFO - ✓ Instructions sent
2026-01-24 12:00:03 - session_controller - INFO - Waiting for initialized marker (timeout: 60s)...
2026-01-24 12:00:15 - session_controller - INFO - ✓ Session initialized successfully
2026-01-24 12:00:15 - __main__ - INFO - ✓ Session created successfully: tmux_builder_default_user_1737712800
```

When you send a message:
```
2026-01-24 12:01:00 - __main__ - INFO - === CHAT MESSAGE ===
2026-01-24 12:01:00 - __main__ - INFO - Message: Hello Claude!...
2026-01-24 12:01:00 - session_controller - INFO - === SENDING MESSAGE ===
2026-01-24 12:01:00 - session_controller - INFO - Appending user message to history...
2026-01-24 12:01:00 - session_controller - INFO - Sending message to tmux session: tmux_builder_default_user_1737712800
2026-01-24 12:01:00 - session_controller - INFO - ✓ Message sent to Claude
2026-01-24 12:01:00 - session_controller - INFO - Waiting for completion marker (timeout: 60s)...
2026-01-24 12:01:05 - session_controller - INFO - ✓ Completion marker received
2026-01-24 12:01:05 - session_controller - INFO - Response received: Hello! How can I help you today?...
2026-01-24 12:01:05 - __main__ - INFO - ✓ Response sent successfully
```

### Frontend Logs (Browser Console - F12)

The frontend will show status checks and API calls:
```
Checking status...
Creating session...
Session created: tmux_builder_default_user_1737712800
Sending message: Hello Claude!
Received response
```

## Troubleshooting

### Backend Won't Start

**Error: `ModuleNotFoundError: No module named 'fastapi'`**

Solution:
```bash
cd backend
pip3 install --user fastapi==0.104.1 uvicorn[standard]==0.24.0 pydantic==2.5.0 python-multipart==0.0.6
```

**Error: `Address already in use` (Port 8000)**

Solution:
```bash
# Kill existing process
pkill -f "python3 main.py"
# Or use different port
export API_PORT=8001
./start-backend.sh
```

### Frontend Won't Start

**Error: `ENOENT: no such file or directory`**

Solution:
```bash
cd frontend
npm install
```

**Error: `Port 5173 already in use`**

Solution:
```bash
# Kill existing process
pkill -f "vite"
# Or Vite will auto-increment to 5174
```

### UI Connection Errors

**Error: `ERR_CONNECTION_REFUSED` or `ERR_CONNECTION_RESET`**

Check:
1. Is backend running? (Should see "Uvicorn running on http://0.0.0.0:8000")
2. Is backend accessible? `curl http://localhost:8000/`
3. Check backend logs for errors

**Error: `Failed to create session`**

Check backend logs for:
- tmux not installed: `sudo apt-get install tmux`
- Claude CLI not found: Install from https://claude.ai/download
- Permission issues: Check session directory permissions

**Error: `Timeout waiting for response`**

Check:
1. Is tmux session alive? `tmux list-sessions`
2. Attach to session to see Claude: `tmux attach -t tmux_builder_*`
3. Check if Claude CLI is responding
4. Increase timeout in `backend/config.py` if needed

## Debugging Commands

### Check Backend Status
```bash
# Is backend running?
ps aux | grep "python3 main.py"

# Test backend directly
curl http://localhost:8000/
curl http://localhost:8000/api/status
```

### Check TMUX Sessions
```bash
# List all tmux sessions
tmux list-sessions

# Attach to Claude session (watch in real-time)
tmux attach -t tmux_builder_default_user_*

# Detach: Press Ctrl+B then D

# Capture pane output
tmux capture-pane -t tmux_builder_default_user_* -p | tail -50
```

### Check Session Files
```bash
# View session directory
ls -la sessions/default_user/

# View chat history
cat sessions/default_user/chat_history.jsonl

# Check markers
ls -la sessions/default_user/markers/
```

### Clean Up Everything
```bash
# Stop backend
pkill -f "python3 main.py"

# Stop frontend
pkill -f "vite"

# Kill all tmux sessions
tmux kill-server

# Clean session data
rm -rf sessions/default_user/
```

## Test Sequence

1. **Start Backend** - Watch for "Uvicorn running" message
2. **Start Frontend** - Watch for "Local: http://localhost:5173"
3. **Open Browser** - Navigate to http://localhost:5173
4. **Create Session** - Click button, watch backend logs for initialization
5. **Send Message** - Type "Hello Claude!" and press Enter
6. **Watch Logs** - See message flow through backend
7. **Get Response** - See Claude's response appear in UI

## Success Indicators

✅ Backend shows: `INFO:     Uvicorn running on http://0.0.0.0:8000`
✅ Frontend shows: `➜  Local:   http://localhost:5173/`
✅ Browser loads UI without errors
✅ "Create Session" succeeds (button changes to "Clear Chat")
✅ Backend logs show "✓ Session initialized successfully"
✅ Messages send and receive responses
✅ Backend logs show "✓ Response sent successfully"

## Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Backend import errors | Missing dependencies | Run `pip3 install --user -r backend/requirements.txt` |
| Port already in use | Previous instance running | Kill process: `pkill -f "python3 main.py"` |
| CORS errors | Wrong frontend URL | Check backend CORS settings match frontend port |
| Session creation fails | tmux/Claude CLI missing | Install dependencies |
| Timeout waiting | Claude CLI slow/stuck | Increase timeout or restart |
| No response | Marker files not created | Check Claude CLI is responding |

## Next Steps

Once everything works:
- Test file uploads (if implemented)
- Test session persistence
- Test error handling (invalid inputs)
- Monitor performance (response times)
- Check memory usage during long conversations
