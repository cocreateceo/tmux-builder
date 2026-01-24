# Tmux Builder

A simplified chat interface that communicates with Claude AI through persistent tmux sessions, featuring the SmartBuild pattern for AI-driven workflows.

## Quick Links

- [Getting Started](docs/QUICKSTART.md)
- [Architecture Details](docs/ARCHITECTURE.md)
- [SmartBuild Pattern](docs/SMARTBUILD_ARCHITECTURE_ANALYSIS.md)
- [Implementation Guide](docs/HOW_TO_IMPLEMENT_TMUX_IN_ANY_PROJECT.md)

## Architecture

- **Frontend**: React + Vite + Tailwind CSS
- **Backend**: Flask (Python)
- **SmartBuild**: File-based I/O pattern for LLM-friendly operations
- **Session Management**: tmux
- **AI Engine**: Claude CLI

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
├── backend/              # Python Flask server
│   ├── app.py           # REST API endpoints
│   ├── smartbuild.py    # SmartBuild file-based operations
│   └── test_smartbuild.py  # Test suite
├── frontend/            # React application
│   └── src/
│       ├── components/  # UI components
│       └── services/    # API client
├── docs/                # All project documentation
└── sessions/            # Runtime storage (auto-created)
    └── active/          # Active session data
```

## Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python app.py
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
