"""Tests for E2E test runner."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_e2e_runner_generate_tests_sends_prompt(tmp_path):
    """Test generate_tests sends prompt to tmux."""
    from e2e_runner import E2ERunner

    session_path = tmp_path / "session"
    session_path.mkdir()

    runner = E2ERunner(str(session_path), "https://example.com")

    mock_tmux = MagicMock()
    runner.generate_tests(mock_tmux, "user123_sess456")

    mock_tmux.send_instruction.assert_called_once()
    call_args = mock_tmux.send_instruction.call_args[0]
    assert "exec_user123_sess456" in call_args[0]
    assert "https://example.com" in call_args[1]


def test_e2e_runner_run_tests_skips_if_no_test_file(tmp_path):
    """Test run_tests returns skipped if no test file exists."""
    from e2e_runner import E2ERunner

    session_path = tmp_path / "session"
    (session_path / "deployment" / "tests").mkdir(parents=True)

    runner = E2ERunner(str(session_path), "https://example.com")
    result = runner.run_tests()

    assert result["status"] == "skipped"
    assert "No tests generated" in result["reason"]


def test_e2e_runner_save_results_writes_json(tmp_path):
    """Test save_results writes results.json."""
    from e2e_runner import E2ERunner

    session_path = tmp_path / "session"
    (session_path / "deployment" / "tests").mkdir(parents=True)

    runner = E2ERunner(str(session_path), "https://example.com")
    runner.save_results({"status": "passed", "tests_run": 5})

    results_file = session_path / "deployment" / "tests" / "results.json"
    assert results_file.exists()

    data = json.loads(results_file.read_text())
    assert data["status"] == "passed"
    assert data["url_tested"] == "https://example.com"
    assert "timestamp" in data
