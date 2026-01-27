# CLAUDE.md - Project Context for AI Assistants

## Project Overview

Tmux Builder: Web UI for interacting with Claude CLI through isolated tmux sessions with real-time progress updates.

## Architecture

**Dual-channel WebSocket:**
- Channel 1 (port 8000): HTTP REST API for chat - UI ↔ FastAPI ↔ tmux ↔ Claude
- Channel 2 (port 8001): WebSocket for progress - Claude → notify.sh → ws_server → UI

**Key insight:** Channel 2 uses asyncio.Event for instant backend notification (not polling).

## Key Files

- `backend/main.py` - FastAPI app, session management, auto-create on first message
- `backend/ws_server.py` - Progress WebSocket server with asyncio.Event signaling
- `backend/session_controller.py` - Message orchestration, waits on events
- `backend/session_initializer.py` - Creates tmux session, generates notify.sh
- `frontend/src/components/SplitChatView.jsx` - Main UI component
- `frontend/src/hooks/useProgressSocket.js` - Channel 2 WebSocket hook

## Common Patterns

### Session re-attachment after server restart
```python
# In /api/chat - auto-create if session_controller is None or GUID mismatch
needs_session_switch = (
    session_controller is None or
    (requested_guid and session_controller.guid != requested_guid)
)
```

### Event-based ack/done waiting (not polling!)
```python
# In session_controller.py
event = server.get_ack_event(self.guid)
event.clear()  # Reset before waiting
await asyncio.wait_for(event.wait(), timeout=timeout)
```

### UI loading state
- Controlled by HTTP request lifecycle in handleSendMessage
- NOT by WebSocket ack events (prevents init ack from blocking UI)

## Gotchas

- **GUID in localStorage**: Handle "null"/"undefined" strings, not just null
- **Init ack vs message ack**: Claude sends ack on session init (health check) AND on each message - don't let init ack block UI
- **Polling race condition**: If using polling, acks that arrive before wait loop starts get missed - use asyncio.Event instead
- **tmux session name**: `tmux_builder_{guid}` format

## Testing

```bash
# Start backend
cd backend && source venv/bin/activate && python main.py

# Test API
curl http://localhost:8000/

# Test chat with existing session
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "guid": "<guid>"}'

# List tmux sessions
tmux list-sessions
```

## Session Folder Structure

```
sessions/<guid>/
├── system_prompt.txt   # Agent instructions (read once at init)
├── notify.sh           # Progress script (GUID baked in)
├── prompt.txt          # User message (written per message)
├── chat_history.jsonl  # Persisted chat
├── activity_log.jsonl  # Persisted activity log
└── status.json         # Session state
```
