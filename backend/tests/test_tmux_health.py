import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tmux_helper import TmuxHelper, TmuxHealthCheck


class TestTmuxHealthCheck:
    """Test TMUX health check and handshake."""

    def test_health_check_structure(self):
        """Verify health check returns expected structure."""
        result = TmuxHealthCheck(
            session_exists=True,
            claude_responding=True,
            probe_success=True,
            probe_timestamp="2026-01-24T10:00:00Z",
            error=None
        )
        assert result.session_exists == True
        assert result.claude_responding == True
        assert result.is_healthy() == True

    def test_health_check_unhealthy_when_session_missing(self):
        """Verify unhealthy when session doesn't exist."""
        result = TmuxHealthCheck(
            session_exists=False,
            claude_responding=False,
            probe_success=False,
            probe_timestamp=None,
            error="Session not found"
        )
        assert result.is_healthy() == False

    @patch('tmux_helper.subprocess.run')
    @patch('tmux_helper.time.sleep')
    def test_perform_health_probe_sends_correct_commands(self, mock_sleep, mock_run):
        """Verify probe sends echo command and captures output."""
        mock_run.return_value = MagicMock(returncode=0)

        # Mock capture_pane_output to return a string that contains whatever probe marker was sent
        def mock_capture(session_name, lines=100):
            # Return output that includes the probe marker pattern
            from datetime import datetime
            timestamp = datetime.now().strftime("%H%M%S")
            return f"[PROBE {timestamp}] Claude ready"

        with patch.object(TmuxHelper, 'session_exists', return_value=True):
            with patch.object(TmuxHelper, 'capture_pane_output', side_effect=mock_capture):
                result = TmuxHelper.perform_health_probe("test_session", max_retries=1)

        assert result.is_healthy() == True
        assert result.probe_success == True
        assert result.session_exists == True
        assert result.claude_responding == True
