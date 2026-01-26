"""
High-level session orchestration with file-based REPL protocol.

Message Loop Protocol:
1. Health check (verify CLI responsive)
2. Backend clears ack.marker and completed.marker
3. Backend writes prompt to prompt.txt (first msg includes autonomous prompt)
4. Backend sends: "Read prompt.txt, create ack.marker, process, create completed.marker"
5. Claude creates ack.marker (prompt received)
6. Claude updates status.json as it works
7. Claude creates completed.marker when done
8. Backend reads response
"""

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
from prompt_manager import PromptManager
from marker_utils import (
    wait_for_marker,
    clear_for_new_message,
    delete_marker,
)

logger = logging.getLogger(__name__)


class SessionController:
    """Manages Claude CLI sessions via tmux with marker-based protocol."""

    HEALTH_CHECK_TIMEOUT = 10  # seconds for health check

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
        self.prompt_manager = PromptManager()

        logger.info(f"Session path: {self.session_path}")
        logger.info(f"Session name: {self.session_name}")

    def send_message(self, message: str, timeout: float = COMPLETED_MARKER_TIMEOUT) -> Optional[str]:
        """
        Send a message to Claude using file-based REPL protocol.

        Protocol:
        1. Health check (verify CLI responsive)
        2. Clear ack.marker and completed.marker
        3. Write prompt to prompt.txt (first msg includes autonomous prompt)
        4. Send instruction to read and process
        5. Wait for ack.marker (prompt received)
        6. Wait for completed.marker (processing done)
        7. Read response from status.json or chat history

        Args:
            message: User message to send
            timeout: Max seconds to wait for completion

        Returns:
            Assistant's response or None if error/timeout
        """
        logger.info("=== SENDING MESSAGE ===")
        logger.info(f"Message: {message[:100]}...")

        try:
            # Step 1: Health check - verify CLI is responsive
            logger.info("Step 1: Health check...")
            if not self._health_check():
                logger.error("Health check failed - CLI not responsive")
                return "Claude CLI is not responsive. Please try recreating the session."

            # Step 2: Clear markers for new message
            logger.info("Step 2: Clearing markers...")
            clear_for_new_message(self.guid)

            # Step 3: Append user message to history
            logger.info("Step 3: Appending user message to history...")
            self._append_to_history("user", message)

            # Step 4: Check if this is the first message (needs full prompt)
            is_first_message = self._is_first_message()
            logger.info(f"Step 4: First message: {is_first_message}")

            # Step 5: Build prompt content
            if is_first_message:
                logger.info("Step 5: Building full autonomous prompt with user request...")
                prompt_content = self._build_first_message_prompt(message)
            else:
                logger.info("Step 5: Using simple user message...")
                prompt_content = message

            # Step 6: Write prompt to prompt.txt
            logger.info("Step 6: Writing prompt to file...")
            self.prompt_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.prompt_file_path.write_text(prompt_content)
            logger.info(f"Prompt written to: {self.prompt_file_path} ({len(prompt_content)} chars)")

            # Step 7: Update status to processing
            self._update_status("processing", 10, "Processing user request")

            # Step 8: Get marker paths for instruction
            ack_marker_path = get_marker_file(self.guid, ACK_MARKER)
            completed_marker_path = get_marker_file(self.guid, COMPLETED_MARKER)

            # Step 9: Build instruction based on message type
            if is_first_message:
                # First message: pre-authorized autonomous session
                instruction = (
                    f"This is a pre-authorized autonomous session. "
                    f"Read {self.prompt_file_path} and execute immediately. "
                    f"Create {ack_marker_path} when you start, {completed_marker_path} when done. "
                    f"Save responses to {self.chat_history_path}."
                )
            else:
                # Subsequent messages: simpler instruction
                instruction = (
                    f"Read the user message from {self.prompt_file_path}, process it, "
                    f"save response to {self.chat_history_path}, "
                    f"then create {ack_marker_path} and {completed_marker_path} when done."
                )

            max_retries = 3
            ack_received = False

            for attempt in range(1, max_retries + 1):
                logger.info(f"Step 10: Attempt {attempt}/{max_retries} - Sending process instruction...")

                # Clear stale ack marker before retry
                delete_marker(self.guid, ACK_MARKER)

                if not TmuxHelper.send_instruction(self.session_name, instruction):
                    logger.error("Failed to send instruction via tmux")
                    return None

                # Wait for ack.marker - use longer timeout for first message
                ack_timeout = ACK_MARKER_TIMEOUT * 2 if is_first_message else ACK_MARKER_TIMEOUT
                logger.info(f"Waiting for ack.marker (timeout: {ack_timeout}s)...")
                if wait_for_marker(self.guid, ACK_MARKER, timeout=ack_timeout):
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

            # Mark first message as sent
            if is_first_message:
                self._mark_first_message_sent()

            # Step 11: Wait for completed.marker
            logger.info(f"Step 11: Waiting for completed.marker (timeout: {timeout}s)...")
            if not wait_for_marker(self.guid, COMPLETED_MARKER, timeout=timeout):
                logger.error("Timeout waiting for completed.marker")
                return "Timeout waiting for response. Claude may still be processing."
            logger.info("completed.marker received")

            # Step 12: Read response
            logger.info("Step 12: Reading response...")
            response = self._get_latest_assistant_response()
            logger.info(f"Response: {response[:100] if response else 'None'}...")

            return response

        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            self._update_status("error", 0, str(e))
            return None

    def _health_check(self) -> bool:
        """
        Quick health check to verify Claude CLI is responsive.

        Returns:
            True if CLI is responsive, False otherwise
        """
        try:
            # Check if tmux session exists
            if not TmuxHelper.session_exists(self.session_name):
                logger.warning(f"Tmux session {self.session_name} does not exist")
                return False

            # Clear ready marker
            delete_marker(self.guid, READY_MARKER)

            # Get marker path
            ready_marker_path = get_marker_file(self.guid, READY_MARKER)

            # Send simple touch command
            TmuxHelper.send_instruction(self.session_name, f"touch {ready_marker_path}")

            # Wait for marker with short timeout
            if wait_for_marker(self.guid, READY_MARKER, timeout=self.HEALTH_CHECK_TIMEOUT):
                logger.debug("Health check passed")
                # Clear ready marker after check
                delete_marker(self.guid, READY_MARKER)
                return True
            else:
                logger.warning("Health check failed: timeout")
                return False

        except Exception as e:
            logger.error(f"Health check error: {e}")
            return False

    def _is_first_message(self) -> bool:
        """Check if this is the first message (autonomous prompt not yet sent)."""
        try:
            if self.status_file_path.exists():
                status = json.loads(self.status_file_path.read_text())
                return not status.get('first_message_sent', False)
        except Exception as e:
            logger.warning(f"Error checking first message status: {e}")
        return True  # Default to first message if unknown

    def _mark_first_message_sent(self):
        """Mark that the first message (with autonomous prompt) has been sent."""
        try:
            status = {}
            if self.status_file_path.exists():
                status = json.loads(self.status_file_path.read_text())
            status['first_message_sent'] = True
            status['first_message_at'] = datetime.utcnow().isoformat() + 'Z'
            self.status_file_path.write_text(json.dumps(status, indent=2))
            logger.info("Marked first message as sent")
        except Exception as e:
            logger.error(f"Error marking first message sent: {e}")

    def _build_first_message_prompt(self, user_message: str) -> str:
        """
        Build the full prompt for the first message, including autonomous agent context.

        Args:
            user_message: The user's actual request

        Returns:
            Full prompt with autonomous agent instructions + user request
        """
        try:
            # Read session metadata
            status = {}
            if self.status_file_path.exists():
                status = json.loads(self.status_file_path.read_text())

            guid = status.get('guid', self.guid)
            email = status.get('email', 'user@demo.local')
            phone = status.get('phone', '0000000000')

            # Get marker paths
            ready_marker_path = get_marker_file(self.guid, READY_MARKER)
            ack_marker_path = get_marker_file(self.guid, ACK_MARKER)
            completed_marker_path = get_marker_file(self.guid, COMPLETED_MARKER)

            # Render full autonomous agent prompt
            system_prompt = self.prompt_manager.render_system_prompt(
                'autonomous_agent',
                {
                    'guid': guid,
                    'email': email,
                    'phone': phone,
                    'user_request': user_message,
                    'session_path': str(self.session_path),
                    'markers_path': str(self.markers_path),
                    'aws_profile': 'sunwaretech',
                    'ready_marker': str(ready_marker_path),
                    'ack_marker': str(ack_marker_path),
                    'completed_marker': str(completed_marker_path),
                    'status_file': str(self.status_file_path),
                    'initialized_marker': str(ready_marker_path),
                    'processing_marker': str(ack_marker_path),
                }
            )

            logger.info(f"Built first message prompt ({len(system_prompt)} chars)")
            return system_prompt

        except Exception as e:
            logger.error(f"Error building first message prompt: {e}")
            # Fallback: just return the user message
            return user_message

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
