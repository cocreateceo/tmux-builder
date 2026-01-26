# PTY + WebSocket Streaming Implementation Plan

## Overview
Replace file-based marker protocol with PTY + WebSocket streaming (like claude-code-web).
Keep status.json for progress tracking. Remove marker files.

## Architecture

```
Browser (xterm.js)
    ↕ WebSocket
FastAPI Server (with WebSocket endpoint)
    ↕ node-pty (or Python pty)
Claude Code CLI Process
```

## What Changes

| Component | Before (markers) | After (streaming) |
|-----------|------------------|-------------------|
| Session start | tmux + markers | PTY spawn |
| Communication | File polling | WebSocket streaming |
| User input | File write → instruction | Direct PTY input |
| Output | Capture pane → file | Real-time stream |
| Status tracking | status.json + markers | status.json only |

## Tasks

### Task 1: Add WebSocket dependencies
- Add `websockets` package to requirements.txt
- Add `ptyprocess` for Python PTY handling
- Verify imports work

### Task 2: Create PTY manager module
- Create `backend/pty_manager.py`
- Class to spawn Claude CLI process via PTY
- Methods: create_session, send_input, read_output, kill_session
- Handle process lifecycle

### Task 3: Create WebSocket endpoint
- Add WebSocket route to FastAPI (`/ws/{session_id}`)
- Handle connection, disconnection
- Bridge PTY output → WebSocket
- Bridge WebSocket input → PTY

### Task 4: Create session streaming controller
- Create `backend/stream_controller.py`
- Manage PTY sessions by GUID
- Track active connections
- Handle reconnection (buffer last N lines)

### Task 5: Update frontend for streaming
- Add xterm.js to frontend
- Connect to WebSocket endpoint
- Render terminal output
- Send user input

### Task 6: Update session initialization
- Modify `session_initializer.py` to use PTY instead of tmux
- Remove marker file logic
- Keep status.json updates

### Task 7: Remove marker dependencies
- Remove `marker_utils.py` imports
- Remove marker-related config
- Clean up old marker code

### Task 8: Integration testing
- Test session creation via PTY
- Test WebSocket streaming
- Test input/output flow
- Test reconnection

## Verification
- [ ] WebSocket connects successfully
- [ ] Claude CLI output streams to browser
- [ ] User input reaches Claude CLI
- [ ] status.json still updates
- [ ] Sessions can be reconnected

## Files to Create
- `backend/pty_manager.py`
- `backend/stream_controller.py`
- `frontend/src/components/Terminal.tsx` (or update existing)

## Files to Modify
- `backend/requirements.txt`
- `backend/main.py`
- `backend/session_initializer.py`
- `backend/config.py`

## Files to Remove/Deprecate
- `backend/marker_utils.py` (keep for reference, mark deprecated)
