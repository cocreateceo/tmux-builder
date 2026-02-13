"""
Generate per-session notify.sh script from template.

This module creates a session-specific notify.sh script with the GUID baked in,
allowing Claude CLI to easily send progress updates to the UI.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Get the directory where this script is located
BACKEND_DIR = Path(__file__).parent
TEMPLATE_PATH = BACKEND_DIR / "scripts" / "notify_template.sh"


def generate_notify_script(session_path: Path, guid: str) -> Path:
    """
    Generate a session-specific notify.sh script.

    Args:
        session_path: Path to the session directory (e.g., sessions/<guid>/)
        guid: The session GUID to bake into the script

    Returns:
        Path to the generated notify.sh script
    """
    try:
        # Read template
        if not TEMPLATE_PATH.exists():
            raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")

        template_content = TEMPLATE_PATH.read_text()

        # Replace placeholder with actual GUID
        script_content = template_content.replace("{{GUID}}", guid)

        # Ensure session directory exists
        session_path.mkdir(parents=True, exist_ok=True)

        # Write notify.sh
        notify_path = session_path / "notify.sh"
        notify_path.write_text(script_content)

        # Make executable
        os.chmod(notify_path, 0o755)

        logger.info(f"Generated notify.sh for session {guid} at {notify_path}")
        return notify_path

    except Exception as e:
        logger.error(f"Failed to generate notify.sh: {e}")
        raise


def get_notify_script_path(guid: str) -> Path:
    """Get the absolute path to notify.sh for a session."""
    from config import ACTIVE_SESSIONS_DIR
    return ACTIVE_SESSIONS_DIR / guid / "notify.sh"


def get_notify_instructions(guid: str) -> str:
    """
    Get instructions for Claude on how to use notify.sh.

    Returns a string that can be included in Claude's prompt.
    Uses absolute path to avoid working directory issues.
    """
    notify_path = get_notify_script_path(guid)
    return f"""
## Progress Updates

Use the notify.sh script to send progress updates to the user interface.

**IMPORTANT:** Use the absolute path: {notify_path}

```bash
{notify_path} ack                          # Acknowledge you received the task
{notify_path} status "Analyzing code..."   # Send status message
{notify_path} working "Refactoring auth"   # What you're currently working on
{notify_path} progress 50                  # Report progress percentage (0-100)
{notify_path} found "3 bugs in login.py"   # Report findings
{notify_path} done                         # Signal task completed
{notify_path} error "Config not found"     # Report an error
```

**Important:** Call `{notify_path} ack` immediately after receiving a task to confirm you're working on it.
Send periodic status updates so the user knows you're making progress.
Call `{notify_path} done` when you've completed the task.
""".strip()
