# Tmux Builder Architecture

Dual-channel WebSocket architecture with MCP-based progress communication.

## System Overview

Tmux Builder enables web UI interaction with Claude AI through isolated tmux sessions. The architecture uses **MCP (Model Context Protocol)** for real-time progress updates from Claude CLI to the browser.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           BROWSER (React UI)                                     │
│                                                                                  │
│  ┌────────────────────────────────────┬────────────────────────────────────────┐│
│  │      LEFT: Chat Panel              │      RIGHT: MCP Tools Log Panel        ││
│  │      (Channel 1)                   │      (Channel 2)                       ││
│  │                                    │                                        ││
│  │  User messages                     │  Real-time tool call log:              ││
│  │  Claude responses                  │  • notify_ack(guid)                    ││
│  │                                    │  • send_progress(guid, 50%)            ││
│  │                                    │  • send_status(guid, "Working...")     ││
│  │                                    │  • send_response(guid, content)        ││
│  │                                    │  • notify_complete(guid)               ││
│  └────────────┬───────────────────────┴──────────────────┬─────────────────────┘│
│               │                                          │                      │
│               │ HTTP + WebSocket                         │ WebSocket            │
│               │ Port 8000                                │ Port 8001            │
└───────────────┼──────────────────────────────────────────┼──────────────────────┘
                │                                          │
                ▼                                          ▼
┌───────────────────────────────────┐    ┌────────────────────────────────────────┐
│      FastAPI Backend              │    │      MCP Server (Python)               │
│      Port 8000                    │    │      Port 8001 (WebSocket)             │
│                                   │    │                                        │
│  • Session lifecycle              │    │  • Spawned by Claude CLI as subprocess │
│  • Tmux management                │    │  • stdio ↔ Claude CLI (MCP protocol)   │
│  • Write prompt.txt               │    │  • WebSocket ↔ UI (progress broadcast) │
│  • Send instruction via tmux      │    │  • Logs all tool calls                 │
│  • Wait for MCP signals           │    │                                        │
│                                   │    │  Available Tools:                      │
└─────────────┬─────────────────────┘    │  • notify_ack(guid)                    │
              │                          │  • send_progress(guid, percent)        │
              │ tmux send-keys           │  • send_status(guid, message, phase)   │
              ▼                          │  • send_response(guid, content)        │
┌─────────────────────────────────────────┤  • notify_complete(guid, success)      │
│              TMUX SESSION              │  • notify_error(guid, error)          │
│                                        └──────────────────┬─────────────────────┘
│    ┌──────────────────────────────────────────────────────┼───────────────────┐     │
│    │                     CLAUDE CLI                       │               │     │
│    │                                                      │ stdio (MCP)   │     │
│    │    Registered MCP server: tmux-progress              ▼               │     │
│    │    (auto-spawns mcp_server/server.py)                                │     │
│    │                                                                      │     │
│    │    On instruction, Claude:                                           │     │
│    │    1. Calls notify_ack(guid)                                         │     │
│    │    2. Calls send_progress/send_status as it works                    │     │
│    │    3. Calls send_response(guid, content) with result                 │     │
│    │    4. Calls notify_complete(guid)                                    │     │
│    └──────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Dual-Channel Architecture

### Channel 1: Chat (Port 8000)
- **Transport**: HTTP REST + WebSocket
- **Purpose**: Session management, message sending, response delivery
- **Flow**: UI → FastAPI Backend → tmux → Claude CLI

### Channel 2: Progress (Port 8001)
- **Transport**: WebSocket
- **Purpose**: Real-time progress updates, tool call logging
- **Flow**: Claude CLI → MCP Server → WebSocket → UI

## MCP Server Registration

The MCP server must be registered with Claude CLI before use:

```bash
# Run setup script
./scripts/setup-mcp.sh

# Or manually:
claude mcp add tmux-progress -- python3 /path/to/backend/mcp_server/server.py
```

## Message Flow

1. User types message in UI (left panel)
2. UI sends via HTTP POST to backend
3. Backend writes prompt.txt, sends tmux instruction with MCP tool guidance
4. Claude CLI processes and calls MCP tools:
   - `notify_ack(guid)` → Broadcast to UI
   - `send_progress(percent)` → Broadcast to UI
   - `send_response(content)` → Broadcast to UI
   - `notify_complete(success)` → Broadcast to UI
5. Backend detects completion via MCP server registry
6. Backend returns response via HTTP

## Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| React UI | Split-view chat + MCP log display |
| FastAPI Backend | Session lifecycle, tmux management |
| MCP Server | stdio ↔ Claude CLI, WebSocket broadcasts |
| TmuxHelper | Low-level tmux command execution |
| SessionController | Message orchestration with MCP protocol |
| SessionInitializer | Session creation with MCP health check |

## Configuration

Key configuration in `backend/config.py`:

```python
MCP_SERVER_NAME = 'tmux-progress'
MCP_WS_PORT = 8001
MCP_ACK_TIMEOUT = 30  # seconds
MCP_RESPONSE_TIMEOUT = 300  # seconds
```

## Setup Requirements

1. tmux installed and in PATH
2. Claude CLI installed and authenticated
3. MCP server registered via `scripts/setup-mcp.sh`
4. Backend running on port 8000
5. Frontend running (Vite dev server)
