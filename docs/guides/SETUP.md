# Setup Guide for Tmux Builder

Complete setup instructions for the dual-channel WebSocket architecture.

Yes, admin login was added. Here's the summary:                                                                                                                                              
                                                                                                                                                                                               
  Admin Login                                                                                                                                                                                  
                                                                                                                                                                                               
  Password: tmux@admin2026                                                                                                                                                                     
                                                                                                                                                                                               
  - Non-logged-in users see embed mode (no sidebar)                                                                                                                                            
  - Click "Admin Login" button in header → enter password → get sidebar access                                                                                                                 
  - Stored in localStorage.tmux_admin_auth                                                                                                                                                     
                                                                                                                                                                                               
  ---                                                                                                                                                                                          
  API Integration for Main Application                                                                                                                                                         
                                                                                                                                                                                               
  Create Client Session                                                                                                                                                                        
                                                                                                                                                                                               
  Endpoint: POST https://d3r4k77gnvpmzn.cloudfront.net/api/admin/sessions                                                                                                                      
                                                                                                                                                                                               
  Request:                                                                                                                                                                                     
  {                                                                                                                                                                                            
    "name": "John Doe",                                                                                                                                                                        
    "email": "john@example.com",                                                                                                                                                               
    "phone": "+1-555-123-4567",                                                                                                                                                                
    "initial_request": "I need help building a landing page for my SaaS product"                                                                                                               
  }                                                                                                                                                                                            
                                                                                                                                                                                               
  Success Response:                                                                                                                                                                            
  {                                                                                                                                                                                            
    "success": true,                                                                                                                                                                           
    "guid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",                                                                                                                                            
    "link": "https://d3r4k77gnvpmzn.cloudfront.net/?guid=a1b2c3d4-e5f6-7890-abcd-ef1234567890&embed=true"                                                                                      
  }                                                                                                                                                                                            
                                                                                                                                                                                               
  Failure Response:                                                                                                                                                                            
  {                                                                                                                                                                                            
    "success": false,                                                                                                                                                                          
    "error": "Failed to create session: <reason>"                                                                                                                                              
  }                                                                                                                                                                                            
                                                                                                                                                                                               
  ---                                                                                                                                                                                          
  What to do in your main app                                                                                                                                                                  
                                                                                                                                                                                               
  1. Collect user info (name, email, phone, what they want)                                                                                                                                    
  2. POST to the API with the data above                                                                                                                                                       
  3. Redirect user to the link returned in response                                                                                                                                            
  4. User sees their request in chat, Claude processes it in activity log                                                                                                                      
                                                                                                                                                                                               
  Example (JavaScript):                                                                                                                                                                        
  const response = await fetch('https://d3r4k77gnvpmzn.cloudfront.net/api/admin/sessions', {                                                                                                   
    method: 'POST',                                                                                                                                                                            
    headers: { 'Content-Type': 'application/json' },                                                                                                                                           
    body: JSON.stringify({                                                                                                                                                                     
      name: 'John Doe',                                                                                                                                                                        
      email: 'john@example.com',                                                                                                                                                               
      phone: '+1-555-123-4567',                                                                                                                                                                
      initial_request: 'Build me a landing page'                                                                                                                                               
    })                                                                                                                                                                                         
  });                                                                                                                                                                                          
                                                                                                                                                                                               
  const data = await response.json();                                                                                                                                                          
  if (data.success) {                                                                                                                                                                          
    window.location.href = data.link;  // or open in iframe                                                                                                                                    
  }                                                                                                                                                                                            
                                        
## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.8+** - [Download](https://www.python.org/downloads/)
- **Node.js 16+** - [Download](https://nodejs.org/)
- **tmux** - Terminal multiplexer
  - Linux: `sudo apt-get install tmux`
  - macOS: `brew install tmux`
  - WSL2: `sudo apt-get install tmux`
- **Claude CLI** - Anthropic's Claude command-line interface
  - Installation: Follow [Claude CLI documentation](https://docs.anthropic.com)
  - Verify: `claude --version`

## Installation Steps

### 1. Clone or Navigate to Project

```bash
cd /mnt/c/Development/Builder-CLI/tmux-builder
```

### 2. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS/WSL:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify websockets is installed (required for notify.sh)
python3 -c "import websockets; print('websockets OK')"
```

### 3. Frontend Setup

```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install dependencies
npm install
```

### 4. Verify Setup

```bash
# Check tmux
tmux -V

# Test tmux session
tmux new-session -d -s test_session
tmux kill-session -t test_session

# Check Claude CLI
claude --version

# Check Python websockets
python3 -c "import websockets; print('OK')"
```

## Running the Application

### Terminal 1: Start Backend Server

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
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Terminal 2: Start Frontend Dev Server

```bash
cd frontend
npm run dev
```

**Expected output:**
```
  VITE v5.0.8  ready in XXX ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### Access the Application

Open your browser: **http://localhost:5173**

## Architecture Overview

The application uses a **dual-channel WebSocket architecture**:

```
┌────────────────────────────────────────────────────────┐
│                    Browser (React UI)                   │
│                                                         │
│   ┌─────────────────┬─────────────────────────────┐   │
│   │  Chat Panel     │   Activity Log Panel        │   │
│   │  (Channel 1)    │   (Channel 2)               │   │
│   └────────┬────────┴──────────────┬──────────────┘   │
│            │                       │                   │
│            │ Port 8000             │ Port 8001         │
└────────────┼───────────────────────┼───────────────────┘
             │                       │
             ▼                       ▼
┌────────────────────┐   ┌───────────────────────────────┐
│  FastAPI Backend   │   │  Progress WebSocket Server    │
│  Port 8000         │   │  Port 8001                    │
│                    │   │                               │
│  - Session mgmt    │   │  - Path-based: /ws/<guid>     │
│  - tmux control    │   │  - Broadcasts to UI           │
│  - generate        │   │  - Receives from notify.sh    │
│    notify.sh       │   │                               │
└────────┬───────────┘   └───────────────────────────────┘
         │                           ▲
         │ tmux send-keys            │ WebSocket
         ▼                           │
┌────────────────────────────────────────────────────────┐
│                    TMUX SESSION                         │
│                                                         │
│   Claude CLI                                            │
│     │                                                   │
│     └──► ./notify.sh status "Working on it..." ────────│──┘
│                                                         │
└────────────────────────────────────────────────────────┘
```

### Key Components

1. **FastAPI Backend (Port 8000)**: Session management, chat API, notify.sh generation
2. **Progress WebSocket Server (Port 8001)**: Real-time progress broadcasts to UI
3. **notify.sh**: Per-session bash script Claude uses to send progress updates
4. **Claude CLI in tmux**: Isolated session executing user tasks

## Using the Application

1. **Create Session**: Click "Create Session" button
   - Initializes a tmux session with Claude CLI
   - Generates `notify.sh` script for the session
   - Sends health check (`./notify.sh ack`)
   - Wait for "Session ready" status

2. **Send Messages**: Type message and press Enter
   - Shift+Enter for multi-line messages
   - Watch Activity Log panel for progress

3. **Monitor Progress**: Right panel shows real-time updates
   - `[HH:MM:SS] ACK - Ready to work`
   - `[HH:MM:SS] STATUS - Analyzing code...`
   - `[HH:MM:SS] WORKING - Refactoring module`
   - `[HH:MM:SS] DONE - Task completed`

4. **Clear Session**: Click "Clear Session" to reset
   - Kills the tmux session
   - Clears chat history

## Configuration

Edit `backend/config.py` to customize:

```python
# WebSocket Configuration
API_PORT = 8000
PROGRESS_WS_PORT = 8001

# Backend Configuration
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]

# Claude CLI Configuration
CLI_PATH = 'claude'
CLI_FLAGS = '--dangerously-skip-permissions'

# Timeouts
HEALTH_CHECK_TIMEOUT = 30  # seconds
```

## Troubleshooting

### notify.sh not working

**Symptoms:** Claude runs `./notify.sh` but UI doesn't update

**Solutions:**
1. Verify WebSocket server is running on port 8001
2. Check notify.sh has correct GUID:
   ```bash
   cat sessions/<guid>/notify.sh | grep GUID
   ```
3. Test manually:
   ```bash
   cd sessions/<guid>
   ./notify.sh test "hello"
   ```
4. Check Python websockets installed:
   ```bash
   python3 -c "import websockets; print('OK')"
   ```

### Session creation times out

**Symptoms:** "Timeout waiting for ack - Claude CLI not responsive"

**Solutions:**
1. Check backend is running on port 8000
2. Verify WebSocket server started on port 8001
3. Attach to tmux session to debug:
   ```bash
   tmux list-sessions
   tmux attach -t tmux_builder_*
   ```

### Backend won't start

- Check Python version: `python3 --version`
- Ensure venv is activated
- Verify all dependencies installed: `pip list`
- Check ports aren't in use: `lsof -i :8000` and `lsof -i :8001`

### Frontend won't start

- Check Node version: `node --version`
- Delete node_modules and reinstall: `rm -rf node_modules && npm install`

### WebSocket connection fails

- Check browser console for WebSocket errors
- Verify Progress WebSocket server is running on port 8001
- Check firewall isn't blocking WebSocket connections

### WSL2 specific issues

- Sessions directory uses native Linux path (`~/tmux-builder/sessions/`) for performance
- Ensure WSL2 is updated
- Check file permissions in session directory

## Development Tips

### View tmux session

```bash
# List active sessions
tmux list-sessions

# Attach to session (see Claude in real-time)
tmux attach-session -t tmux_builder_*

# Detach: Press Ctrl+B, then D
```

### Test notify.sh manually

```bash
# Navigate to session directory
cd sessions/<your-guid>

# Test sending a message
./notify.sh test "Hello from manual test"

# Check if WebSocket received it (look at backend logs)
```

### API testing

```bash
# Test backend
curl http://localhost:8000/

# Test session status
curl http://localhost:8000/api/session/<guid>/status
```

### Debug logging

Set environment variable for verbose logging:
```bash
LOG_LEVEL=DEBUG python main.py
```

## Clean Up

```bash
# Kill all tmux sessions
tmux kill-server

# Delete session directories
rm -rf ~/tmux-builder/sessions/active/*
```

## Production Deployment

For production use:

1. Use production WSGI server (gunicorn)
2. Build frontend: `npm run build`
3. Serve static files with nginx
4. Use environment variables for config
5. Implement authentication
6. Add rate limiting
7. Configure HTTPS for WebSocket connections

## File Structure

```
tmux-builder/
├── backend/
│   ├── main.py                    # FastAPI server
│   ├── ws_server.py               # Progress WebSocket server (port 8001)
│   ├── config.py                  # Configuration
│   ├── tmux_helper.py             # TMUX operations (launches from session folder)
│   ├── session_controller.py      # Message orchestration
│   ├── session_initializer.py     # Session creation + file generation
│   ├── system_prompt_generator.py # Generate system_prompt.txt
│   ├── notify_generator.py        # Generate notify.sh from template
│   └── scripts/
│       └── notify_template.sh     # Template with {{GUID}} placeholder
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── SplitChatView.jsx   # Main split view
│   │   │   ├── MessageList.jsx     # Chat messages
│   │   │   ├── InputArea.jsx       # User input
│   │   │   └── McpToolsLog.jsx     # Activity log panel
│   │   ├── hooks/
│   │   │   └── useProgressSocket.js # Progress WebSocket hook
│   │   └── services/
│   │       └── api.js              # HTTP API client
│   └── package.json
├── sessions/
│   └── <guid>/
│       ├── system_prompt.txt   # Autonomous agent instructions (generated)
│       ├── notify.sh           # Progress script (generated, GUID baked in)
│       ├── prompt.txt          # User's message (created on send)
│       ├── status.json         # Session state
│       ├── tmp/                # Scratch work
│       ├── code/               # Application code
│       ├── infrastructure/     # IaC files
│       └── docs/               # Documentation
└── docs/
    ├── architecture/
    │   └── ARCHITECTURE.md     # Full architecture details
    └── guides/
        ├── QUICKSTART.md       # Quick start guide
        └── SETUP.md            # This file
```
