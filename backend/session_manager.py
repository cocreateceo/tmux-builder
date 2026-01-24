"""
Session Manager Module

Handles session data persistence including job queues, metadata, and logs.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from config import (
    get_session_path,
    get_job_queue_path,
    get_session_metadata_path,
    get_session_log_path
)

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session data persistence."""

    @staticmethod
    def create_session(session_id: str, metadata: Dict) -> Path:
        """
        Create a new session directory and metadata file.

        Args:
            session_id: Unique session identifier
            metadata: Session metadata dictionary

        Returns:
            Path to session directory
        """
        session_path = get_session_path(session_id)
        session_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (session_path / "prompts").mkdir(exist_ok=True)
        (session_path / "output").mkdir(exist_ok=True)
        (session_path / "logs").mkdir(exist_ok=True)

        # Save metadata
        metadata['created_at'] = datetime.utcnow().isoformat() + 'Z'
        metadata['session_id'] = session_id

        metadata_path = get_session_metadata_path(session_id)
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        # Initialize empty job queue
        job_queue_path = get_job_queue_path(session_id)
        with open(job_queue_path, 'w', encoding='utf-8') as f:
            json.dump([], f)

        logger.info(f"Created session: {session_id}")
        return session_path

    @staticmethod
    def load_metadata(session_id: str) -> Optional[Dict]:
        """Load session metadata."""
        metadata_path = get_session_metadata_path(session_id)

        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            return None

    @staticmethod
    def save_metadata(session_id: str, metadata: Dict):
        """Save session metadata."""
        metadata_path = get_session_metadata_path(session_id)

        metadata['last_modified'] = datetime.utcnow().isoformat() + 'Z'

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

    @staticmethod
    def load_job_queue(session_id: str) -> List[Dict]:
        """Load job queue from disk."""
        job_queue_path = get_job_queue_path(session_id)

        if not job_queue_path.exists():
            return []

        try:
            with open(job_queue_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading job queue: {e}")
            return []

    @staticmethod
    def save_job_queue(session_id: str, jobs: List[Dict]):
        """Save job queue to disk."""
        job_queue_path = get_job_queue_path(session_id)

        try:
            with open(job_queue_path, 'w', encoding='utf-8') as f:
                json.dump(jobs, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving job queue: {e}")
            raise

    @staticmethod
    def add_job(session_id: str, job: Dict) -> str:
        """
        Add a job to the queue.

        Args:
            session_id: Session ID
            job: Job dictionary (must have 'id' field)

        Returns:
            Job ID
        """
        jobs = SessionManager.load_job_queue(session_id)

        # Add timestamps
        job['created_at'] = datetime.utcnow().isoformat() + 'Z'
        job['status'] = 'pending'
        job['progress'] = 0

        jobs.append(job)
        SessionManager.save_job_queue(session_id, jobs)

        logger.info(f"Added job {job['id']} to session {session_id}")
        return job['id']

    @staticmethod
    def update_job(session_id: str, job_id: str, updates: Dict):
        """Update a job in the queue."""
        jobs = SessionManager.load_job_queue(session_id)

        for job in jobs:
            if job['id'] == job_id:
                job.update(updates)
                break
        else:
            raise ValueError(f"Job {job_id} not found in queue")

        SessionManager.save_job_queue(session_id, jobs)

    @staticmethod
    def get_job(session_id: str, job_id: str) -> Optional[Dict]:
        """Get a specific job from the queue."""
        jobs = SessionManager.load_job_queue(session_id)

        for job in jobs:
            if job['id'] == job_id:
                return job

        return None

    @staticmethod
    def log_event(session_id: str, component: str, message: str):
        """
        Log an event to the session log file.

        Args:
            session_id: Session ID
            component: Component name (e.g., "JOB_EXECUTION", "TMUX_HELPER")
            message: Log message
        """
        log_path = get_session_log_path(session_id)
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        log_entry = f"[{timestamp}] [{component}] {message}\n"

        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Error writing to session log: {e}")

    @staticmethod
    def session_exists(session_id: str) -> bool:
        """Check if a session exists."""
        return get_session_path(session_id).exists()

    @staticmethod
    def delete_session(session_id: str):
        """Delete a session (move to deleted folder)."""
        from config import DELETED_SESSIONS_DIR
        import shutil

        session_path = get_session_path(session_id)

        if not session_path.exists():
            return

        # Move to deleted folder with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        deleted_path = DELETED_SESSIONS_DIR / f"{session_id}_{timestamp}"

        shutil.move(str(session_path), str(deleted_path))
        logger.info(f"Deleted session: {session_id}")
