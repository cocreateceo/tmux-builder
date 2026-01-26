"""
High-level session orchestration with MCP-based protocol.

Message Loop Protocol:
1. Backend writes prompt to prompt.txt
2. Backend sends instruction with MCP tool usage instructions
3. Claude calls notify_ack() via MCP
4. Claude processes, calling send_progress/send_status
5. Claude calls send_response() with content
6. Claude calls notify_complete()
7. Backend reads response from MCP cache
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

    def get_chat_history(self) -> List[Dict]:
        """Load and return chat history from JSONL file."""
        if not self.chat_history_path.exists():
            return []

        messages = []
        try:
            with open(self.chat_history_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        messages.append(json.loads(line))
        except Exception as e:
            logger.error(f"Error loading chat history: {e}")

        return messages

    def get_status(self) -> Dict:
        """Read current status from status.json."""
        try:
            if self.status_file_path.exists():
                return json.loads(self.status_file_path.read_text())
        except Exception as e:
            logger.error(f"Error reading status: {e}")

        return {
            'state': 'unknown',
            'progress': 0,
            'message': 'Unable to read status'
        }

    def clear_session(self) -> bool:
        """Clear the session and reset state."""
        try:
            # Kill tmux session
            TmuxHelper.kill_session(self.session_name)

            # Clear chat history
            if self.chat_history_path.exists():
                self.chat_history_path.unlink()

            # Clear prompt file
            if self.prompt_file_path.exists():
                self.prompt_file_path.unlink()

            # Reset MCP session
            reset_session(self.guid)

            logger.info(f"Session {self.guid} cleared")
            return True

        except Exception as e:
            logger.error(f"Error clearing session: {e}")
            return False

    def is_active(self) -> bool:
        """Check if the tmux session is active."""
        return TmuxHelper.session_exists(self.session_name)

    def _append_to_history(self, role: str, content: str):
        """Append a message to chat history JSONL file."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        self.chat_history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.chat_history_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(message) + '\n')

    def _update_status(self, state: str, progress: int, message: str):
        """Update status.json with current state."""
        try:
            status = {
                'state': state,
                'progress': progress,
                'message': message,
                'phase': state,
                'updated_at': datetime.utcnow().isoformat() + 'Z'
            }

            # Preserve existing fields if status file exists
            if self.status_file_path.exists():
                try:
                    existing = json.loads(self.status_file_path.read_text())
                    for key in ['guid', 'email', 'user_request']:
                        if key in existing:
                            status[key] = existing[key]
                except Exception:
                    pass

            self.status_file_path.write_text(json.dumps(status, indent=2))
        except Exception as e:
            logger.error(f"Error updating status: {e}")
