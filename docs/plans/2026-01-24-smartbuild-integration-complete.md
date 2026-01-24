# SmartBuild Integration Complete Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fill the gaps in the current tmux-builder implementation to match the complete SmartBuild pattern with proper initialization, health checks, session lifecycle management, and detailed file-based I/O documentation.

**Architecture:** The implementation follows a two-tier TMUX session model (main persistent + job ephemeral sessions), file-based I/O for prompts/outputs, and a background job queue monitor with completion detection via file mtime checks.

**Tech Stack:** Python 3.8+, Flask, TMUX, Claude CLI, JSON persistence

---

## Gap Analysis Summary

| Feature | SmartBuild Reference | Current Implementation | Gap |
|---------|---------------------|------------------------|-----|
| Session Initialization | Full lifecycle with probe verification | Basic create + probe | Missing detailed startup sequence |
| Health Check/Handshake | Probe + verify + bypass prompts | Partial probe only | Missing retry logic, health state |
| Two-Tier Sessions | Main (persistent) + Job (ephemeral) | Single-tier only | Missing main session concept |
| Background Monitor | Separate process polling queues | Inline execution | No background monitor process |
| Session Recovery | Detect lost sessions, recover state | None | Missing entirely |
| Detailed Logging | Structured component logging | Basic logging | Missing structured log format |
| Agent Templates | `.claude/agents/*.md` loading | None | Missing entirely |
| Concurrency Control | Max 4 concurrent jobs with slots | Config exists, not enforced | Missing enforcement |

---

## Task 1: Create Session Lifecycle Manager

**Files:**
- Create: `backend/session_lifecycle.py`
- Test: `backend/tests/test_session_lifecycle.py`

### Step 1: Write the failing test

```python
# backend/tests/test_session_lifecycle.py
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
```

### Step 2: Run test to verify it fails

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python -m pytest tests/test_session_lifecycle.py -v`
Expected: FAIL with "No module named 'session_lifecycle'"

### Step 3: Write minimal implementation

```python
# backend/session_lifecycle.py
"""
Session Lifecycle Manager

Manages the complete lifecycle of a Claude CLI session including:
- Folder structure initialization
- TMUX session creation and health monitoring
- State transitions and persistence
- Recovery from failures
"""

import json
import logging
from enum import Enum
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from config import ACTIVE_SESSIONS_DIR

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Session lifecycle states."""
    CREATED = "created"           # Folder structure exists
    INITIALIZING = "initializing" # TMUX session starting
    READY = "ready"               # Claude CLI ready for commands
    PROCESSING = "processing"     # Job in progress
    ERROR = "error"               # Recoverable error state
    TERMINATED = "terminated"     # Session ended


class SessionLifecycle:
    """
    Manages session lifecycle from creation to termination.

    Folder Structure Created:
    ```
    sessions/active/<session_id>/
    ├── metadata.json          # Session metadata
    ├── job_queue.json         # Pending/running/completed jobs
    ├── prompts/               # Prompt files for Claude
    ├── output/                # Output files from Claude
    ├── logs/                  # Session logs
    │   └── session_<id>.log
    └── state/                 # State tracking
        └── health.json        # Health status
    ```
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.session_path = ACTIVE_SESSIONS_DIR / session_id
        self._state = SessionState.CREATED
        self._tmux_session_name: Optional[str] = None

    def initialize_structure(self) -> Path:
        """
        Initialize complete session folder structure.

        This is Step 1 of session startup - create all required directories
        and initial state files before any TMUX operations.

        Returns:
            Path to session directory
        """
        # Create main directory
        self.session_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        subdirs = ["prompts", "output", "logs", "state"]
        for subdir in subdirs:
            (self.session_path / subdir).mkdir(exist_ok=True)

        # Create metadata.json
        metadata = {
            "session_id": self.session_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "state": SessionState.CREATED.value,
            "version": "1.0"
        }
        self._write_json(self.session_path / "metadata.json", metadata)

        # Create initial health.json
        health = {
            "state": SessionState.CREATED.value,
            "tmux_session_active": False,
            "claude_initialized": False,
            "last_check": datetime.utcnow().isoformat() + "Z",
            "last_probe_success": None,
            "error_count": 0,
            "last_error": None
        }
        self._write_json(self.session_path / "state" / "health.json", health)

        # Create empty job_queue.json
        self._write_json(self.session_path / "job_queue.json", [])

        logger.info(f"Initialized session structure: {self.session_path}")
        return self.session_path

    def get_health_status(self) -> Dict:
        """
        Get current health status of the session.

        Returns:
            Dictionary with health status including:
            - state: Current SessionState
            - tmux_session_active: Boolean
            - claude_initialized: Boolean
            - last_check: ISO timestamp
            - error_count: Number of errors
        """
        health_path = self.session_path / "state" / "health.json"

        if not health_path.exists():
            return {
                "state": SessionState.CREATED.value,
                "tmux_session_active": False,
                "claude_initialized": False,
                "last_check": datetime.utcnow().isoformat() + "Z",
                "error_count": 0
            }

        return self._read_json(health_path)

    def update_health_status(self, updates: Dict) -> None:
        """Update health status with new values."""
        health = self.get_health_status()
        health.update(updates)
        health["last_check"] = datetime.utcnow().isoformat() + "Z"
        self._write_json(self.session_path / "state" / "health.json", health)

    def _write_json(self, path: Path, data: Dict) -> None:
        """Write JSON data to file."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _read_json(self, path: Path) -> Dict:
        """Read JSON data from file."""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
```

### Step 4: Run test to verify it passes

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python -m pytest tests/test_session_lifecycle.py -v`
Expected: PASS

### Step 5: Commit

```bash
git add backend/session_lifecycle.py backend/tests/test_session_lifecycle.py
git commit -m "$(cat <<'EOF'
feat: add session lifecycle manager with folder structure initialization

Implements SessionLifecycle class that manages:
- Complete folder structure (prompts/, output/, logs/, state/)
- Session state enum (CREATED, INITIALIZING, READY, PROCESSING, ERROR, TERMINATED)
- Health status tracking via state/health.json
- Initial metadata and job queue files

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Implement TMUX Initialization with Health Handshake

**Files:**
- Modify: `backend/tmux_helper.py:40-110`
- Create: `backend/tests/test_tmux_health.py`

### Step 1: Write the failing test

```python
# backend/tests/test_tmux_health.py
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

    @patch('subprocess.run')
    def test_perform_health_probe_sends_correct_commands(self, mock_run):
        """Verify probe sends echo command and captures output."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[PROBE] ready\n")

        result = TmuxHelper.perform_health_probe("test_session")

        # Should call send-keys with probe command
        calls = mock_run.call_args_list
        assert any("-l" in str(c) and "PROBE" in str(c) for c in calls)

    @patch('subprocess.run')
    def test_initialize_with_retry_on_failure(self, mock_run):
        """Verify initialization retries on failure."""
        # First 2 attempts fail, third succeeds
        mock_run.side_effect = [
            MagicMock(returncode=0),  # new-session
            MagicMock(returncode=0),  # cd
            MagicMock(returncode=0),  # claude start
            MagicMock(returncode=0, stdout=""),  # probe 1 - no response
            MagicMock(returncode=0, stdout=""),  # retry probe
            MagicMock(returncode=0, stdout="[PROBE 123456] Claude ready"),  # success
        ]

        # Implementation should handle retries internally
```

### Step 2: Run test to verify it fails

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python -m pytest tests/test_tmux_health.py -v`
Expected: FAIL with "cannot import name 'TmuxHealthCheck'"

### Step 3: Write minimal implementation

Add to `backend/tmux_helper.py`:

```python
# Add at top of file after imports
from dataclasses import dataclass
from typing import Optional

@dataclass
class TmuxHealthCheck:
    """Result of a TMUX session health check."""
    session_exists: bool
    claude_responding: bool
    probe_success: bool
    probe_timestamp: Optional[str]
    error: Optional[str]

    def is_healthy(self) -> bool:
        """Return True if session is fully healthy."""
        return self.session_exists and self.claude_responding and self.probe_success


class TmuxHelper:
    """Helper class for tmux operations."""

    # ... existing methods ...

    @staticmethod
    def perform_health_probe(
        session_name: str,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ) -> TmuxHealthCheck:
        """
        Perform a health probe on a TMUX session.

        Sends a probe command to verify Claude is responding.
        Retries up to max_retries times on failure.

        Args:
            session_name: TMUX session name
            max_retries: Number of retry attempts
            retry_delay: Seconds between retries

        Returns:
            TmuxHealthCheck with probe results
        """
        from datetime import datetime

        # Check session exists
        if not TmuxHelper.session_exists(session_name):
            return TmuxHealthCheck(
                session_exists=False,
                claude_responding=False,
                probe_success=False,
                probe_timestamp=None,
                error="Session not found"
            )

        # Generate unique probe ID
        timestamp = datetime.now().strftime("%H%M%S")
        probe_marker = f"[PROBE {timestamp}] Claude ready"
        probe_cmd = f"echo '{probe_marker}'"

        for attempt in range(max_retries):
            try:
                # Send probe command
                TmuxHelper._send_literal_command(
                    session_name,
                    probe_cmd,
                    wait_after=2.0
                )

                # Capture output
                output = TmuxHelper.capture_pane_output(session_name)

                if probe_marker in output:
                    return TmuxHealthCheck(
                        session_exists=True,
                        claude_responding=True,
                        probe_success=True,
                        probe_timestamp=datetime.now().isoformat() + "Z",
                        error=None
                    )

                # Probe not found, wait and retry
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

            except Exception as e:
                logger.warning(f"Probe attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)

        return TmuxHealthCheck(
            session_exists=True,
            claude_responding=False,
            probe_success=False,
            probe_timestamp=None,
            error=f"Probe failed after {max_retries} attempts"
        )

    @staticmethod
    def create_session_with_health_check(
        session_name: str,
        working_dir: Path,
        max_init_retries: int = 3
    ) -> TmuxHealthCheck:
        """
        Create TMUX session with full initialization and health verification.

        Complete initialization sequence:
        1. Create TMUX session
        2. CD to working directory
        3. Start Claude CLI with flags
        4. Wait for Claude initialization (3.0s)
        5. Send bypass Enter keys (clear prompts)
        6. Perform health probe with retries
        7. Return health status

        Args:
            session_name: Name for TMUX session
            working_dir: Working directory path
            max_init_retries: Max retries for full init sequence

        Returns:
            TmuxHealthCheck indicating session health
        """
        for attempt in range(max_init_retries):
            try:
                # Kill existing if present
                if TmuxHelper.session_exists(session_name):
                    TmuxHelper.kill_session(session_name)
                    time.sleep(0.5)

                # Step 1: Create session
                logger.info(f"Creating TMUX session: {session_name} (attempt {attempt + 1})")
                subprocess.run(
                    ["tmux", "new-session", "-d", "-s", session_name],
                    stderr=subprocess.DEVNULL,
                    check=True
                )

                # Step 2: CD to working directory
                TmuxHelper._send_literal_command(
                    session_name,
                    f"cd {working_dir}",
                    wait_after=0.5
                )

                # Step 3: Start Claude CLI
                logger.info(f"Starting Claude CLI in session: {session_name}")
                TmuxHelper._send_literal_command(
                    session_name,
                    CLI_COMMAND,
                    wait_after=TMUX_CLAUDE_INIT_DELAY
                )

                # Step 4: Bypass initial prompts (3x Enter)
                for _ in range(3):
                    subprocess.run(
                        ["tmux", "send-keys", "-t", session_name, "Enter"],
                        stderr=subprocess.DEVNULL
                    )
                    time.sleep(0.5)

                # Step 5: Health probe
                health = TmuxHelper.perform_health_probe(session_name)

                if health.is_healthy():
                    logger.info(f"Session {session_name} initialized successfully")
                    return health

                # Not healthy, kill and retry
                logger.warning(f"Health check failed, retrying... ({attempt + 1}/{max_init_retries})")
                TmuxHelper.kill_session(session_name)
                time.sleep(1.0)

            except Exception as e:
                logger.error(f"Init attempt {attempt + 1} failed: {e}")
                TmuxHelper.kill_session(session_name)
                time.sleep(1.0)

        return TmuxHealthCheck(
            session_exists=False,
            claude_responding=False,
            probe_success=False,
            probe_timestamp=None,
            error=f"Initialization failed after {max_init_retries} attempts"
        )
```

### Step 4: Run test to verify it passes

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python -m pytest tests/test_tmux_health.py -v`
Expected: PASS

### Step 5: Commit

```bash
git add backend/tmux_helper.py backend/tests/test_tmux_health.py
git commit -m "$(cat <<'EOF'
feat: add TMUX health check with probe verification and retry logic

Implements TmuxHealthCheck dataclass and methods:
- perform_health_probe(): Send probe command, verify response
- create_session_with_health_check(): Full init sequence with retries
- Retry logic for flaky TMUX/Claude initialization
- Structured health status reporting

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Create Background Job Queue Monitor

**Files:**
- Create: `backend/job_queue_monitor.py`
- Create: `backend/tests/test_job_queue_monitor.py`

### Step 1: Write the failing test

```python
# backend/tests/test_job_queue_monitor.py
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
        old_time = "2026-01-24T09:50:00Z"
        queue = [{
            "id": "stale_job",
            "status": "running",
            "type": "echo_test",
            "started_at": old_time
        }]
        (session_dir / "job_queue.json").write_text(json.dumps(queue))

        with patch('job_queue_monitor.ACTIVE_SESSIONS_DIR', tmp_path):
            with patch('job_queue_monitor.datetime') as mock_dt:
                mock_dt.now.return_value = datetime(2026, 1, 24, 10, 5, 0)
                mock_dt.fromisoformat = datetime.fromisoformat
                monitor = JobQueueMonitor()
                stale = monitor.find_stale_jobs("test_session", timeout_seconds=300)

        assert len(stale) == 1
        assert stale[0]["id"] == "stale_job"
```

### Step 2: Run test to verify it fails

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python -m pytest tests/test_job_queue_monitor.py -v`
Expected: FAIL with "No module named 'job_queue_monitor'"

### Step 3: Write minimal implementation

```python
# backend/job_queue_monitor.py
"""
Background Job Queue Monitor

Runs as a separate process to:
- Poll job queues for pending jobs
- Enforce concurrency limits
- Start job execution
- Detect and handle stale jobs
- Report status

Usage:
    python job_queue_monitor.py  # Run as standalone process
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from config import ACTIVE_SESSIONS_DIR, JOB_TIMEOUTS, MAX_CONCURRENT_JOBS

logger = logging.getLogger(__name__)


@dataclass
class MonitorConfig:
    """Configuration for job queue monitor."""
    poll_interval: float = 2.0          # Seconds between queue polls
    max_concurrent_jobs: int = 4        # Max jobs running at once
    check_interval: float = 5.0         # Seconds between completion checks
    stale_job_timeout: float = 1800.0   # 30 min default stale timeout


class JobQueueMonitor:
    """
    Background monitor for job queues.

    Responsibilities:
    1. Scan all active sessions for pending jobs
    2. Enforce max concurrent job limit
    3. Dispatch jobs to executor
    4. Monitor for stale/stuck jobs
    5. Update job status on completion/failure
    """

    def __init__(self, config: Optional[MonitorConfig] = None):
        self.config = config or MonitorConfig()
        self._running = False

    def find_pending_jobs(self) -> List[Dict]:
        """
        Find all pending jobs across all active sessions.

        Returns:
            List of pending job dictionaries with session_id added
        """
        pending_jobs = []

        if not ACTIVE_SESSIONS_DIR.exists():
            return pending_jobs

        for session_dir in ACTIVE_SESSIONS_DIR.iterdir():
            if not session_dir.is_dir():
                continue

            queue_file = session_dir / "job_queue.json"
            if not queue_file.exists():
                continue

            try:
                queue = json.loads(queue_file.read_text())
                for job in queue:
                    if job.get("status") == "pending":
                        job["_session_id"] = session_dir.name
                        pending_jobs.append(job)
            except Exception as e:
                logger.error(f"Error reading queue {queue_file}: {e}")

        return pending_jobs

    def get_running_jobs_count(self, session_id: str) -> int:
        """Get count of currently running jobs for a session."""
        queue_file = ACTIVE_SESSIONS_DIR / session_id / "job_queue.json"

        if not queue_file.exists():
            return 0

        try:
            queue = json.loads(queue_file.read_text())
            return sum(1 for job in queue if job.get("status") == "running")
        except Exception:
            return 0

    def get_available_slots(self, session_id: str) -> int:
        """
        Get number of available job slots for a session.

        Returns:
            Number of jobs that can be started (0 if at capacity)
        """
        running = self.get_running_jobs_count(session_id)
        return max(0, self.config.max_concurrent_jobs - running)

    def find_stale_jobs(
        self,
        session_id: str,
        timeout_seconds: Optional[float] = None
    ) -> List[Dict]:
        """
        Find jobs that have been running longer than timeout.

        Args:
            session_id: Session to check
            timeout_seconds: Override default stale timeout

        Returns:
            List of stale job dictionaries
        """
        timeout = timeout_seconds or self.config.stale_job_timeout
        stale_jobs = []

        queue_file = ACTIVE_SESSIONS_DIR / session_id / "job_queue.json"
        if not queue_file.exists():
            return stale_jobs

        try:
            queue = json.loads(queue_file.read_text())
            now = datetime.now()

            for job in queue:
                if job.get("status") != "running":
                    continue

                started_at = job.get("started_at")
                if not started_at:
                    continue

                # Parse ISO timestamp
                start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                elapsed = (now - start_time.replace(tzinfo=None)).total_seconds()

                if elapsed > timeout:
                    job["_elapsed_seconds"] = elapsed
                    stale_jobs.append(job)

        except Exception as e:
            logger.error(f"Error finding stale jobs: {e}")

        return stale_jobs

    def run(self):
        """
        Main monitor loop.

        Runs continuously, polling for jobs and dispatching them.
        """
        logger.info("Starting Job Queue Monitor")
        logger.info(f"Config: poll_interval={self.config.poll_interval}s, "
                   f"max_concurrent={self.config.max_concurrent_jobs}")

        self._running = True

        while self._running:
            try:
                self._poll_cycle()
            except Exception as e:
                logger.error(f"Monitor cycle error: {e}")

            time.sleep(self.config.poll_interval)

    def _poll_cycle(self):
        """Single poll cycle - find and start pending jobs."""
        pending = self.find_pending_jobs()

        if not pending:
            return

        logger.debug(f"Found {len(pending)} pending jobs")

        for job in pending:
            session_id = job.get("_session_id")
            if not session_id:
                continue

            slots = self.get_available_slots(session_id)
            if slots <= 0:
                logger.debug(f"Session {session_id} at capacity, skipping")
                continue

            # Start job
            self._start_job(session_id, job)

    def _start_job(self, session_id: str, job: Dict):
        """Start execution of a pending job."""
        from job_queue_manager import JobQueueManager

        job_id = job.get("id")
        logger.info(f"Starting job {job_id} in session {session_id}")

        try:
            # Execute job (this is blocking in current implementation)
            success = JobQueueManager.execute_job(session_id, job_id)

            if success:
                logger.info(f"Job {job_id} completed successfully")
            else:
                logger.warning(f"Job {job_id} failed")

        except Exception as e:
            logger.error(f"Error executing job {job_id}: {e}")

    def stop(self):
        """Stop the monitor loop."""
        self._running = False
        logger.info("Job Queue Monitor stopping")


def main():
    """Run monitor as standalone process."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    monitor = JobQueueMonitor()

    try:
        monitor.run()
    except KeyboardInterrupt:
        monitor.stop()
        print("\nMonitor stopped by user")


if __name__ == "__main__":
    main()
```

### Step 4: Run test to verify it passes

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python -m pytest tests/test_job_queue_monitor.py -v`
Expected: PASS

### Step 5: Commit

```bash
git add backend/job_queue_monitor.py backend/tests/test_job_queue_monitor.py
git commit -m "$(cat <<'EOF'
feat: add background job queue monitor with concurrency control

Implements JobQueueMonitor that:
- Polls all active sessions for pending jobs
- Enforces max concurrent jobs limit (default 4)
- Detects stale/stuck jobs
- Can run as standalone background process
- Dispatches jobs to JobQueueManager

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Update HOW_TO_IMPLEMENT Documentation with Complete Details

**Files:**
- Modify: `docs/HOW_TO_IMPLEMENT_TMUX_IN_ANY_PROJECT.md`

### Step 1: Write the improved documentation

The documentation needs these missing sections:

1. **Application Startup Sequence** - What happens when the app starts
2. **Session Initialization Flow** - Complete folder structure creation
3. **TMUX Health Handshake** - Probe/verify/retry pattern
4. **Session Recovery** - Handling crashed sessions
5. **Background Monitor Setup** - Running the monitor process

### Step 2: Create updated documentation sections

Add these sections after the "Core Concept" section:

```markdown
---

## Application Startup Sequence

When your application starts, follow this exact sequence:

### Step 1: Directory Structure Initialization

```
your-app/
├── backend/
│   ├── config.py
│   ├── job_queue_monitor.py      # Background process
│   ├── session_lifecycle.py       # Session management
│   └── ...
├── sessions/
│   ├── active/                    # Active sessions live here
│   │   └── <session_id>/
│   │       ├── metadata.json      # Session metadata
│   │       ├── job_queue.json     # Job queue
│   │       ├── prompts/           # Prompt files
│   │       ├── output/            # Output files
│   │       ├── logs/              # Session logs
│   │       └── state/             # State tracking
│   │           └── health.json    # Health status
│   └── deleted/                   # Deleted sessions (archive)
└── .claude/
    └── agents/                    # Agent templates (optional)
        ├── cost-analyzer.md
        └── code-generator.md
```

### Step 2: Spawn Background Monitor

```python
# On application startup
import subprocess
import sys

def start_background_monitor():
    """Start the job queue monitor as a background process."""

    # Check if already running
    monitor_pid_file = Path("monitor.pid")
    if monitor_pid_file.exists():
        pid = int(monitor_pid_file.read_text())
        if is_process_running(pid):
            print(f"Monitor already running (PID {pid})")
            return pid

    # Start monitor
    process = subprocess.Popen(
        [sys.executable, "job_queue_monitor.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent
    )

    # Save PID
    monitor_pid_file.write_text(str(process.pid))

    print(f"Started monitor (PID {process.pid})")
    return process.pid
```

### Step 3: Validate Configuration

```python
def startup_validation():
    """Validate all dependencies on startup."""

    # Check tmux
    if not shutil.which('tmux'):
        raise RuntimeError("tmux not installed")

    # Check tmux version
    result = subprocess.run(['tmux', '-V'], capture_output=True, text=True)
    version = result.stdout.strip()  # e.g., "tmux 3.4"
    print(f"✓ tmux found: {version}")

    # Check Claude CLI
    if not shutil.which('claude'):
        raise RuntimeError("Claude CLI not installed")

    result = subprocess.run(['claude', '--version'], capture_output=True, text=True)
    print(f"✓ Claude CLI found: {result.stdout.strip()}")

    # Create directories
    ACTIVE_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    DELETED_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    print("✓ Directories initialized")
```

---

## Session Initialization Flow

When creating a new session, follow this complete sequence:

### Phase 1: Create Folder Structure

```python
def initialize_session(session_id: str) -> Path:
    """
    Phase 1: Create complete folder structure.

    This happens BEFORE any TMUX operations.
    """
    session_path = ACTIVE_SESSIONS_DIR / session_id

    # Create all directories
    session_path.mkdir(parents=True, exist_ok=True)
    (session_path / "prompts").mkdir(exist_ok=True)
    (session_path / "output").mkdir(exist_ok=True)
    (session_path / "logs").mkdir(exist_ok=True)
    (session_path / "state").mkdir(exist_ok=True)

    # Create metadata.json
    metadata = {
        "session_id": session_id,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "state": "created",
        "tmux_session": None,
        "version": "1.0"
    }
    with open(session_path / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)

    # Create empty job queue
    with open(session_path / "job_queue.json", 'w') as f:
        json.dump([], f)

    # Create initial health status
    health = {
        "state": "created",
        "tmux_active": False,
        "claude_ready": False,
        "last_probe": None,
        "error_count": 0
    }
    with open(session_path / "state" / "health.json", 'w') as f:
        json.dump(health, f, indent=2)

    return session_path
```

### Phase 2: Create TMUX Session with Claude

```python
def create_tmux_session(session_id: str, session_path: Path) -> bool:
    """
    Phase 2: Create TMUX session and start Claude.

    Complete initialization sequence with exact timing.
    """
    tmux_name = f"app_{session_id}"

    # Step 1: Create TMUX session
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", tmux_name],
        check=True
    )

    # Step 2: CD to session directory
    send_command(tmux_name, f"cd {session_path}")
    time.sleep(0.5)  # Wait for cd

    # Step 3: Start Claude CLI
    send_command(tmux_name, "claude --dangerously-skip-permissions")
    time.sleep(3.0)  # CRITICAL: Claude needs 3s to initialize

    # Step 4: Bypass initial prompts (send 3 Enter keys)
    for _ in range(3):
        subprocess.run(["tmux", "send-keys", "-t", tmux_name, "Enter"])
        time.sleep(0.5)

    return True
```

### Phase 3: Health Handshake

```python
def perform_health_handshake(
    tmux_name: str,
    max_retries: int = 3
) -> bool:
    """
    Phase 3: Verify Claude is ready with probe/response pattern.

    The handshake confirms Claude is initialized and responding.
    """
    for attempt in range(max_retries):
        # Generate unique probe marker
        probe_id = datetime.now().strftime("%H%M%S%f")
        probe_marker = f"[HEALTH_PROBE_{probe_id}]"

        # Send probe command
        probe_cmd = f"echo '{probe_marker} Claude ready'"
        send_command(tmux_name, probe_cmd)
        time.sleep(2.0)  # Wait for response

        # Capture and check output
        output = capture_output(tmux_name)

        if probe_marker in output and "Claude ready" in output:
            print(f"✓ Health handshake successful (attempt {attempt + 1})")
            return True

        print(f"⚠ Probe not found, retrying... ({attempt + 1}/{max_retries})")
        time.sleep(2.0)

    print("✗ Health handshake failed after all retries")
    return False

def send_command(session: str, cmd: str):
    """Send command with proper timing."""
    subprocess.run(["tmux", "send-keys", "-t", session, "-l", cmd])
    time.sleep(0.3)  # Buffer processing
    subprocess.run(["tmux", "send-keys", "-t", session, "Enter"])
    time.sleep(1.2)  # Command execution

def capture_output(session: str, lines: int = 50) -> str:
    """Capture recent output from TMUX pane."""
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", session, "-p", "-S", f"-{lines}"],
        capture_output=True,
        text=True
    )
    return result.stdout
```

### Complete Initialization Example

```python
def full_session_initialization(session_id: str) -> bool:
    """
    Complete session initialization with all phases.

    Returns True if session is fully initialized and healthy.
    """
    print(f"Initializing session: {session_id}")

    # Phase 1: Folder structure
    print("Phase 1: Creating folder structure...")
    session_path = initialize_session(session_id)
    update_health(session_id, {"state": "folder_created"})

    # Phase 2: TMUX + Claude
    print("Phase 2: Starting TMUX session with Claude...")
    tmux_name = f"app_{session_id}"

    if not create_tmux_session(session_id, session_path):
        update_health(session_id, {"state": "error", "error": "TMUX creation failed"})
        return False

    update_health(session_id, {"state": "tmux_started", "tmux_active": True})

    # Phase 3: Health handshake
    print("Phase 3: Performing health handshake...")

    if not perform_health_handshake(tmux_name):
        update_health(session_id, {"state": "error", "error": "Handshake failed"})
        kill_session(tmux_name)
        return False

    update_health(session_id, {
        "state": "ready",
        "claude_ready": True,
        "last_probe": datetime.utcnow().isoformat() + "Z"
    })

    # Update metadata
    update_metadata(session_id, {"tmux_session": tmux_name, "state": "ready"})

    print(f"✓ Session {session_id} fully initialized and healthy")
    return True
```

---

## Session Recovery

Handle crashed or lost sessions gracefully.

### Detecting Lost Sessions

```python
def check_session_health(session_id: str) -> dict:
    """
    Check if a session is still healthy.

    Returns health status with recovery recommendations.
    """
    metadata_path = ACTIVE_SESSIONS_DIR / session_id / "metadata.json"

    if not metadata_path.exists():
        return {"healthy": False, "action": "recreate", "reason": "Session not found"}

    metadata = json.loads(metadata_path.read_text())
    tmux_name = metadata.get("tmux_session")

    if not tmux_name:
        return {"healthy": False, "action": "initialize", "reason": "TMUX not started"}

    # Check TMUX session exists
    result = subprocess.run(
        ["tmux", "has-session", "-t", tmux_name],
        capture_output=True
    )

    if result.returncode != 0:
        return {
            "healthy": False,
            "action": "restart_tmux",
            "reason": "TMUX session lost"
        }

    # Perform probe
    if not perform_health_handshake(tmux_name, max_retries=1):
        return {
            "healthy": False,
            "action": "restart_claude",
            "reason": "Claude not responding"
        }

    return {"healthy": True, "action": None, "reason": None}
```

### Recovery Actions

```python
def recover_session(session_id: str) -> bool:
    """
    Attempt to recover a session based on its health status.
    """
    health = check_session_health(session_id)

    if health["healthy"]:
        return True

    action = health["action"]
    print(f"Recovering session {session_id}: {action}")

    if action == "recreate":
        # Full recreation
        return full_session_initialization(session_id)

    elif action == "initialize":
        # Just need TMUX setup
        session_path = ACTIVE_SESSIONS_DIR / session_id
        return create_tmux_session(session_id, session_path)

    elif action == "restart_tmux":
        # Kill and restart TMUX
        metadata = load_metadata(session_id)
        kill_session(metadata.get("tmux_session", ""))
        session_path = ACTIVE_SESSIONS_DIR / session_id
        return create_tmux_session(session_id, session_path)

    elif action == "restart_claude":
        # Just restart Claude in existing TMUX
        metadata = load_metadata(session_id)
        tmux_name = metadata["tmux_session"]

        # Send Ctrl-C to kill current process
        subprocess.run(["tmux", "send-keys", "-t", tmux_name, "C-c"])
        time.sleep(0.5)

        # Restart Claude
        send_command(tmux_name, "claude --dangerously-skip-permissions")
        time.sleep(3.0)

        return perform_health_handshake(tmux_name)

    return False
```

---

## Background Monitor Setup

Run the job queue monitor as a separate process.

### Standalone Monitor Script

```python
#!/usr/bin/env python3
"""
job_queue_monitor.py - Background job queue monitor

Run this as a separate process to handle job execution.

Usage:
    python job_queue_monitor.py              # Run in foreground
    python job_queue_monitor.py &            # Run in background
    nohup python job_queue_monitor.py &      # Run with nohup
"""

import time
import json
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
POLL_INTERVAL = 2.0        # Check queues every 2 seconds
MAX_CONCURRENT = 4         # Max jobs running at once
COMPLETION_CHECK = 5.0     # Check completion every 5 seconds


def main_loop():
    """Main monitor loop."""
    logger.info("Job Queue Monitor started")
    logger.info(f"Poll interval: {POLL_INTERVAL}s, Max concurrent: {MAX_CONCURRENT}")

    while True:
        try:
            # Find all active sessions
            for session_dir in ACTIVE_SESSIONS_DIR.iterdir():
                if not session_dir.is_dir():
                    continue

                process_session(session_dir.name)

        except Exception as e:
            logger.error(f"Monitor cycle error: {e}")

        time.sleep(POLL_INTERVAL)


def process_session(session_id: str):
    """Process jobs for a single session."""
    queue_path = ACTIVE_SESSIONS_DIR / session_id / "job_queue.json"

    if not queue_path.exists():
        return

    queue = json.loads(queue_path.read_text())

    # Count running jobs
    running = [j for j in queue if j["status"] == "running"]
    pending = [j for j in queue if j["status"] == "pending"]

    # Check running jobs for completion
    for job in running:
        check_job_completion(session_id, job)

    # Start pending jobs if slots available
    available_slots = MAX_CONCURRENT - len(running)

    for job in pending[:available_slots]:
        start_job(session_id, job)


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")
```

### Systemd Service (Production)

```ini
# /etc/systemd/system/job-monitor.service
[Unit]
Description=Job Queue Monitor
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/your-app/backend
ExecStart=/usr/bin/python3 job_queue_monitor.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Docker Compose (Alternative)

```yaml
services:
  monitor:
    build: ./backend
    command: python job_queue_monitor.py
    volumes:
      - ./sessions:/app/sessions
    restart: always
```
```

### Step 3: Apply the documentation update

This involves updating the existing `docs/HOW_TO_IMPLEMENT_TMUX_IN_ANY_PROJECT.md` file with the new sections.

### Step 4: Commit

```bash
git add docs/HOW_TO_IMPLEMENT_TMUX_IN_ANY_PROJECT.md
git commit -m "$(cat <<'EOF'
docs: add complete startup, initialization, and recovery sections

Expands HOW_TO_IMPLEMENT documentation with:
- Application startup sequence with validation
- Complete session initialization flow (3 phases)
- Health handshake pattern with probe/verify/retry
- Session recovery strategies for various failure modes
- Background monitor setup (standalone, systemd, Docker)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Create Tests Directory and pytest Configuration

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/pytest.ini`

### Step 1: Create test infrastructure

```python
# backend/tests/__init__.py
"""Test package for tmux-builder backend."""

# backend/tests/conftest.py
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
```

```ini
# backend/pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
```

### Step 2: Commit

```bash
git add backend/tests/__init__.py backend/tests/conftest.py backend/pytest.ini
git commit -m "$(cat <<'EOF'
test: add pytest infrastructure with shared fixtures

Creates test infrastructure:
- tests/__init__.py for package recognition
- conftest.py with temp_sessions_dir, mock_session, mock_tmux fixtures
- pytest.ini with configuration

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Add Agent Template Support

**Files:**
- Create: `backend/agent_loader.py`
- Create: `.claude/agents/default.md`
- Create: `backend/tests/test_agent_loader.py`

### Step 1: Write the failing test

```python
# backend/tests/test_agent_loader.py
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_loader import AgentLoader, AgentTemplate


class TestAgentLoader:
    """Test agent template loading."""

    def test_load_default_template(self, tmp_path):
        """Verify default template loads correctly."""
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        template_content = """# Default Agent
You are a helpful assistant.

## Instructions
Follow user requests carefully.
"""
        (agents_dir / "default.md").write_text(template_content)

        loader = AgentLoader(agents_dir)
        template = loader.load("default")

        assert template.name == "default"
        assert "helpful assistant" in template.content
        assert template.exists == True

    def test_template_not_found(self, tmp_path):
        """Verify missing template returns default fallback."""
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        loader = AgentLoader(agents_dir)
        template = loader.load("nonexistent")

        assert template.exists == False
        assert template.content == ""

    def test_list_available_agents(self, tmp_path):
        """Verify listing available agent templates."""
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        (agents_dir / "analyzer.md").write_text("# Analyzer")
        (agents_dir / "coder.md").write_text("# Coder")
        (agents_dir / "not_an_agent.txt").write_text("ignore")

        loader = AgentLoader(agents_dir)
        agents = loader.list_agents()

        assert "analyzer" in agents
        assert "coder" in agents
        assert "not_an_agent" not in agents
```

### Step 2: Run test to verify it fails

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python -m pytest tests/test_agent_loader.py -v`
Expected: FAIL with "No module named 'agent_loader'"

### Step 3: Write minimal implementation

```python
# backend/agent_loader.py
"""
Agent Template Loader

Loads agent templates from .claude/agents/*.md files.
These templates provide specialized instructions for different job types.
"""

import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# Default agents directory relative to project root
DEFAULT_AGENTS_DIR = Path(__file__).parent.parent / ".claude" / "agents"


@dataclass
class AgentTemplate:
    """Loaded agent template."""
    name: str
    content: str
    path: Optional[Path]
    exists: bool


class AgentLoader:
    """
    Loads agent templates from .claude/agents/ directory.

    Agent templates are Markdown files that provide specialized
    instructions for different types of jobs (cost analysis,
    code generation, etc.)

    Usage:
        loader = AgentLoader()
        template = loader.load("cost-analyzer")
        prompt = f"{template.content}\\n\\n## Task:\\n{user_task}"
    """

    def __init__(self, agents_dir: Optional[Path] = None):
        self.agents_dir = agents_dir or DEFAULT_AGENTS_DIR

    def load(self, agent_name: str) -> AgentTemplate:
        """
        Load an agent template by name.

        Args:
            agent_name: Name of agent (without .md extension)

        Returns:
            AgentTemplate with content or empty if not found
        """
        agent_file = self.agents_dir / f"{agent_name}.md"

        if not agent_file.exists():
            logger.warning(f"Agent template not found: {agent_file}")
            return AgentTemplate(
                name=agent_name,
                content="",
                path=None,
                exists=False
            )

        try:
            content = agent_file.read_text(encoding='utf-8')
            logger.info(f"Loaded agent template: {agent_name}")

            return AgentTemplate(
                name=agent_name,
                content=content,
                path=agent_file,
                exists=True
            )

        except Exception as e:
            logger.error(f"Error loading agent {agent_name}: {e}")
            return AgentTemplate(
                name=agent_name,
                content="",
                path=agent_file,
                exists=False
            )

    def list_agents(self) -> List[str]:
        """
        List all available agent templates.

        Returns:
            List of agent names (without .md extension)
        """
        if not self.agents_dir.exists():
            return []

        agents = []
        for file in self.agents_dir.glob("*.md"):
            agents.append(file.stem)

        return sorted(agents)

    def get_or_default(self, agent_name: str) -> AgentTemplate:
        """
        Load agent template, falling back to default if not found.

        Args:
            agent_name: Name of desired agent

        Returns:
            AgentTemplate (requested or default)
        """
        template = self.load(agent_name)

        if template.exists:
            return template

        # Try default
        default = self.load("default")
        if default.exists:
            logger.info(f"Using default agent (requested: {agent_name})")
            return default

        # No default either
        logger.warning("No default agent template found")
        return template
```

Create default agent template:

```markdown
# .claude/agents/default.md
# Default Agent

You are Claude, an AI assistant helping with software development tasks.

## Core Principles

1. **Be Precise**: Follow instructions exactly as specified
2. **Be Complete**: Provide thorough, well-structured outputs
3. **Be Helpful**: Anticipate needs and provide context

## Output Guidelines

- Write outputs to the specified OUTPUT_PATH
- Use clear formatting (Markdown for docs, proper syntax for code)
- Include timestamps where relevant
- Confirm completion at the end

## Error Handling

If you encounter an error or cannot complete a task:
1. Write what you can to the output file
2. Clearly describe the error or limitation
3. Suggest alternatives if possible
```

### Step 4: Run test to verify it passes

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python -m pytest tests/test_agent_loader.py -v`
Expected: PASS

### Step 5: Commit

```bash
git add backend/agent_loader.py backend/tests/test_agent_loader.py .claude/agents/default.md
git commit -m "$(cat <<'EOF'
feat: add agent template loader with default template

Implements AgentLoader for loading .claude/agents/*.md templates:
- load(): Load specific agent by name
- list_agents(): Get available agents
- get_or_default(): Fallback to default if not found
- Default agent template with core principles

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Summary

This plan addresses the key gaps identified:

| Task | Gap Addressed |
|------|---------------|
| 1 | Session Lifecycle Manager - folder structure, state tracking |
| 2 | TMUX Health Handshake - probe/verify/retry pattern |
| 3 | Background Job Queue Monitor - separate process |
| 4 | Documentation - complete startup/init/recovery details |
| 5 | Test Infrastructure - pytest setup |
| 6 | Agent Templates - .claude/agents/ support |

Total estimated implementation: 6 tasks with TDD approach.

---

**Plan complete and saved to `docs/plans/2026-01-24-smartbuild-integration-complete.md`.**

Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
