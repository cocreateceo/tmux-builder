# WebSocket MCP Protocol Design

**Date:** 2026-01-26
**Status:** Proposed
**Replaces:** File-based REPL protocol

## Overview

This design replaces the file-based marker protocol with a WebSocket-based MCP (Model Context Protocol) approach. Claude CLI communicates directly via MCP tools, and the MCP server broadcasts to the UI in real-time.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                  │
│                                                                              │
│   ┌──────────────────────┐          ┌──────────────────────┐                │
│   │  Channel 1: Chat     │          │  Channel 2: Progress │                │
│   │  (request/response)  │          │  (real-time status)  │                │
│   └──────────┬───────────┘          └──────────┬───────────┘                │
└──────────────┼──────────────────────────────────┼────────────────────────────┘
               │                                  │
               │ WebSocket                        │ WebSocket
               │ ws://localhost:8000/ws/{guid}    │ ws://localhost:8001/ws/{guid}
               │                                  │
               v                                  v
┌──────────────────────────┐          ┌──────────────────────────────────────┐
│                          │          │                                      │
│    FASTAPI BACKEND       │          │    MCP SERVER (Python)               │
│    Port 8000             │          │    Port 8001                         │
│                          │          │                                      │
│  Responsibilities:       │          │  Responsibilities:                   │
│  • Session lifecycle     │          │  • Expose MCP tools to CLI           │
│  • Tmux management       │          │  • WebSocket server for UI           │
│  • Send prompts to CLI   │          │  • Broadcast progress real-time      │
│  • Receive final response│          │  • Session-aware routing             │
│                          │          │                                      │
└──────────┬───────────────┘          │  MCP Tools:                          │
           │                          │  • notify_ack(guid)                  │
           │                          │  • send_progress(guid, %)            │
           │                          │  • send_status(guid, message)        │
           │                          │  • send_response(guid, content)      │
           │                          │  • notify_complete(guid)             │
           │                          │  • notify_error(guid, error)         │
           │                          │                                      │
           │ tmux send-keys           └──────────────────┬───────────────────┘
           │                                             │
           v                                             │
┌──────────────────────────────────────────────────────────────────────────────┐
│                           TMUX SESSION                                       │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │   CLAUDE CLI                                                           │ │
│  │                                                                        │ │
│  │   Started with: claude --mcp-server tmux-progress                      │ │
│  │                                                                        │ │
│  │   Has access to MCP tools:                                             │ │
│  │   • notify_ack(guid) - "I received the prompt"                         │ │
│  │   • send_progress(guid, percent) - "I'm X% done"                       │ │
│  │   • send_status(guid, message) - "Currently doing Y"                   │ │
│  │   • send_response(guid, content) - "Here's my response"                │ │
│  │   • notify_complete(guid) - "I'm finished"                             │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Communication Flow

### Session Initialization

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│    UI    │     │ Backend  │     │   MCP    │     │  Claude  │
│          │     │          │     │  Server  │     │   CLI    │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │ 1. Create      │                │                │
     │    Session     │                │                │
     │───────────────>│                │                │
     │                │                │                │
     │                │ 2. Create tmux │                │
     │                │    session     │                │
     │                │───────────────────────────────>│
     │                │                │                │
     │                │ 3. Start CLI   │                │
     │                │    with MCP    │                │
     │                │───────────────────────────────>│
     │                │                │                │
     │                │                │ 4. CLI connects│
     │                │                │<───────────────│
     │                │                │    to MCP      │
     │                │                │                │
     │ 5. Connect     │                │                │
     │    Channel 1   │                │                │
     │<───────────────│                │                │
     │                │                │                │
     │ 6. Connect Channel 2            │                │
     │────────────────────────────────>│                │
     │                │                │                │
     │                │ 7. Return      │                │
     │ 8. Session     │    ready       │                │
     │    ready       │<───────────────│                │
     │<───────────────│                │                │
     │                │                │                │
```

### Message Flow (Request → Response)

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│    UI    │     │ Backend  │     │   MCP    │     │  Claude  │
│          │     │          │     │  Server  │     │   CLI    │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │ 1. Send msg    │                │                │
     │   (Channel 1)  │                │                │
     │───────────────>│                │                │
     │                │                │                │
     │                │ 2. Write       │                │
     │                │    prompt.txt  │                │
     │                │───────────────────────────────>│
     │                │                │                │
     │                │ 3. Send tmux   │                │
     │                │    instruction │                │
     │                │───────────────────────────────>│
     │                │                │                │
     │                │                │ 4. notify_ack()│
     │                │                │<───────────────│
     │                │                │                │
     │ 5. ACK         │                │                │
     │   (Channel 2)  │                │                │
     │<────────────────────────────────│                │
     │                │                │                │
     │                │                │ 6. send_       │
     │                │                │    progress(25)│
     │                │                │<───────────────│
     │ 7. Progress 25%│                │                │
     │<────────────────────────────────│                │
     │                │                │                │
     │                │                │ 8. send_       │
     │                │                │    status(msg) │
     │                │                │<───────────────│
     │ 9. Status msg  │                │                │
     │<────────────────────────────────│                │
     │                │                │                │
     │                │                │ ...more progress│
     │                │                │                │
     │                │                │ 10. send_      │
     │                │                │    response()  │
     │                │                │<───────────────│
     │                │                │                │
     │                │                │ 11. notify_    │
     │                │                │    complete()  │
     │                │                │<───────────────│
     │                │                │                │
     │ 12. Complete   │                │                │
     │   (Channel 2)  │                │                │
     │<────────────────────────────────│                │
     │                │                │                │
     │                │ 13. Read       │                │
     │                │   response     │                │
     │                │<───────────────│                │
     │                │                │                │
     │ 14. Response   │                │                │
     │   (Channel 1)  │                │                │
     │<───────────────│                │                │
     │                │                │                │
```

## MCP Server Implementation

### Tools Specification

```python
# mcp_server/tools.py

TOOLS = [
    {
        "name": "notify_ack",
        "description": "Signal that you received and understood the prompt",
        "parameters": {
            "guid": {"type": "string", "description": "Session GUID"}
        }
    },
    {
        "name": "send_progress",
        "description": "Report progress percentage (0-100)",
        "parameters": {
            "guid": {"type": "string", "description": "Session GUID"},
            "percent": {"type": "integer", "minimum": 0, "maximum": 100}
        }
    },
    {
        "name": "send_status",
        "description": "Send human-readable status message",
        "parameters": {
            "guid": {"type": "string", "description": "Session GUID"},
            "message": {"type": "string"},
            "phase": {"type": "string", "enum": ["analyzing", "planning", "implementing", "deploying", "verifying"]}
        }
    },
    {
        "name": "send_response",
        "description": "Send the response content to the user",
        "parameters": {
            "guid": {"type": "string", "description": "Session GUID"},
            "content": {"type": "string", "description": "Response text"}
        }
    },
    {
        "name": "notify_complete",
        "description": "Signal that processing is complete",
        "parameters": {
            "guid": {"type": "string", "description": "Session GUID"},
            "success": {"type": "boolean", "default": true}
        }
    },
    {
        "name": "notify_error",
        "description": "Report an error condition",
        "parameters": {
            "guid": {"type": "string", "description": "Session GUID"},
            "error": {"type": "string"},
            "recoverable": {"type": "boolean", "default": false}
        }
    }
]
```

### WebSocket Protocol

```typescript
// Messages from MCP Server to UI (Channel 2)

interface AckMessage {
    type: "ack";
    guid: string;
    timestamp: string;
}

interface ProgressMessage {
    type: "progress";
    guid: string;
    percent: number;
    timestamp: string;
}

interface StatusMessage {
    type: "status";
    guid: string;
    message: string;
    phase: string;
    timestamp: string;
}

interface ResponseMessage {
    type: "response";
    guid: string;
    content: string;
    timestamp: string;
}

interface CompleteMessage {
    type: "complete";
    guid: string;
    success: boolean;
    timestamp: string;
}

interface ErrorMessage {
    type: "error";
    guid: string;
    error: string;
    recoverable: boolean;
    timestamp: string;
}
```

## File Structure

```
backend/
├── main.py                    # FastAPI backend (Channel 1)
├── mcp_server/
│   ├── __init__.py
│   ├── server.py              # MCP server + WebSocket (Channel 2)
│   ├── tools.py               # MCP tool definitions
│   ├── websocket_manager.py   # WebSocket connection manager
│   └── session_registry.py    # Track active sessions
├── session_controller.py      # Simplified - no marker polling
├── tmux_helper.py             # Unchanged
├── prompt_manager.py          # Unchanged
└── config.py                  # Add MCP server config

frontend/
├── src/
│   ├── hooks/
│   │   ├── useWebSocket.js    # Channel 1 (existing)
│   │   └── useProgressSocket.js  # Channel 2 (new)
│   └── components/
│       └── ChatInterface.jsx  # Use both channels
```

## Configuration

### Claude CLI MCP Configuration

```json
// ~/.config/claude/mcp_servers.json
{
    "tmux-progress": {
        "command": "python",
        "args": ["/path/to/mcp_server/server.py"],
        "transport": "stdio"
    }
}
```

### Starting Claude CLI with MCP

```bash
# In tmux session
claude --mcp-server tmux-progress --dangerously-skip-permissions
```

## Session Lifecycle

### Creation

1. Backend creates tmux session
2. Backend starts MCP server (if not running)
3. Backend starts Claude CLI with `--mcp-server tmux-progress`
4. UI connects to both WebSocket channels
5. Session ready

### Message Processing

1. UI sends message via Channel 1 (Backend)
2. Backend writes prompt.txt
3. Backend sends tmux instruction: "Read prompt.txt, use MCP tools to report progress"
4. Claude calls `notify_ack()` - UI receives via Channel 2
5. Claude processes, calling `send_progress()` and `send_status()` periodically
6. Claude calls `send_response()` with content
7. Claude calls `notify_complete()`
8. Backend reads response from MCP server's cache
9. Backend sends final response via Channel 1

### Cleanup

1. Backend kills tmux session
2. MCP server cleans up session state
3. UI disconnects from both channels

## Error Handling

| Error | Detection | Recovery |
|-------|-----------|----------|
| MCP server crash | WebSocket disconnect | Auto-restart MCP server |
| Claude CLI crash | No activity timeout | Notify UI, offer retry |
| Network disconnect | WebSocket close event | Auto-reconnect with backoff |
| Invalid GUID | MCP tool validation | Return error to CLI |

## Benefits Over File-Based

| Aspect | File-Based | WebSocket/MCP |
|--------|------------|---------------|
| Latency | 6+ seconds (WSL) | <100ms |
| Delivery confirmation | None | WebSocket ACK |
| Progress updates | Polling status.json | Real-time push |
| Race conditions | Possible | Ordered messages |
| Debugging | Check multiple files | Single message stream |
| Platform dependency | WSL issues | None |

## Implementation Phases

### Phase 1: MCP Server Core
- [ ] Create MCP server with stdio transport
- [ ] Implement tool handlers
- [ ] Add WebSocket server for UI

### Phase 2: Backend Integration
- [ ] Update session_controller to use MCP
- [ ] Remove marker file logic
- [ ] Add MCP server lifecycle management

### Phase 3: Frontend Integration
- [ ] Create useProgressSocket hook
- [ ] Update ChatInterface for dual channels
- [ ] Add progress UI components

### Phase 4: Testing & Documentation
- [ ] Integration tests
- [ ] Update all documentation
- [ ] Performance benchmarks

## Open Questions

1. **MCP Server Lifecycle:** One global server or per-session?
   - Recommendation: One global server, session-aware routing

2. **Response Delivery:** Via MCP only or also write to file?
   - Recommendation: MCP primary, file backup for debugging

3. **Prompt Delivery:** Keep prompt.txt or send via MCP?
   - Recommendation: Keep prompt.txt for simplicity (tmux send-keys has limits)
