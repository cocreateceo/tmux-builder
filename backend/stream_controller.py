"""
Stream Controller for PTY-based Claude CLI sessions.

High-level orchestration for streaming sessions:
- Session lifecycle management
- Status.json updates (keeps progress tracking)
- System prompt injection
- Connection state tracking
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from config import (
    ACTIVE_SESSIONS_DIR,
    get_session_path,
    get_status_file,
    CHAT_HISTORY_FILE,
)
from pty_manager import pty_manager, PTYSession
from prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class StreamController:
    """
    Manages a streaming Claude CLI session.

    Replaces SessionController for the streaming architecture.
    Keeps status.json updates for progress tracking.
    """

    def __init__(self, guid: str):
        """
        Initialize StreamController.

        Args:
            guid: Session GUID
        """
        self.guid = guid
        self.session_path = get_session_path(guid)
        self.status_file = get_status_file(guid)
        self.chat_history_path = self.session_path / CHAT_HISTORY_FILE
        self.prompt_manager = PromptManager()

        # Ensure directories exist
        self.session_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"StreamController initialized for {guid}")

    def initialize_session(
        self,
        email: str,
        phone: str,
        user_request: str,
        aws_profile: str = "sunwaretech"
    ) -> Dict[str, Any]:
        """
        Initialize a new streaming session.

        Args:
            email: User email
            phone: User phone
            user_request: Initial build request
            aws_profile: AWS profile for deployments

        Returns:
            Result dict with success status
        """
        try:
            logger.info(f"=== INITIALIZING STREAM SESSION: {self.guid} ===")

            # Update status
            self._update_status("initializing", 10, "Creating PTY session")

            # Create PTY session
            session = pty_manager.create_session(self.guid, self.session_path)
            if not session:
                return {
                    "success": False,
                    "error": "Failed to create PTY session"
                }

            # Update status
            self._update_status("initializing", 30, "PTY session created")

            # Prepare system prompt
            system_prompt = self.prompt_manager.render_system_prompt(
                'autonomous_agent',
                {
                    'guid': self.guid,
                    'email': email,
                    'phone': phone,
                    'user_request': user_request,
                    'session_path': str(self.session_path),
                    'aws_profile': aws_profile,
                    # Streaming mode - no markers needed
                    'ready_marker': '/dev/null',
                    'ack_marker': '/dev/null',
                    'completed_marker': '/dev/null',
                    'status_file': str(self.status_file),
                    'initialized_marker': '/dev/null',
                    'processing_marker': '/dev/null',
                }
            )

            # Write system prompt to file
            system_prompt_file = self.session_path / "system_prompt.txt"
            system_prompt_file.write_text(system_prompt)
            logger.info(f"System prompt written to {system_prompt_file}")

            # Initialize status.json
            initial_status = {
                'state': 'ready',
                'progress': 100,
                'message': 'Session ready - connected via WebSocket',
                'phase': 'ready',
                'updated_at': datetime.utcnow().isoformat() + 'Z',
                'guid': self.guid,
                'email': email,
                'user_request': user_request,
                'mode': 'streaming',
            }
            self.status_file.write_text(json.dumps(initial_status, indent=2))

            logger.info("Stream session initialized successfully")
            return {
                "success": True,
                "guid": self.guid,
                "session_path": str(self.session_path),
                "websocket_url": f"/ws/{self.guid}"
            }

        except Exception as e:
            logger.exception(f"Failed to initialize stream session: {e}")
            self._update_status("error", 0, str(e))
            return {
                "success": False,
                "error": str(e)
            }

    def send_system_prompt(self) -> bool:
        """
        Send system prompt to the PTY session.

        Returns:
            True if sent successfully
        """
        session = pty_manager.get_session(self.guid)
        if not session:
            logger.error(f"No PTY session found: {self.guid}")
            return False

        system_prompt_file = self.session_path / "system_prompt.txt"
        if not system_prompt_file.exists():
            logger.error(f"System prompt file not found: {system_prompt_file}")
            return False

        # Send instruction to read system prompt
        instruction = (
            f"This is a pre-authorized autonomous build session. "
            f"Read {system_prompt_file} and execute immediately. "
            f"Do NOT ask for confirmation - the user already approved by submitting.\n"
        )

        return session.send_input(instruction)

    def send_message(self, message: str) -> bool:
        """
        Send a message to the PTY session.

        Args:
            message: Message to send

        Returns:
            True if sent successfully
        """
        session = pty_manager.get_session(self.guid)
        if not session:
            logger.error(f"No PTY session found: {self.guid}")
            return False

        # Append to chat history
        self._append_to_history("user", message)

        # Send to PTY (add newline to submit)
        return session.send_input(message + "\n")

    def get_status(self) -> Dict[str, Any]:
        """Read current status from status.json."""
        try:
            if self.status_file.exists():
                return json.loads(self.status_file.read_text())
        except Exception as e:
            logger.error(f"Error reading status: {e}")

        return {
            'state': 'unknown',
            'progress': 0,
            'message': 'Unable to read status'
        }

    def get_chat_history(self) -> List[Dict]:
        """Load chat history from JSONL file."""
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

    def is_active(self) -> bool:
        """Check if PTY session is active."""
        session = pty_manager.get_session(self.guid)
        return session is not None and session.is_alive()

    def kill(self) -> bool:
        """Kill the PTY session."""
        self._update_status("terminated", 0, "Session terminated")
        return pty_manager.kill_session(self.guid)

    def _update_status(self, state: str, progress: int, message: str):
        """Update status.json."""
        try:
            status = {
                'state': state,
                'progress': progress,
                'message': message,
                'phase': state,
                'updated_at': datetime.utcnow().isoformat() + 'Z'
            }

            # Preserve existing fields
            if self.status_file.exists():
                try:
                    existing = json.loads(self.status_file.read_text())
                    for key in ['guid', 'email', 'user_request', 'mode']:
                        if key in existing:
                            status[key] = existing[key]
                except Exception:
                    pass

            self.status_file.parent.mkdir(parents=True, exist_ok=True)
            self.status_file.write_text(json.dumps(status, indent=2))
        except Exception as e:
            logger.error(f"Error updating status: {e}")

    def _append_to_history(self, role: str, content: str):
        """Append message to chat history."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        self.chat_history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.chat_history_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(message) + '\n')
