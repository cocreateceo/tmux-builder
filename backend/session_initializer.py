"""
Manages Claude CLI session initialization with PTY streaming.

Streaming Protocol (replaces marker-based):
1. Create PTY session, start Claude CLI
2. Write system_prompt.txt
3. Send instruction to read system prompt
4. Session ready for WebSocket streaming

No markers needed - real-time output via WebSocket.
"""

import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import json

from config import (
    SESSIONS_DIR,
    ACTIVE_SESSIONS_DIR,
    get_session_path,
    get_status_file,
)
from pty_manager import pty_manager
from prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class SessionInitializer:
    """Handles initialization of Claude CLI sessions with PTY streaming."""

    # Session reuse settings
    MAX_SESSION_AGE_DAYS = 5

    def __init__(self):
        """Initialize SessionInitializer."""
        self.prompt_manager = PromptManager()
        logger.info("SessionInitializer ready (PTY streaming mode)")

    @staticmethod
    def get_session_name(guid: str) -> str:
        """Generate session name from GUID (for compatibility)."""
        return f"pty_{guid}"

    @staticmethod
    def get_session_path(guid: str) -> Path:
        """Get session directory path for GUID."""
        session_path = ACTIVE_SESSIONS_DIR / guid
        session_path.mkdir(parents=True, exist_ok=True)
        return session_path

    def initialize_session(
        self,
        guid: str,
        email: str,
        phone: str,
        user_request: str
    ) -> Dict[str, Any]:
        """
        Initialize Claude CLI session with PTY streaming.

        Args:
            guid: User GUID
            email: User email
            phone: User phone
            user_request: User's build request

        Returns:
            Dictionary with success status and session info
        """
        try:
            logger.info(f"=== INITIALIZING PTY SESSION FOR GUID: {guid} ===")

            session_path = self.get_session_path(guid)
            status_file_path = get_status_file(guid)

            logger.info(f"Session path: {session_path}")

            # Update status
            self._update_status(status_file_path, "initializing", 10, "Creating PTY session", guid, email, user_request)

            # Step 1: Check for existing session and reuse if healthy
            existing_session = pty_manager.get_session(guid)
            if existing_session and existing_session.is_alive():
                session_age_days = self._get_session_age_days(guid)
                if session_age_days is not None and session_age_days < self.MAX_SESSION_AGE_DAYS:
                    logger.info(f"Reusing existing PTY session (age: {session_age_days:.1f} days)")
                    self._update_status(status_file_path, "ready", 100, "Session ready (reused)", guid, email, user_request)
                    return {
                        'success': True,
                        'session_name': self.get_session_name(guid),
                        'session_path': str(session_path),
                        'guid': guid,
                        'websocket_url': f'/ws/{guid}',
                        'reused': True
                    }
                else:
                    # Kill old session
                    logger.info("Killing old PTY session")
                    pty_manager.kill_session(guid)

            # Step 2: Create new PTY session
            logger.info("Creating new PTY session...")
            session = pty_manager.create_session(guid, session_path)

            if not session:
                logger.error("Failed to create PTY session")
                self._update_status(status_file_path, "error", 0, "Failed to create PTY session", guid, email, user_request)
                return {
                    'success': False,
                    'error': 'Failed to create PTY session'
                }

            logger.info(f"PTY session created with PID: {session.pty.pid if session.pty else 'unknown'}")
            self._update_status(status_file_path, "initializing", 30, "PTY session created", guid, email, user_request)

            # Step 3: Prepare system prompt
            logger.info("Preparing system prompt...")

            system_prompt = self.prompt_manager.render_system_prompt(
                'autonomous_agent',
                {
                    'guid': guid,
                    'email': email,
                    'phone': phone,
                    'user_request': user_request,
                    'session_path': str(session_path),
                    'aws_profile': 'sunwaretech',
                    'status_file': str(status_file_path),
                    # No markers in streaming mode - use /dev/null as placeholder
                    'ready_marker': '/dev/null',
                    'ack_marker': '/dev/null',
                    'completed_marker': '/dev/null',
                    'markers_path': '/dev/null',
                    'initialized_marker': '/dev/null',
                    'processing_marker': '/dev/null',
                }
            )

            # Write system prompt to file
            system_prompt_file = session_path / "system_prompt.txt"
            system_prompt_file.write_text(system_prompt)
            logger.info(f"System prompt written to {system_prompt_file}")

            self._update_status(status_file_path, "initializing", 50, "System prompt prepared", guid, email, user_request)

            # Step 4: Wait for Claude CLI to initialize
            logger.info("Waiting for Claude CLI to initialize...")
            time.sleep(3.0)  # Give Claude CLI time to start

            # Step 5: Send instruction to read system prompt
            logger.info("Sending system prompt instruction...")
            instruction = (
                f"This is a pre-authorized autonomous build session. "
                f"Read {system_prompt_file} and execute immediately. "
                f"Do NOT ask for confirmation - the user already approved by submitting.\n"
            )

            if not session.send_input(instruction):
                logger.error("Failed to send system prompt instruction")
                self._update_status(status_file_path, "error", 0, "Failed to send instruction", guid, email, user_request)
                return {
                    'success': False,
                    'error': 'Failed to send system prompt instruction'
                }

            # Step 6: Update status to ready
            self._update_status(status_file_path, "ready", 100, "Session ready - streaming via WebSocket", guid, email, user_request, mode="streaming")

            logger.info("PTY session initialization complete")
            return {
                'success': True,
                'session_name': self.get_session_name(guid),
                'session_path': str(session_path),
                'guid': guid,
                'websocket_url': f'/ws/{guid}',
                'reused': False
            }

        except Exception as e:
            logger.exception(f"Session initialization failed: {e}")
            try:
                self._update_status(status_file_path, "error", 0, str(e), guid, email, user_request)
            except Exception:
                pass
            return {
                'success': False,
                'error': str(e)
            }

    def _update_status(
        self,
        status_file: Path,
        state: str,
        progress: int,
        message: str,
        guid: str,
        email: str,
        user_request: str,
        mode: str = "initializing"
    ):
        """Update status.json file."""
        try:
            status = {
                'state': state,
                'progress': progress,
                'message': message,
                'phase': state,
                'updated_at': datetime.utcnow().isoformat() + 'Z',
                'guid': guid,
                'email': email,
                'user_request': user_request,
                'mode': mode,
            }
            status_file.parent.mkdir(parents=True, exist_ok=True)
            status_file.write_text(json.dumps(status, indent=2))
        except Exception as e:
            logger.error(f"Error updating status: {e}")

    def _get_session_age_days(self, guid: str) -> Optional[float]:
        """Get age of session in days from status.json."""
        try:
            session_path = self.get_session_path(guid)
            status_file = session_path / "status.json"

            if not status_file.exists():
                return None

            status = json.loads(status_file.read_text())
            created_at_str = status.get('updated_at') or status.get('created_at')

            if not created_at_str:
                return None

            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            age = datetime.utcnow() - created_at.replace(tzinfo=None)

            return age.total_seconds() / 86400

        except Exception as e:
            logger.warning(f"Unable to determine session age: {e}")
            return None
