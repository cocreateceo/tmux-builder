"""Tests for SessionCreator - session folder creation and configuration."""

import pytest
import json
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
import sys
import re
sys.path.insert(0, str(Path(__file__).parent.parent))

from session_creator import SessionCreator, AWS_PROFILE, AZURE_PROFILE


class TestSessionCreator:
    """Test session creation functionality."""

    def test_create_session_generates_id(self, tmp_path):
        """Returns timestamped session ID starting with 'sess_'."""
        with patch('session_creator.USERS_DIR', tmp_path):
            # Create user folder first
            user_id = "test-user-guid-123"
            (tmp_path / user_id / "sessions").mkdir(parents=True)

            creator = SessionCreator()
            session_id = creator.create_session(
                user_id=user_id,
                host_provider="aws",
                site_type="static"
            )

            # Session ID should start with "sess_"
            assert session_id.startswith("sess_")

            # Session ID should match format: sess_YYYYMMDD_HHMMSS
            pattern = r"^sess_\d{8}_\d{6}$"
            assert re.match(pattern, session_id), f"Session ID '{session_id}' doesn't match format sess_YYYYMMDD_HHMMSS"

    def test_session_folder_structure_created(self, tmp_path):
        """All session folders are created correctly."""
        with patch('session_creator.USERS_DIR', tmp_path):
            # Create user folder first
            user_id = "test-user-guid-456"
            (tmp_path / user_id / "sessions").mkdir(parents=True)

            creator = SessionCreator()
            session_id = creator.create_session(
                user_id=user_id,
                host_provider="azure",
                site_type="dynamic"
            )

            session_path = tmp_path / user_id / "sessions" / session_id

            # Verify all expected directories exist
            assert session_path.is_dir()
            assert (session_path / ".claude").is_dir()
            assert (session_path / ".claude" / "agents").is_dir()
            assert (session_path / ".claude" / "skills").is_dir()
            assert (session_path / "source").is_dir()
            assert (session_path / "deployment").is_dir()
            assert (session_path / "deployment" / "tests").is_dir()
            assert (session_path / "logs").is_dir()
            assert (session_path / "prompts").is_dir()
            assert (session_path / "output").is_dir()
            assert (session_path / "state").is_dir()

    def test_session_config_saved(self, tmp_path):
        """config.json has correct structure with sunwaretech profiles."""
        with patch('session_creator.USERS_DIR', tmp_path):
            # Create user folder first
            user_id = "test-user-guid-789"
            (tmp_path / user_id / "sessions").mkdir(parents=True)

            creator = SessionCreator()
            session_id = creator.create_session(
                user_id=user_id,
                host_provider="aws",
                site_type="static"
            )

            session_path = tmp_path / user_id / "sessions" / session_id
            config_path = session_path / "deployment" / "config.json"

            # Config file should exist
            assert config_path.is_file()

            # Load and verify config structure
            config = json.loads(config_path.read_text())

            assert config["host_provider"] == "aws"
            assert config["site_type"] == "static"
            assert config["aws_profile"] == "sunwaretech"
            assert config["azure_profile"] == "sunwaretech"
            assert config["url"] is None
            assert "created_at" in config
            assert config["last_deployed"] is None
            assert config["deploy_count"] == 0
            assert "aws" in config  # Provider-specific config section

    def test_session_claude_md_created(self, tmp_path):
        """CLAUDE.md exists and contains provider info."""
        with patch('session_creator.USERS_DIR', tmp_path):
            # Create user folder first
            user_id = "test-user-guid-abc"
            (tmp_path / user_id / "sessions").mkdir(parents=True)

            creator = SessionCreator()
            session_id = creator.create_session(
                user_id=user_id,
                host_provider="azure",
                site_type="dynamic"
            )

            session_path = tmp_path / user_id / "sessions" / session_id
            claude_md_path = session_path / ".claude" / "CLAUDE.md"

            # CLAUDE.md should exist
            assert claude_md_path.is_file()

            # Read and verify content
            content = claude_md_path.read_text()

            # Should contain user and session info
            assert user_id in content
            assert session_id in content

            # Should contain provider info
            assert "azure" in content.lower()
            assert "dynamic" in content.lower()

            # Should contain profile names
            assert "sunwaretech" in content

            # Should mention agents/skills
            assert "agent" in content.lower() or "skill" in content.lower()


class TestSessionCreatorConstants:
    """Test module-level constants."""

    def test_aws_profile_constant(self):
        """AWS_PROFILE is set to 'sunwaretech'."""
        assert AWS_PROFILE == "sunwaretech"

    def test_azure_profile_constant(self):
        """AZURE_PROFILE is set to 'sunwaretech'."""
        assert AZURE_PROFILE == "sunwaretech"


class TestSessionCreatorHelpers:
    """Test helper methods."""

    def test_get_session_path(self, tmp_path):
        """get_session_path returns correct Path to session directory."""
        with patch('session_creator.USERS_DIR', tmp_path):
            creator = SessionCreator()
            user_id = "user-guid-test"
            session_id = "sess_20260124_120000"

            path = creator.get_session_path(user_id, session_id)

            expected = tmp_path / user_id / "sessions" / session_id
            assert path == expected

    def test_list_sessions(self, tmp_path):
        """list_sessions returns list of session IDs for a user."""
        with patch('session_creator.USERS_DIR', tmp_path):
            user_id = "user-with-sessions"
            sessions_dir = tmp_path / user_id / "sessions"
            sessions_dir.mkdir(parents=True)

            # Create some session folders
            (sessions_dir / "sess_20260124_100000").mkdir()
            (sessions_dir / "sess_20260124_110000").mkdir()
            (sessions_dir / "sess_20260124_120000").mkdir()

            creator = SessionCreator()
            sessions = creator.list_sessions(user_id)

            assert len(sessions) == 3
            assert "sess_20260124_100000" in sessions
            assert "sess_20260124_110000" in sessions
            assert "sess_20260124_120000" in sessions
