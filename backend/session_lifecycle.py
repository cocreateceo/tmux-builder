"""
Session Lifecycle Manager

Manages the complete lifecycle of a Claude CLI session including:
- Folder structure initialization
- TMUX session creation and health monitoring
- State transitions and persistence
- Recovery from failures
"""

import json
import logging
from enum import Enum
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from config import ACTIVE_SESSIONS_DIR

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Session lifecycle states."""
    CREATED = "created"           # Folder structure exists
    INITIALIZING = "initializing" # TMUX session starting
    READY = "ready"               # Claude CLI ready for commands
    PROCESSING = "processing"     # Job in progress
    ERROR = "error"               # Recoverable error state
    TERMINATED = "terminated"     # Session ended


class SessionLifecycle:
    """
    Manages session lifecycle from creation to termination.

    Folder Structure Created:
    ```
    sessions/active/<session_id>/
    ├── metadata.json          # Session metadata
    ├── job_queue.json         # Pending/running/completed jobs
    ├── prompts/               # Prompt files for Claude
    ├── output/                # Output files from Claude
    ├── logs/                  # Session logs
    │   └── session_<id>.log
    └── state/                 # State tracking
        └── health.json        # Health status
    ```
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session_path = ACTIVE_SESSIONS_DIR / session_id
        self._state = SessionState.CREATED
        self._tmux_session_name: Optional[str] = None

    def initialize_structure(self) -> Path:
        """
        Initialize complete session folder structure.

        This is Step 1 of session startup - create all required directories
        and initial state files before any TMUX operations.

        Returns:
            Path to session directory
        """
        # Create main directory
        self.session_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        subdirs = ["prompts", "output", "logs", "state"]
        for subdir in subdirs:
            (self.session_path / subdir).mkdir(exist_ok=True)

        # Create metadata.json
        metadata = {
            "session_id": self.session_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "state": SessionState.CREATED.value,
            "version": "1.0"
        }
        self._write_json(self.session_path / "metadata.json", metadata)

        # Create initial health.json
        health = {
            "state": SessionState.CREATED.value,
            "tmux_session_active": False,
            "claude_initialized": False,
            "last_check": datetime.utcnow().isoformat() + "Z",
            "last_probe_success": None,
            "error_count": 0,
            "last_error": None
        }
        self._write_json(self.session_path / "state" / "health.json", health)

        # Create empty job_queue.json
        self._write_json(self.session_path / "job_queue.json", [])

        logger.info(f"Initialized session structure: {self.session_path}")
        return self.session_path

    def get_health_status(self) -> Dict:
        """
        Get current health status of the session.

        Returns:
            Dictionary with health status including:
            - state: Current SessionState
            - tmux_session_active: Boolean
            - claude_initialized: Boolean
            - last_check: ISO timestamp
            - error_count: Number of errors
        """
        health_path = self.session_path / "state" / "health.json"

        if not health_path.exists():
            return {
                "state": SessionState.CREATED.value,
                "tmux_session_active": False,
                "claude_initialized": False,
                "last_check": datetime.utcnow().isoformat() + "Z",
                "error_count": 0
            }

        return self._read_json(health_path)

    def update_health_status(self, updates: Dict) -> None:
        """Update health status with new values."""
        health = self.get_health_status()
        health.update(updates)
        health["last_check"] = datetime.utcnow().isoformat() + "Z"
        self._write_json(self.session_path / "state" / "health.json", health)

    def _write_json(self, path: Path, data) -> None:
        """Write JSON data to file."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _read_json(self, path: Path) -> Dict:
        """Read JSON data from file."""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
