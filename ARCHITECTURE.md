# Tmux Builder Architecture

Detailed technical architecture based on SmartDeploy/Builder-CLI project.

## System Overview

Tmux Builder is a web-based chat interface that enables users to interact with Claude AI through persistent tmux sessions. The architecture separates concerns across three main layers: **Frontend (React)**, **Backend (FastAPI)**, and **Session Management (tmux + Claude CLI)**.

## Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER BROWSER                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  React Frontend (Vite + Tailwind)                     │  │
│  │  - ChatInterface.jsx (state management)               │  │
│  │  - MessageList.jsx (display messages)                 │  │
│  │  - InputArea.jsx (capture input)                      │  │
│  │  - api.js (HTTP client)                               │  │
│  └───────────────────┬───────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────┘
                         │ HTTP/JSON
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python)                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  main.py - REST API Server                            │  │
│  │  ├─ POST /api/session/create                          │  │
│  │  ├─ GET  /api/status                                  │  │
│  │  ├─ POST /api/chat                                    │  │
│  │  ├─ GET  /api/history                                 │  │
│  │  └─ POST /api/clear                                   │  │
│  └───────────────────┬───────────────────────────────────┘  │
│                      │                                       │
│  ┌───────────────────▼───────────────────────────────────┐  │
│  │  session_controller.py - Session Orchestration        │  │
│  │  ├─ initialize_session()                              │  │
│  │  ├─ send_message()                                    │  │
│  │  ├─ get_chat_history()                                │  │
│  │  └─ clear_session()                                   │  │
│  └───────────────────┬───────────────────────────────────┘  │
│                      │                                       │
│  ┌───────────────────▼───────────────────────────────────┐  │
│  │  tmux_helper.py - Low-level tmux operations           │  │
│  │  ├─ create_session()                                  │  │
│  │  ├─ send_command()                                    │  │
│  │  ├─ kill_session()                                    │  │
│  │  └─ capture_pane_output()                             │  │
│  └───────────────────┬───────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────┘
                         │ tmux commands
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    tmux Session Layer                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Session: tmux_builder_default_user_<timestamp>       │  │
│  │  ├─ Pane 0: Claude CLI running                        │  │
│  │  └─ Working Dir: /sessions/default_user/              │  │
│  └───────────────────┬───────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Claude CLI Process                      │
│  - Receives messages via stdin (tmux send-keys)             │
│  - Processes with Claude AI model                           │
│  - Writes responses to chat_history.jsonl                   │
│  - Creates marker files for synchronization                 │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow: Sending a Message

### Step-by-Step Flow

1. **User Input (Frontend)**
   ```
   User types message → InputArea.jsx captures input → handleSendMessage()
   ```

2. **API Call**
   ```javascript
   api.sendMessage(message) → POST /api/chat
   ```

3. **Backend Processing**
   ```python
   main.py:chat() → SessionController.send_message(message)
   ```

4. **Save User Message**
   ```python
   # Append to chat_history.jsonl
   {"role":"user","content":"message","timestamp":"2026-01-23T..."}
   ```

5. **Clear Previous Marker**
   ```python
   # Remove old completed.marker
   sessions/default_user/markers/completed.marker → deleted
   ```

6. **Send to tmux**
   ```python
   TmuxHelper.send_command(session_name, message)
   ↓
   tmux send-keys -t session_name C-u  # Clear input
   tmux send-keys -t session_name -l "message"  # Send literally
   tmux send-keys -t session_name Enter  # Submit
   tmux send-keys -t session_name Enter  # WSL2 double-enter
   ```

7. **Claude Processes**
   ```
   Claude CLI receives message → Processes → Generates response
   ```

8. **Claude Writes Response**
   ```jsonl
   # Appended to chat_history.jsonl
   {"role":"assistant","content":"response","timestamp":"2026-01-23T..."}
   ```

9. **Claude Creates Marker**
   ```bash
   touch sessions/default_user/markers/completed.marker
   ```

10. **Backend Polls for Marker**
    ```python
    # Poll every 0.5s for up to 60s
    while time < 60s:
        if completed.marker exists:
            break
    ```

11. **Backend Reads Response**
    ```python
    # Read chat_history.jsonl
    messages = load_history()
    # Extract last assistant message
    response = get_last_assistant_message(messages)
    ```

12. **Return to Frontend**
    ```python
    return ChatResponse(success=True, response=response, timestamp=...)
    ```

13. **UI Update**
    ```javascript
    setMessages(prev => [...prev, assistantMessage])
    // React re-renders MessageList
    ```

## Marker-Based Synchronization

### Why Markers?

Marker files provide reliable inter-process communication (IPC) between the backend and Claude CLI:

- **Reliable**: File existence is atomic and cross-platform
- **Simple**: No parsing stdout or complex regex
- **WSL2 Compatible**: Works around timing issues
- **Stateless**: Each request creates fresh markers

### Marker Types

| Marker File | Purpose | Created By | Polled By |
|-------------|---------|------------|-----------|
| `initialized.marker` | Session ready | Claude CLI | Backend (on init) |
| `processing.marker` | Request in progress | Claude CLI | Backend (optional) |
| `completed.marker` | Response ready | Claude CLI | Backend (on message) |

### Marker Lifecycle

```
Backend sends message
    ↓
Delete old completed.marker
    ↓
Send message to tmux
    ↓
[Claude processes...]
    ↓
Claude creates completed.marker
    ↓
Backend detects marker (polling)
    ↓
Backend reads response from JSONL
    ↓
Delete completed.marker (next request)
```

## Persistence: JSONL Format

### Chat History Structure

**File**: `sessions/default_user/chat_history.jsonl`

```jsonl
{"role":"user","content":"Hello Claude","timestamp":"2026-01-23T10:30:00Z"}
{"role":"assistant","content":"Hello! How can I help you?","timestamp":"2026-01-23T10:30:02Z"}
{"role":"user","content":"What is tmux?","timestamp":"2026-01-23T10:31:00Z"}
{"role":"assistant","content":"tmux is a terminal multiplexer...","timestamp":"2026-01-23T10:31:03Z"}
```

### Benefits of JSONL

- **Append-only**: Fast writes, no need to rewrite entire file
- **Simple parsing**: One line = one message
- **Human readable**: Easy to debug and inspect
- **Robust**: Partial writes don't corrupt previous messages
- **Streaming friendly**: Can read while writing

## Session Lifecycle

### Session Creation

```
1. User clicks "Create Session"
   ↓
2. POST /api/session/create
   ↓
3. SessionController.initialize_session()
   ├─ Kill old sessions
   ├─ Create tmux session: tmux_builder_default_user_<timestamp>
   ├─ Start Claude CLI in session
   ├─ Send initialization instructions
   └─ Wait for initialized.marker (60s timeout)
   ↓
4. Frontend polls /api/status every 2s
   ↓
5. When status.ready == true:
   ├─ Load chat history
   └─ Enable input area
```

### Active Session

```
Session ready
    ↓
User sends messages → Backend → tmux → Claude → Response
    ↓
Repeat...
```

### Session Cleanup

```
1. User clicks "Clear Chat"
   ↓
2. POST /api/clear
   ↓
3. SessionController.clear_session()
   ├─ tmux kill-session
   ├─ Delete chat_history.jsonl
   ├─ Clear all markers
   └─ Reset session state
```

## WSL2 Compatibility

### Double-Enter Pattern

WSL2 has timing issues with long inputs to tmux. Solution:

```python
# Send message
tmux send-keys -l "long message here..."
time.sleep(2.0)  # Wait for text to appear
tmux send-keys Enter  # First Enter
time.sleep(3.0)  # Wait before second
tmux send-keys Enter  # Second Enter (ensures submission)
```

### Why This Works

- WSL2 has input buffering delays
- Long messages may not fully render before Enter
- Double-enter ensures the full message is submitted
- Timing delays allow tmux pane to catch up

## Configuration

### Backend Config (`backend/config.py`)

```python
# Timeouts
MARKER_TIMEOUT = 60  # Wait up to 60s for response
MARKER_POLL_INTERVAL = 0.5  # Check every 0.5s

# Timing (WSL2)
SEND_COMMAND_WAIT = 2.0  # Wait after sending text
SEND_COMMAND_ENTER_WAIT = 3.0  # Wait before second enter

# Paths
SESSIONS_DIR = BASE_DIR / "sessions"
DEFAULT_USER = "default_user"
```

## Error Handling

### Timeout Handling

```python
if not self._wait_for_marker(COMPLETED_MARKER, timeout=60):
    return "Timeout waiting for response. Please try again."
```

### Session Validation

```python
if not session_controller.is_active():
    raise HTTPException(400, "Session is not active")
```

### Frontend Error Display

```javascript
catch (err) {
    const errorMessage = {
        role: 'assistant',
        content: `Error: ${err.response?.data?.detail}`,
        timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, errorMessage]);
}
```

## Security Considerations

### Current Implementation (Development)

- No authentication
- No rate limiting
- CORS allows localhost only
- Single-user design

### Production Recommendations

1. **Authentication**: Add user login and session management
2. **Authorization**: Isolate users' tmux sessions and data
3. **Rate Limiting**: Prevent abuse of Claude API
4. **Input Validation**: Sanitize user messages
5. **HTTPS**: Encrypt traffic
6. **Secrets Management**: Store Claude API keys securely

## Performance Characteristics

### Latency Sources

| Component | Typical Latency |
|-----------|----------------|
| Frontend → Backend | 10-50ms |
| Backend → tmux | 10-100ms |
| Claude processing | 1-10s |
| Marker polling overhead | 500ms max |
| JSONL read/write | <10ms |

### Scalability

**Current design**: Single-user, single-session

**Multi-user scaling**:
- One tmux session per user
- Shared backend can handle multiple concurrent sessions
- JSONL files isolated per user
- Markers namespaced by user ID

## Future Enhancements

1. **Multi-user support**: User authentication and isolation
2. **File uploads**: Implement file attachment handling
3. **Screenshot capture**: Enable screenshot sharing (like SmartDeploy)
4. **Session persistence**: Save/restore sessions across restarts
5. **Real-time updates**: WebSocket for live responses (no polling)
6. **Advanced features**: Code execution, web search, tool use

## Key Differences from SmartDeploy

This implementation is a **simplified version** of SmartDeploy/Builder-CLI:

| Feature | SmartDeploy | Tmux Builder |
|---------|-------------|--------------|
| File uploads | ✅ Full support | ❌ Not implemented |
| Screenshots | ✅ html2canvas | ❌ Not implemented |
| Session meta | ✅ session.meta.json | ❌ Simplified |
| User management | ✅ Multi-user | ⚠️ Single user (default_user) |
| Uploads dir | ✅ Persistent uploads | ❌ Not needed (no uploads) |
| Error recovery | ✅ Robust | ⚠️ Basic |

## Conclusion

Tmux Builder demonstrates the core architecture pattern from SmartDeploy: **web UI → API → tmux → Claude CLI → marker-based sync → JSONL persistence**. This pattern enables stateful, persistent conversations with Claude through a clean web interface while leveraging tmux for process isolation and management.
