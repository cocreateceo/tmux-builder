"""Tests for JobRunner pipeline orchestration."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_job_runner_init_loads_execution_metadata(tmp_path, monkeypatch):
    """Test JobRunner loads execution metadata on init."""
    mock_tracker = MagicMock()
    mock_tracker.get_status.return_value = {
        'execution_id': 'user123_sess456',
        'user_id': 'user123',
        'session_id': 'sess456',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a blog'
    }

    with patch('job_runner.ExecutionTracker', return_value=mock_tracker):
        with patch('job_runner.TmuxHelper'):
            from job_runner import JobRunner
            runner = JobRunner('user123_sess456')

    assert runner.user_id == 'user123'
    assert runner.session_id == 'sess456'
    assert runner.host_provider == 'aws'
    assert runner.site_type == 'static'
    assert runner.requirements == 'Build a blog'


def test_job_runner_gather_requirements_writes_file(tmp_path, monkeypatch):
    """Test _gather_requirements writes requirements to prompts/requirements.txt."""
    session_path = tmp_path / "users" / "user123" / "sessions" / "sess456"
    (session_path / "prompts").mkdir(parents=True)

    mock_tracker = MagicMock()
    mock_tracker.get_status.return_value = {
        'execution_id': 'user123_sess456',
        'user_id': 'user123',
        'session_id': 'sess456',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a portfolio site'
    }

    with patch('job_runner.ExecutionTracker', return_value=mock_tracker):
        with patch('job_runner.TmuxHelper'):
            with patch('job_runner.USERS_DIR', tmp_path / "users"):
                from job_runner import JobRunner
                runner = JobRunner('user123_sess456')
                runner._gather_requirements()

    req_file = session_path / "prompts" / "requirements.txt"
    assert req_file.exists()
    assert 'Build a portfolio site' in req_file.read_text()


def test_job_runner_run_pipeline_updates_status_at_each_step(tmp_path, monkeypatch):
    """Test run_pipeline calls update_step for each step."""
    mock_tracker = MagicMock()
    mock_tracker.get_status.return_value = {
        'execution_id': 'user123_sess456',
        'user_id': 'user123',
        'session_id': 'sess456',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a blog'
    }

    mock_tmux = MagicMock()
    mock_health = MagicMock()
    mock_health.is_healthy.return_value = True
    mock_tmux.create_session_with_health_check.return_value = mock_health

    with patch('job_runner.ExecutionTracker', return_value=mock_tracker):
        with patch('job_runner.TmuxHelper', return_value=mock_tmux):
            with patch('job_runner.USERS_DIR', tmp_path / "users"):
                from job_runner import JobRunner
                runner = JobRunner('user123_sess456')

                # Mock all step methods to avoid actual execution
                runner._gather_requirements = MagicMock()
                runner._create_plan = MagicMock()
                runner._generate_code = MagicMock()
                runner._deploy = MagicMock(return_value={'url': 'https://test.com'})
                runner._health_check = MagicMock()
                runner._screenshot = MagicMock()
                runner._run_e2e_tests = MagicMock()

                result = runner.run_pipeline()

    assert result['status'] == 'completed'
    assert mock_tracker.update_step.call_count >= 7


def test_job_runner_init_raises_on_missing_execution(tmp_path):
    """Test JobRunner raises ValueError when execution not found."""
    mock_tracker = MagicMock()
    mock_tracker.get_status.return_value = None

    with patch('job_runner.ExecutionTracker', return_value=mock_tracker):
        with patch('job_runner.TmuxHelper'):
            from job_runner import JobRunner
            with pytest.raises(ValueError, match="Execution not found"):
                JobRunner('nonexistent_execution')


def test_job_runner_pipeline_stops_on_failure(tmp_path):
    """Test run_pipeline stops and returns error on step failure."""
    mock_tracker = MagicMock()
    mock_tracker.get_status.return_value = {
        'execution_id': 'user123_sess456',
        'user_id': 'user123',
        'session_id': 'sess456',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a blog'
    }

    mock_tmux = MagicMock()
    mock_health = MagicMock()
    mock_health.is_healthy.return_value = True
    mock_tmux.create_session_with_health_check.return_value = mock_health

    with patch('job_runner.ExecutionTracker', return_value=mock_tracker):
        with patch('job_runner.TmuxHelper', return_value=mock_tmux):
            with patch('job_runner.USERS_DIR', tmp_path / "users"):
                from job_runner import JobRunner
                runner = JobRunner('user123_sess456')

                # Mock _gather_requirements to succeed
                runner._gather_requirements = MagicMock()
                # Mock _create_plan to fail
                runner._create_plan = MagicMock(side_effect=RuntimeError("Plan failed"))

                result = runner.run_pipeline()

    assert result['status'] == 'failed'
    assert result['step'] == 'create_plan'
    assert 'Plan failed' in result['error']
    mock_tracker.set_error.assert_called_once()


def test_job_runner_start_claude_session_handles_unhealthy_session(tmp_path):
    """Test _start_claude_session raises on unhealthy session."""
    mock_tracker = MagicMock()
    mock_tracker.get_status.return_value = {
        'execution_id': 'user123_sess456',
        'user_id': 'user123',
        'session_id': 'sess456',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a blog'
    }

    mock_tmux = MagicMock()
    mock_health = MagicMock()
    mock_health.is_healthy.return_value = False
    mock_health.error = "Failed to start Claude"
    mock_tmux.create_session_with_health_check.return_value = mock_health

    with patch('job_runner.ExecutionTracker', return_value=mock_tracker):
        with patch('job_runner.TmuxHelper', return_value=mock_tmux):
            with patch('job_runner.USERS_DIR', tmp_path / "users"):
                from job_runner import JobRunner
                runner = JobRunner('user123_sess456')

                with pytest.raises(RuntimeError, match="Failed to start Claude"):
                    runner._start_claude_session()


def test_job_runner_deploy_calls_aws_deployer_for_aws_static(tmp_path):
    """Test _deploy calls AWSDeployer for aws/static configuration."""
    import sys
    session_path = tmp_path / "users" / "user123" / "sessions" / "sess456"
    (session_path / "source").mkdir(parents=True)

    mock_tracker = MagicMock()
    mock_tracker.get_status.return_value = {
        'execution_id': 'user123_sess456',
        'user_id': 'user123',
        'session_id': 'sess456',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a blog'
    }

    mock_deployer_instance = MagicMock()
    mock_deployer_instance.deploy.return_value = {'url': 'https://example.cloudfront.net'}

    mock_aws_module = MagicMock()
    mock_aws_module.AWSDeployer.return_value = mock_deployer_instance

    mock_azure_module = MagicMock()

    # Pre-patch the deployer modules before test runs
    with patch.dict(sys.modules, {
        'aws_deployer': mock_aws_module,
        'azure_deployer': mock_azure_module
    }):
        with patch('job_runner.ExecutionTracker', return_value=mock_tracker):
            with patch('job_runner.TmuxHelper'):
                with patch('job_runner.USERS_DIR', tmp_path / "users"):
                    from job_runner import JobRunner
                    runner = JobRunner('user123_sess456')
                    result = runner._deploy()

                    assert result['url'] == 'https://example.cloudfront.net'
                    assert runner.deployed_url == 'https://example.cloudfront.net'
                    # Verify set_deployed_url was called on the runner's tracker
                    runner.tracker.set_deployed_url.assert_called_once_with(
                        'user123_sess456', 'https://example.cloudfront.net'
                    )


def test_job_runner_deploy_calls_azure_deployer_for_azure_static(tmp_path):
    """Test _deploy calls AzureDeployer for azure/static configuration."""
    import sys
    session_path = tmp_path / "users" / "user123" / "sessions" / "sess456"
    (session_path / "source").mkdir(parents=True)

    mock_tracker = MagicMock()
    mock_tracker.get_status.return_value = {
        'execution_id': 'user123_sess456',
        'user_id': 'user123',
        'session_id': 'sess456',
        'host_provider': 'azure',
        'site_type': 'static',
        'requirements': 'Build a blog'
    }

    mock_deployer_instance = MagicMock()
    mock_deployer_instance.deploy.return_value = {'url': 'https://example.azureedge.net'}

    mock_aws_module = MagicMock()

    mock_azure_module = MagicMock()
    mock_azure_module.AzureDeployer.return_value = mock_deployer_instance

    # Pre-patch the deployer modules before test runs
    with patch.dict(sys.modules, {
        'aws_deployer': mock_aws_module,
        'azure_deployer': mock_azure_module
    }):
        with patch('job_runner.ExecutionTracker', return_value=mock_tracker):
            with patch('job_runner.TmuxHelper'):
                with patch('job_runner.USERS_DIR', tmp_path / "users"):
                    from job_runner import JobRunner
                    runner = JobRunner('user123_sess456')
                    result = runner._deploy()

                    assert result['url'] == 'https://example.azureedge.net'
                    assert runner.deployed_url == 'https://example.azureedge.net'


def test_job_runner_health_check_raises_on_no_url(tmp_path):
    """Test _health_check raises ValueError when no deployed URL."""
    mock_tracker = MagicMock()
    mock_tracker.get_status.return_value = {
        'execution_id': 'user123_sess456',
        'user_id': 'user123',
        'session_id': 'sess456',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a blog'
    }

    with patch('job_runner.ExecutionTracker', return_value=mock_tracker):
        with patch('job_runner.TmuxHelper'):
            with patch('job_runner.USERS_DIR', tmp_path / "users"):
                from job_runner import JobRunner
                runner = JobRunner('user123_sess456')
                # deployed_url is None by default

                with pytest.raises(ValueError, match="No deployed URL"):
                    runner._health_check()


def test_job_runner_send_prompt_and_wait_writes_prompt_file(tmp_path):
    """Test _send_prompt_and_wait writes prompt to prompts/current.txt."""
    session_path = tmp_path / "users" / "user123" / "sessions" / "sess456"
    (session_path / "prompts").mkdir(parents=True)
    (session_path / "output").mkdir(parents=True)

    # Create status file with completion signal
    status_file = session_path / "output" / "status.txt"
    status_file.write_text("PHASE_COMPLETE: test_phase")

    mock_tracker = MagicMock()
    mock_tracker.get_status.return_value = {
        'execution_id': 'user123_sess456',
        'user_id': 'user123',
        'session_id': 'sess456',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a blog'
    }

    mock_tmux = MagicMock()

    with patch('job_runner.ExecutionTracker', return_value=mock_tracker):
        with patch('job_runner.TmuxHelper', return_value=mock_tmux):
            with patch('job_runner.USERS_DIR', tmp_path / "users"):
                from job_runner import JobRunner
                runner = JobRunner('user123_sess456')
                runner._send_prompt_and_wait("Test prompt content", "PHASE_COMPLETE: test_phase")

    prompt_file = session_path / "prompts" / "current.txt"
    assert prompt_file.exists()
    assert "Test prompt content" in prompt_file.read_text()
    mock_tmux.send_instruction.assert_called_once()


def test_job_runner_wait_for_signal_timeout(tmp_path):
    """Test _wait_for_signal raises TimeoutError on timeout."""
    session_path = tmp_path / "users" / "user123" / "sessions" / "sess456"
    (session_path / "output").mkdir(parents=True)

    # Don't create status file, so signal will never appear

    mock_tracker = MagicMock()
    mock_tracker.get_status.return_value = {
        'execution_id': 'user123_sess456',
        'user_id': 'user123',
        'session_id': 'sess456',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a blog'
    }

    with patch('job_runner.ExecutionTracker', return_value=mock_tracker):
        with patch('job_runner.TmuxHelper'):
            with patch('job_runner.USERS_DIR', tmp_path / "users"):
                # Patch time.sleep to speed up test
                with patch('job_runner.time.sleep'):
                    from job_runner import JobRunner
                    runner = JobRunner('user123_sess456')

                    with pytest.raises(TimeoutError, match="Timeout waiting for signal"):
                        runner._wait_for_signal("PHASE_COMPLETE: never", timeout=0.1)
