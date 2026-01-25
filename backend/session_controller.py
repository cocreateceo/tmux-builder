"""High-level session orchestration and management."""

import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

from config import (
    SESSION_PREFIX,
    MARKER_TIMEOUT,
    MARKER_POLL_INTERVAL,
    CHAT_HISTORY_FILE,
    INITIALIZED_MARKER,
    PROCESSING_MARKER,
    COMPLETED_MARKER,
    get_user_session_path,
    get_markers_path
)
from tmux_helper import TmuxHelper

logger = logging.getLogger(__name__)


class SessionController:
    """Manages Claude CLI sessions via tmux."""

    def __init__(self, username: str = "default_user"):
        logger.info(f"Initializing SessionController for user: {username}")
        self.username = username
        self.session_path = get_user_session_path(username)
        self.markers_path = get_markers_path(username)
        self.chat_history_path = self.session_path / CHAT_HISTORY_FILE
        self.session_name = f"{SESSION_PREFIX}_{username}_{int(time.time())}"
        logger.info(f"Session path: {self.session_path}")
        logger.info(f"Session name: {self.session_name}")
        logger.info(f"Markers path: {self.markers_path}")
        logger.info(f"Chat history: {self.chat_history_path}")

    def initialize_session(self) -> bool:
        """Initialize a new Claude CLI session in tmux."""
        logger.info("=== INITIALIZING SESSION ===")
        try:
            # Create tmux session
            logger.info(f"Creating tmux session: {self.session_name}")
            logger.info(f"Working directory: {self.session_path}")
            if not TmuxHelper.create_session(self.session_name, str(self.session_path)):
                logger.error("Failed to create tmux session")
                return False
            logger.info("✓ Tmux session created")

            # Build and send initialization instructions
            logger.info("Building initialization instructions...")
            instructions = self._build_session_instructions()
            logger.info(f"Instructions length: {len(instructions)} chars")

            # Clear old markers
            logger.info("Clearing old markers...")
            self._clear_markers()

            # Send instructions
            logger.info("Sending initialization instructions to Claude...")
            if not TmuxHelper.send_instruction(self.session_name, instructions):
                logger.error("Failed to send instructions")
                return False
            logger.info("✓ Instructions sent")

            # Wait for initialized marker
            logger.info(f"Waiting for initialized marker (timeout: {MARKER_TIMEOUT}s)...")
            if self._wait_for_marker(INITIALIZED_MARKER, timeout=MARKER_TIMEOUT):
                logger.info("✓ Session initialized successfully")
                return True

            logger.error("Timeout waiting for initialized marker")
            return False

        except Exception as e:
            logger.error(f"Error initializing session: {e}", exc_info=True)
            return False

    def send_message(self, message: str) -> Optional[str]:
        """
        Send a message to Claude and wait for response.

        Returns the assistant's response or None if error/timeout.
        """
        logger.info("=== SENDING MESSAGE ===")
        logger.info(f"Message: {message[:100]}...")
        try:
            # Append user message to history
            logger.info("Appending user message to history...")
            self._append_to_history("user", message)

            # Clear completed marker from previous request
            completed_marker = self.markers_path / COMPLETED_MARKER
            if completed_marker.exists():
                logger.info("Clearing previous completed marker")
                completed_marker.unlink()

            # Send message via tmux
            logger.info(f"Sending message to tmux session: {self.session_name}")
            if not TmuxHelper.send_instruction(self.session_name, message):
                logger.error("Failed to send message via tmux")
                return None
            logger.info("✓ Message sent to Claude")

            # Wait for completion marker
            logger.info(f"Waiting for completion marker (timeout: {MARKER_TIMEOUT}s)...")
            if not self._wait_for_marker(COMPLETED_MARKER, timeout=MARKER_TIMEOUT):
                logger.error("Timeout waiting for completion marker")
                return "Timeout waiting for response. Please try again."
            logger.info("✓ Completion marker received")

            # Read response from chat history
            logger.info("Reading response from chat history...")
            response = self._get_new_assistant_response()
            logger.info(f"Response received: {response[:100] if response else 'None'}...")
            return response

        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            return None

    def get_chat_history(self) -> List[Dict]:
        """Load and return chat history."""
        if not self.chat_history_path.exists():
            return []

        messages = []
        try:
            with open(self.chat_history_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        messages.append(json.loads(line))
        except Exception as e:
            print(f"Error loading chat history: {e}")

        return messages

    def clear_session(self) -> bool:
        """Clear the session and reset state."""
        try:
            # Kill tmux session
            TmuxHelper.kill_session(self.session_name)

            # Clear chat history
            if self.chat_history_path.exists():
                self.chat_history_path.unlink()

            # Clear markers
            self._clear_markers()

            return True

        except Exception as e:
            print(f"Error clearing session: {e}")
            return False

    def _build_session_instructions(self) -> str:
        """Build comprehensive initialization instructions for Claude."""
        instructions = f"""
You are Claude, an AI assistant running in a tmux-based chat interface.

IMPORTANT INSTRUCTIONS:
1. Save all messages (both user and assistant) to: {self.chat_history_path}
   Format: One JSON object per line (JSONL format)
   Example: {{"role":"user","content":"message","timestamp":"2026-01-23T10:30:00Z"}}

2. Create marker files to signal processing state:
   - Create {self.markers_path / INITIALIZED_MARKER} when you're ready
   - Create {self.markers_path / PROCESSING_MARKER} when processing a request
   - Create {self.markers_path / COMPLETED_MARKER} when done with a response

3. For each user message:
   a. Save the user message to chat history
   b. Process the request
   c. Save your response to chat history
   d. Create the completed marker

4. Keep responses concise and helpful.

Please confirm you understand by creating the initialized marker file.
"""
        return instructions.strip()

    def _append_to_history(self, role: str, content: str):
        """Append a message to chat history."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        with open(self.chat_history_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(message) + '\n')

    def _get_new_assistant_response(self) -> str:
        """Read the latest assistant response from chat history."""
        messages = self.get_chat_history()

        # Find last assistant message
        for msg in reversed(messages):
            if msg.get('role') == 'assistant':
                return msg.get('content', '')

        return "No response received."

    def _wait_for_marker(self, marker_name: str, timeout: float) -> bool:
        """Poll for a marker file with timeout."""
        marker_path = self.markers_path / marker_name
        start_time = time.time()

        while time.time() - start_time < timeout:
            if marker_path.exists():
                return True
            time.sleep(MARKER_POLL_INTERVAL)

        return False

    def _clear_markers(self):
        """Clear all marker files."""
        for marker in [INITIALIZED_MARKER, PROCESSING_MARKER, COMPLETED_MARKER]:
            marker_path = self.markers_path / marker
            if marker_path.exists():
                marker_path.unlink()

    def is_active(self) -> bool:
        """Check if the session is active."""
        return TmuxHelper.session_exists(self.session_name)
