"""
WebSocket server for real-time progress updates from Claude CLI.

This server:
- Listens on port 8082 for WebSocket connections
- Uses path-based routing: /ws/<guid>
- Receives progress messages from notify.sh (Claude CLI)
- Broadcasts to UI clients subscribed to the same GUID
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set
import websockets
from websockets.server import WebSocketServerProtocol

from config import WS_MAX_MESSAGE_HISTORY, ACTIVE_SESSIONS_DIR

# Use centralized logging (configured in config.py)
logger = logging.getLogger(__name__)


class ProgressWebSocketServer:
    """
    WebSocket server for progress updates.

    Handles:
    - UI client connections (subscribe to GUID updates)
    - notify.sh connections (send progress for a GUID)
    - Broadcasting messages to subscribed clients
    - Signaling session_controller when ack/done received (asyncio.Event)
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8082):
        self.host = host
        self.port = port
        # Map: guid -> set of connected WebSocket clients
        self.subscribers: Dict[str, Set[WebSocketServerProtocol]] = {}
        # Map: guid -> list of recent messages (for late joiners)
        self.message_history: Dict[str, list] = {}
        self.max_history = WS_MAX_MESSAGE_HISTORY
        self._server = None
        self._running = False

        # Signaling events for session_controller (direct notification)
        self.ack_events: Dict[str, asyncio.Event] = {}
        self.done_events: Dict[str, asyncio.Event] = {}

    def get_ack_event(self, guid: str) -> asyncio.Event:
        """Get or create an ack event for a GUID."""
        if guid not in self.ack_events:
            self.ack_events[guid] = asyncio.Event()
        return self.ack_events[guid]

    def get_done_event(self, guid: str) -> asyncio.Event:
        """Get or create a done event for a GUID."""
        if guid not in self.done_events:
            self.done_events[guid] = asyncio.Event()
        return self.done_events[guid]

    def clear_events(self, guid: str):
        """Clear (reset) events for a GUID before waiting."""
        if guid in self.ack_events:
            self.ack_events[guid].clear()
        if guid in self.done_events:
            self.done_events[guid].clear()

    async def handler(self, websocket: WebSocketServerProtocol):
        """Handle incoming WebSocket connections."""
        # Extract GUID from path: /ws/<guid>
        # websockets v16+ changed API - path is now in websocket.request.path
        path = websocket.request.path
        parts = path.strip('/').split('/')
        if len(parts) < 2 or parts[0] != 'ws':
            logger.warning(f"Invalid path: {path}")
            await websocket.close(1008, "Invalid path. Use /ws/<guid>")
            return

        guid = parts[1]
        if not guid:
            logger.warning("Empty GUID in path")
            await websocket.close(1008, "GUID required")
            return

        # Register subscriber
        await self._subscribe(websocket, guid)

        try:
            async for message in websocket:
                await self._handle_message(websocket, guid, message)
        except websockets.exceptions.ConnectionClosed:
            pass  # Normal disconnect, no logging needed
        except Exception as e:
            logger.error(f"Error handling connection: {e}")
        finally:
            await self._unsubscribe(websocket, guid)

    async def _subscribe(self, websocket: WebSocketServerProtocol, guid: str):
        """Subscribe a client to GUID updates."""
        if guid not in self.subscribers:
            self.subscribers[guid] = set()

        self.subscribers[guid].add(websocket)
        logger.debug(f"Client subscribed to {guid} (total: {len(self.subscribers[guid])})")

        # Always load fresh history from file on each subscribe (browser refresh)
        # This ensures we get all messages even if server was restarted
        file_history = self._load_from_file(guid)
        if file_history:
            # Update in-memory cache
            self.message_history[guid] = file_history
            try:
                await websocket.send(json.dumps({
                    "type": "history",
                    "messages": file_history
                }))
                logger.info(f"Sent {len(file_history)} history messages to client")
            except Exception as e:
                logger.warning(f"Failed to send history: {e}")

    async def _unsubscribe(self, websocket: WebSocketServerProtocol, guid: str):
        """Unsubscribe a client from GUID updates."""
        if guid in self.subscribers:
            self.subscribers[guid].discard(websocket)
            if not self.subscribers[guid]:
                del self.subscribers[guid]
                # Keep history for a while in case they reconnect
            logger.debug(f"Client unsubscribed from {guid}")

    async def _handle_message(self, websocket: WebSocketServerProtocol, guid: str, raw_message: str):
        """Handle incoming message from a client."""
        try:
            message = json.loads(raw_message)
            msg_type = message.get("type", "unknown")

            # Add timestamp if not present
            if "timestamp" not in message:
                message["timestamp"] = datetime.now().isoformat()

            # Add GUID if not present
            if "guid" not in message:
                message["guid"] = guid

            logger.info(f"[{guid}] Received: {msg_type} - {message.get('data', '')[:50]}")

            # Store in history
            self._add_to_history(guid, message)

            # Signal session_controller directly (instant notification)
            if msg_type == 'ack':
                event = self.get_ack_event(guid)
                event.set()
                logger.debug(f"[{guid}] Ack event signaled")
            elif msg_type == 'summary':
                # Read summary from summary.md file
                summary_content = self._read_summary_file(guid)
                if summary_content:
                    # Update message with full summary content
                    message['data'] = summary_content
                    message['message'] = summary_content
                    # Update chat_history with the formatted summary
                    self._append_to_chat_history(guid, summary_content)
                    logger.info(f"[{guid}] Summary loaded from file ({len(summary_content)} chars)")
            elif msg_type in ['done', 'complete', 'completed']:
                event = self.get_done_event(guid)
                event.set()
                logger.debug(f"[{guid}] Done event signaled")
                # Note: Chat history already updated when summary was received
            elif msg_type == 'error':
                # Signal done event on error too (with error flag in history)
                event = self.get_done_event(guid)
                event.set()
                logger.debug(f"[{guid}] Done event signaled (error)")
                # Update chat_history with error message
                error_msg = message.get('data', 'An error occurred')
                self._append_to_chat_history(guid, f"Task completed with errors: {error_msg}")

            # Broadcast to all subscribers of this GUID
            await self._broadcast(guid, message)

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _add_to_history(self, guid: str, message: dict):
        """Add message to history (in-memory + file)."""
        if guid not in self.message_history:
            self.message_history[guid] = []

        self.message_history[guid].append(message)

        # Trim in-memory to max size
        if len(self.message_history[guid]) > self.max_history:
            self.message_history[guid] = self.message_history[guid][-self.max_history:]

        # Persist to file
        self._persist_to_file(guid, message)

    def _read_summary_file(self, guid: str) -> str:
        """Read summary.md file from session folder."""
        try:
            session_path = ACTIVE_SESSIONS_DIR / guid
            summary_file = session_path / "summary.md"

            if not summary_file.exists():
                logger.warning(f"[{guid}] summary.md not found")
                return ""

            content = summary_file.read_text().strip()
            logger.info(f"[{guid}] Read summary.md: {len(content)} chars")
            return content

        except Exception as e:
            logger.warning(f"Failed to read summary.md: {e}")
            return ""

    def _append_to_chat_history(self, guid: str, content: str):
        """Append assistant message to chat_history.jsonl when task completes."""
        try:
            session_path = ACTIVE_SESSIONS_DIR / guid
            if not session_path.exists():
                logger.warning(f"Session path not found for chat history update: {guid}")
                return

            chat_history_file = session_path / "chat_history.jsonl"
            message = {
                "role": "assistant",
                "content": content,
                "timestamp": datetime.now().isoformat() + "Z"
            }

            with open(chat_history_file, 'a') as f:
                f.write(json.dumps(message) + '\n')

            logger.info(f"[{guid}] Updated chat_history with completion message")

        except Exception as e:
            logger.warning(f"Failed to update chat history: {e}")

    def _persist_to_file(self, guid: str, message: dict):
        """Append message to activity_log.jsonl file."""
        try:
            session_path = ACTIVE_SESSIONS_DIR / guid
            if session_path.exists():
                log_file = session_path / "activity_log.jsonl"
                with open(log_file, 'a') as f:
                    f.write(json.dumps(message) + '\n')
        except Exception as e:
            logger.warning(f"Failed to persist activity log: {e}")

    def _load_from_file(self, guid: str) -> list:
        """Load activity log from file."""
        try:
            session_path = ACTIVE_SESSIONS_DIR / guid
            log_file = session_path / "activity_log.jsonl"

            if not log_file.exists():
                return []

            messages = []
            with open(log_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        messages.append(json.loads(line))

            # Return last N messages
            return messages[-self.max_history:]
        except Exception as e:
            logger.warning(f"Failed to load activity log: {e}")
            return []

    async def _broadcast(self, guid: str, message: dict):
        """Broadcast message to all subscribers of a GUID."""
        if guid not in self.subscribers:
            return

        dead_connections = set()
        message_json = json.dumps(message)

        for ws in self.subscribers[guid]:
            try:
                await ws.send(message_json)
            except websockets.exceptions.ConnectionClosed:
                dead_connections.add(ws)
            except Exception as e:
                logger.warning(f"Failed to send to subscriber: {e}")
                dead_connections.add(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self.subscribers[guid].discard(ws)

    async def start(self):
        """Start the WebSocket server."""
        self._running = True
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")

        self._server = await websockets.serve(
            self.handler,
            self.host,
            self.port,
            ping_interval=30,
            ping_timeout=10
        )

        logger.info(f"WebSocket server listening on ws://{self.host}:{self.port}/ws/<guid>")

        # Keep running until stopped
        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        """Stop the WebSocket server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("WebSocket server stopped")


# Global server instance
_server_instance: ProgressWebSocketServer | None = None
_server_task: asyncio.Task | None = None


async def start_progress_server(host: str = "0.0.0.0", port: int = 8082) -> ProgressWebSocketServer:
    """Start the progress WebSocket server in the background."""
    global _server_instance, _server_task

    if _server_instance is None:
        _server_instance = ProgressWebSocketServer(host=host, port=port)

    if _server_task is None or _server_task.done():
        _server_task = asyncio.create_task(_server_instance.start())

    return _server_instance


async def stop_progress_server():
    """Stop the progress WebSocket server."""
    global _server_instance, _server_task

    if _server_instance:
        await _server_instance.stop()

    if _server_task:
        _server_task.cancel()
        try:
            await _server_task
        except asyncio.CancelledError:
            pass

    _server_instance = None
    _server_task = None


def get_server() -> ProgressWebSocketServer | None:
    """Get the current server instance."""
    return _server_instance


# Entry point for standalone testing
if __name__ == "__main__":
    async def main():
        server = ProgressWebSocketServer()
        try:
            await server.start()
        except KeyboardInterrupt:
            await server.stop()

    asyncio.run(main())
