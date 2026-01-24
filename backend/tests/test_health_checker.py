"""Tests for HealthChecker - HTTP health checks on deployed websites with retry logic."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
import sys
import json
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent))

from health_checker import HealthChecker


class TestHealthChecker:
    """Test health checker with mocked requests interactions."""

    SAMPLE_URL = "https://example.cloudfront.net"

    def test_health_check_success(self):
        """Returns passed=True for 200 response with text/html content."""
        with patch("health_checker.requests") as mock_requests:
            # Set up mock response for successful health check
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
            mock_response.content = b"<html><head><title>Test</title></head><body>Hello World</body></html>" * 10
            mock_requests.get.return_value = mock_response

            checker = HealthChecker(timeout=30, max_retries=3, retry_delay=0.1)
            result = checker.check(self.SAMPLE_URL)

            # Verify request was made
            mock_requests.get.assert_called_once_with(self.SAMPLE_URL, timeout=30)

            # Verify result structure
            assert result["test"] == "health_check"
            assert "timestamp" in result
            assert result["passed"] is True
            assert "duration_ms" in result
            assert result["attempts"] == 1
            assert result["error"] is None

            # Verify details
            assert result["details"]["url"] == self.SAMPLE_URL
            assert result["details"]["status_code"] == 200
            assert "text/html" in result["details"]["content_type"]
            assert result["details"]["response_size_bytes"] > 100

    def test_health_check_failure_on_500(self):
        """Returns passed=False for 500 server error response."""
        with patch("health_checker.requests") as mock_requests:
            # Set up mock response for 500 error
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.headers = {"Content-Type": "text/html"}
            mock_response.content = b"<html><body>Internal Server Error</body></html>"
            mock_requests.get.return_value = mock_response

            checker = HealthChecker(timeout=30, max_retries=3, retry_delay=0.1)
            result = checker.check(self.SAMPLE_URL)

            # Verify result indicates failure
            assert result["test"] == "health_check"
            assert result["passed"] is False
            assert result["attempts"] == 1
            assert result["details"]["status_code"] == 500
            # Error should indicate the reason for failure
            assert result["error"] is not None
            assert "500" in result["error"] or "status" in result["error"].lower()

    def test_health_check_retries_on_failure(self):
        """Retries on ConnectionError up to max_retries times."""
        with patch("health_checker.requests") as mock_requests:
            with patch("health_checker.time.sleep") as mock_sleep:
                # Set up mock to fail twice then succeed
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.headers = {"Content-Type": "text/html"}
                mock_response.content = b"<html><body>Success after retries</body></html>" * 5

                # First two calls raise ConnectionError, third succeeds
                mock_requests.exceptions.ConnectionError = ConnectionError
                mock_requests.get.side_effect = [
                    ConnectionError("Connection refused"),
                    ConnectionError("Connection refused"),
                    mock_response
                ]

                checker = HealthChecker(timeout=30, max_retries=3, retry_delay=2.0)
                result = checker.check(self.SAMPLE_URL)

                # Verify retries happened
                assert mock_requests.get.call_count == 3
                assert result["attempts"] == 3
                assert result["passed"] is True

                # Verify sleep was called between retries
                assert mock_sleep.call_count == 2

    def test_health_check_saves_result(self):
        """Saves result to file when output_path is provided."""
        with patch("health_checker.requests") as mock_requests:
            # Set up mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
            mock_response.content = b"<html><body>Test content for save</body></html>" * 5
            mock_requests.get.return_value = mock_response

            checker = HealthChecker(timeout=30, max_retries=3, retry_delay=0.1)

            # Use temporary file for output
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
                output_path = tmp.name

            try:
                result = checker.check(self.SAMPLE_URL, output_path=output_path)

                # Verify file was created and contains valid JSON
                assert Path(output_path).exists()

                with open(output_path, "r") as f:
                    saved_result = json.load(f)

                # Verify saved result matches returned result
                assert saved_result["test"] == result["test"]
                assert saved_result["passed"] == result["passed"]
                assert saved_result["timestamp"] == result["timestamp"]
                assert saved_result["details"]["url"] == result["details"]["url"]
            finally:
                # Cleanup
                Path(output_path).unlink(missing_ok=True)
