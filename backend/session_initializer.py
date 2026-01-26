"""
Manages Claude CLI session initialization with MCP-based health check.

Protocol (MCP-based):
1. Create tmux session, start Claude CLI
2. Register session with MCP server
3. Send instruction to call notify_ack MCP tool
4. Wait for ack via MCP server
5. Done! Session ready for chat.
"""

import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import json

from config import (
    SESSIONS_DIR,
    TMUX_SESSION_PREFIX,
    ACTIVE_SESSIONS_DIR,
)
from tmux_helper import TmuxHelper
from mcp_server import register_session, wait_for_ack

logger = logging.getLogger(__name__)


class SessionInitializer:
    """Handles initialization of Claude CLI sessions with simple health check."""

    # Session reuse settings
    MAX_SESSION_AGE_DAYS = 5
    HEALTH_CHECK_TIMEOUT = 30  # seconds to wait for MCP ack

    def __init__(self):
        """Initialize SessionInitializer."""
        logger.info("SessionInitializer ready")

    @staticmethod
    def get_session_name(guid: str) -> str:
        """Generate tmux session name from GUID."""
        return f"{TMUX_SESSION_PREFIX}_{guid}"

    @staticmethod
    def get_session_path(guid: str) -> Path:
        """Get session directory path for GUID."""
        session_path = ACTIVE_SESSIONS_DIR / guid
        session_path.mkdir(parents=True, exist_ok=True)
        return session_path

    async def initialize_session(
        self,
        guid: str,
        email: str = "",
        phone: str = "",
        user_request: str = ""
    ) -> Dict[str, Any]:
        """
        Initialize Claude CLI session with simple health check.

        This only verifies Claude CLI is alive and ready.
        The full autonomous prompt is sent with the first user message.

        Args:
            guid: User GUID
            email: User email (stored for later use)
            phone: User phone (stored for later use)
            user_request: User's build request (stored for later use)

        Returns:
            Dictionary with success status and session info
        """
        try:
            logger.info(f"=== INITIALIZING SESSION FOR GUID: {guid} ===")

            session_name = self.get_session_name(guid)
            session_path = self.get_session_path(guid)

            logger.info(f"Session name: {session_name}")
            logger.info(f"Session path: {session_path}")

            # Step 1: Ensure healthy session (reuse if possible, create if needed)
            session_created = self._ensure_healthy_session(
                session_name, session_path, guid
            )

            if not session_created:
                return {
                    'success': False,
                    'error': 'Failed to create or recover session'
                }

            # Step 2: Register session with MCP server
            logger.info("Step 2: Registering session with MCP server...")
            register_session(guid)

            # Step 3: Simple health check - ask Claude to call notify_ack
            logger.info("Step 3: Health check - verifying Claude CLI is responsive...")

            health_check_instruction = f'Call your MCP tool: notify_ack(guid="{guid}")'
            TmuxHelper.send_instruction(session_name, health_check_instruction)

            logger.info(f"Waiting for MCP ack from Claude CLI...")
            ack_received = await wait_for_ack(guid, timeout=self.HEALTH_CHECK_TIMEOUT)

            if not ack_received:
                logger.error("Timeout waiting for MCP ack - Claude CLI not responsive")
                return {
                    'success': False,
                    'error': 'Claude CLI did not respond to health check in time'
                }
            logger.info("MCP ack received - Claude CLI is alive and ready")

            # Step 4: Initialize status.json with session metadata
            status_file_path = session_path / "status.json"
            initial_status = {
                'state': 'ready',
                'progress': 100,
                'message': 'Session ready for chat',
                'phase': 'ready',
                'updated_at': datetime.utcnow().isoformat() + 'Z',
                'guid': guid,
                'email': email,
                'phone': phone,
                'user_request': user_request,
                'first_message_sent': False,  # Track if autonomous prompt has been sent
            }
            status_file_path.write_text(json.dumps(initial_status, indent=2))
            logger.info(f"Status written to {status_file_path}")

            logger.info("Session initialization complete")
            return {
                'success': True,
                'session_name': session_name,
                'session_path': str(session_path),
                'guid': guid
            }

        except Exception as e:
            logger.exception(f"Session initialization failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _ensure_healthy_session(
        self,
        session_name: str,
        session_path: Path,
        guid: str
    ) -> bool:
        """
        Ensure session exists and is healthy, or create new one.

        Strategy:
        1. Check if session exists
        2. If exists and < 5 days old, reuse it
        3. Otherwise, kill and recreate

        Returns:
            True if healthy session ready, False otherwise
        """
        try:
            # Check if session exists
            if TmuxHelper.session_exists(session_name):
                logger.info(f"Session {session_name} exists, checking age...")

                session_age_days = self._get_session_age_days(guid)

                if session_age_days is not None and session_age_days < self.MAX_SESSION_AGE_DAYS:
                    logger.info(f"Session is {session_age_days:.1f} days old, reusing")
                    return True
                else:
                    logger.info(f"Session too old ({session_age_days} days), recreating")
                    TmuxHelper.kill_session(session_name)

            # Create new session
            logger.info(f"Creating new tmux session: {session_name}")
            success = TmuxHelper.create_session(session_name, str(session_path))

            if success:
                logger.info("Session created successfully")
                return True
            else:
                logger.error("Failed to create session")
                return False

        except Exception as e:
            logger.exception(f"Error ensuring healthy session: {e}")
            return False

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

    async def health_check(self, guid: str, timeout: int = 10) -> bool:
        """
        Perform a quick health check on an existing session via MCP.

        Verifies Claude CLI is responsive by asking it to call notify_ack.

        Args:
            guid: Session GUID
            timeout: Seconds to wait for response

        Returns:
            True if CLI is responsive, False otherwise
        """
        try:
            session_name = self.get_session_name(guid)

            # Check if tmux session exists
            if not TmuxHelper.session_exists(session_name):
                logger.warning(f"Health check failed: tmux session {session_name} does not exist")
                return False

            # Send instruction to call MCP ack
            TmuxHelper.send_instruction(session_name, f'Call your MCP tool: notify_ack(guid="{guid}")')

            # Wait for ack via MCP
            ack_received = await wait_for_ack(guid, timeout=timeout)

            if ack_received:
                logger.debug(f"Health check passed for {guid}")
                return True
            else:
                logger.warning(f"Health check failed: timeout waiting for MCP ack")
                return False

        except Exception as e:
            logger.error(f"Health check error: {e}")
            return False
