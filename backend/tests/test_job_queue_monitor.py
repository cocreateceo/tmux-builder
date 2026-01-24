import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from job_queue_monitor import JobQueueMonitor, MonitorConfig


class TestJobQueueMonitor:
    """Test background job queue monitor."""

    def test_monitor_config_defaults(self):
        """Verify default configuration values."""
        config = MonitorConfig()
        assert config.poll_interval == 2.0
        assert config.max_concurrent_jobs == 4
        assert config.check_interval == 5.0

    def test_find_pending_jobs(self, tmp_path):
        """Verify monitor finds pending jobs in queue."""
        # Create session with pending job
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        queue = [
            {"id": "job_001", "status": "pending", "type": "echo_test"},
            {"id": "job_002", "status": "running", "type": "echo_test"},
            {"id": "job_003", "status": "completed", "type": "echo_test"},
        ]
        (session_dir / "job_queue.json").write_text(json.dumps(queue))

        with patch('job_queue_monitor.ACTIVE_SESSIONS_DIR', tmp_path):
            monitor = JobQueueMonitor()
            pending = monitor.find_pending_jobs()

        assert len(pending) == 1
        assert pending[0]["id"] == "job_001"

    def test_respects_max_concurrent_jobs(self, tmp_path):
        """Verify monitor respects concurrency limit."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        # 4 running + 2 pending
        queue = [
            {"id": f"running_{i}", "status": "running", "type": "echo_test"}
            for i in range(4)
        ] + [
            {"id": f"pending_{i}", "status": "pending", "type": "echo_test"}
            for i in range(2)
        ]
        (session_dir / "job_queue.json").write_text(json.dumps(queue))

        with patch('job_queue_monitor.ACTIVE_SESSIONS_DIR', tmp_path):
            monitor = JobQueueMonitor(MonitorConfig(max_concurrent_jobs=4))
            can_start = monitor.get_available_slots("test_session")

        assert can_start == 0  # Already at capacity

    def test_detect_stale_running_jobs(self, tmp_path):
        """Verify monitor detects jobs stuck in running state."""
        session_dir = tmp_path / "test_session"
        session_dir.mkdir()

        # Job started 10 minutes ago with 5 minute timeout
        old_time = "2026-01-24T09:50:00"
        queue = [{
            "id": "stale_job",
            "status": "running",
            "type": "echo_test",
            "started_at": old_time
        }]
        (session_dir / "job_queue.json").write_text(json.dumps(queue))

        with patch('job_queue_monitor.ACTIVE_SESSIONS_DIR', tmp_path):
            # Mock datetime.now() to return a time 10 minutes after started_at
            mock_now = datetime(2026, 1, 24, 10, 0, 0)
            with patch('job_queue_monitor.datetime') as mock_dt:
                mock_dt.now.return_value = mock_now
                mock_dt.fromisoformat = datetime.fromisoformat
                monitor = JobQueueMonitor()
                stale = monitor.find_stale_jobs("test_session", timeout_seconds=300)

        assert len(stale) == 1
        assert stale[0]["id"] == "stale_job"

    def test_start_job_calls_job_runner(self, tmp_path):
        """Test _start_job creates and runs JobRunner."""
        from unittest.mock import MagicMock, patch

        mock_runner = MagicMock()
        mock_runner.run_pipeline.return_value = {'status': 'completed'}

        # Patch JobRunner in the job_runner module since it's imported locally
        with patch('job_runner.JobRunner', return_value=mock_runner):
            with patch('job_queue_monitor.ACTIVE_SESSIONS_DIR', tmp_path):
                monitor = JobQueueMonitor()
                monitor._start_job('test_session', {'id': 'job123', 'execution_id': 'user_sess'})

        mock_runner.run_pipeline.assert_called_once()

    def test_start_job_without_execution_id_logs_error(self, tmp_path, caplog):
        """Test _start_job returns early when execution_id is missing."""
        import logging
        from unittest.mock import MagicMock, patch

        mock_runner = MagicMock()

        with patch('job_runner.JobRunner', return_value=mock_runner):
            with patch('job_queue_monitor.ACTIVE_SESSIONS_DIR', tmp_path):
                with caplog.at_level(logging.ERROR):
                    monitor = JobQueueMonitor()
                    monitor._start_job('test_session', {'id': 'job123'})  # No execution_id

        # JobRunner should not be called
        mock_runner.run_pipeline.assert_not_called()
        # Error should be logged
        assert "missing execution_id" in caplog.text
