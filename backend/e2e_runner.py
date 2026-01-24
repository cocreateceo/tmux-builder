"""
E2E Test Runner - Generate and execute end-to-end tests.

Two-phase approach:
1. Claude generates Playwright tests based on deployed site
2. Python executes tests and collects results
"""

import json
import subprocess
import logging
from datetime import datetime, timezone
from pathlib import Path

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
