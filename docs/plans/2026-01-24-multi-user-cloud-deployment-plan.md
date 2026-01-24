# Multi-User Cloud Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform tmux-builder into multi-user architecture with AWS/Azure cloud deployment, using sunwaretech profiles.

**Architecture:** Async pipeline creates user GUID folders, deploys to cloud (S3+CF or EC2 for AWS, Blob+CDN or VM for Azure), runs UI tests, and enables iterative chat-modify-deploy workflow. Claude in tmux session uses injected agents/skills to autonomously deploy and test.

**Tech Stack:** Python 3.8+, boto3 (AWS), azure-storage-blob/azure-mgmt-cdn (Azure), Playwright, Flask

---

## Phase 1: Core Infrastructure

### Task 1.1: User Manager Module

**Files:**
- Create: `backend/user_manager.py`
- Create: `backend/tests/test_user_manager.py`
- Create: `users/.gitkeep`

**Step 1: Write the failing test**

```python
# backend/tests/test_user_manager.py
import pytest
import json
from pathlib import Path


class TestUserManager:
    """Tests for user management functionality."""

    def test_generate_guid_is_unique(self, tmp_path):
        """GUID generation produces unique values."""
        from user_manager import UserManager

        manager = UserManager(users_dir=tmp_path)
        guid1 = manager.generate_guid("test@example.com", "1234567890")
        guid2 = manager.generate_guid("test2@example.com", "0987654321")

        assert guid1 != guid2
        assert len(guid1) == 36  # UUID format

    def test_create_user_creates_folder_structure(self, tmp_path):
        """Creating user creates GUID folder with user.json."""
        from user_manager import UserManager

        manager = UserManager(users_dir=tmp_path)
        result = manager.create_user(
            email="test@example.com",
            phone="1234567890",
            host_provider="aws",
            site_type="static"
        )

        assert result["user_id"] is not None
        user_dir = tmp_path / result["user_id"]
        assert user_dir.exists()
        assert (user_dir / "user.json").exists()
        assert (user_dir / "sessions").exists()

    def test_registry_updated_on_create(self, tmp_path):
        """Registry.json updated with email+phone -> GUID mapping."""
        from user_manager import UserManager

        manager = UserManager(users_dir=tmp_path)
        result = manager.create_user(
            email="test@example.com",
            phone="1234567890",
            host_provider="aws",
            site_type="static"
        )

        registry_path = tmp_path / "registry.json"
        assert registry_path.exists()

        registry = json.loads(registry_path.read_text())
        key = "test@example.com|1234567890"
        assert key in registry
        assert registry[key] == result["user_id"]

    def test_existing_user_returns_same_guid(self, tmp_path):
        """Same email+phone returns existing GUID."""
        from user_manager import UserManager

        manager = UserManager(users_dir=tmp_path)
        result1 = manager.create_user("test@example.com", "1234567890", "aws", "static")
        result2 = manager.create_user("test@example.com", "1234567890", "azure", "dynamic")

        assert result1["user_id"] == result2["user_id"]
        assert result1["is_new"] == True
        assert result2["is_new"] == False
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_user_manager.py -v -p no:anyio`
Expected: FAIL with "No module named 'user_manager'"

**Step 3: Write minimal implementation**

```python
# backend/user_manager.py
"""
User management module for multi-user tmux-builder.

Handles:
- GUID generation for users (email+phone -> UUID)
- User folder creation
- Registry management (mapping email+phone to GUID)
"""

import uuid
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class UserInfo:
    """User information stored in user.json."""
    user_id: str
    email: str
    phone: str
    created_at: str
    host_provider: str
    site_type: str


class UserManager:
    """Manages user creation and registry."""

    def __init__(self, users_dir: Optional[Path] = None):
        """
        Initialize UserManager.

        Args:
            users_dir: Directory for user folders. Defaults to project/users/
        """
        if users_dir is None:
            users_dir = Path(__file__).parent.parent / "users"
        self.users_dir = Path(users_dir)
        self.users_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.users_dir / "registry.json"

    def generate_guid(self, email: str, phone: str) -> str:
        """
        Generate a deterministic GUID from email+phone.

        Uses UUID5 with a namespace for deterministic generation,
        so same email+phone always produces same GUID.
        """
        namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # URL namespace
        combined = f"{email.lower()}|{phone}"
        return str(uuid.uuid5(namespace, combined))

    def _load_registry(self) -> Dict[str, str]:
        """Load registry.json or return empty dict."""
        if self.registry_path.exists():
            return json.loads(self.registry_path.read_text())
        return {}

    def _save_registry(self, registry: Dict[str, str]) -> None:
        """Save registry.json."""
        self.registry_path.write_text(json.dumps(registry, indent=2))

    def get_user_by_email_phone(self, email: str, phone: str) -> Optional[str]:
        """Look up existing user GUID by email+phone."""
        registry = self._load_registry()
        key = f"{email.lower()}|{phone}"
        return registry.get(key)

    def create_user(
        self,
        email: str,
        phone: str,
        host_provider: str,
        site_type: str
    ) -> Dict:
        """
        Create a new user or return existing user.

        Args:
            email: User email
            phone: User phone
            host_provider: "aws" or "azure"
            site_type: "static" or "dynamic"

        Returns:
            Dict with user_id, is_new, session_id
        """
        # Check if user exists
        existing_guid = self.get_user_by_email_phone(email, phone)
        if existing_guid:
            logger.info(f"Existing user found: {existing_guid}")
            return {
                "user_id": existing_guid,
                "is_new": False
            }

        # Generate new GUID
        user_id = self.generate_guid(email, phone)
        logger.info(f"Creating new user: {user_id}")

        # Create folder structure
        user_dir = self.users_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "sessions").mkdir(exist_ok=True)

        # Create user.json
        user_info = UserInfo(
            user_id=user_id,
            email=email,
            phone=phone,
            created_at=datetime.utcnow().isoformat() + "Z",
            host_provider=host_provider,
            site_type=site_type
        )
        (user_dir / "user.json").write_text(
            json.dumps(asdict(user_info), indent=2)
        )

        # Update registry
        registry = self._load_registry()
        key = f"{email.lower()}|{phone}"
        registry[key] = user_id
        self._save_registry(registry)

        logger.info(f"User created successfully: {user_id}")
        return {
            "user_id": user_id,
            "is_new": True
        }

    def get_user_info(self, user_id: str) -> Optional[Dict]:
        """Get user info by GUID."""
        user_json = self.users_dir / user_id / "user.json"
        if user_json.exists():
            return json.loads(user_json.read_text())
        return None

    def list_users(self) -> list:
        """List all user GUIDs."""
        return [
            d.name for d in self.users_dir.iterdir()
            if d.is_dir() and (d / "user.json").exists()
        ]
```

**Step 4: Run test to verify it passes**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_user_manager.py -v -p no:anyio`
Expected: PASS (4 tests)

**Step 5: Create users directory**

```bash
mkdir -p /mnt/c/Development/AI-Product-Site/tmux-builder/users
touch /mnt/c/Development/AI-Product-Site/tmux-builder/users/.gitkeep
```

**Step 6: Commit**

```bash
git add backend/user_manager.py backend/tests/test_user_manager.py users/.gitkeep
git commit -m "feat: add user manager module with GUID generation and registry"
```

---

### Task 1.2: Execution Tracker Module

**Files:**
- Create: `backend/execution_tracker.py`
- Create: `backend/tests/test_execution_tracker.py`
- Create: `executions/.gitkeep`

**Step 1: Write the failing test**

```python
# backend/tests/test_execution_tracker.py
import pytest
import json
from pathlib import Path
from datetime import datetime


class TestExecutionTracker:
    """Tests for execution tracking and deep logging."""

    def test_create_execution_returns_id(self, tmp_path):
        """Creating execution returns execution_id in correct format."""
        from execution_tracker import ExecutionTracker

        tracker = ExecutionTracker(executions_dir=tmp_path)
        exec_id = tracker.create_execution(
            user_id="a1b2c3d4-e5f6-7890-abcd-1234567890ab",
            session_id="sess_20260124_143022"
        )

        assert exec_id == "a1b2c3d4-e5f6-7890-abcd-1234567890ab_sess_20260124_143022"

    def test_execution_file_created(self, tmp_path):
        """Execution creates JSON file with initial state."""
        from execution_tracker import ExecutionTracker

        tracker = ExecutionTracker(executions_dir=tmp_path)
        exec_id = tracker.create_execution(
            user_id="a1b2c3d4",
            session_id="sess_001"
        )

        exec_file = tmp_path / f"{exec_id}.json"
        assert exec_file.exists()

        data = json.loads(exec_file.read_text())
        assert data["status"] == "pending"
        assert data["current_step"] == 0
        assert data["total_steps"] == 7
        assert data["logs"] == []

    def test_log_entry_adds_to_logs(self, tmp_path):
        """Adding log entry appends to logs array."""
        from execution_tracker import ExecutionTracker

        tracker = ExecutionTracker(executions_dir=tmp_path)
        exec_id = tracker.create_execution("user1", "sess1")

        tracker.log(exec_id, "INFO", "Starting deployment", step=1, step_name="create_user")

        data = tracker.get_status(exec_id)
        assert len(data["logs"]) == 1
        assert data["logs"][0]["level"] == "INFO"
        assert data["logs"][0]["message"] == "Starting deployment"
        assert data["logs"][0]["step"] == 1

    def test_update_status_changes_state(self, tmp_path):
        """Updating status changes execution state."""
        from execution_tracker import ExecutionTracker

        tracker = ExecutionTracker(executions_dir=tmp_path)
        exec_id = tracker.create_execution("user1", "sess1")

        tracker.update_status(exec_id, status="running", current_step=3)

        data = tracker.get_status(exec_id)
        assert data["status"] == "running"
        assert data["current_step"] == 3

    def test_set_result_stores_final_data(self, tmp_path):
        """Setting result stores deployment URL and session info."""
        from execution_tracker import ExecutionTracker

        tracker = ExecutionTracker(executions_dir=tmp_path)
        exec_id = tracker.create_execution("user1", "sess1")

        tracker.set_result(exec_id, {
            "user_id": "user1",
            "session_id": "sess1",
            "deployed_url": "https://d1234.cloudfront.net"
        })

        data = tracker.get_status(exec_id)
        assert data["result"]["deployed_url"] == "https://d1234.cloudfront.net"
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_execution_tracker.py -v -p no:anyio`
Expected: FAIL with "No module named 'execution_tracker'"

**Step 3: Write minimal implementation**

```python
# backend/execution_tracker.py
"""
Execution tracking module with deep logging.

Tracks async pipeline execution status and provides detailed logs
for debugging and user status polling.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)

# Pipeline steps
PIPELINE_STEPS = [
    {"id": 1, "name": "create_user", "description": "Create GUID folder & registry entry"},
    {"id": 2, "name": "create_session", "description": "Initialize session folder structure"},
    {"id": 3, "name": "generate_site", "description": "Claude generates initial website code"},
    {"id": 4, "name": "deploy", "description": "Deploy to AWS/Azure"},
    {"id": 5, "name": "health_check", "description": "Verify URL returns 200 OK"},
    {"id": 6, "name": "screenshot", "description": "Capture visual snapshot"},
    {"id": 7, "name": "e2e_tests", "description": "Generate & run E2E tests"},
]


@dataclass
class LogEntry:
    """Single log entry."""
    timestamp: str
    level: str
    message: str
    step: Optional[int] = None
    step_name: Optional[str] = None
    details: Optional[Dict] = None
    trace_id: Optional[str] = None


@dataclass
class ExecutionState:
    """Execution state stored in JSON file."""
    execution_id: str
    user_id: str
    session_id: str
    status: str = "pending"  # pending, running, completed, failed
    current_step: int = 0
    total_steps: int = 7
    created_at: str = ""
    updated_at: str = ""
    logs: list = field(default_factory=list)
    result: Optional[Dict] = None
    error: Optional[str] = None


class ExecutionTracker:
    """Tracks execution status and provides deep logging."""

    def __init__(self, executions_dir: Optional[Path] = None):
        """
        Initialize ExecutionTracker.

        Args:
            executions_dir: Directory for execution JSON files.
        """
        if executions_dir is None:
            executions_dir = Path(__file__).parent.parent / "executions"
        self.executions_dir = Path(executions_dir)
        self.executions_dir.mkdir(parents=True, exist_ok=True)

    def _get_exec_path(self, execution_id: str) -> Path:
        """Get path to execution JSON file."""
        return self.executions_dir / f"{execution_id}.json"

    def _load_execution(self, execution_id: str) -> Optional[Dict]:
        """Load execution state from file."""
        path = self._get_exec_path(execution_id)
        if path.exists():
            return json.loads(path.read_text())
        return None

    def _save_execution(self, state: Dict) -> None:
        """Save execution state to file."""
        state["updated_at"] = datetime.utcnow().isoformat() + "Z"
        path = self._get_exec_path(state["execution_id"])
        path.write_text(json.dumps(state, indent=2, default=str))

    def create_execution(self, user_id: str, session_id: str) -> str:
        """
        Create a new execution tracking entry.

        Args:
            user_id: User GUID
            session_id: Session ID

        Returns:
            execution_id in format {user_id}_{session_id}
        """
        execution_id = f"{user_id}_{session_id}"
        now = datetime.utcnow().isoformat() + "Z"

        state = ExecutionState(
            execution_id=execution_id,
            user_id=user_id,
            session_id=session_id,
            created_at=now,
            updated_at=now
        )

        self._save_execution(asdict(state))
        logger.info(f"Created execution: {execution_id}")
        return execution_id

    def get_status(self, execution_id: str) -> Optional[Dict]:
        """
        Get current execution status.

        Returns full state including status, progress, logs, and result.
        """
        return self._load_execution(execution_id)

    def update_status(
        self,
        execution_id: str,
        status: Optional[str] = None,
        current_step: Optional[int] = None
    ) -> None:
        """Update execution status and/or current step."""
        state = self._load_execution(execution_id)
        if state is None:
            raise ValueError(f"Execution not found: {execution_id}")

        if status is not None:
            state["status"] = status
        if current_step is not None:
            state["current_step"] = current_step

        self._save_execution(state)

    def log(
        self,
        execution_id: str,
        level: str,
        message: str,
        step: Optional[int] = None,
        step_name: Optional[str] = None,
        details: Optional[Dict] = None,
        trace_id: Optional[str] = None
    ) -> None:
        """
        Add a log entry to execution.

        Args:
            execution_id: Execution ID
            level: INFO, WARN, ERROR, DEBUG
            message: Log message
            step: Step number (1-7)
            step_name: Step name
            details: Additional details dict
            trace_id: Optional trace ID for distributed tracing
        """
        state = self._load_execution(execution_id)
        if state is None:
            raise ValueError(f"Execution not found: {execution_id}")

        entry = LogEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level=level,
            message=message,
            step=step,
            step_name=step_name,
            details=details,
            trace_id=trace_id
        )

        state["logs"].append(asdict(entry))
        self._save_execution(state)

        # Also log to Python logger
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"[{execution_id}] Step {step}: {message}")

    def set_result(self, execution_id: str, result: Dict) -> None:
        """Set final result when execution completes."""
        state = self._load_execution(execution_id)
        if state is None:
            raise ValueError(f"Execution not found: {execution_id}")

        state["result"] = result
        state["status"] = "completed"
        self._save_execution(state)

    def set_error(self, execution_id: str, error: str) -> None:
        """Set error when execution fails."""
        state = self._load_execution(execution_id)
        if state is None:
            raise ValueError(f"Execution not found: {execution_id}")

        state["error"] = error
        state["status"] = "failed"
        self._save_execution(state)

    def get_step_info(self, step_number: int) -> Optional[Dict]:
        """Get info about a pipeline step."""
        for step in PIPELINE_STEPS:
            if step["id"] == step_number:
                return step
        return None
```

**Step 4: Run test to verify it passes**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_execution_tracker.py -v -p no:anyio`
Expected: PASS (5 tests)

**Step 5: Create executions directory**

```bash
mkdir -p /mnt/c/Development/AI-Product-Site/tmux-builder/executions
touch /mnt/c/Development/AI-Product-Site/tmux-builder/executions/.gitkeep
```

**Step 6: Commit**

```bash
git add backend/execution_tracker.py backend/tests/test_execution_tracker.py executions/.gitkeep
git commit -m "feat: add execution tracker with deep logging support"
```

---

### Task 1.3: Session Creator Module

**Files:**
- Create: `backend/session_creator.py`
- Create: `backend/tests/test_session_creator.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_session_creator.py
import pytest
import json
from pathlib import Path
from datetime import datetime


class TestSessionCreator:
    """Tests for session creation within user folders."""

    def test_create_session_generates_id(self, tmp_path):
        """Session creation generates timestamped ID."""
        from session_creator import SessionCreator

        creator = SessionCreator(users_dir=tmp_path)
        user_dir = tmp_path / "test-user-guid"
        user_dir.mkdir()
        (user_dir / "sessions").mkdir()

        session_id = creator.create_session(
            user_id="test-user-guid",
            host_provider="aws",
            site_type="static"
        )

        assert session_id.startswith("sess_")
        assert len(session_id) > 10

    def test_session_folder_structure_created(self, tmp_path):
        """Session creates required folder structure."""
        from session_creator import SessionCreator

        creator = SessionCreator(users_dir=tmp_path)
        user_dir = tmp_path / "test-user-guid"
        user_dir.mkdir()
        (user_dir / "sessions").mkdir()

        session_id = creator.create_session("test-user-guid", "aws", "static")

        session_dir = user_dir / "sessions" / session_id
        assert session_dir.exists()
        assert (session_dir / ".claude").exists()
        assert (session_dir / ".claude" / "agents").exists()
        assert (session_dir / ".claude" / "skills").exists()
        assert (session_dir / "source").exists()
        assert (session_dir / "deployment").exists()
        assert (session_dir / "deployment" / "tests").exists()
        assert (session_dir / "logs").exists()

    def test_session_config_saved(self, tmp_path):
        """Session config.json saved with deployment settings."""
        from session_creator import SessionCreator

        creator = SessionCreator(users_dir=tmp_path)
        user_dir = tmp_path / "test-user-guid"
        user_dir.mkdir()
        (user_dir / "sessions").mkdir()

        session_id = creator.create_session("test-user-guid", "azure", "dynamic")

        config_path = user_dir / "sessions" / session_id / "deployment" / "config.json"
        assert config_path.exists()

        config = json.loads(config_path.read_text())
        assert config["host_provider"] == "azure"
        assert config["site_type"] == "dynamic"
        assert config["aws_profile"] == "sunwaretech"
        assert config["azure_profile"] == "sunwaretech"

    def test_session_claude_md_created(self, tmp_path):
        """Session-specific CLAUDE.md created."""
        from session_creator import SessionCreator

        creator = SessionCreator(users_dir=tmp_path)
        user_dir = tmp_path / "test-user-guid"
        user_dir.mkdir()
        (user_dir / "sessions").mkdir()

        session_id = creator.create_session("test-user-guid", "aws", "static")

        claude_md = user_dir / "sessions" / session_id / ".claude" / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text()
        assert "aws" in content.lower()
        assert "static" in content.lower()
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_session_creator.py -v -p no:anyio`
Expected: FAIL with "No module named 'session_creator'"

**Step 3: Write minimal implementation**

```python
# backend/session_creator.py
"""
Session creator module.

Creates session folders within user GUID folders with proper structure
for SmartBuild pattern and cloud deployment.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# AWS and Azure profile names
AWS_PROFILE = "sunwaretech"
AZURE_PROFILE = "sunwaretech"


class SessionCreator:
    """Creates and initializes session folders."""

    def __init__(self, users_dir: Optional[Path] = None):
        """
        Initialize SessionCreator.

        Args:
            users_dir: Base directory for user folders.
        """
        if users_dir is None:
            users_dir = Path(__file__).parent.parent / "users"
        self.users_dir = Path(users_dir)

    def create_session(
        self,
        user_id: str,
        host_provider: str,
        site_type: str
    ) -> str:
        """
        Create a new session for a user.

        Args:
            user_id: User GUID
            host_provider: "aws" or "azure"
            site_type: "static" or "dynamic"

        Returns:
            session_id
        """
        # Generate session ID
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        session_id = f"sess_{timestamp}"

        # Create session directory
        session_dir = self.users_dir / user_id / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating session: {session_id} for user: {user_id}")

        # Create folder structure
        self._create_folder_structure(session_dir)

        # Create deployment config
        self._create_deployment_config(session_dir, host_provider, site_type)

        # Create session-specific CLAUDE.md
        self._create_claude_md(session_dir, user_id, session_id, host_provider, site_type)

        logger.info(f"Session created successfully: {session_id}")
        return session_id

    def _create_folder_structure(self, session_dir: Path) -> None:
        """Create all required folders for a session."""
        folders = [
            ".claude/agents",
            ".claude/skills",
            "source",
            "deployment/tests",
            "logs",
            "prompts",
            "output",
            "state",
        ]

        for folder in folders:
            (session_dir / folder).mkdir(parents=True, exist_ok=True)

    def _create_deployment_config(
        self,
        session_dir: Path,
        host_provider: str,
        site_type: str
    ) -> None:
        """Create deployment config.json."""
        config = {
            "host_provider": host_provider,
            "site_type": site_type,
            "aws_profile": AWS_PROFILE,
            "azure_profile": AZURE_PROFILE,
            "url": None,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "last_deployed": None,
            "deploy_count": 0
        }

        # Provider-specific config
        if host_provider == "aws":
            if site_type == "static":
                config["aws"] = {
                    "bucket": None,
                    "distribution_id": None,
                    "region": "us-east-1"
                }
            else:  # dynamic
                config["aws"] = {
                    "instance_id": None,
                    "public_ip": None,
                    "region": "us-east-1",
                    "instance_type": "t3.micro"
                }
        else:  # azure
            if site_type == "static":
                config["azure"] = {
                    "storage_account": None,
                    "cdn_endpoint": None,
                    "resource_group": None
                }
            else:  # dynamic
                config["azure"] = {
                    "vm_name": None,
                    "public_ip": None,
                    "resource_group": None,
                    "vm_size": "Standard_B1s"
                }

        config_path = session_dir / "deployment" / "config.json"
        config_path.write_text(json.dumps(config, indent=2))

    def _create_claude_md(
        self,
        session_dir: Path,
        user_id: str,
        session_id: str,
        host_provider: str,
        site_type: str
    ) -> None:
        """Create session-specific CLAUDE.md."""
        content = f"""# Session Context

## Session Info
- **User ID:** {user_id}
- **Session ID:** {session_id}
- **Host Provider:** {host_provider}
- **Site Type:** {site_type}
- **AWS Profile:** {AWS_PROFILE}
- **Azure Profile:** {AZURE_PROFILE}

## Your Role
You are building and deploying a {site_type} website to {host_provider.upper()}.

## Available Agents
Check `.claude/agents/` for available deployment and testing agents.

## Available Skills
Check `.claude/skills/` for cloud deployment and testing skills.

## Workflow
1. Generate/modify website code in `source/`
2. Use deployer agent to deploy to {host_provider.upper()}
3. Use tester agent to run health check, capture screenshot, run E2E tests
4. Inform user of deployed URL and test results
5. Repeat as user requests modifications

## Resource Naming
All cloud resources use naming pattern: `tmux-{{user_id_prefix}}-{{session_id}}`

## Important
- Always use `{AWS_PROFILE}` profile for AWS CLI commands
- Always use `{AZURE_PROFILE}` profile/subscription for Azure CLI commands
- Tag ALL resources with required tags for cost tracking
"""

        claude_md_path = session_dir / ".claude" / "CLAUDE.md"
        claude_md_path.write_text(content)

    def get_session_path(self, user_id: str, session_id: str) -> Path:
        """Get path to a session directory."""
        return self.users_dir / user_id / "sessions" / session_id

    def list_sessions(self, user_id: str) -> list:
        """List all sessions for a user."""
        sessions_dir = self.users_dir / user_id / "sessions"
        if not sessions_dir.exists():
            return []
        return [
            d.name for d in sessions_dir.iterdir()
            if d.is_dir() and d.name.startswith("sess_")
        ]
```

**Step 4: Run test to verify it passes**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_session_creator.py -v -p no:anyio`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/session_creator.py backend/tests/test_session_creator.py
git commit -m "feat: add session creator with folder structure and config"
```

---

## Phase 2: Cloud Deployment Modules

### Task 2.1: Cloud Config Module

**Files:**
- Create: `backend/cloud_config.py`
- Create: `backend/tests/test_cloud_config.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_cloud_config.py
import pytest


class TestCloudConfig:
    """Tests for cloud configuration and resource naming."""

    def test_resource_name_format(self):
        """Resource name follows tmux-{guid}-{session} pattern."""
        from cloud_config import CloudConfig

        name = CloudConfig.get_resource_name(
            user_id="a1b2c3d4-e5f6-7890-abcd-1234567890ab",
            session_id="sess_20260124_143022"
        )

        assert name.startswith("tmux-")
        assert "a1b2c3d4" in name

    def test_resource_name_truncation_s3(self):
        """S3 bucket names truncated to 63 chars."""
        from cloud_config import CloudConfig

        name = CloudConfig.get_resource_name(
            user_id="a1b2c3d4-e5f6-7890-abcd-1234567890ab",
            session_id="sess_20260124_143022",
            resource_type="s3"
        )

        assert len(name) <= 63
        assert name.islower()  # S3 requires lowercase

    def test_resource_name_truncation_azure_storage(self):
        """Azure storage names truncated to 24 chars, no hyphens."""
        from cloud_config import CloudConfig

        name = CloudConfig.get_resource_name(
            user_id="a1b2c3d4-e5f6-7890-abcd-1234567890ab",
            session_id="sess_20260124_143022",
            resource_type="azure_storage"
        )

        assert len(name) <= 24
        assert "-" not in name
        assert name.islower()

    def test_get_tags_includes_required_fields(self):
        """Tags include all required fields for cost tracking."""
        from cloud_config import CloudConfig

        tags = CloudConfig.get_tags(
            user_id="a1b2c3d4",
            session_id="sess_001",
            site_type="static"
        )

        assert tags["Project"] == "tmux-builder"
        assert tags["UserGUID"] == "a1b2c3d4"
        assert tags["SessionID"] == "sess_001"
        assert tags["SiteType"] == "static"
        assert tags["CreatedBy"] == "tmux-builder-automation"
        assert "CreatedAt" in tags

    def test_aws_profile_is_sunwaretech(self):
        """AWS profile is sunwaretech."""
        from cloud_config import CloudConfig

        assert CloudConfig.AWS_PROFILE == "sunwaretech"

    def test_azure_profile_is_sunwaretech(self):
        """Azure profile is sunwaretech."""
        from cloud_config import CloudConfig

        assert CloudConfig.AZURE_PROFILE == "sunwaretech"
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_cloud_config.py -v -p no:anyio`
Expected: FAIL with "No module named 'cloud_config'"

**Step 3: Write minimal implementation**

```python
# backend/cloud_config.py
"""
Cloud configuration module.

Provides:
- Resource naming conventions (with truncation)
- Mandatory tags for cost tracking
- AWS/Azure profile configuration
"""

import re
from datetime import datetime
from typing import Dict, Optional


class CloudConfig:
    """Cloud configuration and naming utilities."""

    # Profile names
    AWS_PROFILE = "sunwaretech"
    AZURE_PROFILE = "sunwaretech"

    # AWS regions
    AWS_DEFAULT_REGION = "us-east-1"

    # Azure defaults
    AZURE_DEFAULT_LOCATION = "eastus"

    # Resource name limits
    LIMITS = {
        "s3": 63,
        "cloudfront": 128,
        "ec2": 255,
        "azure_storage": 24,
        "azure_cdn": 50,
        "azure_vm": 64,
        "default": 63
    }

    @classmethod
    def get_resource_name(
        cls,
        user_id: str,
        session_id: str,
        resource_type: str = "default",
        suffix: Optional[str] = None
    ) -> str:
        """
        Generate resource name following naming convention.

        Pattern: tmux-{guid_prefix}-{session_short}[-suffix]

        Args:
            user_id: Full user GUID
            session_id: Session ID (e.g., sess_20260124_143022)
            resource_type: Type of resource for length limits
            suffix: Optional suffix (e.g., "cf" for CloudFront)

        Returns:
            Truncated, valid resource name
        """
        # Get limit for this resource type
        limit = cls.LIMITS.get(resource_type, cls.LIMITS["default"])

        # Extract GUID prefix (first 8 chars)
        guid_prefix = user_id.split("-")[0] if "-" in user_id else user_id[:8]

        # Extract session date (remove sess_ prefix)
        session_short = session_id.replace("sess_", "").replace("_", "")

        # Build base name
        if suffix:
            base_name = f"tmux-{guid_prefix}-{session_short}-{suffix}"
        else:
            base_name = f"tmux-{guid_prefix}-{session_short}"

        # Handle Azure storage (no hyphens, alphanumeric only)
        if resource_type == "azure_storage":
            base_name = re.sub(r'[^a-z0-9]', '', base_name.lower())
        else:
            # Lowercase for S3 compatibility
            base_name = base_name.lower()

        # Truncate if needed
        if len(base_name) > limit:
            base_name = base_name[:limit]

        return base_name

    @classmethod
    def get_tags(
        cls,
        user_id: str,
        session_id: str,
        site_type: str,
        environment: str = "production",
        extra_tags: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Get mandatory tags for cloud resources.

        All resources MUST have these tags for cost tracking.

        Args:
            user_id: User GUID
            session_id: Session ID
            site_type: "static" or "dynamic"
            environment: Environment name
            extra_tags: Additional tags to merge

        Returns:
            Dict of tag key-value pairs
        """
        execution_id = f"{user_id}_{session_id}"

        tags = {
            "Project": "tmux-builder",
            "Environment": environment,
            "UserGUID": user_id,
            "SessionID": session_id,
            "ExecutionID": execution_id,
            "SiteType": site_type,
            "CreatedAt": datetime.utcnow().isoformat() + "Z",
            "CreatedBy": "tmux-builder-automation",
            "CostCenter": "user-sites"
        }

        if extra_tags:
            tags.update(extra_tags)

        return tags

    @classmethod
    def get_aws_tags_list(cls, tags: Dict[str, str]) -> list:
        """Convert tags dict to AWS format [{"Key": k, "Value": v}]."""
        return [{"Key": k, "Value": v} for k, v in tags.items()]

    @classmethod
    def get_azure_tags(cls, tags: Dict[str, str]) -> Dict[str, str]:
        """Azure uses same dict format, but ensure string values."""
        return {k: str(v) for k, v in tags.items()}
```

**Step 4: Run test to verify it passes**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_cloud_config.py -v -p no:anyio`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add backend/cloud_config.py backend/tests/test_cloud_config.py
git commit -m "feat: add cloud config with resource naming and tagging"
```

---

### Task 2.2: AWS Static Deployer (S3 + CloudFront)

**Files:**
- Create: `backend/aws_deployer.py`
- Create: `backend/tests/test_aws_deployer.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_aws_deployer.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestAWSDeployer:
    """Tests for AWS S3 + CloudFront deployment."""

    def test_deployer_uses_sunwaretech_profile(self):
        """Deployer configured with sunwaretech profile."""
        from aws_deployer import AWSStaticDeployer

        deployer = AWSStaticDeployer(
            user_id="test-user",
            session_id="sess_001"
        )

        assert deployer.profile == "sunwaretech"

    def test_bucket_name_generated_correctly(self):
        """S3 bucket name follows naming convention."""
        from aws_deployer import AWSStaticDeployer

        deployer = AWSStaticDeployer(
            user_id="a1b2c3d4-e5f6-7890-abcd-1234567890ab",
            session_id="sess_20260124_143022"
        )

        assert deployer.bucket_name.startswith("tmux-")
        assert len(deployer.bucket_name) <= 63

    @patch('aws_deployer.boto3')
    def test_deploy_creates_bucket_with_tags(self, mock_boto3):
        """Deploy creates S3 bucket with required tags."""
        from aws_deployer import AWSStaticDeployer

        mock_s3 = MagicMock()
        mock_boto3.Session.return_value.client.return_value = mock_s3

        deployer = AWSStaticDeployer("test-user", "sess_001")
        deployer._create_bucket()

        # Verify bucket created
        mock_s3.create_bucket.assert_called_once()

        # Verify tags applied
        mock_s3.put_bucket_tagging.assert_called_once()
        call_args = mock_s3.put_bucket_tagging.call_args
        tagging = call_args[1]["Tagging"]["TagSet"]
        tag_keys = [t["Key"] for t in tagging]
        assert "Project" in tag_keys
        assert "UserGUID" in tag_keys

    @patch('aws_deployer.boto3')
    def test_deploy_uploads_files(self, mock_boto3, tmp_path):
        """Deploy uploads all files from source directory."""
        from aws_deployer import AWSStaticDeployer

        # Create test files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "index.html").write_text("<html>Test</html>")
        (source_dir / "style.css").write_text("body {}")

        mock_s3 = MagicMock()
        mock_boto3.Session.return_value.client.return_value = mock_s3

        deployer = AWSStaticDeployer("test-user", "sess_001")
        deployer._upload_files(source_dir)

        # Verify files uploaded
        assert mock_s3.upload_file.call_count == 2

    @patch('aws_deployer.boto3')
    def test_deploy_returns_cloudfront_url(self, mock_boto3):
        """Deploy returns CloudFront distribution URL."""
        from aws_deployer import AWSStaticDeployer

        mock_cf = MagicMock()
        mock_cf.create_distribution.return_value = {
            "Distribution": {
                "Id": "E1234ABCD",
                "DomainName": "d1234abcd.cloudfront.net"
            }
        }
        mock_boto3.Session.return_value.client.return_value = mock_cf

        deployer = AWSStaticDeployer("test-user", "sess_001")
        deployer.cf_client = mock_cf

        result = deployer._create_cloudfront_distribution()

        assert "cloudfront.net" in result["url"]
        assert result["distribution_id"] == "E1234ABCD"
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_aws_deployer.py -v -p no:anyio`
Expected: FAIL with "No module named 'aws_deployer'"

**Step 3: Write minimal implementation**

```python
# backend/aws_deployer.py
"""
AWS Static Deployer (S3 + CloudFront).

Deploys static websites to S3 with CloudFront CDN.
Uses sunwaretech AWS profile.
"""

import os
import json
import mimetypes
import logging
from pathlib import Path
from typing import Dict, Optional

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None
    ClientError = Exception

from cloud_config import CloudConfig

logger = logging.getLogger(__name__)


class AWSStaticDeployer:
    """Deploy static sites to AWS S3 + CloudFront."""

    def __init__(
        self,
        user_id: str,
        session_id: str,
        region: str = None
    ):
        """
        Initialize AWS deployer.

        Args:
            user_id: User GUID
            session_id: Session ID
            region: AWS region (default: us-east-1)
        """
        self.user_id = user_id
        self.session_id = session_id
        self.profile = CloudConfig.AWS_PROFILE
        self.region = region or CloudConfig.AWS_DEFAULT_REGION

        # Generate resource names
        self.bucket_name = CloudConfig.get_resource_name(
            user_id, session_id, "s3"
        )
        self.distribution_name = CloudConfig.get_resource_name(
            user_id, session_id, "cloudfront", suffix="cf"
        )

        # Get tags
        self.tags = CloudConfig.get_tags(user_id, session_id, "static")
        self.aws_tags = CloudConfig.get_aws_tags_list(self.tags)

        # Initialize clients (lazy)
        self._s3_client = None
        self._cf_client = None

    @property
    def s3_client(self):
        """Lazy-load S3 client with profile."""
        if self._s3_client is None:
            session = boto3.Session(
                profile_name=self.profile,
                region_name=self.region
            )
            self._s3_client = session.client('s3')
        return self._s3_client

    @property
    def cf_client(self):
        """Lazy-load CloudFront client with profile."""
        if self._cf_client is None:
            session = boto3.Session(
                profile_name=self.profile,
                region_name=self.region
            )
            self._cf_client = session.client('cloudfront')
        return self._cf_client

    @cf_client.setter
    def cf_client(self, value):
        """Allow setting cf_client for testing."""
        self._cf_client = value

    def deploy(self, source_dir: Path) -> Dict:
        """
        Deploy static site to S3 + CloudFront.

        Args:
            source_dir: Directory containing website files

        Returns:
            Dict with url, bucket, distribution_id
        """
        logger.info(f"Deploying to AWS S3 + CloudFront: {self.bucket_name}")

        # Step 1: Create/verify bucket
        self._create_bucket()

        # Step 2: Upload files
        self._upload_files(source_dir)

        # Step 3: Create/update CloudFront
        cf_result = self._create_cloudfront_distribution()

        return {
            "url": cf_result["url"],
            "bucket": self.bucket_name,
            "distribution_id": cf_result["distribution_id"],
            "region": self.region
        }

    def _create_bucket(self) -> None:
        """Create S3 bucket with static website hosting."""
        try:
            # Create bucket
            if self.region == "us-east-1":
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=self.bucket_name,
                    CreateBucketConfiguration={
                        'LocationConstraint': self.region
                    }
                )
            logger.info(f"Created S3 bucket: {self.bucket_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
                logger.info(f"Bucket already exists: {self.bucket_name}")
            else:
                raise

        # Enable static website hosting
        self.s3_client.put_bucket_website(
            Bucket=self.bucket_name,
            WebsiteConfiguration={
                'IndexDocument': {'Suffix': 'index.html'},
                'ErrorDocument': {'Key': 'error.html'}
            }
        )

        # Apply tags
        self.s3_client.put_bucket_tagging(
            Bucket=self.bucket_name,
            Tagging={'TagSet': self.aws_tags}
        )

        # Set bucket policy for public read
        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{self.bucket_name}/*"
            }]
        }
        self.s3_client.put_bucket_policy(
            Bucket=self.bucket_name,
            Policy=json.dumps(policy)
        )

    def _upload_files(self, source_dir: Path) -> int:
        """Upload all files from source directory to S3."""
        source_dir = Path(source_dir)
        uploaded = 0

        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                # Get relative path for S3 key
                key = str(file_path.relative_to(source_dir))

                # Detect content type
                content_type, _ = mimetypes.guess_type(str(file_path))
                if content_type is None:
                    content_type = 'application/octet-stream'

                # Upload
                self.s3_client.upload_file(
                    str(file_path),
                    self.bucket_name,
                    key,
                    ExtraArgs={'ContentType': content_type}
                )
                uploaded += 1
                logger.debug(f"Uploaded: {key}")

        logger.info(f"Uploaded {uploaded} files to S3")
        return uploaded

    def _create_cloudfront_distribution(self) -> Dict:
        """Create CloudFront distribution for the S3 bucket."""
        origin_id = f"S3-{self.bucket_name}"

        distribution_config = {
            'CallerReference': f"{self.bucket_name}-{self.session_id}",
            'Comment': f"tmux-builder: {self.user_id}/{self.session_id}",
            'Enabled': True,
            'Origins': {
                'Quantity': 1,
                'Items': [{
                    'Id': origin_id,
                    'DomainName': f"{self.bucket_name}.s3.amazonaws.com",
                    'S3OriginConfig': {
                        'OriginAccessIdentity': ''
                    }
                }]
            },
            'DefaultCacheBehavior': {
                'TargetOriginId': origin_id,
                'ViewerProtocolPolicy': 'redirect-to-https',
                'AllowedMethods': {
                    'Quantity': 2,
                    'Items': ['GET', 'HEAD'],
                    'CachedMethods': {
                        'Quantity': 2,
                        'Items': ['GET', 'HEAD']
                    }
                },
                'ForwardedValues': {
                    'QueryString': False,
                    'Cookies': {'Forward': 'none'}
                },
                'MinTTL': 0,
                'DefaultTTL': 86400,
                'MaxTTL': 31536000,
                'Compress': True
            },
            'DefaultRootObject': 'index.html',
            'PriceClass': 'PriceClass_100'
        }

        response = self.cf_client.create_distribution(
            DistributionConfig=distribution_config
        )

        distribution = response['Distribution']
        distribution_id = distribution['Id']
        domain_name = distribution['DomainName']

        # Tag the distribution
        self.cf_client.tag_resource(
            Resource=f"arn:aws:cloudfront::{self._get_account_id()}:distribution/{distribution_id}",
            Tags={'Items': self.aws_tags}
        )

        logger.info(f"Created CloudFront distribution: {distribution_id}")

        return {
            "distribution_id": distribution_id,
            "url": f"https://{domain_name}"
        }

    def _get_account_id(self) -> str:
        """Get AWS account ID."""
        session = boto3.Session(profile_name=self.profile)
        sts = session.client('sts')
        return sts.get_caller_identity()['Account']

    def invalidate_cache(self, distribution_id: str, paths: list = None) -> str:
        """
        Invalidate CloudFront cache.

        Args:
            distribution_id: CloudFront distribution ID
            paths: List of paths to invalidate (default: /*)

        Returns:
            Invalidation ID
        """
        if paths is None:
            paths = ['/*']

        response = self.cf_client.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                'Paths': {
                    'Quantity': len(paths),
                    'Items': paths
                },
                'CallerReference': f"invalidate-{self.session_id}-{os.urandom(4).hex()}"
            }
        )

        invalidation_id = response['Invalidation']['Id']
        logger.info(f"Created cache invalidation: {invalidation_id}")
        return invalidation_id

    def redeploy(self, source_dir: Path, distribution_id: str) -> Dict:
        """
        Redeploy by uploading new files and invalidating cache.

        Args:
            source_dir: Directory containing updated website files
            distribution_id: Existing CloudFront distribution ID

        Returns:
            Dict with url, invalidation_id
        """
        logger.info(f"Redeploying to existing distribution: {distribution_id}")

        # Upload new files
        self._upload_files(source_dir)

        # Invalidate cache
        invalidation_id = self.invalidate_cache(distribution_id)

        # Get distribution domain
        response = self.cf_client.get_distribution(Id=distribution_id)
        domain_name = response['Distribution']['DomainName']

        return {
            "url": f"https://{domain_name}",
            "invalidation_id": invalidation_id
        }
```

**Step 4: Run test to verify it passes**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_aws_deployer.py -v -p no:anyio`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add backend/aws_deployer.py backend/tests/test_aws_deployer.py
git commit -m "feat: add AWS static deployer with S3 + CloudFront"
```

---

### Task 2.3: Azure Static Deployer (Blob + CDN)

**Files:**
- Create: `backend/azure_deployer.py`
- Create: `backend/tests/test_azure_deployer.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_azure_deployer.py
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestAzureDeployer:
    """Tests for Azure Blob + CDN deployment."""

    def test_deployer_uses_sunwaretech_profile(self):
        """Deployer configured with sunwaretech profile."""
        from azure_deployer import AzureStaticDeployer

        deployer = AzureStaticDeployer(
            user_id="test-user",
            session_id="sess_001"
        )

        assert deployer.profile == "sunwaretech"

    def test_storage_account_name_valid(self):
        """Storage account name is valid (no hyphens, <=24 chars)."""
        from azure_deployer import AzureStaticDeployer

        deployer = AzureStaticDeployer(
            user_id="a1b2c3d4-e5f6-7890-abcd-1234567890ab",
            session_id="sess_20260124_143022"
        )

        assert len(deployer.storage_account_name) <= 24
        assert "-" not in deployer.storage_account_name
        assert deployer.storage_account_name.islower()
        assert deployer.storage_account_name.isalnum()

    def test_tags_include_required_fields(self):
        """Tags include all required fields for cost tracking."""
        from azure_deployer import AzureStaticDeployer

        deployer = AzureStaticDeployer("test-user", "sess_001")

        assert deployer.tags["Project"] == "tmux-builder"
        assert deployer.tags["UserGUID"] == "test-user"
        assert deployer.tags["SessionID"] == "sess_001"
        assert deployer.tags["SiteType"] == "static"

    def test_resource_group_name_format(self):
        """Resource group follows naming convention."""
        from azure_deployer import AzureStaticDeployer

        deployer = AzureStaticDeployer(
            user_id="a1b2c3d4",
            session_id="sess_001"
        )

        assert deployer.resource_group_name.startswith("tmux-")
        assert "rg" in deployer.resource_group_name
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_azure_deployer.py -v -p no:anyio`
Expected: FAIL with "No module named 'azure_deployer'"

**Step 3: Write minimal implementation**

```python
# backend/azure_deployer.py
"""
Azure Static Deployer (Blob Storage + CDN).

Deploys static websites to Azure Blob Storage with CDN.
Uses sunwaretech Azure profile/subscription.
"""

import os
import json
import mimetypes
import logging
from pathlib import Path
from typing import Dict, Optional

try:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.storage import StorageManagementClient
    from azure.mgmt.cdn import CdnManagementClient
    from azure.storage.blob import BlobServiceClient, ContentSettings
except ImportError:
    DefaultAzureCredential = None
    StorageManagementClient = None
    CdnManagementClient = None
    BlobServiceClient = None
    ContentSettings = None

from cloud_config import CloudConfig

logger = logging.getLogger(__name__)


class AzureStaticDeployer:
    """Deploy static sites to Azure Blob Storage + CDN."""

    def __init__(
        self,
        user_id: str,
        session_id: str,
        location: str = None,
        subscription_id: str = None
    ):
        """
        Initialize Azure deployer.

        Args:
            user_id: User GUID
            session_id: Session ID
            location: Azure region (default: eastus)
            subscription_id: Azure subscription ID
        """
        self.user_id = user_id
        self.session_id = session_id
        self.profile = CloudConfig.AZURE_PROFILE
        self.location = location or CloudConfig.AZURE_DEFAULT_LOCATION
        self.subscription_id = subscription_id or os.environ.get('AZURE_SUBSCRIPTION_ID')

        # Generate resource names
        self.storage_account_name = CloudConfig.get_resource_name(
            user_id, session_id, "azure_storage"
        )
        self.resource_group_name = CloudConfig.get_resource_name(
            user_id, session_id, "default", suffix="rg"
        )
        self.cdn_profile_name = CloudConfig.get_resource_name(
            user_id, session_id, "azure_cdn", suffix="cdn"
        )
        self.cdn_endpoint_name = CloudConfig.get_resource_name(
            user_id, session_id, "azure_cdn", suffix="ep"
        )

        # Get tags
        self.tags = CloudConfig.get_azure_tags(
            CloudConfig.get_tags(user_id, session_id, "static")
        )

        # Initialize clients (lazy)
        self._credential = None
        self._storage_client = None
        self._cdn_client = None
        self._blob_service_client = None

    @property
    def credential(self):
        """Get Azure credential."""
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        return self._credential

    @property
    def storage_client(self):
        """Lazy-load Storage Management client."""
        if self._storage_client is None:
            self._storage_client = StorageManagementClient(
                self.credential,
                self.subscription_id
            )
        return self._storage_client

    @property
    def cdn_client(self):
        """Lazy-load CDN Management client."""
        if self._cdn_client is None:
            self._cdn_client = CdnManagementClient(
                self.credential,
                self.subscription_id
            )
        return self._cdn_client

    def deploy(self, source_dir: Path) -> Dict:
        """
        Deploy static site to Azure Blob Storage + CDN.

        Args:
            source_dir: Directory containing website files

        Returns:
            Dict with url, storage_account, cdn_endpoint
        """
        logger.info(f"Deploying to Azure Blob + CDN: {self.storage_account_name}")

        # Step 1: Create resource group
        self._create_resource_group()

        # Step 2: Create storage account with static website
        storage_url = self._create_storage_account()

        # Step 3: Upload files
        self._upload_files(source_dir)

        # Step 4: Create CDN
        cdn_url = self._create_cdn()

        return {
            "url": cdn_url,
            "storage_url": storage_url,
            "storage_account": self.storage_account_name,
            "cdn_endpoint": self.cdn_endpoint_name,
            "resource_group": self.resource_group_name
        }

    def _create_resource_group(self) -> None:
        """Create Azure resource group."""
        from azure.mgmt.resource import ResourceManagementClient

        resource_client = ResourceManagementClient(
            self.credential,
            self.subscription_id
        )

        resource_client.resource_groups.create_or_update(
            self.resource_group_name,
            {
                "location": self.location,
                "tags": self.tags
            }
        )
        logger.info(f"Created resource group: {self.resource_group_name}")

    def _create_storage_account(self) -> str:
        """Create storage account with static website hosting."""
        # Create storage account
        poller = self.storage_client.storage_accounts.begin_create(
            self.resource_group_name,
            self.storage_account_name,
            {
                "location": self.location,
                "kind": "StorageV2",
                "sku": {"name": "Standard_LRS"},
                "tags": self.tags,
                "allow_blob_public_access": True
            }
        )
        poller.result()
        logger.info(f"Created storage account: {self.storage_account_name}")

        # Enable static website hosting
        self.storage_client.blob_services.set_service_properties(
            self.resource_group_name,
            self.storage_account_name,
            {
                "static_website": {
                    "enabled": True,
                    "index_document": "index.html",
                    "error_document_404_path": "error.html"
                }
            }
        )

        # Get static website URL
        account = self.storage_client.storage_accounts.get_properties(
            self.resource_group_name,
            self.storage_account_name
        )

        return account.primary_endpoints.web

    def _get_blob_service_client(self) -> 'BlobServiceClient':
        """Get blob service client for the storage account."""
        if self._blob_service_client is None:
            # Get account key
            keys = self.storage_client.storage_accounts.list_keys(
                self.resource_group_name,
                self.storage_account_name
            )
            account_key = keys.keys[0].value

            connection_string = (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={self.storage_account_name};"
                f"AccountKey={account_key};"
                f"EndpointSuffix=core.windows.net"
            )

            self._blob_service_client = BlobServiceClient.from_connection_string(
                connection_string
            )
        return self._blob_service_client

    def _upload_files(self, source_dir: Path) -> int:
        """Upload files to $web container."""
        source_dir = Path(source_dir)
        blob_service = self._get_blob_service_client()
        container_client = blob_service.get_container_client("$web")

        uploaded = 0
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                blob_name = str(file_path.relative_to(source_dir))

                # Detect content type
                content_type, _ = mimetypes.guess_type(str(file_path))
                if content_type is None:
                    content_type = 'application/octet-stream'

                content_settings = ContentSettings(content_type=content_type)

                with open(file_path, "rb") as data:
                    container_client.upload_blob(
                        blob_name,
                        data,
                        overwrite=True,
                        content_settings=content_settings
                    )
                uploaded += 1
                logger.debug(f"Uploaded: {blob_name}")

        logger.info(f"Uploaded {uploaded} files to Azure Blob")
        return uploaded

    def _create_cdn(self) -> str:
        """Create CDN profile and endpoint."""
        # Create CDN profile
        poller = self.cdn_client.profiles.begin_create(
            self.resource_group_name,
            self.cdn_profile_name,
            {
                "location": "global",
                "sku": {"name": "Standard_Microsoft"},
                "tags": self.tags
            }
        )
        poller.result()
        logger.info(f"Created CDN profile: {self.cdn_profile_name}")

        # Create CDN endpoint
        origin_hostname = f"{self.storage_account_name}.z13.web.core.windows.net"

        poller = self.cdn_client.endpoints.begin_create(
            self.resource_group_name,
            self.cdn_profile_name,
            self.cdn_endpoint_name,
            {
                "location": "global",
                "origins": [{
                    "name": "blob-origin",
                    "host_name": origin_hostname
                }],
                "origin_host_header": origin_hostname,
                "is_compression_enabled": True,
                "content_types_to_compress": [
                    "text/html", "text/css", "application/javascript",
                    "application/json", "image/svg+xml"
                ],
                "tags": self.tags
            }
        )
        endpoint = poller.result()
        logger.info(f"Created CDN endpoint: {self.cdn_endpoint_name}")

        return f"https://{endpoint.host_name}"

    def purge_cdn(self, paths: list = None) -> None:
        """
        Purge CDN cache.

        Args:
            paths: List of paths to purge (default: /*)
        """
        if paths is None:
            paths = ['/*']

        poller = self.cdn_client.endpoints.begin_purge_content(
            self.resource_group_name,
            self.cdn_profile_name,
            self.cdn_endpoint_name,
            {"content_paths": paths}
        )
        poller.result()
        logger.info(f"Purged CDN cache for paths: {paths}")

    def redeploy(self, source_dir: Path) -> Dict:
        """
        Redeploy by uploading new files and purging CDN.

        Args:
            source_dir: Directory containing updated website files

        Returns:
            Dict with url
        """
        logger.info("Redeploying to Azure")

        # Upload new files
        self._upload_files(source_dir)

        # Purge CDN cache
        self.purge_cdn()

        # Get CDN URL
        endpoint = self.cdn_client.endpoints.get(
            self.resource_group_name,
            self.cdn_profile_name,
            self.cdn_endpoint_name
        )

        return {
            "url": f"https://{endpoint.host_name}"
        }
```

**Step 4: Run test to verify it passes**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_azure_deployer.py -v -p no:anyio`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/azure_deployer.py backend/tests/test_azure_deployer.py
git commit -m "feat: add Azure static deployer with Blob + CDN"
```

---

## Phase 3: Testing Modules

### Task 3.1: Health Checker Module

**Files:**
- Create: `backend/health_checker.py`
- Create: `backend/tests/test_health_checker.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_health_checker.py
import pytest
from unittest.mock import Mock, patch


class TestHealthChecker:
    """Tests for HTTP health checking."""

    def test_health_check_success(self):
        """Health check passes for 200 response."""
        from health_checker import HealthChecker

        with patch('health_checker.requests') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {'content-type': 'text/html'}
            mock_response.content = b"<html>Hello</html>"
            mock_requests.get.return_value = mock_response

            checker = HealthChecker()
            result = checker.check("https://example.com")

            assert result["passed"] == True
            assert result["status_code"] == 200

    def test_health_check_failure_on_500(self):
        """Health check fails for 500 response."""
        from health_checker import HealthChecker

        with patch('health_checker.requests') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_requests.get.return_value = mock_response

            checker = HealthChecker()
            result = checker.check("https://example.com")

            assert result["passed"] == False
            assert result["status_code"] == 500

    def test_health_check_retries_on_failure(self):
        """Health check retries on connection error."""
        from health_checker import HealthChecker
        import requests

        with patch('health_checker.requests') as mock_requests:
            mock_requests.exceptions = requests.exceptions
            mock_requests.get.side_effect = [
                requests.exceptions.ConnectionError(),
                Mock(status_code=200, headers={'content-type': 'text/html'}, content=b"OK")
            ]

            checker = HealthChecker(max_retries=3)
            result = checker.check("https://example.com")

            assert result["passed"] == True
            assert mock_requests.get.call_count == 2

    def test_health_check_saves_result(self, tmp_path):
        """Health check saves result to file."""
        from health_checker import HealthChecker

        with patch('health_checker.requests') as mock_requests:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {'content-type': 'text/html'}
            mock_response.content = b"<html>Test</html>"
            mock_requests.get.return_value = mock_response

            checker = HealthChecker()
            result = checker.check("https://example.com", output_path=tmp_path / "health.json")

            assert (tmp_path / "health.json").exists()
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_health_checker.py -v -p no:anyio`
Expected: FAIL with "No module named 'health_checker'"

**Step 3: Write minimal implementation**

```python
# backend/health_checker.py
"""
Health checker module.

Performs HTTP health checks on deployed websites.
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)


class HealthChecker:
    """Perform HTTP health checks on URLs."""

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        """
        Initialize health checker.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def check(
        self,
        url: str,
        output_path: Optional[Path] = None
    ) -> Dict:
        """
        Perform health check on URL.

        Args:
            url: URL to check
            output_path: Optional path to save result JSON

        Returns:
            Dict with passed, status_code, details
        """
        start_time = time.time()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True
                )

                duration_ms = int((time.time() - start_time) * 1000)

                passed = (
                    response.status_code == 200 and
                    'text/html' in response.headers.get('content-type', '') and
                    len(response.content) > 100
                )

                result = {
                    "test": "health_check",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "passed": passed,
                    "duration_ms": duration_ms,
                    "attempts": attempt + 1,
                    "details": {
                        "url": url,
                        "status_code": response.status_code,
                        "content_type": response.headers.get('content-type', ''),
                        "response_size_bytes": len(response.content)
                    }
                }

                if not passed:
                    result["error"] = f"Unexpected status code: {response.status_code}"

                # Save result if path provided
                if output_path:
                    output_path = Path(output_path)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(json.dumps(result, indent=2))

                logger.info(f"Health check {'PASSED' if passed else 'FAILED'}: {url}")
                return result

            except requests.exceptions.RequestException as e:
                last_error = str(e)
                logger.warning(f"Health check attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)

        # All retries failed
        duration_ms = int((time.time() - start_time) * 1000)
        result = {
            "test": "health_check",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "passed": False,
            "duration_ms": duration_ms,
            "attempts": self.max_retries,
            "error": last_error,
            "details": {
                "url": url,
                "status_code": None,
                "content_type": None,
                "response_size_bytes": 0
            }
        }

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(result, indent=2))

        logger.error(f"Health check FAILED after {self.max_retries} attempts: {url}")
        return result
```

**Step 4: Run test to verify it passes**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_health_checker.py -v -p no:anyio`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/health_checker.py backend/tests/test_health_checker.py
git commit -m "feat: add health checker with retry logic"
```

---

### Task 3.2: Screenshot Capture Module

**Files:**
- Create: `backend/screenshot_capture.py`
- Create: `backend/tests/test_screenshot_capture.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_screenshot_capture.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestScreenshotCapture:
    """Tests for Playwright screenshot capture."""

    def test_capture_saves_screenshot(self, tmp_path):
        """Screenshot capture saves PNG file."""
        from screenshot_capture import ScreenshotCapture

        with patch('screenshot_capture.sync_playwright') as mock_pw:
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page

            capture = ScreenshotCapture()
            output_path = tmp_path / "screenshot.png"

            result = capture.capture("https://example.com", output_path)

            mock_page.goto.assert_called_once()
            mock_page.screenshot.assert_called_once()
            assert result["passed"] == True

    def test_capture_creates_thumbnail(self, tmp_path):
        """Screenshot capture creates thumbnail."""
        from screenshot_capture import ScreenshotCapture

        with patch('screenshot_capture.sync_playwright') as mock_pw:
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page

            # Mock screenshot to create actual file
            def save_screenshot(**kwargs):
                Path(kwargs['path']).write_bytes(b'PNG fake data')
            mock_page.screenshot.side_effect = save_screenshot

            capture = ScreenshotCapture()
            output_path = tmp_path / "screenshot.png"

            with patch('screenshot_capture.Image') as mock_image:
                mock_img = MagicMock()
                mock_image.open.return_value = mock_img

                result = capture.capture(
                    "https://example.com",
                    output_path,
                    create_thumbnail=True
                )

                # Verify thumbnail creation attempted
                assert result["passed"] == True

    def test_capture_result_format(self, tmp_path):
        """Screenshot result includes required fields."""
        from screenshot_capture import ScreenshotCapture

        with patch('screenshot_capture.sync_playwright') as mock_pw:
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_pw.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
            mock_browser.new_page.return_value = mock_page

            capture = ScreenshotCapture()
            result = capture.capture("https://example.com", tmp_path / "shot.png")

            assert "test" in result
            assert result["test"] == "screenshot"
            assert "timestamp" in result
            assert "passed" in result
            assert "duration_ms" in result
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_screenshot_capture.py -v -p no:anyio`
Expected: FAIL with "No module named 'screenshot_capture'"

**Step 3: Write minimal implementation**

```python
# backend/screenshot_capture.py
"""
Screenshot capture module using Playwright.

Captures full-page screenshots of deployed websites.
"""

import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

try:
    from PIL import Image
except ImportError:
    Image = None

logger = logging.getLogger(__name__)


class ScreenshotCapture:
    """Capture screenshots using Playwright."""

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        wait_for_network: bool = True,
        timeout: int = 30000
    ):
        """
        Initialize screenshot capture.

        Args:
            width: Viewport width
            height: Viewport height
            wait_for_network: Wait for network idle
            timeout: Page load timeout in ms
        """
        self.width = width
        self.height = height
        self.wait_for_network = wait_for_network
        self.timeout = timeout

    def capture(
        self,
        url: str,
        output_path: Path,
        create_thumbnail: bool = True,
        thumbnail_size: tuple = (400, 225)
    ) -> Dict:
        """
        Capture screenshot of URL.

        Args:
            url: URL to capture
            output_path: Path to save screenshot
            create_thumbnail: Also create thumbnail
            thumbnail_size: Thumbnail dimensions (width, height)

        Returns:
            Dict with passed, path, details
        """
        start_time = time.time()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    viewport={"width": self.width, "height": self.height}
                )

                # Navigate to URL
                wait_until = "networkidle" if self.wait_for_network else "load"
                page.goto(url, wait_until=wait_until, timeout=self.timeout)

                # Capture screenshot
                page.screenshot(
                    path=str(output_path),
                    full_page=True
                )

                browser.close()

            duration_ms = int((time.time() - start_time) * 1000)

            # Create thumbnail if requested
            thumbnail_path = None
            if create_thumbnail and Image and output_path.exists():
                thumbnail_path = output_path.parent / f"{output_path.stem}_thumb.png"
                self._create_thumbnail(output_path, thumbnail_path, thumbnail_size)

            result = {
                "test": "screenshot",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "passed": True,
                "duration_ms": duration_ms,
                "details": {
                    "url": url,
                    "path": str(output_path),
                    "thumbnail_path": str(thumbnail_path) if thumbnail_path else None,
                    "viewport": {"width": self.width, "height": self.height}
                }
            }

            logger.info(f"Screenshot captured: {output_path}")
            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            result = {
                "test": "screenshot",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "passed": False,
                "duration_ms": duration_ms,
                "error": str(e),
                "details": {
                    "url": url,
                    "path": None,
                    "thumbnail_path": None
                }
            }

            logger.error(f"Screenshot capture failed: {e}")
            return result

    def _create_thumbnail(
        self,
        source_path: Path,
        output_path: Path,
        size: tuple
    ) -> None:
        """Create thumbnail from screenshot."""
        try:
            with Image.open(source_path) as img:
                img.thumbnail(size, Image.Resampling.LANCZOS)
                img.save(output_path)
            logger.debug(f"Created thumbnail: {output_path}")
        except Exception as e:
            logger.warning(f"Failed to create thumbnail: {e}")
```

**Step 4: Run test to verify it passes**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_screenshot_capture.py -v -p no:anyio`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/screenshot_capture.py backend/tests/test_screenshot_capture.py
git commit -m "feat: add Playwright screenshot capture with thumbnails"
```

---

### Task 3.3: Injection Engine Module

**Files:**
- Create: `backend/injection_engine.py`
- Create: `backend/tests/test_injection_engine.py`
- Create: `backend/injection_rules.json`

**Step 1: Write the failing test**

```python
# backend/tests/test_injection_engine.py
import pytest
import json
from pathlib import Path


class TestInjectionEngine:
    """Tests for skill/agent injection system."""

    def test_match_rule_aws_static(self, tmp_path):
        """Matches correct rule for AWS static."""
        from injection_engine import InjectionEngine

        # Create test rules
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(json.dumps({
            "rules": [
                {
                    "match": {"host_provider": "aws", "site_type": "static"},
                    "inject": {"agents": ["deployers/aws-s3"], "skills": ["aws/s3"]}
                },
                {
                    "match": {"host_provider": "azure", "site_type": "static"},
                    "inject": {"agents": ["deployers/azure-blob"], "skills": ["azure/blob"]}
                }
            ]
        }))

        engine = InjectionEngine(rules_path=rules_path)
        result = engine.match_rule("aws", "static")

        assert "deployers/aws-s3" in result["agents"]
        assert "aws/s3" in result["skills"]

    def test_inject_copies_files(self, tmp_path):
        """Injection copies agent/skill files to session."""
        from injection_engine import InjectionEngine

        # Setup source library
        library_dir = tmp_path / "library" / ".claude"
        (library_dir / "agents" / "deployers").mkdir(parents=True)
        (library_dir / "skills" / "aws").mkdir(parents=True)
        (library_dir / "agents" / "deployers" / "aws-s3.md").write_text("# AWS S3 Deploy")
        (library_dir / "skills" / "aws" / "s3-upload.md").write_text("# S3 Upload Skill")

        # Setup target session
        session_dir = tmp_path / "session"
        session_dir.mkdir()

        # Create rules
        rules_path = tmp_path / "rules.json"
        rules_path.write_text(json.dumps({
            "rules": [{
                "match": {"host_provider": "aws", "site_type": "static"},
                "inject": {
                    "agents": ["deployers/aws-s3"],
                    "skills": ["aws/s3-upload"]
                }
            }]
        }))

        engine = InjectionEngine(
            rules_path=rules_path,
            library_dir=library_dir.parent
        )
        engine.inject("aws", "static", session_dir)

        # Verify files copied
        assert (session_dir / ".claude" / "agents" / "aws-s3.md").exists()
        assert (session_dir / ".claude" / "skills" / "s3-upload.md").exists()

    def test_wildcard_matching(self, tmp_path):
        """Wildcard patterns match multiple files."""
        from injection_engine import InjectionEngine

        # Setup library with multiple test files
        library_dir = tmp_path / "library" / ".claude"
        (library_dir / "agents" / "testers").mkdir(parents=True)
        (library_dir / "agents" / "testers" / "health.md").write_text("# Health")
        (library_dir / "agents" / "testers" / "screenshot.md").write_text("# Screenshot")
        (library_dir / "agents" / "testers" / "e2e.md").write_text("# E2E")

        session_dir = tmp_path / "session"
        session_dir.mkdir()

        rules_path = tmp_path / "rules.json"
        rules_path.write_text(json.dumps({
            "rules": [{
                "match": {"host_provider": "aws", "site_type": "static"},
                "inject": {"agents": ["testers/*"], "skills": []}
            }]
        }))

        engine = InjectionEngine(
            rules_path=rules_path,
            library_dir=library_dir.parent
        )
        engine.inject("aws", "static", session_dir)

        # All tester agents should be copied
        agents_dir = session_dir / ".claude" / "agents"
        assert (agents_dir / "health.md").exists()
        assert (agents_dir / "screenshot.md").exists()
        assert (agents_dir / "e2e.md").exists()
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_injection_engine.py -v -p no:anyio`
Expected: FAIL with "No module named 'injection_engine'"

**Step 3: Write minimal implementation**

```python
# backend/injection_engine.py
"""
Injection engine for skills and agents.

Copies only the required agents and skills from the master library
to user session folders based on host_provider and site_type.
"""

import json
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class InjectionEngine:
    """Inject agents and skills into session folders."""

    def __init__(
        self,
        rules_path: Optional[Path] = None,
        library_dir: Optional[Path] = None
    ):
        """
        Initialize injection engine.

        Args:
            rules_path: Path to injection_rules.json
            library_dir: Path to master .claude library
        """
        if rules_path is None:
            rules_path = Path(__file__).parent / "injection_rules.json"
        if library_dir is None:
            library_dir = Path(__file__).parent.parent / ".claude"

        self.rules_path = Path(rules_path)
        self.library_dir = Path(library_dir)
        self._rules = None

    @property
    def rules(self) -> List[Dict]:
        """Load and cache rules."""
        if self._rules is None:
            if self.rules_path.exists():
                data = json.loads(self.rules_path.read_text())
                self._rules = data.get("rules", [])
            else:
                self._rules = []
        return self._rules

    def match_rule(self, host_provider: str, site_type: str) -> Dict:
        """
        Find matching injection rule.

        Args:
            host_provider: "aws" or "azure"
            site_type: "static" or "dynamic"

        Returns:
            Dict with agents and skills lists
        """
        for rule in self.rules:
            match = rule.get("match", {})
            if (match.get("host_provider") == host_provider and
                match.get("site_type") == site_type):
                return rule.get("inject", {"agents": [], "skills": []})

        # No matching rule
        logger.warning(f"No injection rule for {host_provider}/{site_type}")
        return {"agents": [], "skills": []}

    def inject(
        self,
        host_provider: str,
        site_type: str,
        session_dir: Path
    ) -> Dict:
        """
        Inject agents and skills into session folder.

        Args:
            host_provider: "aws" or "azure"
            site_type: "static" or "dynamic"
            session_dir: Session directory path

        Returns:
            Dict with injected agents and skills counts
        """
        session_dir = Path(session_dir)
        inject_config = self.match_rule(host_provider, site_type)

        # Create target directories
        target_agents_dir = session_dir / ".claude" / "agents"
        target_skills_dir = session_dir / ".claude" / "skills"
        target_agents_dir.mkdir(parents=True, exist_ok=True)
        target_skills_dir.mkdir(parents=True, exist_ok=True)

        agents_copied = 0
        skills_copied = 0

        # Copy agents
        for agent_pattern in inject_config.get("agents", []):
            copied = self._copy_files(
                agent_pattern,
                self.library_dir / ".claude" / "agents",
                target_agents_dir
            )
            agents_copied += copied

        # Copy skills
        for skill_pattern in inject_config.get("skills", []):
            copied = self._copy_files(
                skill_pattern,
                self.library_dir / ".claude" / "skills",
                target_skills_dir
            )
            skills_copied += copied

        logger.info(
            f"Injected {agents_copied} agents and {skills_copied} skills "
            f"into {session_dir}"
        )

        return {
            "agents_copied": agents_copied,
            "skills_copied": skills_copied
        }

    def _copy_files(
        self,
        pattern: str,
        source_base: Path,
        target_dir: Path
    ) -> int:
        """
        Copy files matching pattern from source to target.

        Args:
            pattern: Pattern like "deployers/aws-s3" or "testers/*"
            source_base: Base directory for source files
            target_dir: Target directory

        Returns:
            Number of files copied
        """
        copied = 0

        if pattern.endswith("/*"):
            # Wildcard - copy all files in directory
            dir_name = pattern[:-2]
            source_dir = source_base / dir_name
            if source_dir.exists():
                for file_path in source_dir.glob("*.md"):
                    target_path = target_dir / file_path.name
                    shutil.copy2(file_path, target_path)
                    copied += 1
                    logger.debug(f"Copied: {file_path.name}")
        else:
            # Specific file
            # Try with .md extension
            source_file = source_base / f"{pattern}.md"
            if not source_file.exists():
                # Try as subdirectory file
                parts = pattern.split("/")
                if len(parts) == 2:
                    source_file = source_base / parts[0] / f"{parts[1]}.md"

            if source_file.exists():
                target_path = target_dir / source_file.name
                shutil.copy2(source_file, target_path)
                copied += 1
                logger.debug(f"Copied: {source_file.name}")
            else:
                logger.warning(f"Source file not found: {pattern}")

        return copied
```

**Step 4: Create injection_rules.json**

```json
{
  "rules": [
    {
      "match": {"host_provider": "aws", "site_type": "static"},
      "inject": {
        "agents": [
          "deployers/aws-s3-static",
          "testers/*",
          "utilities/cache-invalidator"
        ],
        "skills": [
          "aws/s3-upload",
          "aws/cloudfront-create",
          "aws/cloudfront-invalidate",
          "testing/*"
        ]
      }
    },
    {
      "match": {"host_provider": "aws", "site_type": "dynamic"},
      "inject": {
        "agents": [
          "deployers/aws-ec2-dynamic",
          "testers/*",
          "utilities/cache-invalidator"
        ],
        "skills": [
          "aws/ec2-launch",
          "aws/ec2-ssh",
          "aws/route53",
          "testing/*"
        ]
      }
    },
    {
      "match": {"host_provider": "azure", "site_type": "static"},
      "inject": {
        "agents": [
          "deployers/azure-blob-static",
          "testers/*"
        ],
        "skills": [
          "azure/blob-upload",
          "azure/cdn-create",
          "azure/cdn-purge",
          "testing/*"
        ]
      }
    },
    {
      "match": {"host_provider": "azure", "site_type": "dynamic"},
      "inject": {
        "agents": [
          "deployers/azure-vm-dynamic",
          "testers/*"
        ],
        "skills": [
          "azure/vm-launch",
          "azure/vm-ssh",
          "azure/dns-zone",
          "testing/*"
        ]
      }
    }
  ]
}
```

**Step 5: Run test to verify it passes**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_injection_engine.py -v -p no:anyio`
Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add backend/injection_engine.py backend/tests/test_injection_engine.py backend/injection_rules.json
git commit -m "feat: add injection engine for skills and agents"
```

---

## Phase 4: API Endpoints

### Task 4.1: Create User Endpoint

**Files:**
- Modify: `backend/app.py`
- Create: `backend/tests/test_api_endpoints.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_api_endpoints.py
import pytest
from unittest.mock import Mock, patch
import json


class TestCreateUserEndpoint:
    """Tests for POST /api/create-user endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_create_user_returns_execution_id(self, client):
        """POST /api/create-user returns execution_id."""
        with patch('app.UserManager') as mock_um, \
             patch('app.SessionCreator') as mock_sc, \
             patch('app.ExecutionTracker') as mock_et:

            mock_um.return_value.create_user.return_value = {
                "user_id": "test-guid",
                "is_new": True
            }
            mock_sc.return_value.create_session.return_value = "sess_001"
            mock_et.return_value.create_execution.return_value = "test-guid_sess_001"

            response = client.post('/api/create-user', json={
                "email": "test@example.com",
                "phone": "1234567890",
                "host_provider": "aws",
                "site_type": "static"
            })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert "execution_id" in data
            assert data["execution_id"] == "test-guid_sess_001"

    def test_create_user_validates_host_provider(self, client):
        """Invalid host_provider returns 400."""
        response = client.post('/api/create-user', json={
            "email": "test@example.com",
            "phone": "1234567890",
            "host_provider": "invalid",
            "site_type": "static"
        })

        assert response.status_code == 400

    def test_create_user_validates_site_type(self, client):
        """Invalid site_type returns 400."""
        response = client.post('/api/create-user', json={
            "email": "test@example.com",
            "phone": "1234567890",
            "host_provider": "aws",
            "site_type": "invalid"
        })

        assert response.status_code == 400


class TestStatusEndpoint:
    """Tests for GET /api/status/{execution_id} endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_status_returns_execution_state(self, client):
        """GET /api/status/{id} returns execution state."""
        with patch('app.ExecutionTracker') as mock_et:
            mock_et.return_value.get_status.return_value = {
                "execution_id": "test-guid_sess_001",
                "status": "running",
                "current_step": 3,
                "total_steps": 7,
                "logs": []
            }

            response = client.get('/api/status/test-guid_sess_001')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["status"] == "running"
            assert data["current_step"] == 3

    def test_status_not_found(self, client):
        """GET /api/status/{id} returns 404 for unknown id."""
        with patch('app.ExecutionTracker') as mock_et:
            mock_et.return_value.get_status.return_value = None

            response = client.get('/api/status/nonexistent')

            assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_api_endpoints.py -v -p no:anyio`
Expected: FAIL (endpoints don't exist yet)

**Step 3: Add endpoints to app.py**

Add to `backend/app.py`:

```python
# Add imports at top
from user_manager import UserManager
from session_creator import SessionCreator
from execution_tracker import ExecutionTracker
from injection_engine import InjectionEngine

# Initialize managers
user_manager = UserManager()
session_creator = SessionCreator()
execution_tracker = ExecutionTracker()
injection_engine = InjectionEngine()

# Valid values
VALID_HOST_PROVIDERS = ["aws", "azure"]
VALID_SITE_TYPES = ["static", "dynamic"]


@app.route('/api/create-user', methods=['POST'])
def create_user():
    """
    Create a new user and start deployment pipeline.

    Request body:
        email: User email
        phone: User phone
        host_provider: "aws" or "azure"
        site_type: "static" or "dynamic"

    Returns:
        execution_id for status polling
    """
    data = request.get_json()

    # Validate required fields
    required = ['email', 'phone', 'host_provider', 'site_type']
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    # Validate host_provider
    if data['host_provider'] not in VALID_HOST_PROVIDERS:
        return jsonify({
            "error": f"Invalid host_provider. Must be one of: {VALID_HOST_PROVIDERS}"
        }), 400

    # Validate site_type
    if data['site_type'] not in VALID_SITE_TYPES:
        return jsonify({
            "error": f"Invalid site_type. Must be one of: {VALID_SITE_TYPES}"
        }), 400

    # Create user (or get existing)
    user_result = user_manager.create_user(
        email=data['email'],
        phone=data['phone'],
        host_provider=data['host_provider'],
        site_type=data['site_type']
    )
    user_id = user_result['user_id']

    # Create session
    session_id = session_creator.create_session(
        user_id=user_id,
        host_provider=data['host_provider'],
        site_type=data['site_type']
    )

    # Create execution tracking
    execution_id = execution_tracker.create_execution(user_id, session_id)

    # Inject agents/skills into session
    session_path = session_creator.get_session_path(user_id, session_id)
    injection_engine.inject(
        data['host_provider'],
        data['site_type'],
        session_path
    )

    # TODO: Start background job pipeline
    # For now, just return the execution_id

    return jsonify({
        "execution_id": execution_id,
        "user_id": user_id,
        "session_id": session_id,
        "is_new_user": user_result['is_new']
    })


@app.route('/api/status/<execution_id>', methods=['GET'])
def get_status(execution_id):
    """
    Get execution status.

    Returns:
        Full execution state including status, progress, logs, result
    """
    status = execution_tracker.get_status(execution_id)

    if status is None:
        return jsonify({"error": "Execution not found"}), 404

    return jsonify(status)


@app.route('/api/user/<user_id>/sessions', methods=['GET'])
def list_user_sessions(user_id):
    """
    List all sessions for a user.

    Returns:
        List of session IDs
    """
    sessions = session_creator.list_sessions(user_id)
    return jsonify({"sessions": sessions})
```

**Step 4: Run test to verify it passes**

Run: `cd /mnt/c/Development/AI-Product-Site/tmux-builder/backend && python3 -m pytest tests/test_api_endpoints.py -v -p no:anyio`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add backend/app.py backend/tests/test_api_endpoints.py
git commit -m "feat: add create-user and status API endpoints"
```

---

## Phase 5: Agent & Skill Library

### Task 5.1: AWS Deployer Agent

**Files:**
- Create: `.claude/agents/deployers/aws-s3-static.md`

**Step 1: Create agent file**

```markdown
# AWS S3 Static Site Deployer Agent

You are a deployment agent specialized in deploying static websites to AWS S3 with CloudFront CDN.

## Your Capabilities

1. **Deploy static sites** to S3 bucket with CloudFront distribution
2. **Update existing deployments** by uploading new files and invalidating cache
3. **Verify deployments** by checking CloudFront URL responds correctly

## Configuration

- **AWS Profile:** sunwaretech
- **Default Region:** us-east-1

## Deployment Process

### Initial Deploy

1. Read deployment config from `deployment/config.json`
2. Use the `aws/s3-upload` skill to upload `source/` files to S3
3. Use the `aws/cloudfront-create` skill to create CloudFront distribution
4. Update `deployment/config.json` with bucket name, distribution ID, URL
5. Run health check on deployed URL
6. Capture screenshot
7. Report success with URL to user

### Redeploy (Update)

1. Read existing config from `deployment/config.json`
2. Upload updated files from `source/` to existing S3 bucket
3. Use `aws/cloudfront-invalidate` skill to invalidate cache
4. Wait for invalidation to complete
5. Run health check
6. Capture new screenshot
7. Report success to user

## Resource Naming

All resources follow naming pattern:
```
tmux-{guid_prefix}-{session_short}
```

Example: `tmux-a1b2c3d4-20260124143022`

## Required Tags

Apply these tags to ALL resources:

```json
{
  "Project": "tmux-builder",
  "UserGUID": "{user_id}",
  "SessionID": "{session_id}",
  "SiteType": "static",
  "CreatedBy": "tmux-builder-automation"
}
```

## Error Handling

- If S3 upload fails, retry up to 3 times
- If CloudFront creation fails, check if distribution already exists
- Log all errors with full details for debugging
- Report clear error messages to user

## Commands

When user asks to deploy:
```
I'll deploy your site to AWS S3 + CloudFront now.

1. Uploading files to S3...
2. Creating CloudFront distribution...
3. Running health check...
4. Capturing screenshot...

✅ Deployed successfully!
URL: https://d1234abcd.cloudfront.net
```
```

**Step 2: Commit**

```bash
mkdir -p .claude/agents/deployers
git add .claude/agents/deployers/aws-s3-static.md
git commit -m "feat: add AWS S3 static deployer agent"
```

---

### Task 5.2: AWS Skills

**Files:**
- Create: `.claude/skills/aws/s3-upload.md`
- Create: `.claude/skills/aws/cloudfront-create.md`
- Create: `.claude/skills/aws/cloudfront-invalidate.md`

**Step 1: Create skill files**

```markdown
# .claude/skills/aws/s3-upload.md

# S3 Upload Skill

Upload files to AWS S3 bucket.

## Usage

```bash
# Set AWS profile
export AWS_PROFILE=sunwaretech

# Upload single file
aws s3 cp source/index.html s3://{bucket_name}/index.html --content-type "text/html"

# Upload entire directory
aws s3 sync source/ s3://{bucket_name}/ --delete

# Upload with proper content types
aws s3 sync source/ s3://{bucket_name}/ \
  --exclude "*" \
  --include "*.html" --content-type "text/html" \
  --include "*.css" --content-type "text/css" \
  --include "*.js" --content-type "application/javascript"
```

## Parameters

- `bucket_name`: S3 bucket name (from deployment/config.json)
- `source_dir`: Source directory (default: source/)

## Required Tags

When creating bucket, apply tags:

```bash
aws s3api put-bucket-tagging --bucket {bucket_name} --tagging 'TagSet=[{Key=Project,Value=tmux-builder},{Key=UserGUID,Value={user_id}}]'
```
```

```markdown
# .claude/skills/aws/cloudfront-create.md

# CloudFront Create Skill

Create CloudFront distribution for S3 static website.

## Usage

```bash
export AWS_PROFILE=sunwaretech

# Create distribution
aws cloudfront create-distribution \
  --origin-domain-name {bucket_name}.s3.amazonaws.com \
  --default-root-object index.html

# Get distribution domain
aws cloudfront get-distribution --id {distribution_id} \
  --query 'Distribution.DomainName' --output text
```

## Full Distribution Config

Save to `cf-config.json`:

```json
{
  "CallerReference": "{bucket_name}-{timestamp}",
  "Origins": {
    "Quantity": 1,
    "Items": [{
      "Id": "S3-{bucket_name}",
      "DomainName": "{bucket_name}.s3.amazonaws.com",
      "S3OriginConfig": {"OriginAccessIdentity": ""}
    }]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-{bucket_name}",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
    "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
    "ForwardedValues": {"QueryString": false, "Cookies": {"Forward": "none"}},
    "MinTTL": 0,
    "DefaultTTL": 86400,
    "MaxTTL": 31536000,
    "Compress": true
  },
  "Comment": "tmux-builder: {user_id}/{session_id}",
  "Enabled": true,
  "DefaultRootObject": "index.html",
  "PriceClass": "PriceClass_100"
}
```

Then:
```bash
aws cloudfront create-distribution --distribution-config file://cf-config.json
```
```

```markdown
# .claude/skills/aws/cloudfront-invalidate.md

# CloudFront Cache Invalidation Skill

Invalidate CloudFront cache after updating S3 files.

## Usage

```bash
export AWS_PROFILE=sunwaretech

# Invalidate all files
aws cloudfront create-invalidation \
  --distribution-id {distribution_id} \
  --paths "/*"

# Invalidate specific files
aws cloudfront create-invalidation \
  --distribution-id {distribution_id} \
  --paths "/index.html" "/style.css" "/app.js"

# Check invalidation status
aws cloudfront get-invalidation \
  --distribution-id {distribution_id} \
  --id {invalidation_id}
```

## Parameters

- `distribution_id`: CloudFront distribution ID (from deployment/config.json)
- `paths`: Paths to invalidate (default: /*)

## Notes

- Invalidation takes 10-15 minutes to propagate globally
- First 1000 invalidations per month are free
- Use `/*` for full site updates
```

**Step 2: Commit**

```bash
mkdir -p .claude/skills/aws
git add .claude/skills/aws/
git commit -m "feat: add AWS S3 and CloudFront skills"
```

---

### Task 5.3: Testing Agents

**Files:**
- Create: `.claude/agents/testers/health-check.md`
- Create: `.claude/agents/testers/screenshot.md`

**Step 1: Create agent files**

```markdown
# .claude/agents/testers/health-check.md

# Health Check Agent

Verify deployed websites are responding correctly.

## Checks Performed

1. **HTTP Status**: URL returns 200 OK
2. **Content-Type**: Response is text/html
3. **Response Size**: Body > 100 bytes (not empty)
4. **Response Time**: Under 10 seconds

## Usage

After deployment, run health check:

```bash
# Simple check
curl -I -s https://{deployed_url} | head -1

# Full check with timing
curl -w "%{http_code} %{time_total}s %{size_download}bytes\n" \
  -o /dev/null -s https://{deployed_url}
```

## Output

Save results to `deployment/tests/health.json`:

```json
{
  "test": "health_check",
  "timestamp": "2026-01-24T14:35:00Z",
  "passed": true,
  "duration_ms": 245,
  "details": {
    "url": "https://d1234.cloudfront.net",
    "status_code": 200,
    "content_type": "text/html",
    "response_size_bytes": 4523
  }
}
```

## Retry Logic

- Retry up to 3 times on failure
- Wait 2 seconds between retries
- Report final result after all retries
```

```markdown
# .claude/agents/testers/screenshot.md

# Screenshot Capture Agent

Capture visual screenshots of deployed websites using Playwright.

## Usage

```bash
# Install playwright if needed
pip install playwright
playwright install chromium

# Capture screenshot (Python)
python -c "
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    page.goto('{deployed_url}', wait_until='networkidle')
    page.screenshot(path='deployment/tests/screenshot.png', full_page=True)
    browser.close()
"
```

## Output

- Full screenshot: `deployment/tests/screenshot.png`
- Thumbnail: `deployment/tests/screenshot_thumb.png`

## Result JSON

Save to `deployment/tests/screenshot.json`:

```json
{
  "test": "screenshot",
  "timestamp": "2026-01-24T14:35:30Z",
  "passed": true,
  "duration_ms": 3200,
  "details": {
    "url": "https://d1234.cloudfront.net",
    "path": "deployment/tests/screenshot.png",
    "thumbnail_path": "deployment/tests/screenshot_thumb.png",
    "viewport": {"width": 1920, "height": 1080}
  }
}
```
```

**Step 2: Commit**

```bash
mkdir -p .claude/agents/testers
git add .claude/agents/testers/
git commit -m "feat: add health check and screenshot agents"
```

---

## Summary

This plan contains **18 tasks** across **5 phases**:

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1.1-1.3 | Core Infrastructure (user_manager, execution_tracker, session_creator) |
| 2 | 2.1-2.3 | Cloud Deployment (cloud_config, aws_deployer, azure_deployer) |
| 3 | 3.1-3.3 | Testing Modules (health_checker, screenshot_capture, injection_engine) |
| 4 | 4.1 | API Endpoints (create-user, status) |
| 5 | 5.1-5.3 | Agent & Skill Library (AWS agents, skills, testing agents) |

All tasks follow TDD with:
- Failing test first
- Minimal implementation
- Test verification
- Commit after each task

AWS and Azure both use **sunwaretech** profile for authentication.
