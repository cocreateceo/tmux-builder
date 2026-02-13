"""Background worker for async session initialization."""

import asyncio
import threading
import logging
import time
from typing import Dict, Any
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """Manages background initialization of Claude CLI sessions."""

    def __init__(self):
        """Initialize BackgroundWorker."""
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        logger.info("BackgroundWorker initialized")

    def start_initialization(
        self,
        guid: str,
        email: str,
        phone: str,
        user_request: str
    ) -> None:
        """
        Start session initialization in background thread.

        This method returns immediately. Initialization happens asynchronously.

        Args:
            guid: User GUID
            email: User email
            phone: User phone
            user_request: User's build request
        """
        with self.lock:
            # Track job
            self.jobs[guid] = {
                'status': 'pending',
                'email': email,
                'phone': phone,
                'user_request': user_request,
                'started_at': datetime.now(timezone.utc).isoformat(),
                'progress': 0,
                'message': 'Queued for initialization'
            }

        # Start worker thread
        worker = threading.Thread(
            target=self._worker_thread,
            args=(guid, email, phone, user_request),
            daemon=True,
            name=f"Worker-{guid}"
        )
        worker.start()

        logger.info(f"Started initialization worker for GUID: {guid}")

    def _worker_thread(
        self,
        guid: str,
        email: str,
        phone: str,
        user_request: str
    ) -> None:
        """
        Worker thread that performs actual initialization.

        This runs in background and updates job status as it progresses.

        Args:
            guid: User GUID
            email: User email
            phone: User phone
            user_request: User's build request
        """
        try:
            logger.info(f"Worker thread started for GUID: {guid}")

            # Import here to avoid circular dependencies
            try:
                from session_initializer import SessionInitializer
            except ImportError:
                # SessionInitializer not yet implemented - stub for now
                logger.warning("SessionInitializer not available, using stub")
                self._update_job_status(guid, {
                    'status': 'failed',
                    'progress': 0,
                    'message': 'SessionInitializer not yet implemented',
                    'error': 'SessionInitializer module not found'
                })
                return

            # Update status
            self._update_job_status(guid, {
                'status': 'initializing',
                'progress': 10,
                'message': 'Initializing session...'
            })

            # Initialize session (async method - run in event loop)
            initializer = SessionInitializer()
            result = asyncio.run(initializer.initialize_session(guid, email, phone, user_request))

            if result['success']:
                # Update status to ready
                self._update_job_status(guid, {
                    'status': 'ready',
                    'progress': 100,
                    'message': 'Session initialized successfully',
                    'session_name': result.get('session_name'),
                    'session_path': result.get('session_path')
                })
                logger.info(f"✓ Session initialization complete for GUID: {guid}")
            else:
                # Update status to failed
                self._update_job_status(guid, {
                    'status': 'failed',
                    'progress': 0,
                    'message': f"Initialization failed: {result.get('error')}",
                    'error': result.get('error')
                })
                logger.error(f"✗ Session initialization failed for GUID: {guid}")

        except Exception as e:
            logger.exception(f"Worker thread exception for GUID {guid}: {e}")
            self._update_job_status(guid, {
                'status': 'failed',
                'progress': 0,
                'message': f"Initialization error: {str(e)}",
                'error': str(e)
            })

    def _update_job_status(self, guid: str, updates: Dict[str, Any]) -> None:
        """
        Update job status thread-safely.

        Args:
            guid: User GUID
            updates: Dictionary of fields to update
        """
        with self.lock:
            if guid in self.jobs:
                self.jobs[guid].update(updates)
                self.jobs[guid]['updated_at'] = datetime.now(timezone.utc).isoformat()

    def get_job_status(self, guid: str) -> Dict[str, Any]:
        """
        Get current status of a job.

        Args:
            guid: User GUID

        Returns:
            Job status dictionary or None if not found
        """
        with self.lock:
            return self.jobs.get(guid, None)

    def cleanup_old_jobs(self, max_age_seconds: int = 86400) -> int:
        """
        Clean up old completed/failed jobs.

        Args:
            max_age_seconds: Maximum age in seconds (default: 24 hours)

        Returns:
            Number of jobs cleaned up
        """
        current_time = time.time()
        cleaned = 0

        with self.lock:
            guids_to_remove = []

            for guid, job in self.jobs.items():
                # Parse started_at timestamp
                started_at_str = job['started_at']
                if started_at_str.endswith('Z'):
                    started_at_str = started_at_str[:-1] + '+00:00'
                started_at = datetime.fromisoformat(started_at_str)
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                age_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()

                # Remove if old and not pending/initializing
                if age_seconds > max_age_seconds and job['status'] not in ['pending', 'initializing']:
                    guids_to_remove.append(guid)

            for guid in guids_to_remove:
                del self.jobs[guid]
                cleaned += 1

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old jobs")

        return cleaned
