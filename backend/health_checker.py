"""Health Checker Module - HTTP health checks on deployed websites with retry logic."""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class HealthChecker:
    """Performs HTTP health checks on deployed websites with retry logic.

    Pass criteria:
    - status_code == 200
    - content_type contains "text/html"
    - response size > 100 bytes
    """

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        """Initialize health checker.

        Args:
            timeout: HTTP request timeout in seconds
            max_retries: Maximum number of retry attempts on connection error
            retry_delay: Seconds to wait between retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def check(self, url: str, output_path: Optional[str] = None) -> dict:
        """Perform health check on a URL.

        Args:
            url: The URL to check
            output_path: Optional path to save result JSON

        Returns:
            dict with: test, timestamp, passed, duration_ms, attempts, details, error
        """
        start_time = time.time()
        timestamp = datetime.now(timezone.utc).isoformat()

        attempts = 0
        last_error = None
        response = None

        # Retry loop for connection errors
        while attempts < self.max_retries:
            attempts += 1
            try:
                logger.info(f"Health check attempt {attempts}/{self.max_retries} for {url}")
                response = requests.get(url, timeout=self.timeout)
                break  # Success, exit retry loop
            except requests.exceptions.ConnectionError as e:
                last_error = str(e)
                logger.warning(f"Connection error on attempt {attempts}: {last_error}")
                if attempts < self.max_retries:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error on attempt {attempts}: {last_error}")
                break  # Don't retry on non-connection errors

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Build result
        if response is not None:
            status_code = response.status_code
            content_type = response.headers.get("Content-Type", "")
            response_size = len(response.content)

            # Check pass criteria
            passed = (
                status_code == 200 and
                "text/html" in content_type and
                response_size > 100
            )

            # Determine error message if failed
            error = None
            if not passed:
                reasons = []
                if status_code != 200:
                    reasons.append(f"status code {status_code} (expected 200)")
                if "text/html" not in content_type:
                    reasons.append(f"content type '{content_type}' does not contain 'text/html'")
                if response_size <= 100:
                    reasons.append(f"response size {response_size} bytes is <= 100 bytes")
                error = "Health check failed: " + "; ".join(reasons)

            result = {
                "test": "health_check",
                "timestamp": timestamp,
                "passed": passed,
                "duration_ms": duration_ms,
                "attempts": attempts,
                "details": {
                    "url": url,
                    "status_code": status_code,
                    "content_type": content_type,
                    "response_size_bytes": response_size
                },
                "error": error
            }
        else:
            # All retries failed
            result = {
                "test": "health_check",
                "timestamp": timestamp,
                "passed": False,
                "duration_ms": duration_ms,
                "attempts": attempts,
                "details": {
                    "url": url,
                    "status_code": None,
                    "content_type": None,
                    "response_size_bytes": None
                },
                "error": f"Connection failed after {attempts} attempts: {last_error}"
            }

        # Save to file if output_path provided
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2)
            logger.info(f"Health check result saved to {output_path}")

        return result
