# Setup Guide for Tmux Builder

## WSL Auto-Login and Auto-Navigation Setup

### Configure Default User (genai-user)

1. **From Windows PowerShell or CMD**, set the default user for your WSL distribution:

```powershell
# For Ubuntu distribution
ubuntu config --default-user genai-user

# For other distributions, replace 'ubuntu' with your distribution name
# Check your distribution name with: wsl -l -v
```

2. **Verify the configuration** by opening a new WSL terminal - you should automatically be logged in as genai-user.

### Auto-Navigate to Project Folder

The project folder auto-navigation has been configured in `/home/genai-user/.bashrc`. When you open a new terminal, it will automatically navigate to the tmux-builder project directory if you start in your home directory.

To manually add or modify this behavior, add this to your `~/.bashrc`:

```bash
# Auto-navigate to tmux-builder project on new terminal
if [ "$PWD" = "$HOME" ]; then
    cd /mnt/c/Development/AI-Product-Site/tmux-builder
fi
```

After modifying `.bashrc`, reload it with:
```bash
source ~/.bashrc
```

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
cd /mnt/c/Development/AI-Product-Site/tmux-builder
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
```

### 3. Frontend Setup

```bash
# Navigate to frontend directory (from project root)
cd frontend

# Install dependencies
npm install
```

### 4. Verify tmux Installation

```bash
# Check tmux is installed
tmux -V

# Test tmux session creation
tmux new-session -d -s test_session
tmux kill-session -t test_session
```

### 5. Verify Claude CLI

```bash
# Check Claude CLI is installed and configured
claude --version

# Test Claude CLI (optional)
echo "Hello Claude" | claude
```

## Running the Application

### Terminal 1: Start Backend Server

```bash
cd backend
source venv/bin/activate  # Activate venv if not already active
python main.py
```

You should see:
```
Starting Tmux Builder API on 0.0.0.0:8000
Frontend CORS: http://localhost:5173
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Terminal 2: Start Frontend Dev Server

```bash
cd frontend
npm run dev
```

You should see:
```
  VITE v5.0.8  ready in XXX ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### 3. Access the Application

Open your browser and navigate to:
```
http://localhost:5173
```

## Using the Application

1. **Create Session**: Click "Create Session" button
   - This initializes a tmux session with Claude CLI
   - Wait for "Session ready" status

2. **Send Messages**: Type your message in the input area
   - Press Enter to send
   - Shift+Enter for multi-line messages

3. **View Responses**: Claude's responses appear in the chat
   - Supports markdown formatting
   - Code blocks with syntax highlighting

4. **Clear Chat**: Click "Clear Chat" to reset
   - Kills the tmux session
   - Clears chat history

## Architecture Overview

```
User Browser (React)
        ↓
    HTTP Request
        ↓
FastAPI Backend (/api/chat)
        ↓
Session Controller
        ↓
Tmux Helper (send_command)
        ↓
tmux session → Claude CLI
        ↓
Claude processes request
        ↓
Writes to chat_history.jsonl
Creates completed.marker
        ↓
Backend polls for marker
        ↓
Reads response from JSONL
        ↓
Returns to React UI
```

## Troubleshooting

### Backend won't start
- Check Python version: `python3 --version`
- Ensure venv is activated
- Verify all dependencies installed: `pip list`

### Frontend won't start
- Check Node version: `node --version`
- Delete node_modules and reinstall: `rm -rf node_modules && npm install`

### Session creation fails
- Verify tmux is installed: `tmux -V`
- Check Claude CLI works: `claude --version`
- Look at backend logs for specific errors

### Messages timeout
- Increase timeout in `backend/config.py`
- Check tmux session is active: `tmux list-sessions`
- Verify Claude CLI is responding

### WSL2 specific issues
- Ensure WSL2 is updated
- Check file permissions in session directory
- Verify tmux works in WSL: create test session manually

## Development Tips

### View tmux session
```bash
# List active sessions
tmux list-sessions

# Attach to session (view what Claude sees)
tmux attach-session -t tmux_builder_default_user_<timestamp>

# Detach: Press Ctrl+B, then D
```

### Check session files
```bash
# View chat history
cat sessions/default_user/chat_history.jsonl

# Check markers
ls -la sessions/default_user/markers/
```

### API testing
```bash
# Test backend directly
curl http://localhost:8000/

# Check status
curl http://localhost:8000/api/status
```

## Configuration

Edit `backend/config.py` to customize:
- Timeouts
- Session paths
- Claude CLI flags
- API host/port

## Production Deployment

For production use:

1. Use production WSGI server (gunicorn)
2. Build frontend: `npm run build`
3. Serve static files with nginx
4. Use environment variables for config
5. Implement authentication
6. Add rate limiting

## Support

For issues or questions:
- Check tmux installation
- Verify Claude CLI configuration
- Review backend logs
- Check browser console for frontend errors

## License

MIT
