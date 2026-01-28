# CLAUDE.md - Project Context for AI Assistants

## Project Overview

Tmux Builder: Web UI for interacting with Claude CLI through isolated tmux sessions with real-time progress updates.

## Architecture

**Dual-channel WebSocket:**
- Channel 1 (port 8080): HTTP REST API for chat - UI ↔ FastAPI ↔ tmux ↔ Claude
- Channel 2 (port 8082): WebSocket for progress - Claude → notify.sh → ws_server → UI

**Key insight:** Channel 2 uses asyncio.Event for instant backend notification (not polling).

**Sessions path:** `<project>/sessions/active/<guid>/` (in project directory)

## Key Files

- `backend/main.py` - FastAPI app, session management, admin API endpoints
- `backend/ws_server.py` - Progress WebSocket server, reads summary.md for completions
- `backend/session_controller.py` - Message orchestration, timestamped prompt files
- `backend/session_initializer.py` - Creates tmux session, generates notify.sh
- `backend/system_prompt_generator.py` - Generates system_prompt.txt
- `frontend/src/components/SplitChatView.jsx` - Main UI with collapsible sidebar
- `frontend/src/components/SessionSidebar.jsx` - Collapsible session list
- `frontend/src/components/MessageList.jsx` - Chat with markdown rendering
- `frontend/src/hooks/useProgressSocket.js` - Channel 2 WebSocket hook

## Recent Changes (Jan 2026)

### Timestamped Prompt Files
- Each message creates `prompt_{timestamp_ms}.txt` to prevent CLI caching
- Full absolute path sent in instruction to Claude
- Fixes issue where Claude read stale cached prompt content

### Summary.md for Formatted Completions
- Claude writes formatted summary to `summary.md` before calling done
- Backend reads file and sends full markdown to frontend
- Frontend renders with proper styling (headers, lists, links)

### Collapsible Session Sidebar
- Toggle button on left edge (always visible)
- Lists sessions with filter (All/Active/Completed)
- Click session to switch, "New Session" button
- Content area shifts when sidebar opens

### Admin API Endpoints
```
GET  /api/admin/sessions?filter=all|active|completed
POST /api/admin/sessions  (email, phone, initial_request)
GET  /api/admin/sessions/{guid}
```

## Common Patterns

### Session re-attachment after server restart
```python
# In /api/chat - auto-create if session_controller is None or GUID mismatch
needs_session_switch = (
    session_controller is None or
    (requested_guid and session_controller.guid != requested_guid)
)
```

### Timestamped prompt files (prevents caching)
```python
# In session_controller.py
timestamp_ms = int(time.time() * 1000)
prompt_filename = f"prompt_{timestamp_ms}.txt"
prompt_path = self.session_path / prompt_filename
# Full path sent to Claude in instruction
```

### Event-based ack/done waiting (not polling!)
```python
# In session_controller.py
event = server.get_ack_event(self.guid)
event.clear()  # Reset before waiting
await asyncio.wait_for(event.wait(), timeout=timeout)
```

### Summary file reading
```python
# In ws_server.py - when 'summary' message received
summary_content = self._read_summary_file(guid)  # Reads summary.md
message['data'] = summary_content
```

### UI loading state
- Controlled by HTTP request lifecycle in handleSendMessage
- NOT by WebSocket ack events (prevents init ack from blocking UI)
- Cleared when summary is received (task complete)

## Gotchas

- **websockets v16 API**: Handler is `async def handler(self, websocket)` - access path via `websocket.request.path`
- **notify.sh port**: Must match ws_server port (8082) - check `notify_template.sh` if WebSocket fails
- **GUID in localStorage**: Handle "null"/"undefined" strings, not just null
- **Init ack vs message ack**: Claude sends ack on init AND each message
- **Prompt caching**: Use timestamped filenames to force fresh reads
- **Summary format**: Claude writes to summary.md, backend reads it
- **tmux session name**: `tmux_builder_{guid}` format
- **Sessions path**: Project directory, NOT home directory

## Testing

```bash
# Start backend
cd backend && uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# Start frontend
cd frontend && npm run dev

# Test notify.sh manually (from session folder)
./notify.sh status "Testing from CLI"

# Test admin API
curl http://localhost:8000/api/admin/sessions?filter=all

# Test chat with existing session
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "guid": "<guid>"}'

# List tmux sessions
tmux list-sessions
```

## Session Folder Structure

```
sessions/active/<guid>/
├── system_prompt.txt      # Agent instructions (read once at init)
├── notify.sh              # Progress script (GUID baked in)
├── prompt_{timestamp}.txt # User message (unique per message)
├── summary.md             # Formatted completion summary
├── chat_history.jsonl     # Persisted chat
├── activity_log.jsonl     # Persisted activity log
├── status.json            # Session state
├── tmp/                   # Scratch work
├── code/                  # Generated code
├── infrastructure/        # IaC files
└── docs/                  # Documentation
```

## Claude Completion Flow

1. Claude finishes task
2. Claude writes formatted summary to `summary.md`
3. Claude calls `./notify.sh summary`
4. Backend reads `summary.md`, sends to frontend via WebSocket
5. Frontend displays markdown-rendered summary in chat
6. Claude calls `./notify.sh done`

## Deployment

### AWS Infrastructure

See `deployment/README.md` for complete documentation.

**Quick Reference:**
- **CloudFront URL**: https://d3r4k77gnvpmzn.cloudfront.net
- **EC2 IP**: 184.73.78.154 (may change on restart)
- **SSH**: `ssh ai-product-studio`
- **WebSocket**: wss://d3r4k77gnvpmzn.cloudfront.net/ws/{guid}

**Deployment Scripts:**
```bash
# Check infrastructure status
./deployment/aws-setup.sh show-status

# Full deployment to EC2
./deployment/ec2-deploy.sh deploy

# Restart services only
./deployment/ec2-deploy.sh restart

# Invalidate CloudFront cache
./deployment/ec2-deploy.sh invalidate
```

### Production Ports
| Service | Port | Notes |
|---------|------|-------|
| Frontend | 3001 | serve static dist |
| Backend API | 8080 | FastAPI |
| WebSocket | 8082 | ws_server.py (via CloudFront) |
| Nginx WSS | 8443 | SSL proxy fallback |

## Best Practices

### Infrastructure Changes
**IMPORTANT:** After making any AWS/infrastructure changes that work:
1. Document the changes in `deployment/README.md`
2. Update the deployment scripts if needed
3. Test the scripts can recreate the infrastructure
4. Commit the documentation changes

This ensures infrastructure is reproducible and documented.
