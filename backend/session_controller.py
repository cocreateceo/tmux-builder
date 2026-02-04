"""
High-level session orchestration with notify.sh-based protocol.

Protocol:
1. Backend writes prompt to prompt_{timestamp}.txt
2. Backend sends instruction via tmux
3. Claude calls ./notify.sh ack
4. Claude processes, calling ./notify.sh status "..."
5. Claude writes summary.md, calls ./notify.sh summary, then ./notify.sh done
6. ws_server reads summary.md and updates chat_history
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config import (
    ACK_TIMEOUT,
    ACTIVE_SESSIONS_DIR,
    CHAT_HISTORY_FILE,
    SESSION_PREFIX,
)
from tmux_helper import TmuxHelper
from ws_server import get_server

logger = logging.getLogger(__name__)


class SessionController:
    """Manages Claude CLI sessions via tmux with notify.sh-based protocol."""

    def __init__(self, guid: str):
        """Initialize SessionController for a GUID-based session."""
        self.guid = guid
        self.session_path = ACTIVE_SESSIONS_DIR / guid
        self.chat_history_path = self.session_path / CHAT_HISTORY_FILE
        self.session_name = f"{SESSION_PREFIX}_{guid}"
        logger.info(f"SessionController initialized: {self.session_name}")

    async def send_message_async(self, message: str) -> Optional[str]:
        """
        Send a message to Claude using notify.sh-based protocol.

        Returns immediately after receiving ack. Completion updates
        chat_history via ws_server when done/summary arrives.
        """
        logger.info(f"=== SENDING MESSAGE: {message[:50]}... ===")

        # Append user message to history
        self._append_to_history("user", message)

        # Write message to unique prompt file (timestamp prevents caching)
        timestamp_ms = int(time.time() * 1000)
        prompt_path = self.session_path / f"prompt_{timestamp_ms}.txt"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)

        with open(prompt_path, 'w', encoding='utf-8') as f:
            f.write(message)
            f.flush()
            os.fsync(f.fileno())

        # Brief delay for WSL filesystem sync
        await asyncio.sleep(0.3)

        # Build and send instruction via tmux
        instruction = f"""NEW USER MESSAGE - Read this file NOW and execute: {prompt_path}

Remember: Start with ./notify.sh ack, report progress, end with ./notify.sh done"""

        if not TmuxHelper.send_instruction(self.session_name, instruction):
            logger.error("Failed to send instruction via tmux")
            return None

        # Wait for ack (short timeout - just confirm Claude received it)
        ack_received = await self._wait_for_ack()

        if ack_received:
            return "Processing your request. Watch the activity log for updates."
        else:
            logger.warning("Did not receive ack - Claude may still be working")
            return "Message sent. Claude may still be processing."

    async def _wait_for_ack(self, timeout: float = ACK_TIMEOUT) -> bool:
        """Wait for ack message from Claude via WebSocket (event-based)."""
        server = get_server()
        if not server:
            logger.warning("WebSocket server not running, skipping ack wait")
            return False

        event = server.get_ack_event(self.guid)
        event.clear()

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            logger.info(f"Received ack from Claude")
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for ack")
            return False

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
        status_file = self.session_path / "status.json"
        try:
            if status_file.exists():
                return json.loads(status_file.read_text())
        except Exception as e:
            logger.error(f"Error reading status: {e}")
        return {'state': 'unknown', 'progress': 0, 'message': 'Unable to read status'}

    def clear_session(self) -> bool:
        """Clear the session and reset state."""
        try:
            TmuxHelper.kill_session(self.session_name)

            if self.chat_history_path.exists():
                self.chat_history_path.unlink()

            # Clear WebSocket message history
            server = get_server()
            if server and self.guid in server.message_history:
                del server.message_history[self.guid]

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
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.chat_history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.chat_history_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(message) + '\n')
