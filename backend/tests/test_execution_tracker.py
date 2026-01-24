"""Tests for ExecutionTracker - pipeline execution status and deep logging."""

import pytest
import json
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from execution_tracker import ExecutionTracker, PIPELINE_STEPS


class TestExecutionTracker:
    """Test execution tracking functionality."""

    def test_create_execution_returns_id(self, tmp_path):
        """Creating an execution returns correct execution_id format: {user_id}_{session_id}."""
        with patch('execution_tracker.EXECUTIONS_DIR', tmp_path):
            tracker = ExecutionTracker()

            execution_id = tracker.create_execution("user123", "session456")

            # Should return format: {user_id}_{session_id}
            assert execution_id == "user123_session456"

    def test_execution_file_created(self, tmp_path):
        """Creating an execution creates JSON file with initial state."""
        with patch('execution_tracker.EXECUTIONS_DIR', tmp_path):
            tracker = ExecutionTracker()

            execution_id = tracker.create_execution("user_abc", "sess_xyz")

            # File should exist
            execution_file = tmp_path / f"{execution_id}.json"
            assert execution_file.is_file()

            # Load and verify initial state structure
            state = json.loads(execution_file.read_text())
            assert state["execution_id"] == execution_id
            assert state["user_id"] == "user_abc"
            assert state["session_id"] == "sess_xyz"
            assert state["status"] == "pending"
            assert state["current_step"] == 0
            assert state["total_steps"] == 9
            assert "created_at" in state
            assert "updated_at" in state
            assert state["logs"] == []
            assert state["result"] is None
            assert state["error"] is None

    def test_log_entry_adds_to_logs(self, tmp_path):
        """Logging adds entries to the logs array with correct structure."""
        with patch('execution_tracker.EXECUTIONS_DIR', tmp_path):
            tracker = ExecutionTracker()

            execution_id = tracker.create_execution("user1", "session1")

            # Add a log entry
            tracker.log(
                execution_id,
                level="INFO",
                message="Starting pipeline",
                step=1,
                step_name="create_user",
                details={"extra": "data"},
                trace_id="trace-12345"
            )

            # Verify log was added
            state = tracker.get_status(execution_id)
            assert len(state["logs"]) == 1

            log_entry = state["logs"][0]
            assert "timestamp" in log_entry
            assert log_entry["level"] == "INFO"
            assert log_entry["message"] == "Starting pipeline"
            assert log_entry["step"] == 1
            assert log_entry["step_name"] == "create_user"
            assert log_entry["details"] == {"extra": "data"}
            assert log_entry["trace_id"] == "trace-12345"

    def test_update_status_changes_state(self, tmp_path):
        """Updating status and current_step changes the execution state."""
        with patch('execution_tracker.EXECUTIONS_DIR', tmp_path):
            tracker = ExecutionTracker()

            execution_id = tracker.create_execution("userX", "sessionY")

            # Initial state
            initial_state = tracker.get_status(execution_id)
            assert initial_state["status"] == "pending"
            assert initial_state["current_step"] == 0

            # Update status
            tracker.update_status(execution_id, status="running", current_step=3)

            # Verify changes
            updated_state = tracker.get_status(execution_id)
            assert updated_state["status"] == "running"
            assert updated_state["current_step"] == 3

            # updated_at should have changed
            assert updated_state["updated_at"] != initial_state["updated_at"]

    def test_set_result_stores_final_data(self, tmp_path):
        """Setting result stores the data and changes status to 'completed'."""
        with patch('execution_tracker.EXECUTIONS_DIR', tmp_path):
            tracker = ExecutionTracker()

            execution_id = tracker.create_execution("finalUser", "finalSession")

            # Set result
            result_data = {
                "url": "https://example.com",
                "deployment_id": "dep-12345",
                "health_check_passed": True
            }
            tracker.set_result(execution_id, result_data)

            # Verify result and status
            state = tracker.get_status(execution_id)
            assert state["result"] == result_data
            assert state["status"] == "completed"
            assert state["error"] is None

    def test_set_error_stores_error_data(self, tmp_path):
        """Setting error stores the error and changes status to 'failed'."""
        with patch('execution_tracker.EXECUTIONS_DIR', tmp_path):
            tracker = ExecutionTracker()

            execution_id = tracker.create_execution("errorUser", "errorSession")

            # Set error
            error_data = {
                "type": "DeploymentError",
                "message": "Failed to deploy to AWS",
                "step": 4
            }
            tracker.set_error(execution_id, error_data)

            # Verify error and status
            state = tracker.get_status(execution_id)
            assert state["error"] == error_data
            assert state["status"] == "failed"
            assert state["result"] is None


class TestPipelineSteps:
    """Test pipeline steps constant."""

    def test_pipeline_steps_has_nine_steps(self):
        """Verify pipeline has all 9 steps."""
        from execution_tracker import PIPELINE_STEPS
        assert len(PIPELINE_STEPS) == 9
        step_names = [s["name"] for s in PIPELINE_STEPS]
        assert "gather_requirements" in step_names
        assert "create_plan" in step_names
        assert "generate_code" in step_names

    def test_pipeline_steps_structure(self):
        """Pipeline steps should have correct count and structure."""
        assert len(PIPELINE_STEPS) == 9

        # Each step should have id, name, description
        for step in PIPELINE_STEPS:
            assert "id" in step
            assert "name" in step
            assert "description" in step

        # Verify step names
        step_names = [s["name"] for s in PIPELINE_STEPS]
        expected_names = [
            "create_user",
            "create_session",
            "gather_requirements",
            "create_plan",
            "generate_code",
            "deploy",
            "health_check",
            "screenshot",
            "e2e_tests"
        ]
        assert step_names == expected_names
