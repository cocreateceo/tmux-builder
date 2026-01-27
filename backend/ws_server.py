"""
WebSocket server for real-time progress updates from Claude CLI.

This server:
- Listens on port 8001 for WebSocket connections
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

from config import WS_MAX_MESSAGE_HISTORY

# Use centralized logging (configured in config.py)
logger = logging.getLogger(__name__)


class ProgressWebSocketServer:
    """
    WebSocket server for progress updates.

    Handles:
    - UI client connections (subscribe to GUID updates)
    - notify.sh connections (send progress for a GUID)
    - Broadcasting messages to subscribed clients
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8001):
        self.host = host
        self.port = port
        # Map: guid -> set of connected WebSocket clients
        self.subscribers: Dict[str, Set[WebSocketServerProtocol]] = {}
        # Map: guid -> list of recent messages (for late joiners)
        self.message_history: Dict[str, list] = {}
        self.max_history = WS_MAX_MESSAGE_HISTORY
        self._server = None
        self._running = False

    async def handler(self, websocket: WebSocketServerProtocol, path: str):
        """Handle incoming WebSocket connections."""
        # Extract GUID from path: /ws/<guid>
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
            self.message_history[guid] = []

        self.subscribers[guid].add(websocket)
        logger.debug(f"Client subscribed to {guid} (total: {len(self.subscribers[guid])})")

        # Send message history to new subscriber
        if self.message_history[guid]:
            try:
                await websocket.send(json.dumps({
                    "type": "history",
                    "messages": self.message_history[guid]
                }))
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

            # Broadcast to all subscribers of this GUID
            await self._broadcast(guid, message)

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _add_to_history(self, guid: str, message: dict):
        """Add message to history, keeping only last N messages."""
        if guid not in self.message_history:
            self.message_history[guid] = []

        self.message_history[guid].append(message)

        # Trim to max size
        if len(self.message_history[guid]) > self.max_history:
            self.message_history[guid] = self.message_history[guid][-self.max_history:]

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


async def start_progress_server(host: str = "0.0.0.0", port: int = 8001) -> ProgressWebSocketServer:
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
