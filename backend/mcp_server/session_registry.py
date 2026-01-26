"""
Session Registry for MCP Server.

Tracks active sessions, their state, and provides async waiting
for response completion.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class SessionRegistry:
    """Track active sessions and their responses."""

    def __init__(self):
        self._sessions: dict[str, dict[str, Any]] = {}
        self._response_events: dict[str, asyncio.Event] = {}
        self._response_cache: dict[str, str] = {}

    def register_session(self, guid: str) -> None:
        """Register a new session."""
        if guid in self._sessions:
            logger.info(f"Session already registered: {guid}")
            return

        self._sessions[guid] = {
            'ack_received': False,
            'progress': 0,
            'status': '',
            'phase': '',
            'response': None,
            'complete': False,
            'success': None,
            'error': None,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'updated_at': datetime.utcnow().isoformat() + 'Z'
        }
        self._response_events[guid] = asyncio.Event()
        logger.info(f"Session registered: {guid}")

    def unregister_session(self, guid: str) -> None:
        """Unregister a session."""
        if guid in self._sessions:
            del self._sessions[guid]
        if guid in self._response_events:
            del self._response_events[guid]
        if guid in self._response_cache:
            del self._response_cache[guid]
        logger.info(f"Session unregistered: {guid}")

    def get_session(self, guid: str) -> dict[str, Any] | None:
        """Get session data."""
        return self._sessions.get(guid)

    def session_exists(self, guid: str) -> bool:
        """Check if session exists."""
        return guid in self._sessions

    def update_session(self, guid: str, **kwargs) -> None:
        """Update session data."""
        if guid not in self._sessions:
            self.register_session(guid)

        self._sessions[guid].update(kwargs)
        self._sessions[guid]['updated_at'] = datetime.utcnow().isoformat() + 'Z'

    def set_ack(self, guid: str) -> None:
        """Mark session as acknowledged."""
        self.update_session(guid, ack_received=True)

    def set_progress(self, guid: str, percent: int) -> None:
        """Update progress percentage."""
        self.update_session(guid, progress=percent)

    def set_status(self, guid: str, message: str, phase: str = '') -> None:
        """Update status message and phase."""
        self.update_session(guid, status=message, phase=phase)

    def set_response(self, guid: str, response: str) -> None:
        """Set the response for a session."""
        if guid not in self._sessions:
            self.register_session(guid)
        self._sessions[guid]['response'] = response
        self._response_cache[guid] = response
        logger.info(f"Response set for session: {guid} ({len(response)} chars)")

    def get_response(self, guid: str) -> str | None:
        """Get the cached response for a session."""
        return self._response_cache.get(guid)

    def set_complete(self, guid: str, success: bool = True) -> None:
        """Mark session as complete and signal waiting coroutines."""
        if guid not in self._sessions:
            self.register_session(guid)

        self._sessions[guid]['complete'] = True
        self._sessions[guid]['success'] = success
        self._sessions[guid]['completed_at'] = datetime.utcnow().isoformat() + 'Z'

        if guid in self._response_events:
            self._response_events[guid].set()

        logger.info(f"Session completed: {guid} (success={success})")

    def set_error(self, guid: str, error: str, recoverable: bool = False) -> None:
        """Set error for a session."""
        self.update_session(guid, error=error, recoverable=recoverable)
        logger.error(f"Session error: {guid} - {error}")

    def is_complete(self, guid: str) -> bool:
        """Check if session is complete."""
        session = self._sessions.get(guid)
        return session.get('complete', False) if session else False

    def is_acked(self, guid: str) -> bool:
        """Check if session has been acknowledged."""
        session = self._sessions.get(guid)
        return session.get('ack_received', False) if session else False

    async def wait_for_ack(self, guid: str, timeout: float = 30) -> bool:
        """Wait for acknowledgment with timeout."""
        if guid not in self._sessions:
            return False

        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if self._sessions[guid].get('ack_received'):
                return True
            await asyncio.sleep(0.1)

        logger.warning(f"Timeout waiting for ack: {guid}")
        return False

    async def wait_for_response(self, guid: str, timeout: float = 300) -> str | None:
        """Wait for response to be available."""
        if guid not in self._response_events:
            self.register_session(guid)

        try:
            await asyncio.wait_for(self._response_events[guid].wait(), timeout=timeout)
            return self._response_cache.get(guid)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for response: {guid}")
            return None

    def reset_session(self, guid: str) -> None:
        """Reset session state for a new message."""
        if guid in self._sessions:
            self._sessions[guid].update({
                'ack_received': False,
                'progress': 0,
                'status': '',
                'phase': '',
                'response': None,
                'complete': False,
                'success': None,
                'error': None,
                'updated_at': datetime.utcnow().isoformat() + 'Z'
            })
        if guid in self._response_events:
            self._response_events[guid].clear()
        if guid in self._response_cache:
            del self._response_cache[guid]

    def get_all_sessions(self) -> dict[str, dict[str, Any]]:
        """Get all sessions."""
        return self._sessions.copy()
