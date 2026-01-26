#!/usr/bin/env python3
"""
MCP Server for tmux-builder.

This server implements the Model Context Protocol (MCP) to enable
Claude CLI to communicate progress and responses back to the UI.

Architecture:
- Handles stdio communication with Claude CLI (MCP protocol)
- Runs a WebSocket server on port 8001 for UI connections
- Bridges MCP tool calls to WebSocket broadcasts

Usage:
    python -m mcp_server.server

The server is started by Claude CLI via the --mcp-server flag.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports when run directly
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.tools import TOOLS
from mcp_server.session_registry import SessionRegistry
from mcp_server.websocket_manager import WebSocketManager

# Configure logging to stderr (stdout is used for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format='[MCP] %(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


class MCPServer:
    """
    MCP Server implementation.

    Handles:
    - stdio communication with Claude CLI (MCP protocol)
    - WebSocket server for UI on port 8001
    - Bridging tool calls to WebSocket broadcasts
    """

    def __init__(self, ws_port: int = 8001):
        self.ws_port = ws_port
        self.session_registry = SessionRegistry()
        self.ws_manager = WebSocketManager()
        self._running = False
        self._ws_server = None

    async def handle_tool_call(self, name: str, arguments: dict) -> dict:
        """Handle an MCP tool call from Claude CLI."""
        guid = arguments.get('guid', '')

        if not guid:
            return {"success": False, "error": "GUID is required"}

        # Ensure session exists
        if not self.session_registry.session_exists(guid):
            self.session_registry.register_session(guid)

        result = {"success": True}

        if name == "notify_ack":
            self.session_registry.set_ack(guid)
            await self.ws_manager.send_ack(guid)
            result["message"] = "Acknowledgment sent"

        elif name == "send_progress":
            percent = arguments.get('percent', 0)
            self.session_registry.set_progress(guid, percent)
            await self.ws_manager.send_progress(guid, percent)
            result["message"] = f"Progress updated to {percent}%"

        elif name == "send_status":
            message = arguments.get('message', '')
            phase = arguments.get('phase', '')
            self.session_registry.set_status(guid, message, phase)
            await self.ws_manager.send_status(guid, message, phase)
            result["message"] = f"Status updated: {message}"

        elif name == "send_response":
            content = arguments.get('content', '')
            self.session_registry.set_response(guid, content)
            await self.ws_manager.send_response(guid, content)
            result["message"] = "Response sent"

        elif name == "notify_complete":
            success = arguments.get('success', True)
            self.session_registry.set_complete(guid, success)
            await self.ws_manager.send_complete(guid, success)
            result["message"] = "Completion notified"

        elif name == "notify_error":
            error = arguments.get('error', 'Unknown error')
            recoverable = arguments.get('recoverable', False)
            self.session_registry.set_error(guid, error, recoverable)
            await self.ws_manager.send_error(guid, error, recoverable)
            result["message"] = f"Error reported: {error}"

        else:
            result = {"success": False, "error": f"Unknown tool: {name}"}

        # Log the tool call to UI
        await self.ws_manager.send_tool_log(guid, name, arguments, result)

        logger.info(f"Tool call: {name}({guid}) -> {result.get('message', result.get('error'))}")
        return result

    async def handle_mcp_message(self, message: dict) -> dict | None:
        """Handle an incoming MCP protocol message."""
        msg_type = message.get('method', message.get('type', ''))
        msg_id = message.get('id')

        # Handle JSON-RPC style messages
        if msg_type == 'initialize':
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "tmux-builder-mcp",
                        "version": "1.0.0"
                    }
                }
            }

        elif msg_type == 'tools/list':
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": TOOLS
                }
            }

        elif msg_type == 'tools/call':
            params = message.get('params', {})
            tool_name = params.get('name')
            arguments = params.get('arguments', {})

            result = await self.handle_tool_call(tool_name, arguments)

            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result)
                        }
                    ]
                }
            }

        elif msg_type == 'notifications/initialized':
            logger.info("MCP client initialized")
            return None

        elif msg_type == 'ping':
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"status": "ok"}
            }

        else:
            logger.warning(f"Unknown MCP message type: {msg_type}")
            if msg_id:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {msg_type}"
                    }
                }
            return None

    async def stdio_handler(self):
        """Handle stdio communication with Claude CLI."""
        logger.info("Starting stdio handler")

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())

        while self._running:
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=1.0)
                if not line:
                    continue

                line_str = line.decode('utf-8').strip()
                if not line_str:
                    continue

                message = json.loads(line_str)
                response = await self.handle_mcp_message(message)

                if response:
                    response_json = json.dumps(response) + '\n'
                    writer.write(response_json.encode('utf-8'))
                    await writer.drain()

            except asyncio.TimeoutError:
                continue
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
            except Exception as e:
                if self._running:
                    logger.error(f"stdio handler error: {e}")
                break

        logger.info("stdio handler stopped")

    async def websocket_handler(self, websocket, path):
        """Handle WebSocket connections from UI."""
        # Extract GUID from path (e.g., /ws/abc123)
        parts = path.strip('/').split('/')
        guid = parts[-1] if parts else ''

        if not guid or guid == 'ws':
            logger.warning(f"WebSocket connection without GUID: {path}")
            await websocket.close(1008, "GUID required in path")
            return

        await self.ws_manager.connect(websocket, guid)

        # Ensure session is registered
        if not self.session_registry.session_exists(guid):
            self.session_registry.register_session(guid)

        # Send current session state
        session = self.session_registry.get_session(guid)
        if session:
            try:
                await websocket.send(json.dumps({
                    "type": "session_state",
                    "guid": guid,
                    "state": session
                }))
            except Exception:
                pass

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get('type')

                    if msg_type == 'ping':
                        await websocket.send(json.dumps({"type": "pong"}))

                    elif msg_type == 'get_status':
                        session = self.session_registry.get_session(guid)
                        await websocket.send(json.dumps({
                            "type": "session_state",
                            "guid": guid,
                            "state": session
                        }))

                    elif msg_type == 'reset':
                        self.session_registry.reset_session(guid)
                        await websocket.send(json.dumps({
                            "type": "reset_ack",
                            "guid": guid
                        }))

                except json.JSONDecodeError:
                    pass
        except Exception as e:
            logger.debug(f"WebSocket handler ended: {e}")
        finally:
            await self.ws_manager.disconnect(websocket, guid)

    async def start_websocket_server(self):
        """Start the WebSocket server for UI connections."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets package not installed. Run: pip install websockets")
            return

        logger.info(f"Starting WebSocket server on port {self.ws_port}")

        try:
            self._ws_server = await websockets.serve(
                self.websocket_handler,
                "0.0.0.0",
                self.ws_port,
                ping_interval=30,
                ping_timeout=10
            )

            while self._running:
                await asyncio.sleep(1)

        except OSError as e:
            logger.error(f"Failed to start WebSocket server: {e}")
        finally:
            if self._ws_server:
                self._ws_server.close()
                await self._ws_server.wait_closed()

    async def run(self):
        """Run the MCP server (both stdio and WebSocket)."""
        self._running = True
        logger.info("MCP Server starting...")

        # Run both handlers concurrently
        try:
            await asyncio.gather(
                self.stdio_handler(),
                self.start_websocket_server(),
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self._running = False

        logger.info("MCP Server stopped")

    async def run_websocket_only(self):
        """Run only the WebSocket server (for backend integration)."""
        self._running = True
        logger.info("MCP WebSocket Server starting (no stdio)...")

        await self.start_websocket_server()

        logger.info("MCP WebSocket Server stopped")

    def stop(self):
        """Stop the server."""
        self._running = False
        logger.info("MCP Server stopping...")


# Global server instance for backend integration
_server_instance: MCPServer | None = None
_server_task: asyncio.Task | None = None


def get_server(ws_port: int = 8001) -> MCPServer:
    """Get or create the global MCP server instance."""
    global _server_instance
    if _server_instance is None:
        _server_instance = MCPServer(ws_port=ws_port)
    return _server_instance


async def start_server_background(ws_port: int = 8001) -> MCPServer:
    """Start the MCP server in the background (WebSocket only)."""
    global _server_task
    server = get_server(ws_port)

    if _server_task is None or _server_task.done():
        _server_task = asyncio.create_task(server.run_websocket_only())

    return server


async def stop_server():
    """Stop the MCP server."""
    global _server_instance, _server_task
    if _server_instance:
        _server_instance.stop()
    if _server_task:
        _server_task.cancel()
        try:
            await _server_task
        except asyncio.CancelledError:
            pass
    _server_instance = None
    _server_task = None


# Convenience functions for backend
async def wait_for_ack(guid: str, timeout: float = 30) -> bool:
    """Wait for acknowledgment from Claude CLI."""
    server = get_server()
    return await server.session_registry.wait_for_ack(guid, timeout)


async def wait_for_response(guid: str, timeout: float = 300) -> str | None:
    """Wait for response from Claude CLI."""
    server = get_server()
    return await server.session_registry.wait_for_response(guid, timeout)


def register_session(guid: str) -> None:
    """Register a session with the MCP server."""
    server = get_server()
    server.session_registry.register_session(guid)


def reset_session(guid: str) -> None:
    """Reset session state for new message."""
    server = get_server()
    server.session_registry.reset_session(guid)


def get_session_status(guid: str) -> dict | None:
    """Get current session status."""
    server = get_server()
    return server.session_registry.get_session(guid)


def get_response(guid: str) -> str | None:
    """Get cached response for session."""
    server = get_server()
    return server.session_registry.get_response(guid)


# Entry point when run directly (by Claude CLI)
if __name__ == "__main__":
    server = MCPServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        server.stop()
