"""
DEPRECATED: This module uses the legacy marker-based protocol.

For streaming sessions, use stream_controller.py instead.

Legacy Message Loop Protocol (marker-based):
1. Backend clears ack.marker and completed.marker
2. Backend writes prompt to prompt.txt
3. Backend sends: "Read prompt.txt, create ack.marker, process, create completed.marker"
4. Claude creates ack.marker (prompt received)
5. Claude updates status.json as it works
6. Claude creates completed.marker when done
7. Backend reads response

New Protocol (streaming):
- Use stream_controller.py with WebSocket
- Real-time output via PTY
- No markers needed
"""

import warnings
warnings.warn(
    "session_controller.py is deprecated. Use stream_controller.py for PTY streaming.",
    DeprecationWarning,
    stacklevel=2
)

import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

from config import (
    SESSION_PREFIX,
    CHAT_HISTORY_FILE,
    READY_MARKER,
    ACK_MARKER,
    COMPLETED_MARKER,
    PROMPT_FILE,
    STATUS_FILE,
    ACTIVE_SESSIONS_DIR,
    get_markers_path,
    get_marker_file,
    get_prompt_file,
    get_status_file,
    ACK_MARKER_TIMEOUT,
    COMPLETED_MARKER_TIMEOUT,
)
from tmux_helper import TmuxHelper
from marker_utils import (
    wait_for_marker,
    clear_for_new_message,
    delete_marker,
)

logger = logging.getLogger(__name__)


class SessionController:
    """Manages Claude CLI sessions via tmux with marker-based protocol."""

    def __init__(self, guid: str):
        """
        Initialize SessionController for a GUID-based session.

        Args:
            guid: Session GUID (from SessionInitializer)
        """
        logger.info(f"Initializing SessionController for GUID: {guid}")
        self.guid = guid
        self.session_path = ACTIVE_SESSIONS_DIR / guid
        self.markers_path = get_markers_path(guid)
        self.chat_history_path = self.session_path / CHAT_HISTORY_FILE
        self.prompt_file_path = get_prompt_file(guid)
        self.status_file_path = get_status_file(guid)
        self.session_name = f"{SESSION_PREFIX}_{guid}"

        logger.info(f"Session path: {self.session_path}")
        logger.info(f"Session name: {self.session_name}")

    def send_message(self, message: str, timeout: float = COMPLETED_MARKER_TIMEOUT) -> Optional[str]:
        """
        Send a message to Claude using file-based REPL protocol.

        Protocol:
        1. Clear ack.marker and completed.marker
        2. Write message to prompt.txt
        3. Send instruction to read and process
        4. Wait for ack.marker (prompt received)
        5. Wait for completed.marker (processing done)
        6. Read response from status.json or chat history

        Args:
            message: User message to send
            timeout: Max seconds to wait for completion

        Returns:
            Assistant's response or None if error/timeout
        """
        logger.info("=== SENDING MESSAGE ===")
        logger.info(f"Message: {message[:100]}...")

        try:
            # Step 1: Clear markers for new message
            logger.info("Step 1: Clearing markers...")
            clear_for_new_message(self.guid)

            # Step 2: Append user message to history
            logger.info("Step 2: Appending user message to history...")
            self._append_to_history("user", message)

            # Step 3: Write message to prompt.txt
            logger.info("Step 3: Writing prompt to file...")
            self.prompt_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.prompt_file_path.write_text(message)
            logger.info(f"Prompt written to: {self.prompt_file_path}")

            # Step 4: Update status to processing
            self._update_status("processing", 10, "Processing user request")

            # Step 5: Get marker paths for instruction
            ack_marker_path = get_marker_file(self.guid, ACK_MARKER)
            completed_marker_path = get_marker_file(self.guid, COMPLETED_MARKER)

            # Step 6: Send instruction to Claude with retry logic
            # Single-line instruction (avoid multi-line issues with tmux)
            instruction = (
                f"Read the user message from {self.prompt_file_path}, process it, "
                f"save response to {self.chat_history_path}, "
                f"then create {ack_marker_path} and {completed_marker_path} when done."
            )

            max_retries = 3
            ack_received = False

            for attempt in range(1, max_retries + 1):
                logger.info(f"Step 6: Attempt {attempt}/{max_retries} - Sending process instruction...")

                # Clear stale ack marker before retry
                delete_marker(self.guid, ACK_MARKER)

                if not TmuxHelper.send_instruction(self.session_name, instruction):
                    logger.error("Failed to send instruction via tmux")
                    return None

                # Wait for ack.marker
                logger.info(f"Waiting for ack.marker (timeout: {ACK_MARKER_TIMEOUT}s)...")
                if wait_for_marker(self.guid, ACK_MARKER, timeout=ACK_MARKER_TIMEOUT):
                    logger.info("ack.marker received")
                    ack_received = True
                    break
                else:
                    logger.warning(f"Attempt {attempt} failed - ack.marker not received")
                    if attempt < max_retries:
                        retry_delay = 3.0 * attempt
                        logger.info(f"Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)

            if not ack_received:
                logger.error(f"Failed to receive ack.marker after {max_retries} attempts")
                return "Claude did not acknowledge the message after multiple attempts. Please try again."

            # Step 8: Wait for completed.marker
            logger.info(f"Step 8: Waiting for completed.marker (timeout: {timeout}s)...")
            if not wait_for_marker(self.guid, COMPLETED_MARKER, timeout=timeout):
                logger.error("Timeout waiting for completed.marker")
                return "Timeout waiting for response. Claude may still be processing."
            logger.info("completed.marker received")

            # Step 9: Read response
            logger.info("Step 9: Reading response...")
            response = self._get_latest_assistant_response()
            logger.info(f"Response: {response[:100] if response else 'None'}...")

            return response

        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            self._update_status("error", 0, str(e))
            return None

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

            # Clear markers
            for marker in [READY_MARKER, ACK_MARKER, COMPLETED_MARKER]:
                delete_marker(self.guid, marker)

            # Clear prompt file
            if self.prompt_file_path.exists():
                self.prompt_file_path.unlink()

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

    def _get_latest_assistant_response(self) -> str:
        """Read the latest assistant response from chat history."""
        messages = self.get_chat_history()

        # Find last assistant message
        for msg in reversed(messages):
            if msg.get('role') == 'assistant':
                return msg.get('content', '')

        # Fallback: check status.json for response
        status = self.get_status()
        if status.get('state') == 'completed' and status.get('response'):
            return status.get('response')

        return "No response received."

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
                    pass  # Ignore JSON parse errors

            self.status_file_path.write_text(json.dumps(status, indent=2))
        except Exception as e:
            logger.error(f"Error updating status: {e}")
