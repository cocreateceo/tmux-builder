"""
Low-level tmux operations for managing Claude CLI sessions.

CRITICAL: This module implements the exact SmartBuild pattern for tmux command sending.
Do not modify timing or command structure without thorough testing.
"""

import subprocess
import time
import logging
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

from config import (
    CLI_COMMAND,
    TMUX_SEND_COMMAND_DELAY,
    TMUX_SEND_ENTER_DELAY,
    TMUX_CLAUDE_INIT_DELAY
)

logger = logging.getLogger(__name__)


@dataclass
class TmuxHealthCheck:
    """Result of a TMUX session health check."""
    session_exists: bool
    claude_responding: bool
    probe_success: bool
    probe_timestamp: Optional[str]
    error: Optional[str]

    def is_healthy(self) -> bool:
        """Return True if session is fully healthy."""
        return self.session_exists and self.claude_responding and self.probe_success


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

            # Step 4: Send bypass Enter keys (clear any initial prompts)
            for i in range(3):
                subprocess.run(
                    ["tmux", "send-keys", "-t", session_name, "Enter"],
                    stderr=subprocess.DEVNULL
                )
                time.sleep(0.5)

            # Step 5: Verify Claude is ready with probe
            from datetime import datetime
            timestamp = datetime.now().strftime("%H%M%S")
            probe_cmd = f"echo '[PROBE {timestamp}] Claude ready'"

            TmuxHelper._send_literal_command(session_name, probe_cmd, wait_after=2.0)

            # Capture and verify
            output = TmuxHelper.capture_pane_output(session_name)
            if "[PROBE" in output and "Claude ready" in output:
                logger.info(f"Claude CLI initialized successfully in: {session_name}")
                return True
            else:
                logger.warning(f"Probe verification failed, but continuing")
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
    def perform_health_probe(
        session_name: str,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ) -> TmuxHealthCheck:
        """
        Perform a health probe on a TMUX session.

        Sends a probe command to verify Claude is responding.
        Retries up to max_retries times on failure.
        """
        from datetime import datetime

        # Check session exists
        if not TmuxHelper.session_exists(session_name):
            return TmuxHealthCheck(
                session_exists=False,
                claude_responding=False,
                probe_success=False,
                probe_timestamp=None,
                error="Session not found"
            )

        # Generate unique probe ID
        timestamp = datetime.now().strftime("%H%M%S")
        probe_marker = f"[PROBE {timestamp}] Claude ready"
        probe_cmd = f"echo '{probe_marker}'"

        for attempt in range(max_retries):
            try:
                # Send probe command
                TmuxHelper._send_literal_command(
                    session_name,
                    probe_cmd,
                    wait_after=2.0
                )

                # Capture output
                output = TmuxHelper.capture_pane_output(session_name)

                if probe_marker in output:
                    return TmuxHealthCheck(
                        session_exists=True,
                        claude_responding=True,
                        probe_success=True,
                        probe_timestamp=datetime.now().isoformat() + "Z",
                        error=None
                    )

                # Probe not found, wait and retry
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

            except Exception as e:
                logger.warning(f"Probe attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        return TmuxHealthCheck(
            session_exists=True,
            claude_responding=False,
            probe_success=False,
            probe_timestamp=None,
            error=f"Probe failed after {max_retries} attempts"
        )

    @staticmethod
    def create_session_with_health_check(
        session_name: str,
        working_dir: Path,
        max_init_retries: int = 3
    ) -> TmuxHealthCheck:
        """
        Create TMUX session with full initialization and health verification.

        Complete initialization sequence:
        1. Create TMUX session
        2. CD to working directory
        3. Start Claude CLI with flags
        4. Wait for Claude initialization (3.0s)
        5. Send bypass Enter keys (clear prompts)
        6. Perform health probe with retries
        7. Return health status
        """
        for attempt in range(max_init_retries):
            try:
                # Kill existing if present
                if TmuxHelper.session_exists(session_name):
                    TmuxHelper.kill_session(session_name)
                    time.sleep(0.5)

                # Step 1: Create session
                logger.info(f"Creating TMUX session: {session_name} (attempt {attempt + 1})")
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

                # Step 4: Bypass initial prompts (3x Enter)
                for _ in range(3):
                    subprocess.run(
                        ["tmux", "send-keys", "-t", session_name, "Enter"],
                        stderr=subprocess.DEVNULL
                    )
                    time.sleep(0.5)

                # Step 5: Health probe
                health = TmuxHelper.perform_health_probe(session_name)

                if health.is_healthy():
                    logger.info(f"Session {session_name} initialized successfully")
                    return health

                # Not healthy, kill and retry
                logger.warning(f"Health check failed, retrying... ({attempt + 1}/{max_init_retries})")
                TmuxHelper.kill_session(session_name)
                time.sleep(1.0)

            except Exception as e:
                logger.error(f"Init attempt {attempt + 1} failed: {e}")
                TmuxHelper.kill_session(session_name)
                time.sleep(1.0)

        return TmuxHealthCheck(
            session_exists=False,
            claude_responding=False,
            probe_success=False,
            probe_timestamp=None,
            error=f"Initialization failed after {max_init_retries} attempts"
        )
