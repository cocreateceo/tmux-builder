"""
Manages Claude CLI session initialization with file-based REPL handshake.

Protocol:
1. Create tmux session, start Claude CLI
2. Send: "Create ready.marker when ready"
3. Wait for ready.marker
4. Write system_prompt.txt
5. Send: "Read system_prompt.txt, create ack.marker when done"
6. Wait for ack.marker
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
    READY_MARKER,
    ACK_MARKER,
    get_markers_path,
    get_marker_file,
)
from tmux_helper import TmuxHelper
from prompt_manager import PromptManager
from marker_utils import (
    wait_for_marker,
    clear_markers,
    delete_marker,
)

logger = logging.getLogger(__name__)


class SessionInitializer:
    """Handles initialization of Claude CLI sessions with marker-based handshake."""

    # Session reuse settings
    MAX_SESSION_AGE_DAYS = 5
    HEALTH_CHECK_TIMEOUT = 10

    def __init__(self):
        """Initialize SessionInitializer."""
        self.prompt_manager = PromptManager()
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

    def initialize_session(
        self,
        guid: str,
        email: str,
        phone: str,
        user_request: str
    ) -> Dict[str, Any]:
        """
        Initialize Claude CLI session using file-based REPL handshake.

        Args:
            guid: User GUID
            email: User email
            phone: User phone
            user_request: User's build request

        Returns:
            Dictionary with success status and session info
        """
        try:
            logger.info(f"=== INITIALIZING SESSION FOR GUID: {guid} ===")

            session_name = self.get_session_name(guid)
            session_path = self.get_session_path(guid)

            logger.info(f"Session name: {session_name}")
            logger.info(f"Session path: {session_path}")

            # Setup markers directory
            markers_path = get_markers_path(guid)
            logger.info(f"Markers directory: {markers_path}")

            # Clear any stale markers
            clear_markers(guid)
            logger.info("Cleared stale markers")

            # Get marker file paths for the prompt
            ready_marker_path = get_marker_file(guid, READY_MARKER)
            ack_marker_path = get_marker_file(guid, ACK_MARKER)

            # Step 1: Ensure healthy session (reuse if possible, create if needed)
            session_created = self._ensure_healthy_session(
                session_name, session_path, guid
            )

            if not session_created:
                return {
                    'success': False,
                    'error': 'Failed to create or recover session'
                }

            # Step 2: Send ready instruction and wait for ready.marker
            logger.info("Step 2: Sending ready instruction...")
            ready_instruction = (
                f"You are now connected. Signal that you are ready by creating "
                f"the file: {ready_marker_path}\n"
                f"Use: touch {ready_marker_path}"
            )
            TmuxHelper.send_instruction(session_name, ready_instruction)

            logger.info(f"Waiting for ready.marker: {ready_marker_path}")
            if not wait_for_marker(guid, READY_MARKER):
                logger.error("Timeout waiting for ready.marker")
                return {
                    'success': False,
                    'error': 'Claude CLI did not signal ready in time'
                }
            logger.info("ready.marker received")

            # Step 3: Prepare system prompt with marker paths
            logger.info("Step 3: Preparing system prompt...")

            # Define all marker paths for the system prompt
            completed_marker_path = get_marker_file(guid, "completed.marker")
            status_file_path = session_path / "status.json"

            system_prompt = self.prompt_manager.render_system_prompt(
                'autonomous_agent',
                {
                    'guid': guid,
                    'email': email,
                    'phone': phone,
                    'user_request': user_request,
                    'session_path': str(session_path),
                    'markers_path': str(markers_path),
                    'aws_profile': 'sunware',
                    # New marker names
                    'ready_marker': str(ready_marker_path),
                    'ack_marker': str(ack_marker_path),
                    'completed_marker': str(completed_marker_path),
                    'status_file': str(status_file_path),
                    # Legacy marker names (for template compatibility)
                    'initialized_marker': str(ready_marker_path),  # ready = initialized
                    'processing_marker': str(ack_marker_path),     # ack = processing
                }
            )

            # Write system prompt to file
            system_prompt_file = session_path / "system_prompt.txt"
            system_prompt_file.write_text(system_prompt)
            logger.info(f"System prompt written to {system_prompt_file}")

            # Initialize status.json
            initial_status = {
                'state': 'initializing',
                'progress': 10,
                'message': 'Reading system prompt',
                'phase': 'init',
                'updated_at': datetime.utcnow().isoformat() + 'Z',
                'guid': guid,
                'email': email,
                'user_request': user_request,
            }
            status_file_path.write_text(json.dumps(initial_status, indent=2))
            logger.info(f"Initial status written to {status_file_path}")

            # Step 4: Send instruction to read system prompt, wait for ack
            # Retry up to 3 times with delay if ack.marker not received
            logger.info("Step 4: Sending read-and-ack instruction...")

            # Clear ready marker before sending next instruction
            delete_marker(guid, READY_MARKER)

            # Single-line instruction (avoid multi-line issues with tmux)
            # IMPORTANT: Explicitly tell Claude this is pre-authorized to avoid confirmation prompts
            read_instruction = (
                f"This is a pre-authorized autonomous build session. Read {system_prompt_file} and execute immediately. "
                f"Do NOT ask for confirmation - the user already approved by submitting. Create {ack_marker_path} and start building."
            )

            max_retries = 3
            ack_received = False

            for attempt in range(1, max_retries + 1):
                logger.info(f"Attempt {attempt}/{max_retries}: Sending read instruction...")

                # Clear any stale ack marker before retry
                delete_marker(guid, ACK_MARKER)

                # Send instruction
                TmuxHelper.send_instruction(session_name, read_instruction)

                logger.info(f"Waiting for ack.marker: {ack_marker_path}")
                if wait_for_marker(guid, ACK_MARKER):
                    logger.info("ack.marker received - system prompt acknowledged")
                    ack_received = True
                    break
                else:
                    logger.warning(f"Attempt {attempt} failed - ack.marker not received")
                    if attempt < max_retries:
                        retry_delay = 3.0 * attempt  # Increasing delay: 3s, 6s, 9s
                        logger.info(f"Retrying in {retry_delay}s...")
                        time.sleep(retry_delay)

            if not ack_received:
                logger.error(f"Failed to receive ack.marker after {max_retries} attempts")
                return {
                    'success': False,
                    'error': f'Claude CLI did not acknowledge system prompt after {max_retries} attempts'
                }

            # Step 5: Update status and return success
            final_status = {
                'state': 'ready',
                'progress': 100,
                'message': 'Session initialized and ready',
                'phase': 'ready',
                'updated_at': datetime.utcnow().isoformat() + 'Z',
                'guid': guid,
                'email': email,
                'user_request': user_request,
            }
            status_file_path.write_text(json.dumps(final_status, indent=2))

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
