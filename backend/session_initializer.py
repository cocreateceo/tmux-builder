"""Manages Claude CLI session initialization with health checks."""

import logging
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json

from config import SESSIONS_DIR, TMUX_SESSION_PREFIX
from tmux_helper import TmuxHelper
from prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class SessionInitializer:
    """Handles initialization of Claude CLI sessions with health checks."""

    # Session reuse settings
    MAX_SESSION_AGE_DAYS = 5
    HEALTH_CHECK_TIMEOUT = 10

    def __init__(self):
        """Initialize SessionInitializer."""
        self.prompt_manager = PromptManager()
        logger.info("SessionInitializer ready")

    @staticmethod
    def get_session_name(guid: str) -> str:
        """
        Generate tmux session name from GUID.

        Args:
            guid: User GUID

        Returns:
            Session name string
        """
        return f"{TMUX_SESSION_PREFIX}_{guid}"

    @staticmethod
    def get_session_path(guid: str) -> Path:
        """
        Get session directory path for GUID.

        Args:
            guid: User GUID

        Returns:
            Path to session directory
        """
        # Structure: SESSIONS_DIR/active/<guid>/
        session_path = SESSIONS_DIR / "active" / guid
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
        Initialize Claude CLI session for user.

        Checks if session already exists and is healthy before creating new one.

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

            # Ensure healthy session (reuse if possible, create if needed)
            session_created = self._ensure_healthy_session(
                session_name, session_path, guid
            )

            if not session_created:
                return {
                    'success': False,
                    'error': 'Failed to create or recover session'
                }

            # Create markers directory
            markers_path = session_path / "markers"
            markers_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✓ Markers directory: {markers_path}")

            # Define marker file paths
            initialized_marker = markers_path / "initialized.marker"
            processing_marker = markers_path / "processing.marker"
            completed_marker = markers_path / "completed.marker"

            # Render system prompt
            logger.info("Rendering autonomous agent system prompt...")
            system_prompt = self.prompt_manager.render_system_prompt(
                'autonomous_agent',
                {
                    'guid': guid,
                    'email': email,
                    'phone': phone,
                    'user_request': user_request,
                    'session_path': str(session_path),
                    'aws_profile': 'sunware',
                    'initialized_marker': str(initialized_marker),
                    'processing_marker': str(processing_marker),
                    'completed_marker': str(completed_marker)
                }
            )

            # Write system prompt to file
            system_prompt_file = session_path / "system_prompt.txt"
            system_prompt_file.write_text(system_prompt)
            logger.info(f"✓ System prompt written to {system_prompt_file}")

            # Initialize status.json
            status_file = session_path / "status.json"
            initial_status = {
                'status': 'initializing',
                'phase': 0,
                'progress': 5,
                'message': 'Session initialized, loading instructions',
                'guid': guid,
                'email': email,
                'user_request': user_request,
                'created_at': datetime.utcnow().isoformat() + 'Z'
            }
            status_file.write_text(json.dumps(initial_status, indent=2))
            logger.info(f"✓ Initial status written to {status_file}")

            # Send system prompt to Claude
            logger.info("Sending system prompt to Claude CLI...")
            TmuxHelper.send_keys(session_name, f"cat {system_prompt_file}")
            time.sleep(1)
            TmuxHelper.send_keys(session_name, "")  # Press enter
            time.sleep(0.5)
            # Send enter again to submit
            subprocess_result = subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "Enter"],
                stderr=subprocess.DEVNULL
            )

            # Wait for initialized marker
            logger.info(f"Waiting for initialized marker: {initialized_marker}")
            timeout = 60  # 60 seconds timeout
            start_time = time.time()

            while time.time() - start_time < timeout:
                if initialized_marker.exists():
                    logger.info("✓ Initialized marker detected!")
                    logger.info("✓ Session initialization complete")
                    return {
                        'success': True,
                        'session_name': session_name,
                        'session_path': str(session_path),
                        'guid': guid
                    }
                time.sleep(0.5)

            # Timeout reached
            logger.error(f"Timeout waiting for initialized marker after {timeout}s")
            return {
                'success': False,
                'error': f'Timeout waiting for initialized marker'
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
        2. If exists, verify it's responsive
        3. If responsive and < 5 days old, reuse it
        4. Otherwise, kill and recreate

        Args:
            session_name: TMUX session name
            session_path: Path to session directory
            guid: User GUID

        Returns:
            True if healthy session ready, False otherwise
        """
        try:
            # Check if session exists
            if TmuxHelper.session_exists(session_name):
                logger.info(f"Session {session_name} already exists, checking health...")

                # Verify responsiveness
                is_responsive = TmuxHelper.verify_claude_responsive(
                    session_name,
                    timeout=self.HEALTH_CHECK_TIMEOUT
                )

                if is_responsive:
                    # Check age
                    session_age_days = self._get_session_age_days(guid)

                    if session_age_days is not None and session_age_days < self.MAX_SESSION_AGE_DAYS:
                        logger.info(
                            f"✓ Session is healthy and {session_age_days:.1f} days old, reusing"
                        )
                        return True
                    else:
                        logger.info(
                            f"Session is {session_age_days} days old (max: {self.MAX_SESSION_AGE_DAYS}), recreating"
                        )

                # Not responsive or too old - kill it
                logger.info("Session not healthy, killing and recreating...")
                TmuxHelper.kill_session(session_name)

            # Create new session
            logger.info(f"Creating new tmux session: {session_name}")
            success = TmuxHelper.create_session(session_name, str(session_path))

            if success:
                logger.info("✓ Session created successfully")
                return True
            else:
                logger.error("✗ Failed to create session")
                return False

        except Exception as e:
            logger.exception(f"Error ensuring healthy session: {e}")
            return False

    def _get_session_age_days(self, guid: str) -> Optional[float]:
        """
        Get age of session in days from status.json.

        Args:
            guid: User GUID

        Returns:
            Age in days, or None if unable to determine
        """
        try:
            session_path = self.get_session_path(guid)
            status_file = session_path / "status.json"

            if not status_file.exists():
                return None

            status = json.loads(status_file.read_text())
            created_at_str = status.get('created_at')

            if not created_at_str:
                return None

            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            age = datetime.utcnow() - created_at.replace(tzinfo=None)

            return age.total_seconds() / 86400  # Convert to days

        except Exception as e:
            logger.warning(f"Unable to determine session age: {e}")
            return None
