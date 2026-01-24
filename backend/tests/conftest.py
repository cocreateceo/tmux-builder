"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_sessions_dir(tmp_path):
    """Create a temporary sessions directory."""
    sessions_dir = tmp_path / "sessions" / "active"
    sessions_dir.mkdir(parents=True)
    return sessions_dir


@pytest.fixture
def mock_session(temp_sessions_dir):
    """Create a mock session with basic structure."""
    session_id = "test_session_001"
    session_path = temp_sessions_dir / session_id
    session_path.mkdir()

    # Create subdirectories
    (session_path / "prompts").mkdir()
    (session_path / "output").mkdir()
    (session_path / "logs").mkdir()
    (session_path / "state").mkdir()

    # Create metadata
    import json
    metadata = {
        "session_id": session_id,
        "created_at": "2026-01-24T10:00:00Z",
        "state": "created"
    }
    (session_path / "metadata.json").write_text(json.dumps(metadata))
    (session_path / "job_queue.json").write_text("[]")

    return session_id, session_path


@pytest.fixture
def mock_tmux(monkeypatch):
    """Mock TMUX subprocess calls."""
    from unittest.mock import MagicMock

    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout=""))
    monkeypatch.setattr("subprocess.run", mock_run)

    return mock_run
