"""
DEPRECATED: Marker file utilities for file-based REPL protocol.

This module is deprecated in favor of PTY streaming (pty_manager.py).
Kept for backwards compatibility with the main branch.

For new code, use:
- pty_manager.py for PTY session management
- stream_controller.py for high-level streaming control
- WebSocket endpoint /ws/{guid} for real-time output

Legacy Protocol (marker-based):
1. ready.marker   - Claude creates when ready for input
2. ack.marker     - Claude creates when prompt received
3. completed.marker - Claude creates when task done
4. status.json    - Claude updates with progress
"""

import warnings
warnings.warn(
    "marker_utils.py is deprecated. Use pty_manager.py for PTY streaming.",
    DeprecationWarning,
    stacklevel=2
)

import time
import logging
from pathlib import Path
from typing import Optional

from config import (
    get_markers_path,
    get_marker_file,
    READY_MARKER,
    ACK_MARKER,
    COMPLETED_MARKER,
    MARKER_POLL_INTERVAL,
    READY_MARKER_TIMEOUT,
    ACK_MARKER_TIMEOUT,
    COMPLETED_MARKER_TIMEOUT,
)

logger = logging.getLogger(__name__)


def create_marker(guid: str, marker_name: str) -> Path:
    """
    Create a marker file.

    Args:
        guid: Session GUID
        marker_name: Name of marker file

    Returns:
        Path to created marker file

    Raises:
        OSError: If marker cannot be created due to permissions
    """
    marker_path = get_marker_file(guid, marker_name)
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.touch()
        logger.debug(f"Created marker: {marker_path}")
        return marker_path
    except Exception as e:
        logger.error(f"Failed to create marker {marker_path}: {e}")
        raise


def delete_marker(guid: str, marker_name: str) -> bool:
    """
    Delete a marker file if it exists.

    Args:
        guid: Session GUID
        marker_name: Name of marker file

    Returns:
        True if deleted, False if didn't exist or error
    """
    marker_path = get_marker_file(guid, marker_name)
    try:
        marker_path.unlink()
        logger.debug(f"Deleted marker: {marker_path}")
        return True
    except FileNotFoundError:
        # File already deleted (race condition) - that's fine
        return False
    except Exception as e:
        logger.error(f"Failed to delete marker {marker_path}: {e}")
        return False


def marker_exists(guid: str, marker_name: str) -> bool:
    """
    Check if a marker file exists.

    Args:
        guid: Session GUID
        marker_name: Name of marker file

    Returns:
        True if marker exists
    """
    return get_marker_file(guid, marker_name).exists()


def wait_for_marker(
    guid: str,
    marker_name: str,
    timeout: Optional[float] = None,
    poll_interval: float = MARKER_POLL_INTERVAL,
    settle_delay: float = 2.0
) -> bool:
    """
    Wait for a marker file to appear, then wait for Claude to settle.

    Args:
        guid: Session GUID
        marker_name: Name of marker file to wait for
        timeout: Maximum seconds to wait (None = use default for marker type)
        poll_interval: Seconds between checks
        settle_delay: Seconds to wait AFTER marker appears (let Claude finish output)

    Returns:
        True if marker appeared, False if timeout
    """
    # Use default timeout based on marker type
    if timeout is None:
        if marker_name == READY_MARKER:
            timeout = READY_MARKER_TIMEOUT
        elif marker_name == ACK_MARKER:
            timeout = ACK_MARKER_TIMEOUT
        elif marker_name == COMPLETED_MARKER:
            timeout = COMPLETED_MARKER_TIMEOUT
        else:
            timeout = 60  # Default fallback

    marker_path = get_marker_file(guid, marker_name)
    marker_dir = marker_path.parent
    logger.info(f"Waiting for marker: {marker_path} (timeout: {timeout}s)")

    start_time = time.time()
    while time.time() - start_time < timeout:
        # WSL filesystem hack: list directory to force cache refresh
        # This helps with inter-process file visibility delays on /mnt/c/
        try:
            # Force directory refresh by listing contents
            files_in_dir = list(marker_dir.iterdir())
            marker_exists = marker_path in files_in_dir or marker_path.exists()
        except OSError:
            marker_exists = marker_path.exists()

        if marker_exists:
            elapsed = time.time() - start_time
            logger.info(f"Marker appeared after {elapsed:.1f}s: {marker_path}")
            # CRITICAL: Wait for Claude to finish outputting before returning
            # This prevents sending next instruction while Claude is still writing
            logger.info(f"Waiting {settle_delay}s for Claude to settle...")
            time.sleep(settle_delay)
            return True
        time.sleep(poll_interval)

    logger.warning(f"Timeout waiting for marker: {marker_path}")
    return False


def clear_markers(guid: str, markers: Optional[list] = None) -> int:
    """
    Clear specified markers (or all protocol markers).

    Args:
        guid: Session GUID
        markers: List of marker names to clear, or None for all

    Returns:
        Number of markers deleted
    """
    if markers is None:
        markers = [READY_MARKER, ACK_MARKER, COMPLETED_MARKER]

    count = 0
    for marker_name in markers:
        if delete_marker(guid, marker_name):
            count += 1

    logger.debug(f"Cleared {count} markers for guid {guid}")
    return count


def clear_for_new_message(guid: str) -> None:
    """
    Clear markers in preparation for sending a new message.

    Clears ack.marker and completed.marker, preserving ready.marker.
    """
    delete_marker(guid, ACK_MARKER)
    delete_marker(guid, COMPLETED_MARKER)
    logger.debug(f"Cleared message markers for guid {guid}")


def get_all_marker_paths(guid: str) -> dict:
    """
    Get paths to all protocol marker files.

    Args:
        guid: Session GUID

    Returns:
        Dict mapping marker names to their paths
    """
    return {
        'ready': get_marker_file(guid, READY_MARKER),
        'ack': get_marker_file(guid, ACK_MARKER),
        'completed': get_marker_file(guid, COMPLETED_MARKER),
    }
