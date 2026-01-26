# File-Based Protocol Issues

**Date:** 2026-01-26
**Status:** Deprecated - Moving to WebSocket-based MCP approach

## Overview

This document captures the issues discovered with the file-based marker protocol and why we're transitioning to a WebSocket-based MCP approach.

## What Was Implemented

The file-based REPL protocol used marker files for synchronization:

```
sessions/active/{guid}/
├── markers/
│   ├── ready.marker      # Claude creates when ready
│   ├── ack.marker        # Claude creates when prompt received
│   └── completed.marker  # Claude creates when done
├── prompt.txt            # Backend writes, Claude reads
├── completion.txt        # Claude writes response
├── chat_history.jsonl    # Conversation log
└── status.json           # Progress tracking
```

## Issues Discovered

### 1. WSL Filesystem Latency (Critical)

**Problem:** WSL has ~6 second delays for file visibility across process boundaries.

- Backend creates/deletes a file
- Claude CLI (in tmux) doesn't see the change for up to 6 seconds
- This caused timeout failures even when operations succeeded

**Impact:** Marker detection unreliable, required increasing timeouts significantly.

### 2. Response Read Location Mismatch (Critical)

**Problem:** Documentation and code disagreed on where responses should be written/read.

| Source | Says Response Goes To |
|--------|----------------------|
| ARCHITECTURE.md | `chat_history.jsonl` |
| file-based-repl-protocol-design.md | `chat_history.jsonl` |
| autonomous_agent.txt (prompt) | `completion.txt` |
| session_controller.py | Reads from `chat_history.jsonl` |

**Result:** Claude wrote to `completion.txt`, backend read from `chat_history.jsonl` → "No response received"

### 3. Race Conditions with Delete/Create Cycles

**Problem:** The protocol required clearing markers before each request:

```python
# Backend clears markers
delete_marker(guid, ACK_MARKER)
delete_marker(guid, COMPLETED_MARKER)

# Then sends instruction for Claude to create them
# But: Did delete succeed? Did Claude see the cleared state?
```

**Impact:** No confirmation that operations succeeded, leading to stale marker detection.

### 4. Polling Inefficiency

**Problem:** Backend polls for file existence every 0.5-2 seconds.

```python
while not marker_exists:
    sleep(poll_interval)
    check_file()
```

**Impact:**
- CPU waste during long operations
- Delayed response detection (up to poll_interval latency)
- No real-time progress updates to UI

### 5. No Guaranteed Delivery

**Problem:** File operations have no acknowledgment mechanism.

- Backend writes `prompt.txt` - did Claude read it?
- Claude creates `ack.marker` - did backend see it?
- No way to confirm receipt without another round-trip

### 6. Session Initialization Complexity

**Problem:** Multi-step handshake with retries:

```
1. Send "touch ready.marker"
2. Wait for ready.marker (30s timeout)
3. Write system_prompt.txt
4. Send "read and create ack.marker"
5. Wait for ack.marker (30s timeout, 3 retries)
```

**Result:** Session creation took 30-90 seconds, often failed on first attempt.

## What Works

Despite issues, some parts function correctly:

- ✅ Tmux session creation and management
- ✅ Claude CLI execution in isolated sessions
- ✅ WebSocket connection between UI and backend
- ✅ Basic message flow (when timeouts don't occur)
- ✅ Status.json progress tracking (Claude writes correctly)
- ✅ Completion.txt response writing (Claude writes correctly)

## Root Cause

**Filesystem as IPC is fundamentally flawed for this use case:**

1. No atomicity guarantees for multi-file operations
2. No notification mechanism (must poll)
3. Platform-specific timing issues (WSL)
4. No delivery confirmation

## Solution: WebSocket-based MCP Approach

Instead of file-based communication, we're implementing:

1. **MCP Server** that exposes tools to Claude CLI
2. **Direct WebSocket** from MCP Server to UI for progress
3. **Two channels:**
   - Channel 1: UI ↔ Backend (chat request/response)
   - Channel 2: UI ↔ MCP Server (real-time progress)

### Benefits

| File-Based | WebSocket/MCP |
|------------|---------------|
| 6s+ latency (WSL) | <100ms latency |
| Polling | Push notifications |
| No delivery confirmation | WebSocket acknowledgment |
| Race conditions | Ordered message delivery |
| Platform-dependent | Platform-independent |

## Files to Preserve

The following can be reused in the new implementation:

- `tmux_helper.py` - Tmux session management
- `prompt_manager.py` - Prompt template rendering
- `config.py` - Configuration (with modifications)
- Frontend WebSocket hook - Already implemented

## Files to Replace

- `session_initializer.py` - New MCP-based initialization
- `session_controller.py` - New MCP-based message handling
- `marker_utils.py` - No longer needed
- `main.py` - Updated endpoints for new flow

## Next Steps

See `docs/plans/2026-01-26-websocket-mcp-protocol-design.md` for the new architecture.
