# Tmux Builder - Project Summary

## What is Tmux Builder?

A simplified web-based chat interface for Claude AI, inspired by [SmartDeploy/Builder-CLI](https://github.com/GopiSunware/smartdeploy). It enables persistent conversations with Claude through tmux sessions.

## Created: 2026-01-23

Based on architectural analysis of SmartDeploy project, this implementation demonstrates:
- Web UI → API → tmux → Claude CLI integration
- Marker-based synchronization for reliable IPC
- JSONL persistence for chat history
- Clean separation of concerns

## Technology Stack

### Backend
- **Language**: Python 3.8+
- **Framework**: FastAPI
- **Session Management**: tmux
- **AI Engine**: Claude CLI (Anthropic)
- **Persistence**: JSONL (JSON Lines)

### Frontend
- **Language**: JavaScript/JSX
- **Framework**: React 18
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **HTTP Client**: Axios
- **Markdown**: react-markdown with remark-gfm

## Project Structure

```
tmux-builder/
├── README.md                 # Project overview
├── QUICKSTART.md            # Fast setup guide
├── SETUP.md                 # Detailed installation
├── ARCHITECTURE.md          # Technical deep dive
├── PROJECT_SUMMARY.md       # This file
├── .gitignore              # Git exclusions
│
├── backend/                 # Python FastAPI server
│   ├── main.py             # REST API endpoints (202 lines)
│   ├── session_controller.py  # Session orchestration (177 lines)
│   ├── tmux_helper.py      # Low-level tmux ops (132 lines)
│   ├── config.py           # Configuration (57 lines)
│   └── requirements.txt    # Python dependencies
│
├── frontend/               # React application
│   ├── index.html         # HTML entry point
│   ├── package.json       # Node dependencies
│   ├── vite.config.js     # Vite configuration
│   ├── tailwind.config.js # Tailwind setup
│   ├── postcss.config.js  # PostCSS setup
│   └── src/
│       ├── main.jsx       # React entry point
│       ├── App.jsx        # Root component
│       ├── index.css      # Global styles
│       ├── components/
│       │   ├── ChatInterface.jsx   # Main chat container (146 lines)
│       │   ├── MessageList.jsx     # Message display (79 lines)
│       │   └── InputArea.jsx       # User input (48 lines)
│       └── services/
│           └── api.js     # API client (42 lines)
│
└── sessions/              # Runtime storage (auto-created)
    └── default_user/
        ├── chat_history.jsonl   # JSONL message log
        └── markers/             # Synchronization markers
            ├── initialized.marker
            ├── processing.marker
            └── completed.marker
```

## File Inventory

### Documentation (5 files)
- README.md - Project overview and basic info
- QUICKSTART.md - 5-minute setup guide
- SETUP.md - Comprehensive installation instructions
- ARCHITECTURE.md - Detailed technical architecture
- PROJECT_SUMMARY.md - This file

### Backend (5 files)
- main.py - FastAPI server with API endpoints
- session_controller.py - High-level session management
- tmux_helper.py - Low-level tmux command execution
- config.py - Centralized configuration
- requirements.txt - Python package dependencies

### Frontend (13 files)
- index.html - HTML entry point
- package.json - NPM package configuration
- vite.config.js - Vite build tool config
- tailwind.config.js - Tailwind CSS config
- postcss.config.js - PostCSS config
- src/main.jsx - React application entry
- src/App.jsx - Root React component
- src/index.css - Global CSS with Tailwind
- src/components/ChatInterface.jsx - Main chat UI
- src/components/MessageList.jsx - Message display
- src/components/InputArea.jsx - User input area
- src/services/api.js - Axios HTTP client

### Configuration (1 file)
- .gitignore - Git ignore patterns

**Total Files Created: 24**

## Key Features Implemented

### Core Functionality
✅ Session creation and management
✅ Message sending and receiving
✅ Chat history persistence (JSONL)
✅ Marker-based synchronization
✅ Real-time UI updates
✅ Error handling and timeouts

### UI Features
✅ Clean, modern interface (Tailwind CSS)
✅ Markdown rendering in responses
✅ Code syntax highlighting
✅ User/Assistant message distinction
✅ Timestamps on messages
✅ Loading states and indicators
✅ Session status display

### Technical Features
✅ CORS configuration for local development
✅ RESTful API design
✅ Modular architecture
✅ WSL2 compatibility (double-enter pattern)
✅ Persistent tmux sessions
✅ File-based IPC (markers)
✅ Append-only JSONL persistence

## Architecture Highlights

### Data Flow
```
User Input → React Component → API Service → FastAPI Endpoint
    → Session Controller → Tmux Helper → tmux send-keys
    → Claude CLI → Process → Write to JSONL + Create Marker
    → Backend Polls Marker → Read JSONL → Return to Frontend
    → React State Update → UI Re-render
```

### Key Design Patterns

1. **Marker-Based Sync**: File existence for reliable IPC
2. **JSONL Persistence**: Append-only message storage
3. **Double-Enter Pattern**: WSL2 compatibility workaround
4. **Polling with Timeout**: Marker detection with 60s limit
5. **Component Separation**: Clear boundaries between layers

## API Endpoints

```
POST /api/session/create  - Initialize new tmux session
GET  /api/status         - Check session status
POST /api/chat           - Send message to Claude
GET  /api/history        - Retrieve chat history
POST /api/clear          - Clear session and history
```

## Differences from SmartDeploy

This is a **simplified educational implementation** focusing on core concepts:

| Feature | SmartDeploy | Tmux Builder |
|---------|-------------|--------------|
| File uploads | ✅ | ❌ Not implemented |
| Screenshots | ✅ | ❌ Not implemented |
| Multi-user | ✅ | ⚠️ Single user only |
| Session meta | ✅ | ⚠️ Simplified |
| Error recovery | ✅ Robust | ⚠️ Basic |
| Production ready | ✅ | ❌ Development only |

## Lines of Code

### Backend
- main.py: ~202 lines
- session_controller.py: ~177 lines
- tmux_helper.py: ~132 lines
- config.py: ~57 lines
**Total Backend: ~568 lines**

### Frontend
- ChatInterface.jsx: ~146 lines
- MessageList.jsx: ~79 lines
- InputArea.jsx: ~48 lines
- App.jsx: ~18 lines
- api.js: ~42 lines
- main.jsx: ~9 lines
**Total Frontend: ~342 lines**

### Configuration
- package.json: ~26 lines
- vite.config.js: ~14 lines
- tailwind.config.js: ~17 lines
- Other configs: ~50 lines
**Total Config: ~107 lines**

**Total Project Code: ~1,017 lines** (excluding documentation)

## Learning Outcomes

By studying this project, you'll understand:

1. **Web-to-CLI Integration**: How to bridge web interfaces with CLI tools
2. **tmux Session Management**: Creating and controlling tmux programmatically
3. **Marker-Based IPC**: Using file markers for process synchronization
4. **JSONL Persistence**: Simple, robust data storage pattern
5. **React + FastAPI**: Modern full-stack architecture
6. **Async Communication**: Polling and timeout patterns
7. **WSL2 Compatibility**: Platform-specific workarounds

## Use Cases

- Understanding tmux programmatic control
- Learning marker-based synchronization patterns
- Building CLI tool web interfaces
- Educational full-stack development
- Base for custom Claude CLI interfaces

## Future Enhancements

Potential features to add:
- File upload support
- Screenshot capture and sharing
- Multi-user authentication
- WebSocket real-time updates (eliminate polling)
- Session persistence across restarts
- Advanced error recovery
- Rate limiting and quotas
- Docker containerization
- Production deployment configs

## Dependencies

### Backend (Python)
```
fastapi==0.104.1        # Web framework
uvicorn[standard]==0.24.0  # ASGI server
pydantic==2.5.0         # Data validation
python-multipart==0.0.6 # File upload support
```

### Frontend (Node)
```
react ^18.2.0           # UI library
react-dom ^18.2.0       # React DOM renderer
axios ^1.6.2            # HTTP client
react-markdown ^9.0.1   # Markdown rendering
remark-gfm ^4.0.0       # GitHub Flavored Markdown
vite ^5.0.8             # Build tool
tailwindcss ^3.3.6      # CSS framework
```

## Getting Started

1. **Quick Start**: See [QUICKSTART.md](QUICKSTART.md)
2. **Detailed Setup**: See [SETUP.md](SETUP.md)
3. **Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)

## Credits

- **Inspired by**: [SmartDeploy/Builder-CLI](https://github.com/GopiSunware/smartdeploy)
- **Created by**: Claude AI (Sonnet 4.5)
- **Date**: January 23, 2026
- **Purpose**: Educational demonstration of tmux-based Claude CLI integration

## License

MIT License - Free to use, modify, and distribute.

## Support

For questions or issues:
1. Check the documentation files
2. Review backend logs for errors
3. Inspect browser console (F12)
4. Verify tmux and Claude CLI are working
5. Check [SmartDeploy issues](https://github.com/GopiSunware/smartdeploy/issues) for similar problems

---

**Status**: ✅ Complete and ready to use!
**Last Updated**: 2026-01-23
