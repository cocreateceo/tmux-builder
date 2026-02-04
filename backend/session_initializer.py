"""
Manages Claude CLI session initialization with notify.sh-based health check.

Protocol:
1. Create tmux session, start Claude CLI
2. Generate notify.sh script for the session
3. Send instruction to call ./notify.sh ack
4. Wait for ack via WebSocket server
5. Done! Session ready for chat.
"""

import asyncio
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
from notify_generator import generate_notify_script, get_notify_script_path
from system_prompt_generator import generate_system_prompt
from ws_server import get_server

logger = logging.getLogger(__name__)


class SessionInitializer:
    """Handles initialization of Claude CLI sessions with notify.sh health check."""

    # Session reuse settings
    MAX_SESSION_AGE_DAYS = 5
    HEALTH_CHECK_TIMEOUT = 30  # seconds to wait for ack

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
        user_request: str = "",
        client_name: str = ""
    ) -> Dict[str, Any]:
        """
        Initialize Claude CLI session with notify.sh health check.

        This only verifies Claude CLI is alive and ready.
        The full autonomous prompt is sent with the first user message.

        Args:
            guid: User GUID
            email: User email (stored for later use)
            phone: User phone (stored for later use)
            user_request: User's build request (stored for later use)
            client_name: Client's name (stored for display)

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

            # Step 2: Create session subfolders
            logger.info("Step 2: Creating session folder structure...")
            for folder in ['tmp', 'code', 'infrastructure', 'docs']:
                folder_path = session_path / folder
                folder_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"  Created: {folder}/")

            # Step 3: Generate notify.sh script for this session
            logger.info("Step 3: Generating notify.sh script...")
            notify_path = generate_notify_script(session_path, guid)
            logger.info(f"notify.sh created at: {notify_path}")

            # Step 4: Generate system_prompt.txt
            logger.info("Step 4: Generating system_prompt.txt...")
            system_prompt_path = generate_system_prompt(session_path, guid)
            logger.info(f"system_prompt.txt created at: {system_prompt_path}")

            # Step 5: Clear any stale prompt.txt to prevent auto-execution of old tasks
            logger.info("Step 5: Clearing stale prompt.txt...")
            prompt_file = session_path / "prompt.txt"
            if prompt_file.exists():
                prompt_file.unlink()
                logger.info("  Removed stale prompt.txt")

            # Step 6: Health check - ask Claude to read system_prompt.txt and ack
            logger.info("Step 6: Health check - verifying Claude CLI is responsive...")

            # Claude is in session folder, use relative path for notify.sh
            # IMPORTANT: Tell Claude to ONLY ack, NOT to look for tasks
            health_check_instruction = 'Read system_prompt.txt and run: ./notify.sh ack - then WAIT for the next instruction. Do NOT read prompt.txt yet.'
            TmuxHelper.send_instruction(session_name, health_check_instruction)

            logger.info(f"Waiting for ack from Claude CLI via WebSocket...")
            ack_received = await self._wait_for_ack(guid, timeout=self.HEALTH_CHECK_TIMEOUT)

            if not ack_received:
                logger.warning("Timeout waiting for ack - but continuing anyway (CLI may still work)")
                # Don't fail - the WebSocket server might not have been ready
                # or Claude may have responded differently

            if ack_received:
                logger.info("Ack received - Claude CLI is alive and ready")

            # Step 7: Initialize status.json with session metadata
            # IMPORTANT: Preserve existing metadata if status.json already exists
            # This prevents overwriting client data when re-initializing a session
            status_file_path = session_path / "status.json"
            existing_status = {}
            if status_file_path.exists():
                try:
                    existing_status = json.loads(status_file_path.read_text())
                    logger.info(f"Preserving existing metadata from status.json")
                except (json.JSONDecodeError, IOError):
                    existing_status = {}

            initial_status = {
                'state': 'ready',
                'progress': 100,
                'message': 'Session ready for chat',
                'phase': 'ready',
                # Preserve created_at if exists, otherwise set new
                'created_at': existing_status.get('created_at') or datetime.utcnow().isoformat() + 'Z',
                'updated_at': datetime.utcnow().isoformat() + 'Z',
                'guid': guid,
                # Preserve critical user data - use new values only if provided AND not default
                'email': email if email and email != 'default_user@demo.local' else existing_status.get('email', email),
                'phone': phone if phone else existing_status.get('phone', ''),
                'user_request': user_request if user_request else existing_status.get('user_request', ''),
                'client_name': client_name if client_name else existing_status.get('client_name', ''),
                # Preserve other fields
                'first_message_sent': existing_status.get('first_message_sent', False),
                'deployed_url': existing_status.get('deployed_url'),
                'initial_request': existing_status.get('initial_request', ''),
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
                    # Regenerate notify.sh and system_prompt.txt in case they're missing
                    generate_notify_script(session_path, guid)
                    generate_system_prompt(session_path, guid)
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

    async def _wait_for_ack(self, guid: str, timeout: float = 30) -> bool:
        """
        Wait for ack message from Claude via WebSocket.

        Args:
            guid: Session GUID
            timeout: Seconds to wait

        Returns:
            True if ack received, False if timeout
        """
        server = get_server()
        if not server:
            logger.warning("WebSocket server not running, skipping ack wait")
            return False

        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check message history for ack
            if guid in server.message_history:
                for msg in server.message_history[guid]:
                    if msg.get('type') == 'ack':
                        return True

            await asyncio.sleep(0.5)

        return False

    async def health_check(self, guid: str, timeout: int = 10) -> bool:
        """
        Perform a quick health check on an existing session.

        Verifies Claude CLI is responsive by asking it to call ./notify.sh ack.

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

            # Clear any previous ack messages
            server = get_server()
            if server and guid in server.message_history:
                server.message_history[guid] = [
                    m for m in server.message_history[guid] if m.get('type') != 'ack'
                ]

            # Send instruction to call notify.sh ack (using absolute path)
            notify_path = get_notify_script_path(guid)
            TmuxHelper.send_instruction(session_name, f'{notify_path} ack')

            # Wait for ack via WebSocket
            ack_received = await self._wait_for_ack(guid, timeout=timeout)

            if ack_received:
                logger.debug(f"Health check passed for {guid}")
                return True
            else:
                logger.warning(f"Health check failed: timeout waiting for ack")
                return False

        except Exception as e:
            logger.error(f"Health check error: {e}")
            return False
