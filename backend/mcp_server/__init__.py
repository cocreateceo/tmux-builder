"""
MCP Server for tmux-builder.

Provides MCP tools for Claude CLI to communicate progress and responses
back to the UI in real-time via WebSocket.
"""

from .server import (
    MCPServer,
    get_server,
    start_server_background,
    stop_server,
    wait_for_ack,
    wait_for_response,
    register_session,
    reset_session,
    get_session_status,
    get_response,
)
from .tools import TOOLS, get_tool_by_name, get_tool_names
from .session_registry import SessionRegistry
from .websocket_manager import WebSocketManager

__all__ = [
    'MCPServer',
    'get_server',
    'start_server_background',
    'stop_server',
    'wait_for_ack',
    'wait_for_response',
    'register_session',
    'reset_session',
    'get_session_status',
    'get_response',
    'TOOLS',
    'get_tool_by_name',
    'get_tool_names',
    'SessionRegistry',
    'WebSocketManager',
]
