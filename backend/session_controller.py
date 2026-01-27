"""
High-level session orchestration with notify.sh-based protocol.

Message Loop Protocol:
1. Backend writes prompt to prompt.txt
2. Backend sends instruction with notify.sh usage instructions
3. Claude calls ./notify.sh ack
4. Claude processes, calling ./notify.sh status "..."
5. Claude calls ./notify.sh done when complete
6. Backend reads response from tmux output
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

from config import (
    SESSION_PREFIX,
    CHAT_HISTORY_FILE,
    PROMPT_FILE,
    STATUS_FILE,
    ACTIVE_SESSIONS_DIR,
    ACK_TIMEOUT,
    RESPONSE_TIMEOUT,
    get_prompt_file,
    get_status_file,
)
from tmux_helper import TmuxHelper
from ws_server import get_server

logger = logging.getLogger(__name__)


class SessionController:
    """Manages Claude CLI sessions via tmux with notify.sh-based protocol."""

    def __init__(self, guid: str):
        """Initialize SessionController for a GUID-based session."""
        logger.info(f"Initializing SessionController for GUID: {guid}")
        self.guid = guid
        self.session_path = ACTIVE_SESSIONS_DIR / guid
        self.chat_history_path = self.session_path / CHAT_HISTORY_FILE
        self.prompt_file_path = get_prompt_file(guid)
        self.status_file_path = get_status_file(guid)
        self.session_name = f"{SESSION_PREFIX}_{guid}"

        logger.info(f"Session path: {self.session_path}")
        logger.info(f"Session name: {self.session_name}")

    async def send_message_async(self, message: str, timeout: float = RESPONSE_TIMEOUT) -> Optional[str]:
        """
        Send a message to Claude using notify.sh-based protocol (async version).

        Protocol:
        1. Write message to prompt.txt
        2. Send instruction with notify.sh usage
        3. Wait for ./notify.sh ack (short timeout)
        4. Return immediately - don't block waiting for completion
        5. Completion updates chat_history via ws_server when done arrives
        """
        logger.info("=== SENDING MESSAGE (notify.sh Protocol) ===")
        logger.info(f"Message: {message[:100]}...")

        try:
            # Step 1: Append user message to history
            logger.info("Step 1: Appending user message to history...")
            self._append_to_history("user", message)

            # Step 2: Write message to prompt.txt
            logger.info("Step 2: Writing prompt to file...")
            self.prompt_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.prompt_file_path.write_text(message)

            # Step 3: Build instruction with notify.sh usage
            instruction = self._build_notify_instruction()

            # Step 4: Send instruction via tmux
            logger.info("Step 4: Sending instruction via tmux...")
            if not TmuxHelper.send_instruction(self.session_name, instruction):
                logger.error("Failed to send instruction via tmux")
                return None

            # Step 5: Wait for ack via WebSocket (short timeout - just confirm Claude received it)
            logger.info(f"Step 5: Waiting for ack (timeout: {ACK_TIMEOUT}s)...")
            ack_received = await self._wait_for_ack(timeout=ACK_TIMEOUT)

            if ack_received:
                response = "Processing your request. Watch the activity log for updates."
            else:
                logger.warning("Did not receive ack - Claude may still be working")
                response = "Message sent. Claude may still be processing."

            # Step 6: Return immediately - don't wait for completion
            # The ws_server will update chat_history when done arrives
            logger.info("Step 6: Returning immediately (completion handled by ws_server)")
            logger.info(f"Response: {response}")
            return response

        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            return None

    def send_message(self, message: str, timeout: float = RESPONSE_TIMEOUT) -> Optional[str]:
        """
        Send a message to Claude (sync wrapper - use send_message_async when possible).

        Note: This creates a fire-and-forget task. For proper async handling,
        use send_message_async directly.
        """
        logger.info("=== SENDING MESSAGE (sync wrapper) ===")
        logger.info(f"Message: {message[:100]}...")

        try:
            # Step 1: Append user message to history
            self._append_to_history("user", message)

            # Step 2: Write message to prompt.txt
            self.prompt_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.prompt_file_path.write_text(message)

            # Step 3: Build instruction with notify.sh usage
            instruction = self._build_notify_instruction()

            # Step 4: Send instruction via tmux
            if not TmuxHelper.send_instruction(self.session_name, instruction):
                logger.error("Failed to send instruction via tmux")
                return None

            # Return immediately - actual progress comes via WebSocket
            response = "Message sent. Watch the activity log for progress updates."
            self._append_to_history("assistant", response)
            return response

        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            return None

    async def _wait_for_ack(self, timeout: float = ACK_TIMEOUT) -> bool:
        """Wait for ack message from Claude via WebSocket (event-based)."""
        server = get_server()
        if not server:
            logger.warning("WebSocket server not running, skipping ack wait")
            return False

        # Get the ack event (will be signaled when notify.sh sends ack)
        event = server.get_ack_event(self.guid)

        # Clear the event before waiting (reset for this message)
        event.clear()

        try:
            # Wait for the event to be set (signaled by ws_server when ack received)
            await asyncio.wait_for(event.wait(), timeout=timeout)
            logger.info(f"Received ack from Claude for {self.guid}")
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for ack from {self.guid}")
            return False

    async def _wait_for_done(self, timeout: float = RESPONSE_TIMEOUT) -> tuple[bool, bool]:
        """
        Wait for done or error message from Claude via WebSocket (event-based).

        Returns:
            Tuple of (completed, had_error)
            - (True, False) = completed successfully
            - (True, True) = completed with error
            - (False, False) = timeout
        """
        server = get_server()
        if not server:
            logger.warning("WebSocket server not running, skipping done wait")
            return False, False

        # Get the done event (will be signaled when notify.sh sends done/error)
        event = server.get_done_event(self.guid)

        # Clear the event before waiting (reset for this message)
        event.clear()

        try:
            # Wait for the event to be set (signaled by ws_server when done/error received)
            await asyncio.wait_for(event.wait(), timeout=timeout)

            # Check the last message to determine if it was success or error
            if self.guid in server.message_history:
                for msg in reversed(server.message_history[self.guid]):
                    msg_type = msg.get('type')
                    if msg_type in ['done', 'complete', 'completed']:
                        logger.info(f"Task completed successfully for {self.guid}")
                        return True, False
                    elif msg_type == 'error':
                        error_data = msg.get('data', 'Unknown error')
                        logger.error(f"Task error for {self.guid}: {error_data}")
                        return True, True

            # Event was set but no done/error found - assume success
            logger.info(f"Task completed for {self.guid}")
            return True, False

        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for completion from {self.guid}")
            return False, False

    def _build_notify_instruction(self) -> str:
        """
        Build instruction telling Claude to read the prompt.

        Note: Claude already has system_prompt.txt with all notify.sh instructions,
        so we just tell it to read the new message and process it.
        """
        return f"""New task in prompt.txt. Read it and execute.

Remember: Start with ./notify.sh ack, report progress, end with ./notify.sh done"""

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

            # Clear message history from WebSocket server
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
