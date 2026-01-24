# Quick Start Guide

Get Tmux Builder running in 5 minutes!

## Prerequisites Check

```bash
# Check Python
python3 --version  # Need 3.8+

# Check Node
node --version     # Need 16+

# Check tmux
tmux -V           # Need tmux installed

# Check Claude CLI
claude --version  # Need Claude CLI configured
```

## Setup & Run

### 1. Backend (Terminal 1)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

**Expected output:**
```
Starting Tmux Builder API on 0.0.0.0:8000
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. Frontend (Terminal 2)

```bash
cd frontend
npm install
npm run dev
```

**Expected output:**
```
  VITE v5.0.8  ready in XXX ms
  ➜  Local:   http://localhost:5173/
```

### 3. Open Browser

Navigate to: **http://localhost:5173**

## First Steps

1. Click **"Create Session"** button
2. Wait for initialization (10-20 seconds)
3. Type a message: "Hello, Claude!"
4. Press Enter and watch the magic happen!

## Troubleshooting

### "Failed to create session"
- Verify tmux is installed: `tmux -V`
- Check Claude CLI works: `echo "test" | claude`
- Look at backend terminal for error details

### "Timeout waiting for response"
- Claude CLI might not be responding
- Check if session exists: `tmux list-sessions`
- Restart backend and try again

### Frontend won't connect
- Ensure backend is running on port 8000
- Check browser console (F12) for errors
- Verify CORS settings in backend/main.py

## What's Happening Behind the Scenes?

```
Your Message
    ↓
React Frontend (port 5173)
    ↓ HTTP POST
FastAPI Backend (port 8000)
    ↓ tmux send-keys
Claude CLI in tmux session
    ↓ writes to
chat_history.jsonl + completed.marker
    ↓ backend polls and reads
Response appears in UI!
```

## Project Structure

```
tmux-builder/
├── backend/              # Python FastAPI server
│   ├── main.py          # API endpoints
│   ├── session_controller.py
│   ├── tmux_helper.py
│   └── config.py
├── frontend/            # React + Vite
│   ├── src/
│   │   ├── components/  # UI components
│   │   └── services/    # API client
│   └── package.json
└── sessions/            # Runtime data (auto-created)
    └── default_user/
        ├── chat_history.jsonl
        └── markers/
```

## Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) for deep dive
- Read [SETUP.md](SETUP.md) for detailed setup
- Check out [SmartDeploy](https://github.com/GopiSunware/smartdeploy) for the original inspiration

## Key Features

✅ Persistent tmux sessions
✅ Marker-based synchronization
✅ JSONL chat history
✅ Markdown support in responses
✅ Code syntax highlighting
✅ WSL2 compatible

## Need Help?

- Check backend logs in Terminal 1
- Check frontend console in browser (F12)
- View active tmux sessions: `tmux list-sessions`
- Attach to session to see Claude: `tmux attach -t tmux_builder_*`

## Stop the Application

1. **Backend**: Press `Ctrl+C` in Terminal 1
2. **Frontend**: Press `Ctrl+C` in Terminal 2
3. **Clean up tmux**: `tmux kill-server` (kills all sessions)

Happy chatting! 🚀
