"""
MCP Tool Definitions for tmux-builder.

These tools are exposed to Claude CLI to enable real-time communication
with the UI without relying on file-based markers.
"""

# Tool definitions following MCP specification
TOOLS = [
    {
        "name": "notify_ack",
        "description": "Signal that you received and understood the prompt. Call this IMMEDIATELY after reading the prompt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "guid": {
                    "type": "string",
                    "description": "Session GUID provided in the prompt"
                }
            },
            "required": ["guid"]
        }
    },
    {
        "name": "send_progress",
        "description": "Report progress percentage (0-100). Call this periodically during long-running tasks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "guid": {
                    "type": "string",
                    "description": "Session GUID"
                },
                "percent": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Progress percentage (0-100)"
                }
            },
            "required": ["guid", "percent"]
        }
    },
    {
        "name": "send_status",
        "description": "Send a human-readable status message. Call this when starting a new phase of work.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "guid": {
                    "type": "string",
                    "description": "Session GUID"
                },
                "message": {
                    "type": "string",
                    "description": "Human-readable status message"
                },
                "phase": {
                    "type": "string",
                    "enum": ["analyzing", "planning", "implementing", "deploying", "verifying", "complete"],
                    "description": "Current phase of work"
                }
            },
            "required": ["guid", "message"]
        }
    },
    {
        "name": "send_response",
        "description": "Send the response content to the user. Call this when you have the final response ready.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "guid": {
                    "type": "string",
                    "description": "Session GUID"
                },
                "content": {
                    "type": "string",
                    "description": "The response text to send to the user"
                }
            },
            "required": ["guid", "content"]
        }
    },
    {
        "name": "notify_complete",
        "description": "Signal that processing is complete. Call this as the LAST action after send_response.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "guid": {
                    "type": "string",
                    "description": "Session GUID"
                },
                "success": {
                    "type": "boolean",
                    "description": "Whether the task completed successfully",
                    "default": True
                }
            },
            "required": ["guid"]
        }
    },
    {
        "name": "notify_error",
        "description": "Report an error condition. Call this if something goes wrong during processing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "guid": {
                    "type": "string",
                    "description": "Session GUID"
                },
                "error": {
                    "type": "string",
                    "description": "Error message describing what went wrong"
                },
                "recoverable": {
                    "type": "boolean",
                    "description": "Whether the error is recoverable (user can retry)",
                    "default": False
                }
            },
            "required": ["guid", "error"]
        }
    }
]


def get_tool_by_name(name: str) -> dict | None:
    """Get a tool definition by name."""
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None


def get_tool_names() -> list[str]:
    """Get list of all tool names."""
    return [tool["name"] for tool in TOOLS]
