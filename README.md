# Tmux Builder

A simplified chat interface that communicates with Claude AI through persistent tmux sessions, inspired by SmartDeploy/Builder-CLI.

## Architecture

- **Frontend**: React + Vite + Tailwind CSS
- **Backend**: FastAPI (Python)
- **Session Management**: tmux
- **AI Engine**: Claude CLI
- **Persistence**: JSONL (JSON Lines)

## How It Works

1. **User Input**: Web UI captures messages
2. **API Layer**: FastAPI receives and processes requests
3. **Tmux Integration**: Commands sent to Claude CLI via tmux
4. **Marker-Based Polling**: Backend waits for completion markers
5. **Response Capture**: Reads from JSONL chat history
6. **UI Display**: React renders the conversation

## Project Structure

```
tmux-builder/
├── backend/              # Python FastAPI server
│   ├── main.py          # REST API endpoints
│   ├── session_controller.py  # Session orchestration
│   ├── tmux_helper.py   # Low-level tmux operations
│   └── config.py        # Configuration
├── frontend/            # React application
│   └── src/
│       ├── components/  # UI components
│       └── services/    # API client
└── sessions/            # Runtime storage (auto-created)
```

## Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Usage

1. Start the backend server (default: http://localhost:8000)
2. Start the frontend dev server (default: http://localhost:5173)
3. Click "Create Session" to initialize a tmux session with Claude
4. Start chatting!

## Key Features

- Persistent tmux sessions for stateful conversations
- Marker-based synchronization for reliable IPC
- JSONL persistence for simple message storage
- Clean React UI with Tailwind styling
- WSL2 compatible

## Requirements

- Python 3.8+
- Node.js 16+
- tmux installed
- Claude CLI configured

## License

MIT
