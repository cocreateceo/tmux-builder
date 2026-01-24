"""Execution Tracker - tracks async pipeline execution status with deep logging."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

# Default executions directory (can be patched in tests)
EXECUTIONS_DIR = Path(__file__).parent.parent / "executions"

# Pipeline steps constant
PIPELINE_STEPS = [
    {"id": 1, "name": "create_user", "description": "Create GUID folder & registry entry"},
    {"id": 2, "name": "create_session", "description": "Initialize session folder structure"},
    {"id": 3, "name": "generate_site", "description": "Claude generates initial website code"},
    {"id": 4, "name": "deploy", "description": "Deploy to AWS/Azure"},
    {"id": 5, "name": "health_check", "description": "Verify URL returns 200 OK"},
    {"id": 6, "name": "screenshot", "description": "Capture visual snapshot"},
    {"id": 7, "name": "e2e_tests", "description": "Generate & run E2E tests"},
]


class ExecutionTracker:
    """Tracks pipeline execution status and provides deep logging for debugging."""

    def __init__(self):
        """Initialize ExecutionTracker with executions directory."""
        # Import dynamically to support patching in tests
        import execution_tracker
        self._executions_dir = execution_tracker.EXECUTIONS_DIR
        self._ensure_executions_dir()

    def _ensure_executions_dir(self) -> None:
        """Ensure the executions directory exists."""
        self._executions_dir.mkdir(parents=True, exist_ok=True)

    def _get_execution_path(self, execution_id: str) -> Path:
        """Get path to execution JSON file."""
        return self._executions_dir / f"{execution_id}.json"

    def _load_execution(self, execution_id: str) -> Optional[dict]:
        """Load execution state from file."""
        execution_path = self._get_execution_path(execution_id)
        if execution_path.exists():
            return json.loads(execution_path.read_text())
        return None

    def _save_execution(self, execution_id: str, state: dict) -> None:
        """Save execution state to file."""
        execution_path = self._get_execution_path(execution_id)
        execution_path.write_text(json.dumps(state, indent=2))

    def _get_timestamp(self) -> str:
        """Get current ISO timestamp."""
        return datetime.now(timezone.utc).isoformat()

    def create_execution(self, user_id: str, session_id: str) -> str:
        """
        Create a new execution tracking entry.

        Args:
            user_id: User's GUID
            session_id: Session identifier

        Returns:
            execution_id in format {user_id}_{session_id}
        """
        execution_id = f"{user_id}_{session_id}"
        now = self._get_timestamp()

        # Initial execution state
        state = {
            "execution_id": execution_id,
            "user_id": user_id,
            "session_id": session_id,
            "status": "pending",
            "current_step": 0,
            "total_steps": len(PIPELINE_STEPS),
            "created_at": now,
            "updated_at": now,
            "logs": [],
            "result": None,
            "error": None
        }

        self._save_execution(execution_id, state)
        return execution_id

    def get_status(self, execution_id: str) -> Optional[dict]:
        """
        Get full execution state.

        Args:
            execution_id: Execution identifier

        Returns:
            Full execution state dict or None if not found
        """
        return self._load_execution(execution_id)

    def update_status(
        self,
        execution_id: str,
        status: Optional[str] = None,
        current_step: Optional[int] = None
    ) -> None:
        """
        Update execution status and/or current step.

        Args:
            execution_id: Execution identifier
            status: New status (pending|running|completed|failed)
            current_step: Current pipeline step number
        """
        state = self._load_execution(execution_id)
        if not state:
            return

        if status is not None:
            state["status"] = status
        if current_step is not None:
            state["current_step"] = current_step

        state["updated_at"] = self._get_timestamp()
        self._save_execution(execution_id, state)

    def log(
        self,
        execution_id: str,
        level: str,
        message: str,
        step: Optional[int] = None,
        step_name: Optional[str] = None,
        details: Optional[dict] = None,
        trace_id: Optional[str] = None
    ) -> None:
        """
        Add a log entry to the execution.

        Args:
            execution_id: Execution identifier
            level: Log level (INFO|WARN|ERROR|DEBUG)
            message: Log message
            step: Pipeline step number
            step_name: Pipeline step name
            details: Additional details dict
            trace_id: Trace identifier for distributed tracing
        """
        state = self._load_execution(execution_id)
        if not state:
            return

        log_entry = {
            "timestamp": self._get_timestamp(),
            "level": level,
            "message": message,
            "step": step,
            "step_name": step_name,
            "details": details,
            "trace_id": trace_id
        }

        state["logs"].append(log_entry)
        state["updated_at"] = self._get_timestamp()
        self._save_execution(execution_id, state)

    def set_result(self, execution_id: str, result: Any) -> None:
        """
        Set final result and mark execution as completed.

        Args:
            execution_id: Execution identifier
            result: Final result data
        """
        state = self._load_execution(execution_id)
        if not state:
            return

        state["result"] = result
        state["status"] = "completed"
        state["updated_at"] = self._get_timestamp()
        self._save_execution(execution_id, state)

    def set_error(self, execution_id: str, error: Any) -> None:
        """
        Set error and mark execution as failed.

        Args:
            execution_id: Execution identifier
            error: Error data
        """
        state = self._load_execution(execution_id)
        if not state:
            return

        state["error"] = error
        state["status"] = "failed"
        state["updated_at"] = self._get_timestamp()
        self._save_execution(execution_id, state)
