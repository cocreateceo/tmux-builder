"""Integration test for full pipeline execution.

Tests the complete flow from execution creation through deployment
with all external services mocked. Verifies:
- AWS static site pipeline
- Azure static site pipeline
- Error handling and failure reporting
- Progress tracking at each step
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_all_externals():
    """Mock all external services for integration testing."""
    with patch('job_runner.TmuxHelper') as mock_tmux:
        with patch('job_runner.ExecutionTracker') as mock_tracker_class:
            # Setup mock TmuxHelper
            mock_health_result = MagicMock()
            mock_health_result.is_healthy.return_value = True
            mock_tmux.return_value.create_session_with_health_check.return_value = mock_health_result
            mock_tmux.return_value.send_instruction.return_value = True

            # Setup mock ExecutionTracker
            mock_tracker = MagicMock()
            mock_tracker_class.return_value = mock_tracker

            yield {
                'tmux': mock_tmux,
                'tmux_instance': mock_tmux.return_value,
                'tracker_class': mock_tracker_class,
                'tracker': mock_tracker,
                'health': mock_health_result
            }


@pytest.fixture
def setup_execution_and_session(tmp_path):
    """Setup execution tracker and session directories for testing."""
    def _setup(user_id: str, session_id: str, host_provider: str = 'aws', site_type: str = 'static'):
        import execution_tracker
        import job_runner

        # Setup directories
        users_dir = tmp_path / "users"
        executions_dir = tmp_path / "executions"

        execution_tracker.EXECUTIONS_DIR = executions_dir
        job_runner.USERS_DIR = users_dir

        # Create session directory structure
        session_dir = users_dir / user_id / "sessions" / session_id
        (session_dir / "prompts").mkdir(parents=True)
        (session_dir / "output").mkdir(parents=True)
        (session_dir / "source").mkdir(parents=True)
        (session_dir / "deployment" / "tests").mkdir(parents=True)
        (session_dir / "logs").mkdir(parents=True)
        (session_dir / "state").mkdir(parents=True)

        # Create execution tracking entry
        from execution_tracker import ExecutionTracker
        tracker = ExecutionTracker()
        exec_id = tracker.create_execution(user_id, session_id)
        tracker.update_metadata(exec_id, {
            'host_provider': host_provider,
            'site_type': site_type,
            'requirements': 'Build a simple landing page'
        })

        return {
            'exec_id': exec_id,
            'tracker': tracker,
            'session_dir': session_dir,
            'users_dir': users_dir,
            'executions_dir': executions_dir
        }

    return _setup


def test_full_pipeline_static_aws(tmp_path, mock_all_externals, setup_execution_and_session):
    """Test complete pipeline for AWS static site deployment."""
    # Setup
    setup = setup_execution_and_session('user123', 'sess456', 'aws', 'static')
    exec_id = setup['exec_id']
    session_dir = setup['session_dir']

    # Mock the execution status return for JobRunner init
    mock_all_externals['tracker'].get_status.return_value = {
        'execution_id': exec_id,
        'user_id': 'user123',
        'session_id': 'sess456',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a simple landing page'
    }

    # Create status file for wait_for_signal (simulating Claude completion)
    status_file = session_dir / "output" / "status.txt"
    status_file.write_text("PHASE_COMPLETE: planning\nPHASE_COMPLETE: coding\nPHASE_COMPLETE: test_generation")

    # Mock deployers, health checker, screenshot, e2e runner
    mock_aws_deployer = MagicMock()
    mock_aws_deployer.return_value.deploy.return_value = {'url': 'https://test.cloudfront.net'}

    mock_health_checker = MagicMock()
    mock_health_checker.return_value.check.return_value = {'passed': True, 'status_code': 200}

    mock_screenshot = MagicMock()
    mock_screenshot.return_value.capture.return_value = {'passed': True, 'path': '/test/screenshot.png'}

    mock_e2e_runner = MagicMock()
    mock_e2e_runner.return_value.run_tests.return_value = {'status': 'passed'}

    with patch.dict(sys.modules, {
        'aws_deployer': MagicMock(AWSDeployer=mock_aws_deployer),
        'azure_deployer': MagicMock(),
        'health_checker': MagicMock(HealthChecker=mock_health_checker),
        'screenshot_capture': MagicMock(ScreenshotCapture=mock_screenshot),
        'e2e_runner': MagicMock(E2ERunner=mock_e2e_runner)
    }):
        from job_runner import JobRunner
        runner = JobRunner(exec_id)

        # Mock wait methods to return immediately
        runner._wait_for_signal = MagicMock(return_value="OK")

        result = runner.run_pipeline()

    # Verify result
    assert result['status'] == 'completed'
    assert result['url'] == 'https://test.cloudfront.net'

    # Verify all steps were tracked
    assert mock_all_externals['tracker'].update_step.call_count >= 7
    assert mock_all_externals['tracker'].log.call_count >= 7
    assert mock_all_externals['tracker'].set_result.called


def test_full_pipeline_static_azure(tmp_path, mock_all_externals, setup_execution_and_session):
    """Test complete pipeline for Azure static site deployment."""
    # Setup
    setup = setup_execution_and_session('user789', 'sessabc', 'azure', 'static')
    exec_id = setup['exec_id']
    session_dir = setup['session_dir']

    # Mock the execution status return for JobRunner init
    mock_all_externals['tracker'].get_status.return_value = {
        'execution_id': exec_id,
        'user_id': 'user789',
        'session_id': 'sessabc',
        'host_provider': 'azure',
        'site_type': 'static',
        'requirements': 'Build a portfolio website'
    }

    # Create status file for wait_for_signal
    status_file = session_dir / "output" / "status.txt"
    status_file.write_text("PHASE_COMPLETE: planning\nPHASE_COMPLETE: coding\nPHASE_COMPLETE: test_generation")

    # Mock deployers
    mock_azure_deployer = MagicMock()
    mock_azure_deployer.return_value.deploy.return_value = {'url': 'https://test.azureedge.net'}

    mock_health_checker = MagicMock()
    mock_health_checker.return_value.check.return_value = {'passed': True, 'status_code': 200}

    mock_screenshot = MagicMock()
    mock_screenshot.return_value.capture.return_value = {'passed': True, 'path': '/test/screenshot.png'}

    mock_e2e_runner = MagicMock()
    mock_e2e_runner.return_value.run_tests.return_value = {'status': 'passed'}

    with patch.dict(sys.modules, {
        'aws_deployer': MagicMock(),
        'azure_deployer': MagicMock(AzureDeployer=mock_azure_deployer),
        'health_checker': MagicMock(HealthChecker=mock_health_checker),
        'screenshot_capture': MagicMock(ScreenshotCapture=mock_screenshot),
        'e2e_runner': MagicMock(E2ERunner=mock_e2e_runner)
    }):
        from job_runner import JobRunner
        runner = JobRunner(exec_id)

        # Mock wait methods
        runner._wait_for_signal = MagicMock(return_value="OK")

        result = runner.run_pipeline()

    # Verify result
    assert result['status'] == 'completed'
    assert result['url'] == 'https://test.azureedge.net'

    # Verify set_deployed_url was called with Azure URL
    mock_all_externals['tracker'].set_deployed_url.assert_called_with(
        exec_id, 'https://test.azureedge.net'
    )


def test_pipeline_handles_deploy_failure(tmp_path, mock_all_externals, setup_execution_and_session):
    """Test pipeline handles deployment failure correctly."""
    # Setup
    setup = setup_execution_and_session('userxyz', 'sessfail', 'aws', 'static')
    exec_id = setup['exec_id']
    session_dir = setup['session_dir']

    # Mock the execution status return
    mock_all_externals['tracker'].get_status.return_value = {
        'execution_id': exec_id,
        'user_id': 'userxyz',
        'session_id': 'sessfail',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a landing page'
    }

    # Create status file
    status_file = session_dir / "output" / "status.txt"
    status_file.write_text("PHASE_COMPLETE: planning\nPHASE_COMPLETE: coding")

    # Mock deployer to raise an exception
    mock_aws_deployer = MagicMock()
    mock_aws_deployer.return_value.deploy.side_effect = RuntimeError("AWS deployment failed: bucket creation error")

    with patch.dict(sys.modules, {
        'aws_deployer': MagicMock(AWSDeployer=mock_aws_deployer),
        'azure_deployer': MagicMock(),
        'health_checker': MagicMock(),
        'screenshot_capture': MagicMock(),
        'e2e_runner': MagicMock()
    }):
        from job_runner import JobRunner
        runner = JobRunner(exec_id)

        # Mock wait methods
        runner._wait_for_signal = MagicMock(return_value="OK")

        result = runner.run_pipeline()

    # Verify failure is reported correctly
    assert result['status'] == 'failed'
    assert result['step'] == 'deploy'
    assert 'AWS deployment failed' in result['error']

    # Verify set_error was called
    mock_all_externals['tracker'].set_error.assert_called_once()
    error_call = mock_all_externals['tracker'].set_error.call_args
    assert error_call[0][0] == exec_id
    assert error_call[0][1]['step'] == 6
    assert error_call[0][1]['step_name'] == 'deploy'


def test_pipeline_handles_health_check_failure(tmp_path, mock_all_externals, setup_execution_and_session):
    """Test pipeline handles health check failure correctly."""
    # Setup
    setup = setup_execution_and_session('userhc', 'sesshc', 'aws', 'static')
    exec_id = setup['exec_id']
    session_dir = setup['session_dir']

    # Mock the execution status return
    mock_all_externals['tracker'].get_status.return_value = {
        'execution_id': exec_id,
        'user_id': 'userhc',
        'session_id': 'sesshc',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a landing page'
    }

    # Create status file
    status_file = session_dir / "output" / "status.txt"
    status_file.write_text("PHASE_COMPLETE: planning\nPHASE_COMPLETE: coding")

    # Mock successful deployment but failing health check
    mock_aws_deployer = MagicMock()
    mock_aws_deployer.return_value.deploy.return_value = {'url': 'https://test.cloudfront.net'}

    mock_health_checker = MagicMock()
    mock_health_checker.return_value.check.return_value = {
        'passed': False,
        'status_code': 503,
        'error': 'Service unavailable'
    }

    with patch.dict(sys.modules, {
        'aws_deployer': MagicMock(AWSDeployer=mock_aws_deployer),
        'azure_deployer': MagicMock(),
        'health_checker': MagicMock(HealthChecker=mock_health_checker),
        'screenshot_capture': MagicMock(),
        'e2e_runner': MagicMock()
    }):
        from job_runner import JobRunner
        runner = JobRunner(exec_id)

        # Mock wait methods
        runner._wait_for_signal = MagicMock(return_value="OK")

        result = runner.run_pipeline()

    # Verify failure is reported at health_check step
    assert result['status'] == 'failed'
    assert result['step'] == 'health_check'
    assert 'Health check failed' in result['error']


def test_pipeline_updates_progress_at_each_step(tmp_path, mock_all_externals, setup_execution_and_session):
    """Test that ExecutionTracker updates are made at each pipeline step."""
    # Setup
    setup = setup_execution_and_session('userprog', 'sessprog', 'aws', 'static')
    exec_id = setup['exec_id']
    session_dir = setup['session_dir']

    # Track all update_step calls
    step_updates = []
    def track_step_update(eid, step, step_name, status="running"):
        step_updates.append({'exec_id': eid, 'step': step, 'step_name': step_name, 'status': status})

    mock_all_externals['tracker'].update_step.side_effect = track_step_update

    # Mock the execution status return
    mock_all_externals['tracker'].get_status.return_value = {
        'execution_id': exec_id,
        'user_id': 'userprog',
        'session_id': 'sessprog',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a landing page'
    }

    # Create status file
    status_file = session_dir / "output" / "status.txt"
    status_file.write_text("PHASE_COMPLETE: planning\nPHASE_COMPLETE: coding\nPHASE_COMPLETE: test_generation")

    # Mock all services to succeed
    mock_aws_deployer = MagicMock()
    mock_aws_deployer.return_value.deploy.return_value = {'url': 'https://test.cloudfront.net'}

    mock_health_checker = MagicMock()
    mock_health_checker.return_value.check.return_value = {'passed': True}

    mock_screenshot = MagicMock()
    mock_screenshot.return_value.capture.return_value = {'passed': True}

    mock_e2e_runner = MagicMock()
    mock_e2e_runner.return_value.run_tests.return_value = {'status': 'passed'}

    with patch.dict(sys.modules, {
        'aws_deployer': MagicMock(AWSDeployer=mock_aws_deployer),
        'azure_deployer': MagicMock(),
        'health_checker': MagicMock(HealthChecker=mock_health_checker),
        'screenshot_capture': MagicMock(ScreenshotCapture=mock_screenshot),
        'e2e_runner': MagicMock(E2ERunner=mock_e2e_runner)
    }):
        from job_runner import JobRunner
        runner = JobRunner(exec_id)

        # Mock wait methods
        runner._wait_for_signal = MagicMock(return_value="OK")

        result = runner.run_pipeline()

    # Verify pipeline completed
    assert result['status'] == 'completed'

    # Verify all 7 steps were tracked (steps 3-9)
    assert len(step_updates) == 7

    # Verify step order and names
    expected_steps = [
        (3, 'gather_requirements'),
        (4, 'create_plan'),
        (5, 'generate_code'),
        (6, 'deploy'),
        (7, 'health_check'),
        (8, 'screenshot'),
        (9, 'e2e_tests'),
    ]

    for i, (expected_num, expected_name) in enumerate(expected_steps):
        assert step_updates[i]['step'] == expected_num
        assert step_updates[i]['step_name'] == expected_name
        assert step_updates[i]['status'] == 'running'


def test_pipeline_handles_e2e_test_failure(tmp_path, mock_all_externals, setup_execution_and_session):
    """Test pipeline handles E2E test failure correctly."""
    # Setup
    setup = setup_execution_and_session('usere2e', 'sesse2e', 'aws', 'static')
    exec_id = setup['exec_id']
    session_dir = setup['session_dir']

    # Mock the execution status return
    mock_all_externals['tracker'].get_status.return_value = {
        'execution_id': exec_id,
        'user_id': 'usere2e',
        'session_id': 'sesse2e',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a landing page'
    }

    # Create status file
    status_file = session_dir / "output" / "status.txt"
    status_file.write_text("PHASE_COMPLETE: planning\nPHASE_COMPLETE: coding\nPHASE_COMPLETE: test_generation")

    # Mock successful deployment, health check, screenshot, but failing E2E tests
    mock_aws_deployer = MagicMock()
    mock_aws_deployer.return_value.deploy.return_value = {'url': 'https://test.cloudfront.net'}

    mock_health_checker = MagicMock()
    mock_health_checker.return_value.check.return_value = {'passed': True}

    mock_screenshot = MagicMock()
    mock_screenshot.return_value.capture.return_value = {'passed': True}

    mock_e2e_runner = MagicMock()
    mock_e2e_runner.return_value.run_tests.return_value = {
        'status': 'failed',
        'stderr': 'Test assertion error: Expected 200 but got 404'
    }

    with patch.dict(sys.modules, {
        'aws_deployer': MagicMock(AWSDeployer=mock_aws_deployer),
        'azure_deployer': MagicMock(),
        'health_checker': MagicMock(HealthChecker=mock_health_checker),
        'screenshot_capture': MagicMock(ScreenshotCapture=mock_screenshot),
        'e2e_runner': MagicMock(E2ERunner=mock_e2e_runner)
    }):
        from job_runner import JobRunner
        runner = JobRunner(exec_id)

        # Mock wait methods
        runner._wait_for_signal = MagicMock(return_value="OK")

        result = runner.run_pipeline()

    # Verify failure is reported at e2e_tests step
    assert result['status'] == 'failed'
    assert result['step'] == 'e2e_tests'
    assert 'E2E tests failed' in result['error']


def test_pipeline_handles_tmux_session_failure(tmp_path, setup_execution_and_session):
    """Test pipeline handles tmux session creation failure.

    Note: The pipeline raises RuntimeError when tmux session fails to start,
    rather than returning a failure dict. This is because the session is
    critical infrastructure and the pipeline cannot proceed without it.
    """
    # Setup
    setup = setup_execution_and_session('usertmux', 'sesstmux', 'aws', 'static')
    exec_id = setup['exec_id']

    # Mock TmuxHelper to return unhealthy session
    mock_health = MagicMock()
    mock_health.is_healthy.return_value = False
    mock_health.error = "Failed to start Claude CLI"

    mock_tmux = MagicMock()
    mock_tmux.return_value.create_session_with_health_check.return_value = mock_health

    mock_tracker = MagicMock()
    mock_tracker.get_status.return_value = {
        'execution_id': exec_id,
        'user_id': 'usertmux',
        'session_id': 'sesstmux',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a landing page'
    }

    with patch('job_runner.TmuxHelper', mock_tmux):
        with patch('job_runner.ExecutionTracker', return_value=mock_tracker):
            from job_runner import JobRunner
            runner = JobRunner(exec_id)

            # The pipeline raises RuntimeError when tmux session fails
            with pytest.raises(RuntimeError) as exc_info:
                runner.run_pipeline()

            # Verify the error message
            assert 'Failed to start Claude session' in str(exc_info.value)
            assert 'Failed to start Claude CLI' in str(exc_info.value)


def test_full_pipeline_dynamic_aws_ec2(tmp_path, mock_all_externals, setup_execution_and_session):
    """Test complete pipeline for AWS EC2 dynamic site deployment."""
    # Setup
    setup = setup_execution_and_session('userec2', 'sessec2', 'aws', 'dynamic')
    exec_id = setup['exec_id']
    session_dir = setup['session_dir']

    # Mock the execution status return for JobRunner init
    mock_all_externals['tracker'].get_status.return_value = {
        'execution_id': exec_id,
        'user_id': 'userec2',
        'session_id': 'sessec2',
        'host_provider': 'aws',
        'site_type': 'dynamic',
        'requirements': 'Build a Node.js API server'
    }

    # Create status file
    status_file = session_dir / "output" / "status.txt"
    status_file.write_text("PHASE_COMPLETE: planning\nPHASE_COMPLETE: coding\nPHASE_COMPLETE: test_generation")

    # Mock deployers
    mock_ec2_deployer = MagicMock()
    mock_ec2_deployer.return_value.deploy.return_value = {'url': 'https://ec2-instance.aws.com'}

    mock_health_checker = MagicMock()
    mock_health_checker.return_value.check.return_value = {'passed': True}

    mock_screenshot = MagicMock()
    mock_screenshot.return_value.capture.return_value = {'passed': True}

    mock_e2e_runner = MagicMock()
    mock_e2e_runner.return_value.run_tests.return_value = {'status': 'passed'}

    with patch.dict(sys.modules, {
        'aws_deployer': MagicMock(),
        'aws_ec2_deployer': MagicMock(AWSEC2Deployer=mock_ec2_deployer),
        'azure_deployer': MagicMock(),
        'health_checker': MagicMock(HealthChecker=mock_health_checker),
        'screenshot_capture': MagicMock(ScreenshotCapture=mock_screenshot),
        'e2e_runner': MagicMock(E2ERunner=mock_e2e_runner)
    }):
        from job_runner import JobRunner
        runner = JobRunner(exec_id)

        # Mock wait methods
        runner._wait_for_signal = MagicMock(return_value="OK")

        result = runner.run_pipeline()

    # Verify result
    assert result['status'] == 'completed'
    assert result['url'] == 'https://ec2-instance.aws.com'


def test_full_pipeline_dynamic_azure_vm(tmp_path, mock_all_externals, setup_execution_and_session):
    """Test complete pipeline for Azure VM dynamic site deployment."""
    # Setup
    setup = setup_execution_and_session('uservm', 'sessvm', 'azure', 'dynamic')
    exec_id = setup['exec_id']
    session_dir = setup['session_dir']

    # Mock the execution status return
    mock_all_externals['tracker'].get_status.return_value = {
        'execution_id': exec_id,
        'user_id': 'uservm',
        'session_id': 'sessvm',
        'host_provider': 'azure',
        'site_type': 'dynamic',
        'requirements': 'Build a Python Flask API'
    }

    # Create status file
    status_file = session_dir / "output" / "status.txt"
    status_file.write_text("PHASE_COMPLETE: planning\nPHASE_COMPLETE: coding\nPHASE_COMPLETE: test_generation")

    # Mock deployers
    mock_vm_deployer = MagicMock()
    mock_vm_deployer.return_value.deploy.return_value = {'url': 'https://vm-instance.azure.com'}

    mock_health_checker = MagicMock()
    mock_health_checker.return_value.check.return_value = {'passed': True}

    mock_screenshot = MagicMock()
    mock_screenshot.return_value.capture.return_value = {'passed': True}

    mock_e2e_runner = MagicMock()
    mock_e2e_runner.return_value.run_tests.return_value = {'status': 'passed'}

    with patch.dict(sys.modules, {
        'aws_deployer': MagicMock(),
        'azure_deployer': MagicMock(),
        'azure_vm_deployer': MagicMock(AzureVMDeployer=mock_vm_deployer),
        'health_checker': MagicMock(HealthChecker=mock_health_checker),
        'screenshot_capture': MagicMock(ScreenshotCapture=mock_screenshot),
        'e2e_runner': MagicMock(E2ERunner=mock_e2e_runner)
    }):
        from job_runner import JobRunner
        runner = JobRunner(exec_id)

        # Mock wait methods
        runner._wait_for_signal = MagicMock(return_value="OK")

        result = runner.run_pipeline()

    # Verify result
    assert result['status'] == 'completed'
    assert result['url'] == 'https://vm-instance.azure.com'


def test_pipeline_logging_includes_step_details(tmp_path, mock_all_externals, setup_execution_and_session):
    """Test that pipeline logging includes step number and name details."""
    # Setup
    setup = setup_execution_and_session('userlog', 'sesslog', 'aws', 'static')
    exec_id = setup['exec_id']
    session_dir = setup['session_dir']

    # Track all log calls
    log_calls = []
    def track_log(eid, level, message, step=None, step_name=None, details=None, trace_id=None):
        log_calls.append({
            'exec_id': eid,
            'level': level,
            'message': message,
            'step': step,
            'step_name': step_name,
            'details': details
        })

    mock_all_externals['tracker'].log.side_effect = track_log

    # Mock the execution status return
    mock_all_externals['tracker'].get_status.return_value = {
        'execution_id': exec_id,
        'user_id': 'userlog',
        'session_id': 'sesslog',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a landing page'
    }

    # Create status file
    status_file = session_dir / "output" / "status.txt"
    status_file.write_text("PHASE_COMPLETE: planning\nPHASE_COMPLETE: coding\nPHASE_COMPLETE: test_generation")

    # Mock all services to succeed
    mock_aws_deployer = MagicMock()
    mock_aws_deployer.return_value.deploy.return_value = {'url': 'https://test.cloudfront.net'}

    mock_health_checker = MagicMock()
    mock_health_checker.return_value.check.return_value = {'passed': True}

    mock_screenshot = MagicMock()
    mock_screenshot.return_value.capture.return_value = {'passed': True}

    mock_e2e_runner = MagicMock()
    mock_e2e_runner.return_value.run_tests.return_value = {'status': 'passed'}

    with patch.dict(sys.modules, {
        'aws_deployer': MagicMock(AWSDeployer=mock_aws_deployer),
        'azure_deployer': MagicMock(),
        'health_checker': MagicMock(HealthChecker=mock_health_checker),
        'screenshot_capture': MagicMock(ScreenshotCapture=mock_screenshot),
        'e2e_runner': MagicMock(E2ERunner=mock_e2e_runner)
    }):
        from job_runner import JobRunner
        runner = JobRunner(exec_id)

        # Mock wait methods
        runner._wait_for_signal = MagicMock(return_value="OK")

        result = runner.run_pipeline()

    # Verify pipeline completed
    assert result['status'] == 'completed'

    # Verify logs include step info
    # Should have at least 2 logs per step (starting and completed)
    assert len(log_calls) >= 14

    # Verify log structure
    for log in log_calls:
        assert log['exec_id'] == exec_id
        assert log['level'] == 'INFO'
        assert log['step'] is not None
        assert log['step_name'] is not None
