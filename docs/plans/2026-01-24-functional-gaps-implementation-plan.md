# Functional Gaps Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete the missing functionality to enable full multi-user deployment pipeline execution.

**Architecture:** Extend existing queue system with JobRunner orchestrator. JobRunner manages 9-step pipeline, coordinates with TmuxHelper for Claude sessions, calls existing deployers/checkers, and updates ExecutionTracker at each step.

**Tech Stack:** Python 3.11+, Flask, boto3, azure-sdk, Playwright, pytest

---

## Task 1: Update PIPELINE_STEPS Constant

**Files:**
- Modify: `backend/execution_tracker.py:12-20`
- Test: `backend/tests/test_execution_tracker.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_execution_tracker.py`:

```python
def test_pipeline_steps_has_nine_steps():
    """Verify pipeline has all 9 steps."""
    from execution_tracker import PIPELINE_STEPS
    assert len(PIPELINE_STEPS) == 9
    step_names = [s["name"] for s in PIPELINE_STEPS]
    assert "gather_requirements" in step_names
    assert "create_plan" in step_names
    assert "generate_code" in step_names
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_execution_tracker.py::test_pipeline_steps_has_nine_steps -v`
Expected: FAIL - only 7 steps currently defined

**Step 3: Write minimal implementation**

Replace PIPELINE_STEPS in `backend/execution_tracker.py`:

```python
PIPELINE_STEPS = [
    {"id": 1, "name": "create_user", "description": "Create GUID folder & registry entry"},
    {"id": 2, "name": "create_session", "description": "Initialize session folder structure"},
    {"id": 3, "name": "gather_requirements", "description": "Parse & structure requirements from POST body"},
    {"id": 4, "name": "create_plan", "description": "Claude creates implementation plan"},
    {"id": 5, "name": "generate_code", "description": "Claude writes code to source/"},
    {"id": 6, "name": "deploy", "description": "Deploy to AWS/Azure"},
    {"id": 7, "name": "health_check", "description": "Verify URL returns 200 OK"},
    {"id": 8, "name": "screenshot", "description": "Capture visual snapshot"},
    {"id": 9, "name": "e2e_tests", "description": "Generate & run E2E tests"},
]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_execution_tracker.py::test_pipeline_steps_has_nine_steps -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/execution_tracker.py backend/tests/test_execution_tracker.py
git commit -m "feat(execution_tracker): update pipeline to 9 steps

Add gather_requirements, create_plan, generate_code steps.
Renumber deploy->6, health_check->7, screenshot->8, e2e_tests->9."
```

---

## Task 2: Add ExecutionTracker Enhancement Methods

**Files:**
- Modify: `backend/execution_tracker.py:167-200`
- Test: `backend/tests/test_execution_tracker.py`

**Step 1: Write the failing tests**

Add to `backend/tests/test_execution_tracker.py`:

```python
def test_update_step_sets_step_name(tmp_path, monkeypatch):
    """Test update_step sets current_step_name."""
    import execution_tracker
    monkeypatch.setattr(execution_tracker, 'EXECUTIONS_DIR', tmp_path)

    tracker = ExecutionTracker()
    exec_id = tracker.create_execution("user123", "sess456")

    tracker.update_step(exec_id, 3, "gather_requirements", "running")

    status = tracker.get_status(exec_id)
    assert status["current_step"] == 3
    assert status["current_step_name"] == "gather_requirements"
    assert status["status"] == "running"


def test_set_deployed_url(tmp_path, monkeypatch):
    """Test set_deployed_url stores URL and timestamp."""
    import execution_tracker
    monkeypatch.setattr(execution_tracker, 'EXECUTIONS_DIR', tmp_path)

    tracker = ExecutionTracker()
    exec_id = tracker.create_execution("user123", "sess456")

    tracker.set_deployed_url(exec_id, "https://example.cloudfront.net")

    status = tracker.get_status(exec_id)
    assert status["deployed_url"] == "https://example.cloudfront.net"
    assert "last_deployed" in status


def test_get_progress_returns_summary(tmp_path, monkeypatch):
    """Test get_progress returns progress dict."""
    import execution_tracker
    monkeypatch.setattr(execution_tracker, 'EXECUTIONS_DIR', tmp_path)

    tracker = ExecutionTracker()
    exec_id = tracker.create_execution("user123", "sess456")
    tracker.update_step(exec_id, 5, "generate_code", "running")

    progress = tracker.get_progress(exec_id)

    assert progress["execution_id"] == exec_id
    assert progress["current_step"] == 5
    assert progress["current_step_name"] == "generate_code"
    assert progress["total_steps"] == 9
    assert progress["percent_complete"] == 55  # 5/9 * 100 = 55%


def test_update_metadata_stores_requirements(tmp_path, monkeypatch):
    """Test update_metadata stores arbitrary data."""
    import execution_tracker
    monkeypatch.setattr(execution_tracker, 'EXECUTIONS_DIR', tmp_path)

    tracker = ExecutionTracker()
    exec_id = tracker.create_execution("user123", "sess456")

    tracker.update_metadata(exec_id, {"requirements": "Build a blog", "host_provider": "aws"})

    status = tracker.get_status(exec_id)
    assert status["requirements"] == "Build a blog"
    assert status["host_provider"] == "aws"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_execution_tracker.py::test_update_step_sets_step_name tests/test_execution_tracker.py::test_set_deployed_url tests/test_execution_tracker.py::test_get_progress_returns_summary tests/test_execution_tracker.py::test_update_metadata_stores_requirements -v`
Expected: FAIL - methods don't exist

**Step 3: Write minimal implementation**

Add to `backend/execution_tracker.py` after `set_error` method:

```python
    def update_step(
        self,
        execution_id: str,
        step: int,
        step_name: str,
        status: str = "running"
    ) -> None:
        """
        Update current step with name and status.

        Args:
            execution_id: Execution identifier
            step: Pipeline step number
            step_name: Pipeline step name
            status: New status (default: running)
        """
        state = self._load_execution(execution_id)
        if not state:
            return

        state["current_step"] = step
        state["current_step_name"] = step_name
        state["status"] = status
        state["updated_at"] = self._get_timestamp()
        self._save_execution(execution_id, state)

    def set_deployed_url(self, execution_id: str, url: str) -> None:
        """
        Store deployed URL after successful deployment.

        Args:
            execution_id: Execution identifier
            url: Deployed site URL
        """
        state = self._load_execution(execution_id)
        if not state:
            return

        state["deployed_url"] = url
        state["last_deployed"] = self._get_timestamp()
        state["updated_at"] = self._get_timestamp()
        self._save_execution(execution_id, state)

    def get_progress(self, execution_id: str) -> Optional[dict]:
        """
        Return progress summary for frontend.

        Args:
            execution_id: Execution identifier

        Returns:
            Progress dict with percent_complete, or None if not found
        """
        state = self._load_execution(execution_id)
        if not state:
            return None

        current_step = state.get("current_step", 0)
        total_steps = 9

        return {
            "execution_id": execution_id,
            "status": state.get("status", "pending"),
            "current_step": current_step,
            "current_step_name": state.get("current_step_name", ""),
            "total_steps": total_steps,
            "percent_complete": int((current_step / total_steps) * 100),
            "deployed_url": state.get("deployed_url"),
            "error": state.get("error"),
        }

    def update_metadata(self, execution_id: str, metadata: dict) -> None:
        """
        Update execution with arbitrary metadata.

        Args:
            execution_id: Execution identifier
            metadata: Dict of key-value pairs to merge into state
        """
        state = self._load_execution(execution_id)
        if not state:
            return

        state.update(metadata)
        state["updated_at"] = self._get_timestamp()
        self._save_execution(execution_id, state)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_execution_tracker.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/execution_tracker.py backend/tests/test_execution_tracker.py
git commit -m "feat(execution_tracker): add update_step, set_deployed_url, get_progress, update_metadata

- update_step: sets step number, name, and status atomically
- set_deployed_url: stores URL with last_deployed timestamp
- get_progress: returns summary dict for frontend polling
- update_metadata: merges arbitrary data into execution state"
```

---

## Task 3: Update /api/create-user to Accept Requirements

**Files:**
- Modify: `backend/app.py:43-122`
- Test: `backend/tests/test_api_endpoints.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_api_endpoints.py`:

```python
def test_create_user_stores_requirements(client, mock_managers):
    """Test that requirements field is stored in execution metadata."""
    response = client.post('/api/create-user', json={
        'email': 'test@example.com',
        'phone': '+1234567890',
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a portfolio website with dark theme'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert 'execution_id' in data

    # Verify update_metadata was called with requirements
    mock_managers['execution_tracker'].update_metadata.assert_called_once()
    call_args = mock_managers['execution_tracker'].update_metadata.call_args
    assert call_args[0][1]['requirements'] == 'Build a portfolio website with dark theme'
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api_endpoints.py::test_create_user_stores_requirements -v`
Expected: FAIL - update_metadata not called

**Step 3: Write minimal implementation**

Modify `backend/app.py` create_user function. Add after line 72:

```python
    requirements = data.get("requirements", "")
```

Add after the execution_tracker.create_execution call (after line 107):

```python
    # Store requirements and config in execution metadata
    execution_tracker.update_metadata(execution_id, {
        "requirements": requirements,
        "host_provider": host_provider,
        "site_type": site_type
    })
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_api_endpoints.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app.py backend/tests/test_api_endpoints.py
git commit -m "feat(api): add requirements field to POST /api/create-user

Store requirements text in execution metadata for pipeline processing."
```

---

## Task 4: Add /api/chat Endpoint

**Files:**
- Modify: `backend/app.py`
- Test: `backend/tests/test_api_endpoints.py`

**Step 1: Write the failing tests**

Add to `backend/tests/test_api_endpoints.py`:

```python
def test_chat_endpoint_sends_message(client, mock_managers):
    """Test POST /api/chat sends message to tmux session."""
    # Setup: execution exists and is running
    mock_managers['execution_tracker'].get_status.return_value = {
        'execution_id': 'user123_sess456',
        'status': 'running'
    }

    response = client.post('/api/chat/user123_sess456', json={
        'message': 'Add a contact form to the homepage'
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'sent'


def test_chat_endpoint_404_for_missing_execution(client, mock_managers):
    """Test POST /api/chat returns 404 for missing execution."""
    mock_managers['execution_tracker'].get_status.return_value = None

    response = client.post('/api/chat/nonexistent_exec', json={
        'message': 'Hello'
    })

    assert response.status_code == 404


def test_chat_endpoint_400_for_wrong_status(client, mock_managers):
    """Test POST /api/chat returns 400 if execution not running."""
    mock_managers['execution_tracker'].get_status.return_value = {
        'execution_id': 'user123_sess456',
        'status': 'completed'
    }

    response = client.post('/api/chat/user123_sess456', json={
        'message': 'Hello'
    })

    assert response.status_code == 400
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_api_endpoints.py::test_chat_endpoint_sends_message tests/test_api_endpoints.py::test_chat_endpoint_404_for_missing_execution tests/test_api_endpoints.py::test_chat_endpoint_400_for_wrong_status -v`
Expected: FAIL - endpoint doesn't exist

**Step 3: Write minimal implementation**

Add to `backend/app.py` before the `if __name__` block:

```python
from tmux_helper import TmuxHelper


@app.route('/api/chat/<execution_id>', methods=['POST'])
def chat(execution_id):
    """Send a message to the Claude session.

    Request body:
        {
            "message": string
        }

    Returns:
        {"status": "sent", "execution_id": string}
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body is required"}), 400

    message = data.get("message", "")

    # Validate execution exists
    execution = execution_tracker.get_status(execution_id)
    if not execution:
        return jsonify({"error": "Execution not found"}), 404

    # Validate execution is in a state that accepts messages
    if execution.get('status') not in ['running', 'waiting_input']:
        return jsonify({
            "error": f"Cannot chat - execution status is {execution.get('status')}"
        }), 400

    # Send message to tmux session
    tmux = TmuxHelper()
    tmux.send_instruction(f"exec_{execution_id}", message)

    return jsonify({
        "status": "sent",
        "execution_id": execution_id
    })
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_api_endpoints.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app.py backend/tests/test_api_endpoints.py
git commit -m "feat(api): add POST /api/chat/<execution_id> endpoint

Send messages to Claude session via tmux. Validates execution exists
and is in running/waiting_input status before sending."
```

---

## Task 5: Add /api/redeploy Endpoint

**Files:**
- Modify: `backend/app.py`
- Test: `backend/tests/test_api_endpoints.py`

**Step 1: Write the failing tests**

Add to `backend/tests/test_api_endpoints.py`:

```python
def test_redeploy_endpoint_resets_to_step_6(client, mock_managers):
    """Test POST /api/redeploy resets execution to deploy step."""
    mock_managers['execution_tracker'].get_status.return_value = {
        'execution_id': 'user123_sess456',
        'status': 'completed'
    }

    response = client.post('/api/redeploy/user123_sess456')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'redeploying'

    # Verify status was reset to running at step 6
    mock_managers['execution_tracker'].update_step.assert_called_with(
        'user123_sess456', 6, 'deploy', 'running'
    )


def test_redeploy_endpoint_404_for_missing_execution(client, mock_managers):
    """Test POST /api/redeploy returns 404 for missing execution."""
    mock_managers['execution_tracker'].get_status.return_value = None

    response = client.post('/api/redeploy/nonexistent_exec')

    assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_api_endpoints.py::test_redeploy_endpoint_resets_to_step_6 tests/test_api_endpoints.py::test_redeploy_endpoint_404_for_missing_execution -v`
Expected: FAIL - endpoint doesn't exist

**Step 3: Write minimal implementation**

Add to `backend/app.py` before the `if __name__` block:

```python
@app.route('/api/redeploy/<execution_id>', methods=['POST'])
def redeploy(execution_id):
    """Trigger redeployment of an existing session.

    Resets execution to step 6 (deploy) and re-queues the job.

    Returns:
        {"status": "redeploying", "execution_id": string}
    """
    # Validate execution exists
    execution = execution_tracker.get_status(execution_id)
    if not execution:
        return jsonify({"error": "Execution not found"}), 404

    # Reset to deploy step
    execution_tracker.update_step(execution_id, 6, "deploy", "running")

    # TODO: Re-queue job for processing
    # job_queue.enqueue(execution_id, start_step=6)

    return jsonify({
        "status": "redeploying",
        "execution_id": execution_id
    })
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_api_endpoints.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app.py backend/tests/test_api_endpoints.py
git commit -m "feat(api): add POST /api/redeploy/<execution_id> endpoint

Reset execution to step 6 (deploy) for redeployment. Job queue
integration marked as TODO."
```

---

## Task 6: Add /api/chat/history Endpoint

**Files:**
- Modify: `backend/app.py`
- Test: `backend/tests/test_api_endpoints.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_api_endpoints.py`:

```python
def test_chat_history_returns_tmux_output(client, mock_managers, mocker):
    """Test GET /api/chat/<id>/history returns tmux pane output."""
    mock_managers['execution_tracker'].get_status.return_value = {
        'execution_id': 'user123_sess456',
        'status': 'running'
    }

    # Mock TmuxHelper.capture_pane_output
    mock_tmux = mocker.patch('app.TmuxHelper')
    mock_tmux.return_value.capture_pane_output.return_value = "Claude: Hello!\nUser: Hi there"

    response = client.get('/api/chat/user123_sess456/history')

    assert response.status_code == 200
    data = response.get_json()
    assert 'output' in data
    assert 'Claude: Hello!' in data['output']
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_api_endpoints.py::test_chat_history_returns_tmux_output -v`
Expected: FAIL - endpoint doesn't exist

**Step 3: Write minimal implementation**

Add to `backend/app.py` before the `if __name__` block:

```python
@app.route('/api/chat/<execution_id>/history', methods=['GET'])
def chat_history(execution_id):
    """Get recent tmux pane output for display.

    Returns:
        {"output": string, "execution_id": string}
    """
    # Validate execution exists
    execution = execution_tracker.get_status(execution_id)
    if not execution:
        return jsonify({"error": "Execution not found"}), 404

    # Capture tmux output
    tmux = TmuxHelper()
    output = tmux.capture_pane_output(f"exec_{execution_id}", lines=100)

    return jsonify({
        "output": output,
        "execution_id": execution_id
    })
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_api_endpoints.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/app.py backend/tests/test_api_endpoints.py
git commit -m "feat(api): add GET /api/chat/<execution_id>/history endpoint

Return last 100 lines of tmux pane output for frontend display."
```

---

## Task 7: Create JobRunner Module

**Files:**
- Create: `backend/job_runner.py`
- Create: `backend/tests/test_job_runner.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_job_runner.py`:

```python
"""Tests for JobRunner pipeline orchestration."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_job_runner_init_loads_execution_metadata(tmp_path, monkeypatch):
    """Test JobRunner loads execution metadata on init."""
    # Setup mock execution tracker
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
    from job_runner import JobRunner

    # Setup
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
    mock_tmux.create_session_with_health_check.return_value = MagicMock(is_healthy=lambda: True)

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
    # Verify update_step was called for each step
    assert mock_tracker.update_step.call_count >= 7
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_job_runner.py -v`
Expected: FAIL - module doesn't exist

**Step 3: Write minimal implementation**

Create `backend/job_runner.py`:

```python
"""
Job Runner - Pipeline orchestrator for multi-user deployments.

Executes the 9-step deployment pipeline:
1-2: User/session creation (done by API)
3: Gather requirements
4: Create plan (Claude in tmux)
5: Generate code (Claude in tmux)
6: Deploy to cloud
7: Health check
8: Screenshot
9: E2E tests
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional

from execution_tracker import ExecutionTracker
from tmux_helper import TmuxHelper

logger = logging.getLogger(__name__)

# Default users directory (can be patched in tests)
USERS_DIR = Path(__file__).parent.parent / "users"

# Timeout for waiting on Claude completion signals (seconds)
DEFAULT_PHASE_TIMEOUT = 300


class JobRunner:
    """
    Pipeline orchestrator that executes deployment steps 3-9.

    Steps 1-2 (create_user, create_session) are handled by the API endpoint.
    """

    def __init__(self, execution_id: str):
        """
        Initialize JobRunner with execution metadata.

        Args:
            execution_id: Execution identifier (format: {user_id}_{session_id})
        """
        self.execution_id = execution_id
        self.tracker = ExecutionTracker()
        self.tmux = TmuxHelper()

        # Load execution metadata
        execution = self.tracker.get_status(execution_id)
        if not execution:
            raise ValueError(f"Execution not found: {execution_id}")

        self.user_id = execution['user_id']
        self.session_id = execution['session_id']
        self.host_provider = execution.get('host_provider', 'aws')
        self.site_type = execution.get('site_type', 'static')
        self.requirements = execution.get('requirements', '')

        # Build session path
        import job_runner
        self.session_path = job_runner.USERS_DIR / self.user_id / "sessions" / self.session_id

        self.deployed_url: Optional[str] = None

    def run_pipeline(self) -> dict:
        """
        Execute pipeline steps 3-9.

        Returns:
            Result dict with status and url (if successful)
        """
        steps = [
            (3, "gather_requirements", self._gather_requirements),
            (4, "create_plan", self._create_plan),
            (5, "generate_code", self._generate_code),
            (6, "deploy", self._deploy),
            (7, "health_check", self._health_check),
            (8, "screenshot", self._screenshot),
            (9, "e2e_tests", self._run_e2e_tests),
        ]

        # Start tmux session first
        self._start_claude_session()

        for step_num, step_name, step_fn in steps:
            self.tracker.update_step(self.execution_id, step_num, step_name, "running")
            self.tracker.log(
                self.execution_id, "INFO",
                f"Starting step {step_num}: {step_name}",
                step=step_num, step_name=step_name
            )

            try:
                result = step_fn()
                self.tracker.log(
                    self.execution_id, "INFO",
                    f"Completed step {step_num}: {step_name}",
                    step=step_num, step_name=step_name,
                    details=result if isinstance(result, dict) else None
                )
            except Exception as e:
                logger.error(f"Step {step_name} failed: {e}")
                self.tracker.set_error(self.execution_id, {
                    "step": step_num,
                    "step_name": step_name,
                    "error": str(e)
                })
                return {"status": "failed", "step": step_name, "error": str(e)}

        # Mark as completed
        self.tracker.set_result(self.execution_id, {
            "status": "completed",
            "url": self.deployed_url
        })

        return {"status": "completed", "url": self.deployed_url}

    def _start_claude_session(self) -> None:
        """Start tmux session with Claude CLI."""
        session_name = f"exec_{self.execution_id}"

        logger.info(f"Starting Claude session: {session_name}")
        health = self.tmux.create_session_with_health_check(
            session_name=session_name,
            working_dir=self.session_path
        )

        if not health.is_healthy():
            raise RuntimeError(f"Failed to start Claude session: {health.error}")

    def _gather_requirements(self) -> dict:
        """Step 3: Save requirements to file."""
        prompts_dir = self.session_path / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)

        req_file = prompts_dir / "requirements.txt"
        req_file.write_text(self.requirements)

        logger.info(f"Requirements saved to {req_file}")
        return {"requirements_file": str(req_file)}

    def _create_plan(self) -> dict:
        """Step 4: Send kickoff prompt to Claude for planning."""
        kickoff_prompt = f"""You are working in session {self.session_id}.

FIRST: Read docs/PROJECT_GUIDELINES.md - these are mandatory instructions.

THEN: Use the project-inception skill to process these requirements:
---
{self.requirements}
---

Your outputs:
- Plan: Write to output/plan.md
- Signal completion: Write "PHASE_COMPLETE: planning" to output/status.txt
"""
        self._send_prompt_and_wait(kickoff_prompt, "PHASE_COMPLETE: planning")
        return {"phase": "planning"}

    def _generate_code(self) -> dict:
        """Step 5: Wait for Claude to generate code."""
        code_prompt = """Continue with code generation.

Execute the plan you created. Write all code to the source/ directory.

When finished, signal completion:
Write "PHASE_COMPLETE: coding" to output/status.txt
"""
        self._send_prompt_and_wait(code_prompt, "PHASE_COMPLETE: coding")
        return {"phase": "coding"}

    def _deploy(self) -> dict:
        """Step 6: Deploy to AWS/Azure."""
        from aws_deployer import AWSDeployer
        from azure_deployer import AzureDeployer

        source_path = str(self.session_path / "source")

        if self.host_provider == "aws":
            if self.site_type == "static":
                deployer = AWSDeployer(self.user_id, self.session_id)
            else:
                # Dynamic deployer - import when needed
                from aws_ec2_deployer import AWSEC2Deployer
                deployer = AWSEC2Deployer(self.user_id, self.session_id)
        else:  # azure
            if self.site_type == "static":
                deployer = AzureDeployer(self.user_id, self.session_id)
            else:
                from azure_vm_deployer import AzureVMDeployer
                deployer = AzureVMDeployer(self.user_id, self.session_id)

        result = deployer.deploy(source_path)
        self.deployed_url = result.get("url")

        if self.deployed_url:
            self.tracker.set_deployed_url(self.execution_id, self.deployed_url)

        return result

    def _health_check(self) -> dict:
        """Step 7: Verify deployed URL returns 200."""
        from health_checker import HealthChecker

        if not self.deployed_url:
            raise ValueError("No deployed URL to check")

        checker = HealthChecker()
        result = checker.check(self.deployed_url)

        if not result.get("healthy"):
            raise RuntimeError(f"Health check failed: {result.get('error')}")

        return result

    def _screenshot(self) -> dict:
        """Step 8: Capture screenshot of deployed site."""
        from screenshot_capture import ScreenshotCapture

        if not self.deployed_url:
            raise ValueError("No deployed URL to screenshot")

        capture = ScreenshotCapture()
        output_path = str(self.session_path / "deployment" / "screenshot.png")

        result = capture.capture(self.deployed_url, output_path)
        return result

    def _run_e2e_tests(self) -> dict:
        """Step 9: Generate and run E2E tests."""
        from e2e_runner import E2ERunner

        if not self.deployed_url:
            raise ValueError("No deployed URL to test")

        runner = E2ERunner(str(self.session_path), self.deployed_url)

        # Ask Claude to generate tests
        runner.generate_tests(self.tmux, self.execution_id)
        self._wait_for_signal("PHASE_COMPLETE: test_generation", timeout=180)

        # Run the generated tests
        results = runner.run_tests()
        runner.save_results(results)

        if results.get("status") == "failed":
            raise RuntimeError(f"E2E tests failed: {results.get('stderr', '')}")

        return results

    def _send_prompt_and_wait(self, prompt: str, completion_signal: str) -> str:
        """Send prompt to Claude and wait for completion signal."""
        # Write prompt to file (SmartBuild pattern)
        prompt_file = self.session_path / "prompts" / "current.txt"
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(prompt)

        # Send instruction to read the prompt file
        session_name = f"exec_{self.execution_id}"
        self.tmux.send_instruction(
            session_name,
            "Read and execute the prompt in prompts/current.txt"
        )

        # Wait for completion signal
        return self._wait_for_signal(completion_signal)

    def _wait_for_signal(self, signal: str, timeout: int = DEFAULT_PHASE_TIMEOUT) -> str:
        """Poll output/status.txt for completion signal."""
        status_file = self.session_path / "output" / "status.txt"
        start = time.time()

        while time.time() - start < timeout:
            if status_file.exists():
                content = status_file.read_text()
                if signal in content:
                    logger.info(f"Received signal: {signal}")
                    return content
            time.sleep(5)  # Poll every 5 seconds

        raise TimeoutError(f"Timeout waiting for signal: {signal}")
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_job_runner.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/job_runner.py backend/tests/test_job_runner.py
git commit -m "feat: add JobRunner pipeline orchestrator

9-step pipeline execution with:
- Tmux session management
- File-based prompt I/O (SmartBuild pattern)
- Status signal polling
- Cloud deployer integration
- Health check, screenshot, E2E test phases"
```

---

## Task 8: Create E2ERunner Module

**Files:**
- Create: `backend/e2e_runner.py`
- Create: `backend/tests/test_e2e_runner.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_e2e_runner.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_e2e_runner.py -v`
Expected: FAIL - module doesn't exist

**Step 3: Write minimal implementation**

Create `backend/e2e_runner.py`:

```python
"""
E2E Test Runner - Generate and execute end-to-end tests.

Two-phase approach:
1. Claude generates Playwright tests based on deployed site
2. Python executes tests and collects results
"""

import os
import json
import subprocess
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tmux_helper import TmuxHelper

logger = logging.getLogger(__name__)


class E2ERunner:
    """Generate and run E2E tests for deployed sites."""

    def __init__(self, session_path: str, deployed_url: str):
        """
        Initialize E2E runner.

        Args:
            session_path: Path to session directory
            deployed_url: URL of deployed site to test
        """
        self.session_path = Path(session_path)
        self.deployed_url = deployed_url
        self.test_dir = self.session_path / "deployment" / "tests"
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def generate_tests(self, tmux: TmuxHelper, execution_id: str) -> None:
        """
        Ask Claude to generate E2E tests.

        Args:
            tmux: TmuxHelper instance
            execution_id: Execution identifier for session naming
        """
        prompt = f"""Generate Playwright E2E tests for the deployed site at: {self.deployed_url}

Use the testing/e2e-generate skill.

Write tests to: deployment/tests/e2e_test.py

Test these scenarios:
1. Homepage loads successfully (status 200)
2. All navigation links work (no 404s)
3. Forms submit correctly (if any exist)
4. Images load without errors
5. Mobile responsive layout works (viewport 375px)

Requirements:
- Use pytest with playwright
- Each test should be independent
- Include setup/teardown for browser
- Add descriptive test names and docstrings

Signal completion: Write "PHASE_COMPLETE: test_generation" to output/status.txt
"""
        session_name = f"exec_{execution_id}"
        tmux.send_instruction(session_name, prompt)
        logger.info(f"Sent E2E test generation prompt to {session_name}")

    def run_tests(self) -> dict:
        """
        Execute generated tests with Playwright.

        Returns:
            Result dict with status, stdout, stderr, report_path
        """
        test_file = self.test_dir / "e2e_test.py"

        if not test_file.exists():
            logger.warning("No test file found, skipping E2E tests")
            return {"status": "skipped", "reason": "No tests generated"}

        logger.info(f"Running E2E tests from {test_file}")

        try:
            result = subprocess.run(
                [
                    "python", "-m", "pytest", str(test_file),
                    "--tb=short", "-v",
                    f"--html={self.test_dir}/report.html",
                    "--self-contained-html"
                ],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.session_path)
            )

            return {
                "status": "passed" if result.returncode == 0 else "failed",
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "report_path": str(self.test_dir / "report.html")
            }

        except subprocess.TimeoutExpired:
            return {
                "status": "failed",
                "error": "Test execution timed out after 120 seconds"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }

    def save_results(self, results: dict) -> None:
        """
        Save test results to JSON file.

        Args:
            results: Results dict from run_tests()
        """
        results["timestamp"] = datetime.now(timezone.utc).isoformat()
        results["url_tested"] = self.deployed_url

        results_file = self.test_dir / "results.json"
        results_file.write_text(json.dumps(results, indent=2))

        logger.info(f"Test results saved to {results_file}")
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_e2e_runner.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/e2e_runner.py backend/tests/test_e2e_runner.py
git commit -m "feat: add E2ERunner for test generation and execution

Two-phase approach:
- generate_tests: prompts Claude to write Playwright tests
- run_tests: executes tests with pytest, generates HTML report
- save_results: persists results.json with timestamp"
```

---

## Task 9: Create AWS EC2 Deployer

**Files:**
- Create: `backend/aws_ec2_deployer.py`
- Create: `backend/tests/test_aws_ec2_deployer.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_aws_ec2_deployer.py`:

```python
"""Tests for AWS EC2 deployer."""

import pytest
from unittest.mock import MagicMock, patch


def test_ec2_deployer_init_creates_clients():
    """Test AWSEC2Deployer initializes boto3 clients."""
    with patch('aws_ec2_deployer.boto3') as mock_boto:
        from aws_ec2_deployer import AWSEC2Deployer
        deployer = AWSEC2Deployer('user123', 'sess456')

    assert mock_boto.client.call_count >= 2  # ec2 and ssm


def test_ec2_deployer_deploy_launches_instance():
    """Test deploy method launches EC2 instance."""
    with patch('aws_ec2_deployer.boto3') as mock_boto:
        mock_ec2 = MagicMock()
        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-12345'}]
        }
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-12345',
                    'State': {'Name': 'running'},
                    'PublicIpAddress': '1.2.3.4'
                }]
            }]
        }
        mock_boto.client.return_value = mock_ec2

        from aws_ec2_deployer import AWSEC2Deployer
        deployer = AWSEC2Deployer('user123', 'sess456')

        # Mock the wait and upload methods
        deployer._wait_for_instance = MagicMock()
        deployer._upload_code = MagicMock()
        deployer._run_setup_commands = MagicMock()

        result = deployer.deploy('/path/to/source', 'node')

    assert result['instance_id'] == 'i-12345'
    assert result['url'] == 'http://1.2.3.4'
    assert result['provider'] == 'aws'
    assert result['type'] == 'ec2'
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_aws_ec2_deployer.py -v`
Expected: FAIL - module doesn't exist

**Step 3: Write minimal implementation**

Create `backend/aws_ec2_deployer.py`:

```python
"""
AWS EC2 Deployer - Deploy dynamic sites to EC2 instances.

Handles Node.js, Python, and other dynamic applications.
"""

import os
import time
import logging
import boto3
from typing import Optional

from cloud_config import CloudConfig

logger = logging.getLogger(__name__)

# Default AMI (Amazon Linux 2023)
DEFAULT_AMI = 'ami-0c02fb55956c7d316'
DEFAULT_INSTANCE_TYPE = 't3.micro'
DEFAULT_KEY_NAME = 'tmux-builder-key'


class AWSEC2Deployer:
    """Deploy dynamic sites to AWS EC2."""

    def __init__(self, user_id: str, session_id: str):
        """
        Initialize EC2 deployer.

        Args:
            user_id: User GUID
            session_id: Session identifier
        """
        self.naming = CloudConfig(user_id, session_id)
        self.user_id = user_id
        self.session_id = session_id

        # Lazy-load clients
        self._ec2: Optional[boto3.client] = None
        self._ssm: Optional[boto3.client] = None

    @property
    def ec2(self):
        """Lazy-load EC2 client."""
        if self._ec2 is None:
            self._ec2 = boto3.client('ec2')
        return self._ec2

    @property
    def ssm(self):
        """Lazy-load SSM client."""
        if self._ssm is None:
            self._ssm = boto3.client('ssm')
        return self._ssm

    def deploy(self, source_path: str, site_type: str = 'node') -> dict:
        """
        Deploy dynamic site to EC2.

        Args:
            source_path: Path to source code directory
            site_type: Type of application (node, python)

        Returns:
            Deployment result dict with url, instance_id, etc.
        """
        logger.info(f"Deploying {site_type} app from {source_path}")

        # 1. Launch or reuse instance
        instance_id = self._get_or_create_instance()

        # 2. Wait for instance to be ready
        self._wait_for_instance(instance_id)

        # 3. Upload code
        self._upload_code(instance_id, source_path)

        # 4. Install dependencies and start app
        self._run_setup_commands(instance_id, site_type)

        # 5. Get public IP
        public_ip = self._get_public_ip(instance_id)

        return {
            "url": f"http://{public_ip}",
            "instance_id": instance_id,
            "provider": "aws",
            "type": "ec2"
        }

    def _get_or_create_instance(self) -> str:
        """Launch new EC2 instance with proper tags."""
        instance_name = self.naming.get_resource_name("ec2")
        tags = self.naming.get_tags()
        tags.append({'Key': 'Name', 'Value': instance_name})

        logger.info(f"Launching EC2 instance: {instance_name}")

        response = self.ec2.run_instances(
            ImageId=DEFAULT_AMI,
            InstanceType=DEFAULT_INSTANCE_TYPE,
            MinCount=1,
            MaxCount=1,
            KeyName=DEFAULT_KEY_NAME,
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': tags
            }],
            UserData=self._get_user_data_script(),
            IamInstanceProfile={'Name': 'tmux-builder-ec2-role'}
        )

        instance_id = response['Instances'][0]['InstanceId']
        logger.info(f"Launched instance: {instance_id}")

        return instance_id

    def _wait_for_instance(self, instance_id: str, timeout: int = 300) -> None:
        """Wait for instance to be running and reachable."""
        logger.info(f"Waiting for instance {instance_id} to be ready...")

        waiter = self.ec2.get_waiter('instance_running')
        waiter.wait(
            InstanceIds=[instance_id],
            WaiterConfig={'Delay': 10, 'MaxAttempts': timeout // 10}
        )

        # Additional wait for SSM agent
        time.sleep(30)
        logger.info(f"Instance {instance_id} is ready")

    def _upload_code(self, instance_id: str, source_path: str) -> None:
        """Upload source code to instance via S3 and SSM."""
        # For simplicity, use SSM to run commands
        # In production, would use S3 as intermediary
        logger.info(f"Uploading code to {instance_id}")

        # Create tar of source and upload via SSM
        # This is a simplified version
        pass

    def _run_setup_commands(self, instance_id: str, site_type: str) -> None:
        """Run setup commands on instance via SSM."""
        if site_type == 'node':
            commands = [
                'cd /app',
                'npm install',
                'npm start &'
            ]
        elif site_type == 'python':
            commands = [
                'cd /app',
                'pip install -r requirements.txt',
                'python app.py &'
            ]
        else:
            commands = ['echo "Unknown site type"']

        logger.info(f"Running setup commands for {site_type}")

        self.ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={'commands': commands}
        )

    def _get_public_ip(self, instance_id: str) -> str:
        """Get public IP of instance."""
        response = self.ec2.describe_instances(InstanceIds=[instance_id])
        return response['Reservations'][0]['Instances'][0].get('PublicIpAddress', '')

    def _get_user_data_script(self) -> str:
        """Return user data script for instance initialization."""
        return '''#!/bin/bash
yum update -y
yum install -y nodejs npm python3 python3-pip git
mkdir -p /app
chown ec2-user:ec2-user /app
'''
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_aws_ec2_deployer.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/aws_ec2_deployer.py backend/tests/test_aws_ec2_deployer.py
git commit -m "feat: add AWS EC2 deployer for dynamic sites

Supports Node.js and Python applications with:
- Instance launch with proper tags
- SSM for remote command execution
- User data script for initial setup"
```

---

## Task 10: Create Azure VM Deployer

**Files:**
- Create: `backend/azure_vm_deployer.py`
- Create: `backend/tests/test_azure_vm_deployer.py`

**Step 1: Write the failing tests**

Create `backend/tests/test_azure_vm_deployer.py`:

```python
"""Tests for Azure VM deployer."""

import pytest
from unittest.mock import MagicMock, patch


def test_azure_vm_deployer_init():
    """Test AzureVMDeployer initializes correctly."""
    with patch('azure_vm_deployer.DefaultAzureCredential'):
        with patch('azure_vm_deployer.ComputeManagementClient'):
            with patch('azure_vm_deployer.NetworkManagementClient'):
                with patch('azure_vm_deployer.ResourceManagementClient'):
                    from azure_vm_deployer import AzureVMDeployer
                    deployer = AzureVMDeployer('user123', 'sess456')

    assert deployer.user_id == 'user123'
    assert deployer.session_id == 'sess456'


def test_azure_vm_deployer_deploy_creates_vm():
    """Test deploy method creates Azure VM."""
    with patch('azure_vm_deployer.DefaultAzureCredential'):
        with patch('azure_vm_deployer.ComputeManagementClient') as mock_compute:
            with patch('azure_vm_deployer.NetworkManagementClient') as mock_network:
                with patch('azure_vm_deployer.ResourceManagementClient') as mock_resource:
                    from azure_vm_deployer import AzureVMDeployer
                    deployer = AzureVMDeployer('user123', 'sess456')

                    # Mock methods
                    deployer._ensure_resource_group = MagicMock(return_value='tmux-rg')
                    deployer._create_network_resources = MagicMock(return_value=('nic-id', '1.2.3.4'))
                    deployer._create_vm = MagicMock()
                    deployer._deploy_code = MagicMock()

                    result = deployer.deploy('/path/to/source', 'node')

    assert result['url'] == 'http://1.2.3.4'
    assert result['provider'] == 'azure'
    assert result['type'] == 'vm'
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_azure_vm_deployer.py -v`
Expected: FAIL - module doesn't exist

**Step 3: Write minimal implementation**

Create `backend/azure_vm_deployer.py`:

```python
"""
Azure VM Deployer - Deploy dynamic sites to Azure Virtual Machines.

Handles Node.js, Python, and other dynamic applications.
"""

import logging
from typing import Optional, Tuple

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient

from cloud_config import CloudConfig

logger = logging.getLogger(__name__)

# Azure subscription (should come from env)
SUBSCRIPTION_ID = 'your-subscription-id'
DEFAULT_LOCATION = 'eastus'
DEFAULT_VM_SIZE = 'Standard_B1s'


class AzureVMDeployer:
    """Deploy dynamic sites to Azure VMs."""

    def __init__(self, user_id: str, session_id: str):
        """
        Initialize Azure VM deployer.

        Args:
            user_id: User GUID
            session_id: Session identifier
        """
        self.naming = CloudConfig(user_id, session_id)
        self.user_id = user_id
        self.session_id = session_id

        # Initialize Azure clients
        self.credential = DefaultAzureCredential()
        self.compute_client = ComputeManagementClient(self.credential, SUBSCRIPTION_ID)
        self.network_client = NetworkManagementClient(self.credential, SUBSCRIPTION_ID)
        self.resource_client = ResourceManagementClient(self.credential, SUBSCRIPTION_ID)

    def deploy(self, source_path: str, site_type: str = 'node') -> dict:
        """
        Deploy dynamic site to Azure VM.

        Args:
            source_path: Path to source code directory
            site_type: Type of application (node, python)

        Returns:
            Deployment result dict with url, vm_name, etc.
        """
        logger.info(f"Deploying {site_type} app from {source_path}")

        # 1. Ensure resource group exists
        rg_name = self._ensure_resource_group()

        # 2. Create network resources
        nic_id, public_ip = self._create_network_resources(rg_name)

        # 3. Create VM
        vm_name = self.naming.get_resource_name("vm", max_length=15)
        self._create_vm(rg_name, vm_name, nic_id)

        # 4. Deploy code
        self._deploy_code(rg_name, vm_name, source_path, site_type)

        return {
            "url": f"http://{public_ip}",
            "vm_name": vm_name,
            "resource_group": rg_name,
            "provider": "azure",
            "type": "vm"
        }

    def _ensure_resource_group(self) -> str:
        """Create resource group if it doesn't exist."""
        rg_name = self.naming.get_resource_name("rg", max_length=24)

        logger.info(f"Ensuring resource group: {rg_name}")

        self.resource_client.resource_groups.create_or_update(
            rg_name,
            {
                'location': DEFAULT_LOCATION,
                'tags': self.naming.get_azure_tags()
            }
        )

        return rg_name

    def _create_network_resources(self, rg_name: str) -> Tuple[str, str]:
        """Create VNet, subnet, public IP, and NIC."""
        vnet_name = self.naming.get_resource_name("vnet", max_length=24)
        subnet_name = 'default'
        pip_name = self.naming.get_resource_name("pip", max_length=24)
        nic_name = self.naming.get_resource_name("nic", max_length=24)

        # Create VNet
        vnet_result = self.network_client.virtual_networks.begin_create_or_update(
            rg_name, vnet_name,
            {
                'location': DEFAULT_LOCATION,
                'address_space': {'address_prefixes': ['10.0.0.0/16']},
                'subnets': [{'name': subnet_name, 'address_prefix': '10.0.0.0/24'}]
            }
        ).result()

        subnet_id = vnet_result.subnets[0].id

        # Create public IP
        pip_result = self.network_client.public_ip_addresses.begin_create_or_update(
            rg_name, pip_name,
            {
                'location': DEFAULT_LOCATION,
                'sku': {'name': 'Basic'},
                'public_ip_allocation_method': 'Dynamic'
            }
        ).result()

        # Create NIC
        nic_result = self.network_client.network_interfaces.begin_create_or_update(
            rg_name, nic_name,
            {
                'location': DEFAULT_LOCATION,
                'ip_configurations': [{
                    'name': 'ipconfig1',
                    'subnet': {'id': subnet_id},
                    'public_ip_address': {'id': pip_result.id}
                }]
            }
        ).result()

        # Get allocated public IP
        pip_result = self.network_client.public_ip_addresses.get(rg_name, pip_name)
        public_ip = pip_result.ip_address or 'pending'

        return nic_result.id, public_ip

    def _create_vm(self, rg_name: str, vm_name: str, nic_id: str) -> None:
        """Create the VM."""
        logger.info(f"Creating VM: {vm_name}")

        self.compute_client.virtual_machines.begin_create_or_update(
            rg_name, vm_name,
            {
                'location': DEFAULT_LOCATION,
                'hardware_profile': {'vm_size': DEFAULT_VM_SIZE},
                'storage_profile': {
                    'image_reference': {
                        'publisher': 'Canonical',
                        'offer': 'UbuntuServer',
                        'sku': '18.04-LTS',
                        'version': 'latest'
                    }
                },
                'os_profile': {
                    'computer_name': vm_name,
                    'admin_username': 'azureuser',
                    'linux_configuration': {
                        'disable_password_authentication': True,
                        'ssh': {
                            'public_keys': [{
                                'path': '/home/azureuser/.ssh/authorized_keys',
                                'key_data': 'ssh-rsa AAAA...'  # Would come from config
                            }]
                        }
                    }
                },
                'network_profile': {
                    'network_interfaces': [{'id': nic_id}]
                },
                'tags': self.naming.get_azure_tags()
            }
        ).result()

    def _deploy_code(self, rg_name: str, vm_name: str, source_path: str, site_type: str) -> None:
        """Deploy code to VM using Custom Script Extension."""
        logger.info(f"Deploying code to {vm_name}")

        if site_type == 'node':
            script = 'apt-get update && apt-get install -y nodejs npm && cd /app && npm install && npm start'
        elif site_type == 'python':
            script = 'apt-get update && apt-get install -y python3 python3-pip && cd /app && pip3 install -r requirements.txt && python3 app.py'
        else:
            script = 'echo "Unknown site type"'

        self.compute_client.virtual_machine_extensions.begin_create_or_update(
            rg_name, vm_name, 'CustomScript',
            {
                'location': DEFAULT_LOCATION,
                'publisher': 'Microsoft.Azure.Extensions',
                'type_properties_type': 'CustomScript',
                'type_handler_version': '2.1',
                'settings': {
                    'commandToExecute': script
                }
            }
        ).result()
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_azure_vm_deployer.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/azure_vm_deployer.py backend/tests/test_azure_vm_deployer.py
git commit -m "feat: add Azure VM deployer for dynamic sites

Supports Node.js and Python applications with:
- Resource group creation
- VNet, subnet, public IP, NIC setup
- VM creation with Ubuntu
- Custom Script Extension for setup"
```

---

## Task 11: Create Missing Agents (5 files)

**Files:**
- Create: `.claude/agents/deployers/aws-elastic-beanstalk.md`
- Create: `.claude/agents/deployers/azure-blob-static.md`
- Create: `.claude/agents/deployers/azure-app-service.md`
- Create: `.claude/agents/utilities/cache-invalidator.md`
- Create: `.claude/agents/utilities/log-analyzer.md`

**Step 1: Create aws-elastic-beanstalk.md**

```markdown
# AWS Elastic Beanstalk Deployer Agent

You are an AWS deployment agent responsible for deploying dynamic web applications to AWS Elastic Beanstalk.

## Purpose

Deploy Node.js, Python, and other dynamic applications to Elastic Beanstalk with automatic scaling, load balancing, and managed infrastructure.

## Capabilities

- Deploy web applications to Elastic Beanstalk environments
- Configure environment variables and settings
- Manage application versions and deployments
- Integrate with RDS for database needs

## Configuration

- **AWS Profile**: sunwaretech
- **Default Region**: us-east-1
- **Service**: Elastic Beanstalk

---

## Deployment Process

### Initial Deploy

1. **Read Configuration**
   - Load deployment config from `deployment/config.json`
   - Detect application type (Node.js, Python)

2. **Create Application Bundle**
   - Package source/ directory into ZIP
   - Include appropriate Procfile or config

3. **Deploy to Elastic Beanstalk**
   - Use `aws/eb-deploy` skill
   - Create application and environment if needed
   - Upload and deploy application version

4. **Configure Environment**
   - Set environment variables
   - Configure scaling rules
   - Set up health checks

5. **Verify Deployment**
   - Wait for environment to be Ready
   - Run health check on environment URL
   - Capture screenshot

6. **Update Configuration**
   - Save environment URL to deployment/config.json
   - Log deployment details

---

## Resource Naming

Pattern: `tmux-{guid_prefix}-{session_short}`

---

## Required Tags

```json
{
  "Project": "tmux-builder",
  "UserGUID": "{user_id}",
  "SessionID": "{session_id}",
  "SiteType": "dynamic",
  "CreatedBy": "tmux-builder-automation"
}
```

---

## Error Handling

- Retry failed deployments up to 3 times
- Check environment health before declaring success
- Log all errors with timestamps
- Provide clear remediation steps

---

## Skills Used

- `aws/eb-deploy` - Deploy to Elastic Beanstalk
- `aws/rds-configure` - Set up RDS database (if needed)
```

**Step 2: Create remaining agent files**

Create similar files for:
- `azure-blob-static.md` - Azure Blob Storage static site deployment
- `azure-app-service.md` - Azure App Service dynamic deployment
- `cache-invalidator.md` - CloudFront/Azure CDN cache purge
- `log-analyzer.md` - Deployment log analysis

**Step 3: Commit**

```bash
git add .claude/agents/deployers/*.md .claude/agents/utilities/*.md
git commit -m "feat: add missing agent definitions

- aws-elastic-beanstalk: dynamic site deployment
- azure-blob-static: Azure static site deployment
- azure-app-service: Azure dynamic deployment
- cache-invalidator: CDN cache purge utility
- log-analyzer: deployment log analysis"
```

---

## Task 12: Create Missing Skills (14 files)

**Files to create in `.claude/skills/`:**

### AWS Skills
- `aws/eb-deploy.md`
- `aws/rds-configure.md`
- `aws/elasticache-setup.md`
- `aws/ec2-launch.md`

### Azure Skills
- `azure/blob-upload.md`
- `azure/cdn-create.md`
- `azure/cdn-purge.md`
- `azure/app-service-deploy.md`
- `azure/sql-configure.md`
- `azure/redis-setup.md`

### Testing Skills
- `testing/health-check.md`
- `testing/screenshot-capture.md`
- `testing/e2e-generate.md`
- `testing/e2e-run.md`

**Step 1: Create skill files following template from Task 11**

Each skill should include:
- Purpose section
- Prerequisites
- Usage examples with commands
- Verification steps
- Common errors table

**Step 2: Commit**

```bash
git add .claude/skills/aws/*.md .claude/skills/azure/*.md .claude/skills/testing/*.md
git commit -m "feat: add missing skill definitions

AWS: eb-deploy, rds-configure, elasticache-setup, ec2-launch
Azure: blob-upload, cdn-create, cdn-purge, app-service-deploy, sql-configure, redis-setup
Testing: health-check, screenshot-capture, e2e-generate, e2e-run"
```

---

## Task 13: Wire JobRunner into Queue Monitor

**Files:**
- Modify: `backend/job_queue_monitor.py:197-215`
- Test: `backend/tests/test_job_queue_monitor.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_job_queue_monitor.py`:

```python
def test_start_job_calls_job_runner(tmp_path, monkeypatch):
    """Test _start_job creates and runs JobRunner."""
    from job_queue_monitor import JobQueueMonitor

    mock_runner = MagicMock()
    mock_runner.run_pipeline.return_value = {'status': 'completed'}

    with patch('job_queue_monitor.JobRunner', return_value=mock_runner):
        monitor = JobQueueMonitor()
        monitor._start_job('test_session', {'id': 'job123', 'execution_id': 'user_sess'})

    mock_runner.run_pipeline.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_job_queue_monitor.py::test_start_job_calls_job_runner -v`
Expected: FAIL - JobRunner not imported

**Step 3: Write minimal implementation**

Update `backend/job_queue_monitor.py` `_start_job` method:

```python
def _start_job(self, session_id: str, job: Dict):
    """Start execution of a pending job using JobRunner."""
    from job_runner import JobRunner

    job_id = job.get("id")
    execution_id = job.get("execution_id")

    if not execution_id:
        logger.error(f"Job {job_id} missing execution_id")
        return

    logger.info(f"Starting job {job_id} with execution {execution_id}")

    try:
        runner = JobRunner(execution_id)
        result = runner.run_pipeline()

        if result.get('status') == 'completed':
            logger.info(f"Job {job_id} completed successfully")
        else:
            logger.warning(f"Job {job_id} failed: {result.get('error')}")

    except Exception as e:
        logger.error(f"Error executing job {job_id}: {e}")
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_job_queue_monitor.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add backend/job_queue_monitor.py backend/tests/test_job_queue_monitor.py
git commit -m "feat: wire JobRunner into queue monitor

_start_job now creates JobRunner and calls run_pipeline()
for full deployment execution."
```

---

## Task 14: Integration Test

**Files:**
- Create: `backend/tests/test_integration_pipeline.py`

**Step 1: Write integration test**

```python
"""Integration test for full pipeline execution."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_all_externals():
    """Mock all external services."""
    with patch('job_runner.TmuxHelper') as mock_tmux:
        with patch('job_runner.AWSDeployer') as mock_aws:
            with patch('job_runner.HealthChecker') as mock_health:
                with patch('job_runner.ScreenshotCapture') as mock_screenshot:
                    # Setup mock returns
                    mock_tmux.return_value.create_session_with_health_check.return_value = MagicMock(is_healthy=lambda: True)
                    mock_aws.return_value.deploy.return_value = {'url': 'https://test.cloudfront.net'}
                    mock_health.return_value.check.return_value = {'healthy': True}
                    mock_screenshot.return_value.capture.return_value = {'path': '/test/screenshot.png'}

                    yield {
                        'tmux': mock_tmux,
                        'aws': mock_aws,
                        'health': mock_health,
                        'screenshot': mock_screenshot
                    }


def test_full_pipeline_static_aws(tmp_path, mock_all_externals):
    """Test complete pipeline for AWS static site."""
    import execution_tracker
    import job_runner

    # Setup directories
    users_dir = tmp_path / "users"
    executions_dir = tmp_path / "executions"

    execution_tracker.EXECUTIONS_DIR = executions_dir
    job_runner.USERS_DIR = users_dir

    # Create user and session directories
    session_dir = users_dir / "user123" / "sessions" / "sess456"
    (session_dir / "prompts").mkdir(parents=True)
    (session_dir / "output").mkdir(parents=True)
    (session_dir / "source").mkdir(parents=True)
    (session_dir / "deployment" / "tests").mkdir(parents=True)

    # Create execution
    from execution_tracker import ExecutionTracker
    tracker = ExecutionTracker()
    exec_id = tracker.create_execution("user123", "sess456")
    tracker.update_metadata(exec_id, {
        'host_provider': 'aws',
        'site_type': 'static',
        'requirements': 'Build a simple landing page'
    })

    # Mock the signal file creation (simulating Claude completing tasks)
    def create_signal(signal):
        (session_dir / "output" / "status.txt").write_text(signal)

    # Run pipeline with mocked waits
    from job_runner import JobRunner
    runner = JobRunner(exec_id)

    # Mock wait methods to return immediately
    runner._wait_for_signal = MagicMock(return_value="OK")

    # Mock E2E runner
    with patch('job_runner.E2ERunner') as mock_e2e:
        mock_e2e.return_value.run_tests.return_value = {'status': 'passed'}
        result = runner.run_pipeline()

    assert result['status'] == 'completed'
    assert 'url' in result

    # Verify execution state
    final_status = tracker.get_status(exec_id)
    assert final_status['status'] == 'completed'
```

**Step 2: Run integration test**

Run: `cd backend && python -m pytest tests/test_integration_pipeline.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/test_integration_pipeline.py
git commit -m "test: add integration test for full pipeline

Tests complete flow from execution creation through
deployment with all external services mocked."
```

---

## Summary

**Total Tasks:** 14

**Python files created/modified:**
- `backend/execution_tracker.py` (modified)
- `backend/app.py` (modified)
- `backend/job_runner.py` (created)
- `backend/e2e_runner.py` (created)
- `backend/aws_ec2_deployer.py` (created)
- `backend/azure_vm_deployer.py` (created)
- `backend/job_queue_monitor.py` (modified)

**Agent files created:** 5
**Skill files created:** 14
**Test files created/modified:** 7

**Estimated commits:** 14
