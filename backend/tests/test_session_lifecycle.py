import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from session_lifecycle import SessionLifecycle, SessionState


class TestSessionLifecycle:
    """Test session lifecycle management."""

    def test_session_states_exist(self):
        """Verify all session states are defined."""
        assert SessionState.CREATED.value == "created"
        assert SessionState.INITIALIZING.value == "initializing"
        assert SessionState.READY.value == "ready"
        assert SessionState.PROCESSING.value == "processing"
        assert SessionState.ERROR.value == "error"
        assert SessionState.TERMINATED.value == "terminated"

    def test_session_folder_structure_created(self, tmp_path):
        """Verify complete folder structure is created."""
        session_id = "test_session_001"

        with patch('session_lifecycle.ACTIVE_SESSIONS_DIR', tmp_path):
            lifecycle = SessionLifecycle(session_id)
            lifecycle.initialize_structure()

        session_path = tmp_path / session_id
        assert session_path.exists()
        assert (session_path / "prompts").exists()
        assert (session_path / "output").exists()
        assert (session_path / "logs").exists()
        assert (session_path / "state").exists()
        assert (session_path / "metadata.json").exists()
        assert (session_path / "state" / "health.json").exists()

    def test_health_check_initial_state(self, tmp_path):
        """Verify health check returns proper initial state."""
        session_id = "test_session_002"

        with patch('session_lifecycle.ACTIVE_SESSIONS_DIR', tmp_path):
            lifecycle = SessionLifecycle(session_id)
            lifecycle.initialize_structure()
            health = lifecycle.get_health_status()

        assert health["state"] == "created"
        assert health["tmux_session_active"] == False
        assert health["claude_initialized"] == False
        assert "last_check" in health
