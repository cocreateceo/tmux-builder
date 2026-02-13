# Tmux Builder Architecture

Dual-channel WebSocket architecture with bash-based progress communication for Claude CLI integration.

## System Overview

Tmux Builder enables web UI interaction with Claude AI through isolated tmux sessions. The architecture uses **notify.sh** (a bash script) for real-time progress updates from Claude CLI to the browser.

### Key Architectural Components

1. **FastAPI Backend (Port 8000)**: Session management, chat messaging, main WebSocket for UI
2. **Progress WebSocket Server (Port 8001)**: Real-time progress broadcasts from Claude CLI to UI
3. **notify.sh Script**: Per-session bash script Claude uses to send progress updates
4. **Claude CLI in tmux**: Isolated session executing user tasks

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           BROWSER (React UI)                                     │
│                                                                                  │
│  ┌────────────────────────────────────┬────────────────────────────────────────┐│
│  │      LEFT: Chat Panel              │      RIGHT: Activity Log Panel         ││
│  │      (Channel 1)                   │      (Channel 2)                       ││
│  │                                    │                                        ││
│  │  User messages                     │  [11:34:02] ACK - Ready to work        ││
│  │  Claude responses                  │  [11:34:05] STATUS - Analyzing code    ││
│  │                                    │  [11:34:12] WORKING - Refactoring auth ││
│  │                                    │  [11:34:30] DONE - Task completed      ││
│  └────────────┬───────────────────────┴──────────────────┬─────────────────────┘│
│               │                                          │                      │
│               │ WebSocket                                │ WebSocket            │
│               │ Port 8000                                │ Port 8001            │
└───────────────┼──────────────────────────────────────────┼──────────────────────┘
                │                                          │
                ▼                                          ▼
┌───────────────────────────────────┐    ┌────────────────────────────────────────┐
│      FastAPI Backend              │    │      Progress WebSocket Server         │
│      Port 8000                    │    │      Port 8001                         │
│                                   │    │                                        │
│  • Session lifecycle              │    │  • Path-based routing: /ws/<guid>      │
│  • Tmux management                │    │  • Receives messages from notify.sh    │
│  • Generate notify.sh             │    │  • Broadcasts to subscribed UI clients │
│  • Send instructions via tmux     │    │  • Message history per session         │
│  • Chat WebSocket endpoint        │    │                                        │
└─────────────┬─────────────────────┘    └────────────────────────────────────────┘
              │                                          ▲
              │ tmux send-keys                           │ WebSocket (from notify.sh)
              ▼                                          │
┌─────────────────────────────────────────────────────────────────────────────────┐
│              TMUX SESSION                                                        │
│                                                                                  │
│    ┌──────────────────────────────────────────────────────────────────────────┐ │
│    │                     CLAUDE CLI                                           │ │
│    │                                                                          │ │
│    │    Working directory: sessions/<guid>/                                   │ │
│    │                                                                          │ │
│    │    Progress updates via notify.sh:                                       │ │
│    │    ───────────────────────────────────────────                          │ │
│    │    │ ./notify.sh ack                    → WebSocket → UI               │ │
│    │    │ ./notify.sh status "Analyzing..."  → WebSocket → UI               │ │
│    │    │ ./notify.sh working "Refactoring"  → WebSocket → UI               │ │
│    │    │ ./notify.sh done                   → WebSocket → UI               │ │
│    │    └───────────────────────────────────────────                          │ │
│    │                                                                          │ │
│    └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Dual-Channel Architecture

### Channel 1: Chat (Port 8000)
- **Transport**: HTTP REST + WebSocket
- **Purpose**: Session management, message sending, response delivery
- **Flow**: UI ↔ FastAPI Backend ↔ tmux ↔ Claude CLI

### Channel 2: Progress (Port 8001)
- **Transport**: WebSocket
- **Purpose**: Real-time progress updates, activity logging
- **Flow**: Claude CLI → notify.sh → WebSocket Server → UI
- **Signaling**: asyncio.Event for instant backend notification (ack/done)

### Event-Based Synchronization

The WebSocket server signals the session_controller directly using asyncio.Event:

```
notify.sh sends ack → ws_server receives → sets ack_event → session_controller wakes up instantly
```

This replaces polling-based waiting, eliminating race conditions where acks arrived before wait loops started.

## notify.sh Script

Each session gets a dedicated `notify.sh` script with the session GUID baked in.

**Location:** `sessions/active/<guid>/notify.sh`

**Usage:**
```bash
./notify.sh <type> [data]

# Examples:
./notify.sh ack                          # Acknowledge task received
./notify.sh status "Analyzing code..."   # Send status message
./notify.sh working "Refactoring auth"   # What currently working on
./notify.sh progress 50                  # Progress percentage (0-100)
./notify.sh found "3 bugs in login.py"   # Report findings
./notify.sh summary                      # Signal summary ready (reads summary.md)
./notify.sh done                         # Task completed
./notify.sh error "Config not found"     # Report error
```

## Summary.md for Formatted Completions

Claude writes a formatted markdown summary to `summary.md` before completion:

```bash
# Claude writes formatted summary
cat > summary.md << 'EOF'
## Task Completed

### What was added:
- Feature 1
- Feature 2

**Live URL:** https://example.cloudfront.net
EOF

# Signal backend to read it
./notify.sh summary
./notify.sh done
```

The backend reads `summary.md` and sends the full formatted content to the frontend, which renders it with proper markdown styling.

**How it works:**
1. Backend creates `notify.sh` from template during session initialization
2. Template has `{{GUID}}` placeholder replaced with actual session GUID
3. Script uses Python websockets to send JSON messages to `ws://localhost:8001/ws/<guid>`
4. WebSocket server broadcasts to all UI clients subscribed to that GUID

## Backend Synchronization (asyncio.Event)

The backend uses asyncio.Event for instant notification between components:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BACKEND INTERNAL SIGNALING                              │
│                                                                             │
│  ┌────────────────────┐         ┌─────────────────────┐                    │
│  │  session_controller│         │    ws_server        │                    │
│  │                    │         │                     │                    │
│  │  await event.wait()│◀────────│  event.set()        │◀─── notify.sh ack  │
│  │  (instant wakeup)  │         │  (on ack received)  │                    │
│  └────────────────────┘         └─────────────────────┘                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Why events instead of polling:**
- **Instant**: No 0.5s polling delay
- **Race-safe**: Event persists until waited upon (cleared before each wait)
- **Efficient**: No CPU cycles wasted in tight loops

**Events per GUID:**
- `ack_events[guid]`: Set when Claude sends `./notify.sh ack`
- `done_events[guid]`: Set when Claude sends `./notify.sh done` or `error`

## Message Flow

### Session Initialization

```
1. User clicks "Create Session"
2. Backend creates session folder with subfolders (tmp/, code/, infrastructure/, docs/)
3. Backend generates notify.sh with GUID baked in
4. Backend generates system_prompt.txt with autonomous agent instructions
5. Backend clears any stale prompt.txt (prevents auto-execution of old tasks)
6. Backend creates tmux session, starts Claude CLI FROM session folder
7. Backend sends health check: 'Read system_prompt.txt and run: ./notify.sh ack - then WAIT'
8. Claude reads system_prompt.txt, runs ./notify.sh ack
9. notify.sh sends WebSocket message to port 8001
10. Backend detects ack, marks session ready
11. UI receives ack on Channel 2, shows connected status
12. Claude is now WAITING for explicit task instruction (won't read prompt.txt proactively)
```

### Message Processing

```
1. User sends message via Channel 1 (HTTP to backend)
2. Backend writes prompt_{timestamp}.txt to session directory (unique filename prevents caching)
3. Backend sends tmux instruction with FULL ABSOLUTE PATH to prompt file
4. Claude reads the prompt file, processes request
5. Claude sends progress updates as it works:
   - ./notify.sh ack → WebSocket Server → UI
   - ./notify.sh status "Analyzing..." → WebSocket Server → UI
   - ./notify.sh working "Implementing feature" → WebSocket Server → UI
6. Claude writes formatted summary to summary.md
7. Claude calls ./notify.sh summary → Backend reads summary.md → UI displays formatted
8. Claude calls ./notify.sh done → Backend signals completion
9. UI displays markdown-rendered summary in chat
```

### Timestamped Prompt Files

Each message creates a unique prompt file to prevent CLI caching:

```
prompt_1706012345678.txt  # Message 1
prompt_1706012345999.txt  # Message 2
```

The instruction sent to Claude includes the full absolute path:
```
NEW USER MESSAGE - Read this file NOW and execute: /full/path/to/prompt_1706012345678.txt
```

This ensures Claude CLI cannot serve cached content from a previous prompt.

## Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| React UI | Split-view chat + activity log display, dual WebSocket connections |
| FastAPI Backend | Session lifecycle, tmux management, notify.sh generation |
| Progress WebSocket Server | Real-time broadcasts to UI (port 8001) |
| notify.sh | Bash script to send WebSocket messages from Claude CLI |
| TmuxHelper | Low-level tmux command execution |
| SessionController | Message orchestration |
| SessionInitializer | Session creation with notify.sh generation |
| asyncio.Event | Instant signaling between ws_server and session_controller |

## Message Types

Claude can use any type with notify.sh - these are common conventions:

| Type | Purpose | Example |
|------|---------|---------|
| `ack` | Acknowledge task received | `./notify.sh ack` |
| `status` | General status update | `./notify.sh status "Reading files"` |
| `working` | What currently working on | `./notify.sh working "auth module"` |
| `progress` | Percentage complete | `./notify.sh progress 50` |
| `found` | Report findings | `./notify.sh found "3 issues"` |
| `deployed` | Deployed URL | `./notify.sh deployed "https://..."` |
| `summary` | Signal summary ready | `./notify.sh summary` (reads summary.md) |
| `done` | Task completed | `./notify.sh done` |
| `error` | Report error | `./notify.sh error "File not found"` |

## UI Display Format

Activity log shows timestamped entries:
```
[11:34:02] ACK - Ready to work
[11:34:05] STATUS - Reading the codebase
[11:34:12] WORKING - Refactoring authentication module
[11:34:20] FOUND - 3 issues in login.py
[11:34:30] DONE - Task completed
```

## Configuration

Key configuration in `backend/config.py`:

```python
# WebSocket ports
API_PORT = 8000           # Main backend + chat WebSocket
PROGRESS_WS_PORT = 8001   # Progress updates WebSocket

# Session settings
TMUX_SESSION_PREFIX = 'tmux_builder'
ACTIVE_SESSIONS_DIR = Path('./sessions')

# Timeouts
HEALTH_CHECK_TIMEOUT = 30  # seconds to wait for ack
```

## Session Folder Structure

When a session is created, the following structure is generated:

```
sessions/<guid>/
├── system_prompt.txt   # Comprehensive autonomous agent instructions (read once)
├── notify.sh           # Progress communication script (GUID baked in)
├── prompt.txt          # User task (written when user sends message)
├── status.json         # Session state tracking
├── chat_history.jsonl  # Chat history
├── tmp/                # Scratch work, test files, temporary data
├── code/               # Generated application code
├── infrastructure/     # IaC files (Terraform, CloudFormation)
└── docs/               # Documentation, deployment summaries
```

### system_prompt.txt

Generated by `system_prompt_generator.py` during session initialization. Contains:
- Session GUID and path information
- Operating environment details
- **CRITICAL: Task reception protocol** - instructs Claude to WAIT for explicit task instructions
- Communication protocol using notify.sh
- File organization guidelines
- Skills and agents paths (absolute paths to `.claude/skills/` and `.claude/agents/`)
- Deployment requirements and checklists
- Quality standards

**Key behavior:** Claude reads system_prompt.txt once at init, acknowledges with `./notify.sh ack`, then **STOPS and WAITS** for the backend to send an explicit task instruction. This prevents Claude from auto-executing stale tasks.

## File Structure

```
backend/
├── main.py                    # FastAPI backend + chat WebSocket
├── ws_server.py               # Progress WebSocket server (port 8001)
├── config.py                  # Configuration (ports, timeouts, paths)
├── tmux_helper.py             # TMUX operations (launches Claude from session folder)
├── session_controller.py      # Message orchestration
├── session_initializer.py     # Session creation + folder structure + file generation
├── system_prompt_generator.py # Generate system_prompt.txt for autonomous operation
├── notify_generator.py        # Generate notify.sh from template
└── scripts/
    └── notify_template.sh     # Template with {{GUID}} placeholder

sessions/
└── <guid>/
    ├── system_prompt.txt      # Autonomous agent instructions (generated)
    ├── notify.sh              # Progress script (generated, GUID baked in)
    ├── prompt.txt             # User's message (created when user sends message)
    ├── status.json            # Session state
    ├── chat_history.jsonl     # Conversation history
    ├── tmp/                   # Scratch work
    ├── code/                  # Application code
    ├── infrastructure/        # IaC files
    └── docs/                  # Documentation

frontend/
├── src/
│   ├── hooks/
│   │   ├── useWebSocket.js       # Channel 1 (chat)
│   │   └── useProgressSocket.js  # Channel 2 (progress)
│   ├── components/
│   │   ├── SplitChatView.jsx     # Main split view
│   │   ├── MessageList.jsx       # Chat messages
│   │   ├── InputArea.jsx         # User input
│   │   └── ActivityLog.jsx       # Progress/activity panel
│   └── services/
│       └── api.js                # HTTP API client
```

## Setup Requirements

1. **tmux** installed and in PATH
2. **Claude CLI** installed and authenticated
3. **Python websockets** package installed (`pip install websockets`)
4. **Backend running** on port 8000 (starts progress WebSocket on 8001)
5. **Frontend running** (Vite dev server on port 5173)

## Troubleshooting

### notify.sh not working

**Symptoms:** Claude runs ./notify.sh but UI doesn't update

**Solutions:**
1. Verify WebSocket server is running on port 8001
2. Check notify.sh has correct GUID: `cat sessions/<guid>/notify.sh | grep GUID`
3. Test manually: `cd sessions/<guid> && ./notify.sh test "hello"`
4. Check Python websockets installed: `python3 -c "import websockets; print('OK')"`

### UI not receiving progress updates

**Symptoms:** Chat works but activity log is empty

**Solutions:**
1. Check browser console for WebSocket connection to port 8001
2. Verify UI is subscribing to correct GUID: `ws://localhost:8001/ws/<guid>`
3. Check backend logs for WebSocket server startup message

### Session not initializing

**Symptoms:** Session creation times out

**Solutions:**
1. Verify tmux is installed: `which tmux`
2. Check Claude CLI is authenticated: `claude --version`
3. Look at backend logs for specific error messages
4. Verify sessions directory exists and is writable
