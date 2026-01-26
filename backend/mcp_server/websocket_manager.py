"""
WebSocket Manager for MCP Server.

Manages WebSocket connections from UI clients and broadcasts
messages to them in real-time.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manage WebSocket connections from UI clients."""

    def __init__(self):
        self._connections: dict[str, list] = {}  # guid -> list of websockets
        self._lock = asyncio.Lock()

    async def connect(self, websocket, guid: str) -> None:
        """Register a WebSocket connection for a session."""
        async with self._lock:
            if guid not in self._connections:
                self._connections[guid] = []
            self._connections[guid].append(websocket)
        logger.info(f"WebSocket connected for session: {guid} (total: {len(self._connections.get(guid, []))})")

    async def disconnect(self, websocket, guid: str) -> None:
        """Unregister a WebSocket connection."""
        async with self._lock:
            if guid in self._connections:
                if websocket in self._connections[guid]:
                    self._connections[guid].remove(websocket)
                if not self._connections[guid]:
                    del self._connections[guid]
        logger.info(f"WebSocket disconnected for session: {guid}")

    def has_connections(self, guid: str) -> bool:
        """Check if there are any connections for a session."""
        return guid in self._connections and len(self._connections[guid]) > 0

    def get_connection_count(self, guid: str) -> int:
        """Get number of connections for a session."""
        return len(self._connections.get(guid, []))

    async def broadcast(self, guid: str, message: dict) -> int:
        """
        Broadcast a message to all connections for a session.

        Args:
            guid: Session GUID
            message: Message dict to broadcast

        Returns:
            Number of successful sends
        """
        if guid not in self._connections:
            logger.debug(f"No WebSocket connections for session: {guid}")
            return 0

        # Add timestamp if not present
        if 'timestamp' not in message:
            message['timestamp'] = datetime.utcnow().isoformat() + 'Z'

        message_json = json.dumps(message)
        successful = 0
        disconnected = []

        async with self._lock:
            connections = self._connections.get(guid, []).copy()

        for ws in connections:
            try:
                await ws.send(message_json)
                successful += 1
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(ws)

        # Clean up disconnected sockets
        for ws in disconnected:
            await self.disconnect(ws, guid)

        logger.debug(f"Broadcast to {guid}: {message.get('type')} -> {successful} clients")
        return successful

    async def send_ack(self, guid: str) -> int:
        """Send acknowledgment message."""
        return await self.broadcast(guid, {
            "type": "ack",
            "guid": guid
        })

    async def send_progress(self, guid: str, percent: int) -> int:
        """Send progress update."""
        return await self.broadcast(guid, {
            "type": "progress",
            "guid": guid,
            "progress": percent  # Frontend expects 'progress' field
        })

    async def send_status(self, guid: str, message: str, phase: str = '') -> int:
        """Send status message."""
        return await self.broadcast(guid, {
            "type": "status",
            "guid": guid,
            "message": message,
            "phase": phase
        })

    async def send_response(self, guid: str, content: str) -> int:
        """Send response content."""
        return await self.broadcast(guid, {
            "type": "response",
            "guid": guid,
            "content": content
        })

    async def send_complete(self, guid: str, success: bool = True) -> int:
        """Send completion notification."""
        return await self.broadcast(guid, {
            "type": "complete",
            "guid": guid,
            "success": success
        })

    async def send_error(self, guid: str, error: str, recoverable: bool = False) -> int:
        """Send error notification."""
        return await self.broadcast(guid, {
            "type": "error",
            "guid": guid,
            "error": error,
            "recoverable": recoverable
        })

    async def send_tool_log(self, guid: str, tool: str, args: dict, result: dict) -> int:
        """Send tool call log entry."""
        return await self.broadcast(guid, {
            "type": "tool_log",
            "guid": guid,
            "tool": tool,
            "args": args,
            "result": result
        })

    async def close_all(self, guid: str) -> None:
        """Close all connections for a session."""
        async with self._lock:
            if guid in self._connections:
                for ws in self._connections[guid]:
                    try:
                        await ws.close(1000, "Session ended")
                    except Exception:
                        pass
                del self._connections[guid]
        logger.info(f"Closed all connections for session: {guid}")

    async def close_all_sessions(self) -> None:
        """Close all connections for all sessions."""
        async with self._lock:
            for guid in list(self._connections.keys()):
                for ws in self._connections[guid]:
                    try:
                        await ws.close(1000, "Server shutdown")
                    except Exception:
                        pass
            self._connections.clear()
        logger.info("Closed all WebSocket connections")
