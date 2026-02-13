# Dual-Channel MCP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace file-based marker protocol with MCP-based dual WebSocket channels for real-time progress from Claude CLI to UI.

**Architecture:** Claude CLI auto-spawns our MCP server (registered via `claude mcp add`). MCP server handles stdio from CLI and broadcasts to UI via WebSocket. Single web UI with split view: chat on left, MCP tool logs on right.

**Tech Stack:** Python (FastAPI, websockets, MCP protocol), React (Vite), WebSocket

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           BROWSER (React UI)                                     │
│                                                                                  │
│  ┌────────────────────────────────┬────────────────────────────────────────┐    │
│  │      LEFT: Chat Panel          │      RIGHT: MCP Tools Log Panel        │    │
│  │      (Channel 1)               │      (Channel 2)                       │    │
│  │                                │                                        │    │
│  │  User messages                 │  Real-time tool call log:              │    │
│  │  Claude responses              │  • notify_ack(guid)                    │    │
│  │                                │  • send_progress(guid, 50%)            │    │
│  │                                │  • send_status(guid, "Working...")     │    │
│  │                                │  • send_response(guid, content)        │    │
│  │                                │  • notify_complete(guid)               │    │
│  └────────────┬───────────────────┴──────────────────┬─────────────────────┘    │
│               │                                      │                          │
│               │ useWebSocket                         │ useProgressSocket        │
│               │ ws://localhost:8000/ws/{guid}        │ ws://localhost:8001/ws/{guid}
└───────────────┼──────────────────────────────────────┼──────────────────────────┘
                │                                      │
                ▼                                      ▼
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
              │                          │  • send_response(guid, content)        │
              ▼                          │  • notify_complete(guid, success)      │
┌─────────────────────────────────────────┤  • notify_error(guid, error)          │
│              TMUX SESSION              │                                        │
│                                        └──────────────────┬─────────────────────┘
│    ┌──────────────────────────────────────────────────────┼───────────────┐     │
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
│    │                                                                      │     │
│    └──────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Message Flow

```
1. User types message in UI (left panel)
   │
2. UI sends via Channel 1 (WebSocket port 8000)
   │
3. Backend receives, writes prompt.txt
   │
4. Backend sends tmux instruction with GUID:
   │  "Read prompt.txt. Use MCP tools: notify_ack(guid='...'),
   │   send_progress(...), send_response(...), notify_complete(...)"
   │
5. Claude CLI processes and calls MCP tools:
   │
   ├─→ notify_ack(guid) ──→ MCP Server ──→ Channel 2 ──→ UI (right panel logs)
   ├─→ send_progress(25%) ─→ MCP Server ──→ Channel 2 ──→ UI (right panel logs)
   ├─→ send_status("...") ─→ MCP Server ──→ Channel 2 ──→ UI (right panel logs)
   ├─→ send_response(...) ─→ MCP Server ──→ Channel 2 ──→ UI (right panel logs)
   └─→ notify_complete() ──→ MCP Server ──→ Channel 2 ──→ UI (right panel logs)
   │
6. Backend detects notify_complete via MCP server registry
   │
7. Backend reads response from MCP server cache
   │
8. Backend sends response via Channel 1 ──→ UI (left panel chat)
```

---

## Task 1: Register MCP Server with Claude CLI

**Files:**
- Create: `scripts/setup-mcp.sh`
- Verify: `backend/mcp_server/server.py` (already exists)

**Step 1: Create setup script**

```bash
#!/bin/bash
# scripts/setup-mcp.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PATH="$SCRIPT_DIR/../backend/mcp_server/server.py"

echo "Registering MCP server with Claude CLI..."
echo "Server path: $SERVER_PATH"

# Remove existing registration if any
claude mcp remove tmux-progress 2>/dev/null || true

# Register our MCP server
claude mcp add tmux-progress -- python3 "$SERVER_PATH"

echo "Verifying registration..."
claude mcp list

echo "Done! MCP server 'tmux-progress' is now registered."
```

**Step 2: Run setup script**

```bash
chmod +x scripts/setup-mcp.sh
./scripts/setup-mcp.sh
```

**Step 3: Verify registration**

```bash
claude mcp list
# Expected: tmux-progress listed
```

**Step 4: Commit**

```bash
git add scripts/setup-mcp.sh
git commit -m "feat: add MCP server registration script"
```

---

## Task 2: Update MCP Server for Tool Call Logging

**Files:**
- Modify: `backend/mcp_server/server.py`
- Modify: `backend/mcp_server/websocket_manager.py`

**Step 1: Add tool call logging to server.py**

In `handle_tool_call()`, add logging that gets broadcast to UI:

```python
async def handle_tool_call(self, name: str, arguments: dict) -> dict:
    """Handle an MCP tool call from Claude CLI."""
    guid = arguments.get('guid', '')
    timestamp = datetime.utcnow().isoformat() + 'Z'

    if not guid:
        return {"success": False, "error": "GUID is required"}

    # Ensure session exists
    if not self.session_registry.session_exists(guid):
        self.session_registry.register_session(guid)

    result = {"success": True}

    # Log the tool call for UI display
    log_entry = {
        "type": "tool_call",
        "tool": name,
        "arguments": arguments,
        "timestamp": timestamp
    }

    if name == "notify_ack":
        self.session_registry.set_ack(guid)
        await self.ws_manager.send_ack(guid)
        await self.ws_manager.send_tool_log(guid, log_entry)
        result["message"] = "Acknowledgment sent"

    elif name == "send_progress":
        percent = arguments.get('percent', 0)
        self.session_registry.set_progress(guid, percent)
        await self.ws_manager.send_progress(guid, percent)
        await self.ws_manager.send_tool_log(guid, log_entry)
        result["message"] = f"Progress updated to {percent}%"

    elif name == "send_status":
        message = arguments.get('message', '')
        phase = arguments.get('phase', '')
        self.session_registry.set_status(guid, message, phase)
        await self.ws_manager.send_status(guid, message, phase)
        await self.ws_manager.send_tool_log(guid, log_entry)
        result["message"] = f"Status updated: {message}"

    elif name == "send_response":
        content = arguments.get('content', '')
        self.session_registry.set_response(guid, content)
        await self.ws_manager.send_response(guid, content)
        await self.ws_manager.send_tool_log(guid, log_entry)
        result["message"] = "Response sent"

    elif name == "notify_complete":
        success = arguments.get('success', True)
        self.session_registry.set_complete(guid, success)
        await self.ws_manager.send_complete(guid, success)
        await self.ws_manager.send_tool_log(guid, log_entry)
        result["message"] = "Completion notified"

    elif name == "notify_error":
        error = arguments.get('error', 'Unknown error')
        recoverable = arguments.get('recoverable', False)
        self.session_registry.set_error(guid, error, recoverable)
        await self.ws_manager.send_error(guid, error, recoverable)
        await self.ws_manager.send_tool_log(guid, log_entry)
        result["message"] = f"Error reported: {error}"

    else:
        result = {"success": False, "error": f"Unknown tool: {name}"}

    logger.info(f"Tool call: {name}({guid}) -> {result.get('message', result.get('error'))}")
    return result
```

**Step 2: Add send_tool_log to websocket_manager.py**

```python
async def send_tool_log(self, guid: str, log_entry: dict) -> int:
    """Send tool call log entry to UI."""
    return await self.broadcast(guid, {
        "type": "tool_log",
        "guid": guid,
        **log_entry
    })
```

**Step 3: Commit**

```bash
git add backend/mcp_server/server.py backend/mcp_server/websocket_manager.py
git commit -m "feat: add MCP tool call logging for UI display"
```

---

## Task 3: Update Session Controller for MCP-Based Protocol

**Files:**
- Modify: `backend/session_controller.py`

**Step 1: Replace file-based marker waiting with MCP-based**

```python
"""
High-level session orchestration with MCP-based protocol.

Message Loop Protocol:
1. Backend writes prompt to prompt.txt
2. Backend sends instruction with MCP tool usage instructions
3. Claude calls notify_ack() via MCP
4. Claude processes, calling send_progress/send_status
5. Claude calls send_response() with content
6. Claude calls notify_complete()
7. Backend reads response from MCP server cache
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

from config import (
    SESSION_PREFIX,
    CHAT_HISTORY_FILE,
    PROMPT_FILE,
    STATUS_FILE,
    ACTIVE_SESSIONS_DIR,
    get_prompt_file,
    get_status_file,
)
from tmux_helper import TmuxHelper
from mcp_server import (
    register_session,
    reset_session,
    wait_for_ack,
    wait_for_response,
    get_response,
)

logger = logging.getLogger(__name__)

# Timeouts for MCP-based protocol
MCP_ACK_TIMEOUT = 30  # seconds
MCP_RESPONSE_TIMEOUT = 300  # seconds


class SessionController:
    """Manages Claude CLI sessions via tmux with MCP-based protocol."""

    def __init__(self, guid: str):
        """Initialize SessionController for a GUID-based session."""
        logger.info(f"Initializing SessionController for GUID: {guid}")
        self.guid = guid
        self.session_path = ACTIVE_SESSIONS_DIR / guid
        self.chat_history_path = self.session_path / CHAT_HISTORY_FILE
        self.prompt_file_path = get_prompt_file(guid)
        self.status_file_path = get_status_file(guid)
        self.session_name = f"{SESSION_PREFIX}_{guid}"

        # Register session with MCP server
        register_session(guid)

        logger.info(f"Session path: {self.session_path}")
        logger.info(f"Session name: {self.session_name}")

    def send_message(self, message: str, timeout: float = MCP_RESPONSE_TIMEOUT) -> Optional[str]:
        """
        Send a message to Claude using MCP-based protocol.

        Protocol:
        1. Reset MCP session state
        2. Write message to prompt.txt
        3. Send instruction with MCP tool usage
        4. Wait for notify_ack via MCP
        5. Wait for notify_complete via MCP
        6. Read response from MCP cache
        """
        logger.info("=== SENDING MESSAGE (MCP Protocol) ===")
        logger.info(f"Message: {message[:100]}...")

        try:
            # Step 1: Reset MCP session state
            logger.info("Step 1: Resetting MCP session state...")
            reset_session(self.guid)

            # Step 2: Append user message to history
            logger.info("Step 2: Appending user message to history...")
            self._append_to_history("user", message)

            # Step 3: Write message to prompt.txt
            logger.info("Step 3: Writing prompt to file...")
            self.prompt_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.prompt_file_path.write_text(message)

            # Step 4: Build instruction with MCP tool usage
            instruction = self._build_mcp_instruction()

            # Step 5: Send instruction via tmux
            logger.info("Step 5: Sending instruction via tmux...")
            if not TmuxHelper.send_instruction(self.session_name, instruction):
                logger.error("Failed to send instruction via tmux")
                return None

            # Step 6: Wait for ack via MCP (async in sync context)
            logger.info(f"Step 6: Waiting for MCP ack (timeout: {MCP_ACK_TIMEOUT}s)...")
            loop = asyncio.new_event_loop()
            try:
                ack_received = loop.run_until_complete(
                    wait_for_ack(self.guid, timeout=MCP_ACK_TIMEOUT)
                )
            finally:
                loop.close()

            if not ack_received:
                logger.error("Failed to receive MCP ack")
                return "Claude did not acknowledge the message. Please try again."

            logger.info("MCP ack received!")

            # Step 7: Wait for response via MCP
            logger.info(f"Step 7: Waiting for MCP response (timeout: {timeout}s)...")
            loop = asyncio.new_event_loop()
            try:
                response = loop.run_until_complete(
                    wait_for_response(self.guid, timeout=timeout)
                )
            finally:
                loop.close()

            if not response:
                logger.error("Failed to receive MCP response")
                return "Timeout waiting for response."

            # Step 8: Save to chat history
            logger.info("Step 8: Saving response to history...")
            self._append_to_history("assistant", response)

            logger.info(f"Response received: {response[:100]}...")
            return response

        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            return None

    def _build_mcp_instruction(self) -> str:
        """Build instruction telling Claude to use MCP tools."""
        return f"""Read the user message from {self.prompt_file_path}.

IMPORTANT: Use your MCP tools to communicate progress:

1. IMMEDIATELY call: notify_ack(guid="{self.guid}")
2. As you work, call: send_progress(guid="{self.guid}", percent=N) where N is 0-100
3. For status updates: send_status(guid="{self.guid}", message="...", phase="analyzing|planning|implementing|deploying|verifying")
4. When done, call: send_response(guid="{self.guid}", content="your full response here")
5. Finally call: notify_complete(guid="{self.guid}", success=true)

If you encounter errors: notify_error(guid="{self.guid}", error="description", recoverable=false)

Now process the user's request and use these MCP tools to report your progress."""

    # ... rest of methods unchanged (get_chat_history, clear_session, is_active, etc.)
```

**Step 2: Commit**

```bash
git add backend/session_controller.py
git commit -m "feat: update session_controller for MCP-based protocol"
```

---

## Task 4: Create Split-View UI Component

**Files:**
- Create: `frontend/src/components/SplitChatView.jsx`
- Create: `frontend/src/components/McpToolsLog.jsx`
- Modify: `frontend/src/components/ChatInterface.jsx`

**Step 1: Create McpToolsLog component**

```jsx
// frontend/src/components/McpToolsLog.jsx
import { useState, useEffect, useRef } from 'react';

function McpToolsLog({ logs, connected }) {
  const logEndRef = useRef(null);

  // Auto-scroll to bottom on new logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const formatTimestamp = (ts) => {
    const date = new Date(ts);
    return date.toLocaleTimeString('en-US', { hour12: false });
  };

  const getToolColor = (tool) => {
    const colors = {
      notify_ack: 'text-green-600',
      send_progress: 'text-blue-600',
      send_status: 'text-purple-600',
      send_response: 'text-orange-600',
      notify_complete: 'text-green-700 font-bold',
      notify_error: 'text-red-600 font-bold',
    };
    return colors[tool] || 'text-gray-600';
  };

  const formatArguments = (tool, args) => {
    switch (tool) {
      case 'notify_ack':
        return '';
      case 'send_progress':
        return `${args.percent}%`;
      case 'send_status':
        return `"${args.message}" [${args.phase || 'working'}]`;
      case 'send_response':
        const preview = args.content?.substring(0, 50) || '';
        return `"${preview}${args.content?.length > 50 ? '...' : ''}"`;
      case 'notify_complete':
        return args.success ? 'SUCCESS' : 'FAILED';
      case 'notify_error':
        return `"${args.error}"`;
      default:
        return JSON.stringify(args);
    }
  };

  return (
    <div className="h-full flex flex-col bg-gray-900 text-gray-100 font-mono text-sm">
      {/* Header */}
      <div className="p-3 border-b border-gray-700 flex items-center justify-between">
        <h3 className="font-semibold text-gray-300">MCP Tools Log</h3>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`}></span>
          <span className="text-xs text-gray-500">Channel 2</span>
        </div>
      </div>

      {/* Log entries */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        {logs.length === 0 ? (
          <div className="text-gray-500 text-center py-8">
            Waiting for MCP tool calls...
          </div>
        ) : (
          logs.map((log, index) => (
            <div key={index} className="flex gap-2">
              <span className="text-gray-500 flex-shrink-0">
                {formatTimestamp(log.timestamp)}
              </span>
              <span className={getToolColor(log.tool)}>
                {log.tool}
              </span>
              <span className="text-gray-400">
                {formatArguments(log.tool, log.arguments)}
              </span>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>

      {/* Progress bar */}
      {logs.some(l => l.tool === 'send_progress') && !logs.some(l => l.tool === 'notify_complete') && (
        <div className="p-3 border-t border-gray-700">
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300"
              style={{
                width: `${logs.filter(l => l.tool === 'send_progress').pop()?.arguments?.percent || 0}%`
              }}
            ></div>
          </div>
        </div>
      )}
    </div>
  );
}

export default McpToolsLog;
```

**Step 2: Create SplitChatView component**

```jsx
// frontend/src/components/SplitChatView.jsx
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { useProgressSocket } from '../hooks/useProgressSocket';
import apiService from '../services/api';
import MessageList from './MessageList';
import InputArea from './InputArea';
import McpToolsLog from './McpToolsLog';

function SplitChatView() {
  const [messages, setMessages] = useState([]);
  const [mcpLogs, setMcpLogs] = useState([]);
  const [sessionReady, setSessionReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [guid, setGuid] = useState(() => localStorage.getItem('tmux_builder_guid') || null);

  // Channel 1: Backend WebSocket (chat)
  const wsHandlers = useMemo(() => ({
    onConnect: () => setError(null),
    onMessage: (data) => {
      const msg = { role: 'assistant', content: data.content, timestamp: data.timestamp };
      setMessages(prev => [...prev, msg]);
      setLoading(false);
    },
    onStatus: (status) => {
      if (status.state === 'ready') {
        setSessionReady(true);
        setLoading(false);
      }
    },
    onSessionCreated: (data) => {
      if (data.success) {
        setSessionReady(true);
        setLoading(false);
      }
    },
    onError: (msg) => {
      setError(msg);
      setLoading(false);
    }
  }), []);

  const { connected: ch1Connected, sendMessage: wsSendMessage, reconnect: ch1Reconnect } = useWebSocket(guid, wsHandlers);

  // Channel 2: MCP WebSocket (progress/tools log)
  const mcpHandlers = useMemo(() => ({
    onToolLog: (data) => {
      setMcpLogs(prev => [...prev, {
        tool: data.tool,
        arguments: data.arguments,
        timestamp: data.timestamp
      }]);
    },
    onComplete: () => setLoading(false),
    onError: (data) => setError(data.error || data.message)
  }), []);

  const { connected: ch2Connected, reconnect: ch2Reconnect } = useProgressSocket(guid, mcpHandlers);

  // Create session
  const handleCreateSession = async () => {
    setLoading(true);
    setError(null);
    setMcpLogs([]);

    try {
      const result = await apiService.createSession();
      if (result.success && result.guid) {
        localStorage.setItem('tmux_builder_guid', result.guid);
        setGuid(result.guid);
        setSessionReady(true);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create session');
    } finally {
      setLoading(false);
    }
  };

  // Send message
  const handleSendMessage = useCallback((messageData) => {
    const { message } = messageData;
    setMcpLogs([]); // Clear logs for new message
    setMessages(prev => [...prev, { role: 'user', content: message, timestamp: new Date().toISOString() }]);
    setLoading(true);

    if (ch1Connected) {
      wsSendMessage(message);
    }
  }, [ch1Connected, wsSendMessage]);

  // Clear chat
  const handleClearChat = async () => {
    if (!window.confirm('Clear chat and MCP logs?')) return;
    try {
      await apiService.clearSession();
      setMessages([]);
      setMcpLogs([]);
      setSessionReady(false);
      setGuid(null);
      localStorage.removeItem('tmux_builder_guid');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to clear session');
    }
  };

  // Session creation screen
  if (!sessionReady) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-100">
        <div className="bg-white rounded-lg shadow-lg p-8 text-center max-w-md">
          <h2 className="text-2xl font-bold mb-4">Tmux Builder</h2>
          <p className="text-gray-600 mb-6">Dual-channel chat with MCP progress tracking</p>
          {error && <div className="bg-red-100 text-red-700 p-3 rounded mb-4">{error}</div>}
          <button
            onClick={handleCreateSession}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg disabled:bg-gray-400"
          >
            {loading ? 'Creating...' : 'Create Session'}
          </button>
        </div>
      </div>
    );
  }

  // Main split view
  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-gray-800 text-white p-3 flex justify-between items-center">
        <div className="flex items-center gap-4">
          <h1 className="font-bold">Tmux Builder</h1>
          <div className="flex items-center gap-2 text-sm">
            <span className={`w-2 h-2 rounded-full ${ch1Connected ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span className="text-gray-400">Chat</span>
            <span className={`w-2 h-2 rounded-full ml-2 ${ch2Connected ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span className="text-gray-400">MCP</span>
          </div>
        </div>
        <button onClick={handleClearChat} className="text-sm text-red-400 hover:text-red-300">
          Clear Session
        </button>
      </div>

      {/* Split panels */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Chat */}
        <div className="w-1/2 flex flex-col border-r border-gray-300">
          <div className="flex-1 overflow-y-auto p-4 bg-white">
            <MessageList messages={messages} loading={loading} />
          </div>
          <div className="border-t border-gray-200 p-4 bg-white">
            <InputArea onSendMessage={handleSendMessage} disabled={loading} />
          </div>
        </div>

        {/* Right: MCP Tools Log */}
        <div className="w-1/2">
          <McpToolsLog logs={mcpLogs} connected={ch2Connected} />
        </div>
      </div>
    </div>
  );
}

export default SplitChatView;
```

**Step 3: Update useProgressSocket to handle tool_log type**

```javascript
// In useProgressSocket.js, add to the switch statement:
case 'tool_log':
  handlersRef.current.onToolLog?.(data);
  break;
```

**Step 4: Update App.jsx to use SplitChatView**

```jsx
// frontend/src/App.jsx
import SplitChatView from './components/SplitChatView';

function App() {
  return <SplitChatView />;
}

export default App;
```

**Step 5: Commit**

```bash
git add frontend/src/components/McpToolsLog.jsx frontend/src/components/SplitChatView.jsx frontend/src/App.jsx frontend/src/hooks/useProgressSocket.js
git commit -m "feat: add split-view UI with MCP tools log panel"
```

---

## Task 5: Update Config and Remove Old Marker Code

**Files:**
- Modify: `backend/config.py` - Remove marker configs, add MCP configs
- Delete: `backend/marker_utils.py` - No longer needed

**Step 1: Update config.py**

Remove marker-related configs:
```python
# REMOVE these lines:
# READY_MARKER = "ready.marker"
# ACK_MARKER = "ack.marker"
# COMPLETED_MARKER = "completed.marker"
# ACK_MARKER_TIMEOUT = 30
# COMPLETED_MARKER_TIMEOUT = 300
# get_markers_path()
# get_marker_file()
```

Keep MCP configs:
```python
# MCP SERVER CONFIGURATION
MCP_SERVER_NAME = 'tmux-progress'
MCP_WS_PORT = int(os.getenv('MCP_WS_PORT', '8001'))
MCP_ACK_TIMEOUT = 30
MCP_RESPONSE_TIMEOUT = 300
```

**Step 2: Delete marker_utils.py**

```bash
rm backend/marker_utils.py
```

**Step 3: Commit**

```bash
git add backend/config.py
git rm backend/marker_utils.py
git commit -m "refactor: remove file-based marker code, keep MCP config"
```

---

## Task 6: Update Documentation

**Files:**
- Replace: `docs/architecture/ARCHITECTURE.md`
- Delete: `docs/architecture/FILE_BASED_PROTOCOL_ISSUES.md`
- Delete: `docs/plans/2026-01-25-file-based-repl-protocol-design.md`
- Update: `docs/plans/2026-01-26-websocket-mcp-protocol-design.md`

**Step 1: Replace ARCHITECTURE.md with new dual-channel architecture**

Write new architecture document with:
- Dual-channel diagram (as shown above)
- MCP server registration instructions
- Message flow explanation
- Component responsibilities

**Step 2: Delete obsolete docs**

```bash
rm docs/architecture/FILE_BASED_PROTOCOL_ISSUES.md
rm docs/plans/2026-01-25-file-based-repl-protocol-design.md
```

**Step 3: Commit**

```bash
git add docs/
git commit -m "docs: update architecture for dual-channel MCP design"
```

---

## Task 7: Integration Testing

**Files:**
- Create: `backend/test_mcp_integration.py`

**Step 1: Create test script**

```python
#!/usr/bin/env python3
"""Integration test for MCP-based dual-channel protocol."""

import asyncio
import json
import websockets
import requests
import time

API_URL = "http://localhost:8000"
MCP_WS_URL = "ws://localhost:8001"

async def test_mcp_flow():
    print("=" * 60)
    print("MCP Integration Test")
    print("=" * 60)

    # 1. Create session
    print("\n1. Creating session...")
    resp = requests.post(f"{API_URL}/api/session/create")
    data = resp.json()
    assert data['success'], f"Failed: {data}"
    guid = data['guid']
    print(f"   Session created: {guid[:20]}...")

    # 2. Connect to MCP WebSocket
    print("\n2. Connecting to MCP WebSocket (Channel 2)...")
    async with websockets.connect(f"{MCP_WS_URL}/ws/{guid}") as ws:
        print("   Connected!")

        # 3. Send a test message via API
        print("\n3. Sending test message...")
        resp = requests.post(f"{API_URL}/api/chat", json={
            "message": "Say hello and confirm you received this."
        })

        # 4. Collect MCP tool calls
        print("\n4. Collecting MCP tool calls...")
        tool_calls = []
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=60)
                data = json.loads(msg)
                if data.get('type') == 'tool_log':
                    tool_calls.append(data['tool'])
                    print(f"   -> {data['tool']}({data.get('arguments', {})})")
                if data.get('type') == 'complete':
                    break
        except asyncio.TimeoutError:
            pass

        # 5. Verify expected tools were called
        print("\n5. Verifying tool calls...")
        expected = ['notify_ack', 'send_response', 'notify_complete']
        for tool in expected:
            if tool in tool_calls:
                print(f"   ✓ {tool}")
            else:
                print(f"   ✗ {tool} - MISSING!")

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_mcp_flow())
```

**Step 2: Run test**

```bash
python backend/test_mcp_integration.py
```

**Step 3: Commit**

```bash
git add backend/test_mcp_integration.py
git commit -m "test: add MCP integration test"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Register MCP server | `scripts/setup-mcp.sh` |
| 2 | Add tool call logging | `mcp_server/server.py`, `websocket_manager.py` |
| 3 | Update session controller | `session_controller.py` |
| 4 | Create split-view UI | `SplitChatView.jsx`, `McpToolsLog.jsx` |
| 5 | Remove old marker code | `config.py`, delete `marker_utils.py` |
| 6 | Update documentation | `docs/` |
| 7 | Integration testing | `test_mcp_integration.py` |

---

**Plan complete and saved to `docs/plans/2026-01-26-dual-channel-mcp-implementation.md`.**

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
