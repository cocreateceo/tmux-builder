"""
PTY Manager for Claude CLI sessions.

Replaces tmux-based approach with direct PTY control for real-time streaming.
Uses ptyprocess for cross-platform PTY handling.
"""

import os
import logging
import asyncio
from typing import Optional, Callable, Dict, Any
from pathlib import Path
from datetime import datetime

import ptyprocess

from config import (
    CLI_PATH,
    CLI_FLAGS,
    ACTIVE_SESSIONS_DIR,
    get_session_path,
)

logger = logging.getLogger(__name__)


class PTYSession:
    """Manages a single Claude CLI PTY session."""

    def __init__(self, guid: str, working_dir: Optional[Path] = None):
        """
        Initialize PTY session.

        Args:
            guid: Session GUID
            working_dir: Working directory for Claude CLI
        """
        self.guid = guid
        self.working_dir = working_dir or get_session_path(guid)
        self.pty: Optional[ptyprocess.PtyProcess] = None
        self.created_at = datetime.utcnow()
        self.output_buffer: list[str] = []
        self.max_buffer_lines = 1000
        self._read_task: Optional[asyncio.Task] = None
        self._output_callback: Optional[Callable[[str], None]] = None

        # Ensure working directory exists
        self.working_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"PTYSession initialized: {guid}")

    def start(self, output_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Start Claude CLI in PTY.

        Args:
            output_callback: Async callback for output data

        Returns:
            True if started successfully
        """
        try:
            self._output_callback = output_callback

            # Build command
            cmd = [CLI_PATH] + CLI_FLAGS.split()

            logger.info(f"Starting PTY: {' '.join(cmd)} in {self.working_dir}")

            # Spawn PTY process
            self.pty = ptyprocess.PtyProcess.spawn(
                cmd,
                cwd=str(self.working_dir),
                env={
                    **os.environ,
                    'TERM': 'xterm-256color',
                    'COLUMNS': '120',
                    'LINES': '40',
                }
            )

            logger.info(f"PTY started with PID: {self.pty.pid}")
            return True

        except Exception as e:
            logger.error(f"Failed to start PTY: {e}")
            return False

    def read_output(self, timeout: float = 0.1) -> Optional[str]:
        """
        Read available output from PTY (non-blocking).

        Args:
            timeout: Read timeout in seconds

        Returns:
            Output string or None if no data
        """
        if not self.pty or not self.pty.isalive():
            return None

        try:
            # Check if data available
            if self.pty.read_nonblocking(size=0, timeout=0):
                pass  # Just checking
        except EOFError:
            return None
        except Exception:
            pass

        try:
            data = self.pty.read_nonblocking(size=4096, timeout=timeout)
            if data:
                # Add to buffer
                lines = data.split('\n')
                self.output_buffer.extend(lines)
                # Trim buffer if too large
                if len(self.output_buffer) > self.max_buffer_lines:
                    self.output_buffer = self.output_buffer[-self.max_buffer_lines:]
                return data
        except EOFError:
            logger.info(f"PTY EOF reached for {self.guid}")
            return None
        except ptyprocess.PtyProcessError:
            return None
        except Exception as e:
            # Timeout or no data
            if "Timeout" not in str(e):
                logger.debug(f"Read exception: {e}")
            return None

        return None

    async def read_output_async(self) -> Optional[str]:
        """Async wrapper for read_output."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.read_output)

    def send_input(self, data: str) -> bool:
        """
        Send input to PTY.

        Args:
            data: Input string to send

        Returns:
            True if sent successfully
        """
        if not self.pty or not self.pty.isalive():
            logger.warning(f"Cannot send input - PTY not alive: {self.guid}")
            return False

        try:
            # PTY expects bytes, encode string if needed
            if isinstance(data, str):
                data = data.encode('utf-8')
            self.pty.write(data)
            logger.debug(f"Sent {len(data)} bytes to PTY {self.guid}")
            return True
        except Exception as e:
            logger.error(f"Failed to send input: {e}")
            return False

    def resize(self, rows: int, cols: int) -> bool:
        """
        Resize PTY terminal.

        Args:
            rows: Number of rows
            cols: Number of columns

        Returns:
            True if resized successfully
        """
        if not self.pty or not self.pty.isalive():
            return False

        try:
            self.pty.setwinsize(rows, cols)
            logger.debug(f"Resized PTY {self.guid} to {rows}x{cols}")
            return True
        except Exception as e:
            logger.error(f"Failed to resize PTY: {e}")
            return False

    def is_alive(self) -> bool:
        """Check if PTY process is still running."""
        return self.pty is not None and self.pty.isalive()

    def kill(self) -> bool:
        """
        Kill the PTY process.

        Returns:
            True if killed successfully
        """
        if not self.pty:
            return True

        try:
            if self.pty.isalive():
                self.pty.terminate(force=True)
                logger.info(f"PTY killed: {self.guid}")
            return True
        except Exception as e:
            logger.error(f"Failed to kill PTY: {e}")
            return False

    def get_buffer(self) -> str:
        """Get buffered output for reconnection."""
        return '\n'.join(self.output_buffer)

    def __del__(self):
        """Cleanup on deletion."""
        self.kill()


class PTYManager:
    """Manages multiple PTY sessions."""

    def __init__(self):
        """Initialize PTY manager."""
        self.sessions: Dict[str, PTYSession] = {}
        logger.info("PTYManager initialized")

    def create_session(
        self,
        guid: str,
        working_dir: Optional[Path] = None,
        output_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[PTYSession]:
        """
        Create a new PTY session.

        Args:
            guid: Session GUID
            working_dir: Working directory
            output_callback: Callback for output

        Returns:
            PTYSession if created, None on error
        """
        # Check if session already exists
        if guid in self.sessions:
            existing = self.sessions[guid]
            if existing.is_alive():
                logger.info(f"Returning existing session: {guid}")
                return existing
            else:
                # Clean up dead session
                del self.sessions[guid]

        # Create new session
        session = PTYSession(guid, working_dir)
        if session.start(output_callback):
            self.sessions[guid] = session
            logger.info(f"Created PTY session: {guid}")
            return session

        logger.error(f"Failed to create PTY session: {guid}")
        return None

    def get_session(self, guid: str) -> Optional[PTYSession]:
        """Get existing session by GUID."""
        session = self.sessions.get(guid)
        if session and not session.is_alive():
            del self.sessions[guid]
            return None
        return session

    def kill_session(self, guid: str) -> bool:
        """Kill and remove a session."""
        session = self.sessions.pop(guid, None)
        if session:
            return session.kill()
        return True

    def list_sessions(self) -> list[str]:
        """List active session GUIDs."""
        # Clean up dead sessions
        dead = [g for g, s in self.sessions.items() if not s.is_alive()]
        for g in dead:
            del self.sessions[g]
        return list(self.sessions.keys())

    def cleanup_all(self):
        """Kill all sessions."""
        for guid in list(self.sessions.keys()):
            self.kill_session(guid)
        logger.info("All PTY sessions cleaned up")


# Global PTY manager instance
pty_manager = PTYManager()
