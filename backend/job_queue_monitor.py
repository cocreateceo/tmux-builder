"""
Background Job Queue Monitor

Runs as a separate process to:
- Poll job queues for pending jobs
- Enforce concurrency limits
- Start job execution
- Detect and handle stale jobs
- Report status

Usage:
    python job_queue_monitor.py  # Run as standalone process
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from config import ACTIVE_SESSIONS_DIR, MAX_CONCURRENT_JOBS

logger = logging.getLogger(__name__)


@dataclass
class MonitorConfig:
    """Configuration for job queue monitor."""
    poll_interval: float = 2.0          # Seconds between queue polls
    max_concurrent_jobs: int = 4        # Max jobs running at once
    check_interval: float = 5.0         # Seconds between completion checks
    stale_job_timeout: float = 1800.0   # 30 min default stale timeout


class JobQueueMonitor:
    """
    Background monitor for job queues.

    Responsibilities:
    1. Scan all active sessions for pending jobs
    2. Enforce max concurrent job limit
    3. Dispatch jobs to executor
    4. Monitor for stale/stuck jobs
    5. Update job status on completion/failure
    """

    def __init__(self, config: Optional[MonitorConfig] = None):
        self.config = config or MonitorConfig()
        self._running = False

    def find_pending_jobs(self) -> List[Dict]:
        """
        Find all pending jobs across all active sessions.

        Returns:
            List of pending job dictionaries with session_id added
        """
        pending_jobs = []

        if not ACTIVE_SESSIONS_DIR.exists():
            return pending_jobs

        for session_dir in ACTIVE_SESSIONS_DIR.iterdir():
            if not session_dir.is_dir():
                continue

            queue_file = session_dir / "job_queue.json"
            if not queue_file.exists():
                continue

            try:
                queue = json.loads(queue_file.read_text())
                for job in queue:
                    if job.get("status") == "pending":
                        job["_session_id"] = session_dir.name
                        pending_jobs.append(job)
            except Exception as e:
                logger.error(f"Error reading queue {queue_file}: {e}")

        return pending_jobs

    def get_running_jobs_count(self, session_id: str) -> int:
        """Get count of currently running jobs for a session."""
        queue_file = ACTIVE_SESSIONS_DIR / session_id / "job_queue.json"

        if not queue_file.exists():
            return 0

        try:
            queue = json.loads(queue_file.read_text())
            return sum(1 for job in queue if job.get("status") == "running")
        except Exception:
            return 0

    def get_available_slots(self, session_id: str) -> int:
        """
        Get number of available job slots for a session.

        Returns:
            Number of jobs that can be started (0 if at capacity)
        """
        running = self.get_running_jobs_count(session_id)
        return max(0, self.config.max_concurrent_jobs - running)

    def find_stale_jobs(
        self,
        session_id: str,
        timeout_seconds: Optional[float] = None
    ) -> List[Dict]:
        """
        Find jobs that have been running longer than timeout.

        Args:
            session_id: Session to check
            timeout_seconds: Override default stale timeout

        Returns:
            List of stale job dictionaries
        """
        timeout = timeout_seconds or self.config.stale_job_timeout
        stale_jobs = []

        queue_file = ACTIVE_SESSIONS_DIR / session_id / "job_queue.json"
        if not queue_file.exists():
            return stale_jobs

        try:
            queue = json.loads(queue_file.read_text())
            now = datetime.now()

            for job in queue:
                if job.get("status") != "running":
                    continue

                started_at = job.get("started_at")
                if not started_at:
                    continue

                # Parse ISO timestamp (handle with or without Z)
                started_at_clean = started_at.replace("Z", "").replace("+00:00", "")
                start_time = datetime.fromisoformat(started_at_clean)
                elapsed = (now - start_time).total_seconds()

                if elapsed > timeout:
                    job["_elapsed_seconds"] = elapsed
                    stale_jobs.append(job)

        except Exception as e:
            logger.error(f"Error finding stale jobs: {e}")

        return stale_jobs

    def run(self):
        """
        Main monitor loop.

        Runs continuously, polling for jobs and dispatching them.
        """
        logger.info("Starting Job Queue Monitor")
        logger.info(f"Config: poll_interval={self.config.poll_interval}s, "
                   f"max_concurrent={self.config.max_concurrent_jobs}")

        self._running = True

        while self._running:
            try:
                self._poll_cycle()
            except Exception as e:
                logger.error(f"Monitor cycle error: {e}")

            time.sleep(self.config.poll_interval)

    def _poll_cycle(self):
        """Single poll cycle - find and start pending jobs."""
        pending = self.find_pending_jobs()

        if not pending:
            return

        logger.debug(f"Found {len(pending)} pending jobs")

        for job in pending:
            session_id = job.get("_session_id")
            if not session_id:
                continue

            slots = self.get_available_slots(session_id)
            if slots <= 0:
                logger.debug(f"Session {session_id} at capacity, skipping")
                continue

            # Start job
            self._start_job(session_id, job)

    def _start_job(self, session_id: str, job: Dict):
        """Start execution of a pending job using JobRunner."""
        from job_runner import JobRunner

        job_id = job.get("id")
        execution_id = job.get("execution_id")

        if not execution_id:
            logger.error(f"Job {job_id} missing execution_id")
            return

        logger.info(f"Starting job {job_id} with execution {execution_id}")

        try:
            runner = JobRunner(execution_id)
            result = runner.run_pipeline()

            if result.get('status') == 'completed':
                logger.info(f"Job {job_id} completed successfully")
            else:
                logger.warning(f"Job {job_id} failed: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error executing job {job_id}: {e}")

    def stop(self):
        """Stop the monitor loop."""
        self._running = False
        logger.info("Job Queue Monitor stopping")


def main():
    """Run monitor as standalone process."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    monitor = JobQueueMonitor()

    try:
        monitor.run()
    except KeyboardInterrupt:
        monitor.stop()
        print("\nMonitor stopped by user")


if __name__ == "__main__":
    main()
