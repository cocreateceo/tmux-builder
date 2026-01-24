"""Screenshot Capture Module - Playwright screenshot capture with thumbnails."""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

# Playwright is required but imported this way to support mocking in tests
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    PLAYWRIGHT_AVAILABLE = False

# PIL is optional for thumbnail creation
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None

logger = logging.getLogger(__name__)


class ScreenshotCapture:
    """Captures full-page screenshots of deployed websites using Playwright.

    Features:
    - Configurable viewport dimensions
    - Optional network idle wait
    - Automatic thumbnail creation using PIL
    - Detailed result JSON with timing information
    """

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        wait_for_network: bool = True,
        timeout: int = 30000
    ):
        """Initialize screenshot capturer.

        Args:
            width: Viewport width in pixels
            height: Viewport height in pixels
            wait_for_network: Wait for network to be idle before capture
            timeout: Page load timeout in milliseconds
        """
        self.width = width
        self.height = height
        self.wait_for_network = wait_for_network
        self.timeout = timeout

    def capture(
        self,
        url: str,
        output_path: str,
        create_thumbnail: bool = True,
        thumbnail_size: Tuple[int, int] = (400, 225)
    ) -> dict:
        """Capture screenshot of a URL.

        Args:
            url: The URL to capture
            output_path: Path to save the screenshot PNG
            create_thumbnail: Whether to create a thumbnail image
            thumbnail_size: Thumbnail dimensions (width, height)

        Returns:
            dict with: test, timestamp, passed, duration_ms, details, error
        """
        start_time = time.time()
        timestamp = datetime.now(timezone.utc).isoformat()

        output_file = Path(output_path)
        thumbnail_path = None

        # Ensure parent directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with sync_playwright() as playwright:
                # Launch browser
                logger.info(f"Launching browser for screenshot of {url}")
                browser = playwright.chromium.launch(headless=True)

                # Create context with viewport size
                context = browser.new_context(
                    viewport={"width": self.width, "height": self.height}
                )

                # Create page and navigate
                page = context.new_page()

                # Set timeout
                page.set_default_timeout(self.timeout)

                # Navigate to URL
                wait_until = "networkidle" if self.wait_for_network else "load"
                logger.info(f"Navigating to {url} (wait_until={wait_until})")
                page.goto(url, wait_until=wait_until)

                # Take full-page screenshot
                logger.info(f"Capturing screenshot to {output_path}")
                page.screenshot(path=str(output_file), full_page=True)

                # Close browser
                browser.close()

            # Create thumbnail if requested and PIL is available
            if create_thumbnail and PIL_AVAILABLE and Image is not None:
                thumbnail_path = self._create_thumbnail(
                    output_file, thumbnail_size
                )

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            result = {
                "test": "screenshot",
                "timestamp": timestamp,
                "passed": True,
                "duration_ms": duration_ms,
                "details": {
                    "url": url,
                    "path": str(output_file),
                    "thumbnail_path": str(thumbnail_path) if thumbnail_path else None,
                    "viewport": {
                        "width": self.width,
                        "height": self.height
                    }
                },
                "error": None
            }

            logger.info(f"Screenshot captured successfully in {duration_ms}ms")

        except Exception as e:
            # Calculate duration even on failure
            duration_ms = int((time.time() - start_time) * 1000)

            logger.error(f"Screenshot capture failed: {e}")
            result = {
                "test": "screenshot",
                "timestamp": timestamp,
                "passed": False,
                "duration_ms": duration_ms,
                "details": {
                    "url": url,
                    "path": str(output_file),
                    "thumbnail_path": None,
                    "viewport": {
                        "width": self.width,
                        "height": self.height
                    }
                },
                "error": str(e)
            }

        return result

    def _create_thumbnail(
        self,
        image_path: Path,
        size: Tuple[int, int]
    ) -> Optional[Path]:
        """Create a thumbnail from the screenshot.

        Args:
            image_path: Path to the source image
            size: Thumbnail dimensions (width, height)

        Returns:
            Path to thumbnail file, or None if creation failed
        """
        try:
            # Calculate thumbnail path
            thumb_path = image_path.parent / f"{image_path.stem}_thumb{image_path.suffix}"

            # Open image and create thumbnail
            logger.info(f"Creating thumbnail at {thumb_path}")
            img = Image.open(image_path)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(thumb_path)

            return thumb_path

        except Exception as e:
            logger.warning(f"Failed to create thumbnail: {e}")
            return None
