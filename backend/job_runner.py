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

        if not result.get("passed"):
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
