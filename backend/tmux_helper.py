"""
DEPRECATED: Low-level tmux operations for managing Claude CLI sessions.

This module is deprecated in favor of PTY streaming (pty_manager.py).
Kept for backwards compatibility with the main branch.

For new code, use:
- pty_manager.py for PTY session management
- stream_controller.py for high-level streaming control
- WebSocket endpoint /ws/{guid} for real-time output

Legacy note: This module implements the SmartBuild pattern for tmux command sending.
"""

import subprocess
import time
import logging
from typing import List
from pathlib import Path

from config import (
    CLI_COMMAND,
    TMUX_SEND_COMMAND_DELAY,
    TMUX_SEND_ENTER_DELAY,
    TMUX_CLAUDE_INIT_DELAY
)

logger = logging.getLogger(__name__)


class TmuxHelper:
    """Helper class for tmux operations."""

    @staticmethod
    def session_exists(session_name: str) -> bool:
        """Check if a tmux session exists."""
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", session_name],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def create_session(session_name: str, working_dir: Path) -> bool:
        """
        Create a new tmux session and start Claude CLI.

        Follows SmartBuild pattern exactly:
        1. Create session
        2. CD to working directory
        3. Start Claude with proper flags
        4. Wait for initialization
        5. Send bypass Enter keys
        6. Verify with probe command
        """
        try:
            # Kill existing session if it exists
            if TmuxHelper.session_exists(session_name):
                logger.info(f"Killing existing session: {session_name}")
                TmuxHelper.kill_session(session_name)

            # Step 1: Create new tmux session
            logger.info(f"Creating tmux session: {session_name}")
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name],
                stderr=subprocess.DEVNULL,
                check=True
            )

            # Step 2: CD to working directory
            TmuxHelper._send_literal_command(
                session_name,
                f"cd {working_dir}",
                wait_after=0.5
            )

            # Step 3: Start Claude CLI
            logger.info(f"Starting Claude CLI in session: {session_name}")
            TmuxHelper._send_literal_command(
                session_name,
                CLI_COMMAND,
                wait_after=TMUX_CLAUDE_INIT_DELAY
            )

            # Step 4: Wait for Claude CLI to fully initialize
            # No probe needed - marker-based handshake will verify readiness
            logger.info("Waiting for Claude CLI to initialize...")
            time.sleep(2.0)

            logger.info(f"Claude CLI session created: {session_name}")
            return True

        except Exception as e:
            logger.error(f"Error creating tmux session: {e}")
            return False

    @staticmethod
    def _send_literal_command(
        session_name: str,
        command: str,
        wait_after: float = TMUX_SEND_ENTER_DELAY
    ):
        """
        Send a literal command to tmux (internal helper).

        CRITICAL PATTERN - Do not modify:
        1. Send with -l flag (literal)
        2. Wait TMUX_SEND_COMMAND_DELAY
        3. Send Enter
        4. Wait specified time
        """
        # Send command literally
        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, "-l", command],
            stderr=subprocess.DEVNULL
        )
        time.sleep(TMUX_SEND_COMMAND_DELAY)

        # Send Enter
        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, "Enter"],
            stderr=subprocess.DEVNULL
        )
        time.sleep(wait_after)

    @staticmethod
    def kill_session(session_name: str) -> bool:
        """Kill a tmux session."""
        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", session_name],
                capture_output=True
            )
            return True
        except Exception:
            return False

    @staticmethod
    def send_instruction(session_name: str, instruction: str) -> bool:
        """
        Send an instruction to Claude in a tmux session.

        This is used to send the instruction that tells Claude to read
        a prompt file from disk.

        CRITICAL PATTERN - SmartBuild standard:
        1. Send text literally (-l flag)
        2. Wait 0.3s
        3. Send Enter
        4. Wait 1.2s
        """
        try:
            logger.debug(f"Sending instruction to {session_name}: {instruction[:100]}...")

            # Send instruction literally
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "-l", instruction],
                stderr=subprocess.DEVNULL
            )

            # CRITICAL: Wait for tmux to process
            time.sleep(TMUX_SEND_COMMAND_DELAY)

            # Send Enter
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "Enter"],
                stderr=subprocess.DEVNULL
            )

            # CRITICAL: Wait for Claude to start processing
            time.sleep(TMUX_SEND_ENTER_DELAY)

            logger.debug(f"Instruction sent successfully to {session_name}")
            return True

        except Exception as e:
            logger.error(f"Error sending instruction to tmux: {e}")
            return False

    @staticmethod
    def capture_pane_output(session_name: str, lines: int = 100) -> str:
        """Capture output from a tmux pane."""
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-t", session_name, "-p", "-S", f"-{lines}"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except Exception as e:
            print(f"Error capturing pane output: {e}")
            return ""

    @staticmethod
    def list_sessions() -> List[str]:
        """List all active tmux sessions."""
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return [s.strip() for s in result.stdout.split("\n") if s.strip()]
            return []
        except Exception:
            return []

    @staticmethod
    def verify_claude_responsive(session_name: str, timeout: int = 10) -> bool:
        """
        Verify that Claude CLI in the session is responsive.

        Sends a simple test message and checks for response marker.

        Args:
            session_name: Name of tmux session
            timeout: Timeout in seconds

        Returns:
            True if Claude is responsive, False otherwise
        """
        import tempfile

        try:
            # Create temporary marker file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.marker') as f:
                marker_file = f.name

            # Send test command to create marker
            test_command = f"touch {marker_file}"
            TmuxHelper.send_instruction(session_name, test_command)

            # Wait for marker file to appear
            start_time = time.time()
            while time.time() - start_time < timeout:
                if Path(marker_file).exists():
                    # Clean up and return success
                    Path(marker_file).unlink()
                    logger.debug(f"Session {session_name} is responsive")
                    return True
                time.sleep(0.5)

            # Timeout - not responsive
            logger.warning(f"Session {session_name} not responsive after {timeout}s")
            return False

        except Exception as e:
            logger.error(f"Error checking session responsiveness: {e}")
            return False

    @staticmethod
    def send_keys(session_name: str, keys: str) -> bool:
        """
        Send keys directly to tmux session (simple wrapper).

        Args:
            session_name: Name of tmux session
            keys: Keys to send

        Returns:
            True if successful, False otherwise
        """
        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, "-l", keys],
                stderr=subprocess.DEVNULL
            )
            time.sleep(TMUX_SEND_COMMAND_DELAY)
            return True
        except Exception as e:
            logger.error(f"Error sending keys: {e}")
            return False
