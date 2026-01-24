"""Tests for ScreenshotCapture - Playwright screenshot capture with thumbnails."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys
import json
import tempfile

# Mock playwright before importing the module under test
sys.modules['playwright'] = MagicMock()
sys.modules['playwright.sync_api'] = MagicMock()

sys.path.insert(0, str(Path(__file__).parent.parent))

from screenshot_capture import ScreenshotCapture


class TestScreenshotCapture:
    """Test screenshot capture with mocked Playwright and PIL interactions."""

    SAMPLE_URL = "https://example.cloudfront.net"

    def test_capture_saves_screenshot(self):
        """Captures and saves PNG file to specified path."""
        with patch("screenshot_capture.sync_playwright") as mock_playwright:
            # Set up mock Playwright chain
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_context = MagicMock()

            mock_playwright_instance = MagicMock()
            mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page

            # Create temp directory for output
            with tempfile.TemporaryDirectory() as tmp_dir:
                output_path = Path(tmp_dir) / "screenshots" / "test_screenshot.png"

                capturer = ScreenshotCapture(width=1920, height=1080)
                result = capturer.capture(
                    self.SAMPLE_URL,
                    str(output_path),
                    create_thumbnail=False
                )

                # Verify Playwright was used correctly
                mock_playwright_instance.chromium.launch.assert_called_once()
                mock_browser.new_context.assert_called_once()
                mock_page.goto.assert_called_once()
                mock_page.screenshot.assert_called_once()

                # Verify result structure
                assert result["test"] == "screenshot"
                assert result["passed"] is True
                assert result["details"]["url"] == self.SAMPLE_URL
                assert result["details"]["path"] == str(output_path)
                assert result["details"]["viewport"]["width"] == 1920
                assert result["details"]["viewport"]["height"] == 1080

    def test_capture_creates_thumbnail(self):
        """Creates thumbnail when enabled and PIL is available."""
        with patch("screenshot_capture.sync_playwright") as mock_playwright:
            with patch("screenshot_capture.Image") as mock_image_module:
                with patch("screenshot_capture.PIL_AVAILABLE", True):
                    # Set up mock Playwright chain
                    mock_browser = MagicMock()
                    mock_page = MagicMock()
                    mock_context = MagicMock()

                    mock_playwright_instance = MagicMock()
                    mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
                    mock_playwright_instance.chromium.launch.return_value = mock_browser
                    mock_browser.new_context.return_value = mock_context
                    mock_context.new_page.return_value = mock_page

                    # Set up mock PIL Image
                    mock_image = MagicMock()
                    mock_image_module.open.return_value = mock_image
                    mock_image_module.Resampling.LANCZOS = 1  # Mock the LANCZOS constant

                    # Create temp directory for output
                    with tempfile.TemporaryDirectory() as tmp_dir:
                        output_path = Path(tmp_dir) / "test_screenshot.png"
                        expected_thumb_path = Path(tmp_dir) / "test_screenshot_thumb.png"

                        capturer = ScreenshotCapture(width=1920, height=1080)
                        result = capturer.capture(
                            self.SAMPLE_URL,
                            str(output_path),
                            create_thumbnail=True,
                            thumbnail_size=(400, 225)
                        )

                        # Verify PIL was used for thumbnail creation
                        mock_image_module.open.assert_called_once()
                        mock_image.thumbnail.assert_called_once_with(
                            (400, 225),
                            mock_image_module.Resampling.LANCZOS
                        )
                        mock_image.save.assert_called_once()

                        # Verify thumbnail path in result
                        assert result["passed"] is True
                        assert result["details"]["thumbnail_path"] == str(expected_thumb_path)

    def test_capture_result_format(self):
        """Result has all required fields with correct structure."""
        with patch("screenshot_capture.sync_playwright") as mock_playwright:
            # Set up mock Playwright chain
            mock_browser = MagicMock()
            mock_page = MagicMock()
            mock_context = MagicMock()

            mock_playwright_instance = MagicMock()
            mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
            mock_playwright_instance.chromium.launch.return_value = mock_browser
            mock_browser.new_context.return_value = mock_context
            mock_context.new_page.return_value = mock_page

            # Create temp directory for output
            with tempfile.TemporaryDirectory() as tmp_dir:
                output_path = Path(tmp_dir) / "test_screenshot.png"

                capturer = ScreenshotCapture(width=1920, height=1080, timeout=30000)
                result = capturer.capture(
                    self.SAMPLE_URL,
                    str(output_path),
                    create_thumbnail=False
                )

                # Verify all required top-level fields exist
                assert "test" in result
                assert "timestamp" in result
                assert "passed" in result
                assert "duration_ms" in result
                assert "details" in result
                assert "error" in result

                # Verify field types
                assert result["test"] == "screenshot"
                assert isinstance(result["timestamp"], str)
                assert isinstance(result["passed"], bool)
                assert isinstance(result["duration_ms"], int)
                assert isinstance(result["details"], dict)

                # Verify details structure
                details = result["details"]
                assert "url" in details
                assert "path" in details
                assert "thumbnail_path" in details
                assert "viewport" in details
                assert isinstance(details["viewport"], dict)
                assert "width" in details["viewport"]
                assert "height" in details["viewport"]

                # For successful capture without thumbnail
                assert result["error"] is None
                assert details["thumbnail_path"] is None

    def test_capture_handles_playwright_error(self):
        """Returns passed=False with error message on Playwright failure."""
        with patch("screenshot_capture.sync_playwright") as mock_playwright:
            # Set up mock to raise an exception
            mock_playwright_instance = MagicMock()
            mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
            mock_playwright_instance.chromium.launch.side_effect = Exception("Browser launch failed")

            with tempfile.TemporaryDirectory() as tmp_dir:
                output_path = Path(tmp_dir) / "test_screenshot.png"

                capturer = ScreenshotCapture(width=1920, height=1080)
                result = capturer.capture(
                    self.SAMPLE_URL,
                    str(output_path),
                    create_thumbnail=False
                )

                # Verify result indicates failure
                assert result["test"] == "screenshot"
                assert result["passed"] is False
                assert result["error"] is not None
                assert "Browser launch failed" in result["error"]
