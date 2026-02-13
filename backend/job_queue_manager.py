"""
Job Queue Manager

Manages job execution following SmartBuild pattern.
Handles TMUX session creation, prompt preparation, and completion detection.
"""

import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from config import (
    get_session_path,
    get_tmux_job_session_name,
    JOB_TIMEOUTS,
    JOB_MIN_WAIT_TIMES,
    JOB_CHECK_INTERVAL
)
from tmux_helper import TmuxHelper
from session_manager import SessionManager
from prompt_preparer import (
    prepare_echo_test_prompt,
    prepare_file_analysis_prompt,
    prepare_generic_prompt
)

logger = logging.getLogger(__name__)


class JobQueueManager:
    """Manages job execution and completion detection."""

    @staticmethod
    def execute_job(session_id: str, job_id: str) -> bool:
        """
        Execute a job following SmartBuild pattern.

        Steps:
        1. Get job from queue
        2. Create TMUX session for job
        3. Prepare prompt (write to disk)
        4. Send instruction to Claude (read this file)
        5. Monitor for completion (file existence + mtime)
        6. Update job status

        Args:
            session_id: Session ID
            job_id: Job ID

        Returns:
            True if job executed successfully
        """
        try:
            # Step 1: Get job from queue
            job = SessionManager.get_job(session_id, job_id)
            if not job:
                logger.error(f"Job {job_id} not found in queue")
                return False

            SessionManager.log_event(session_id, "JOB_EXECUTION", f"Starting job {job_id}")
            SessionManager.log_event(session_id, "JOB_EXECUTION", f"Type: {job['type']}")

            # Update job status
            job_start_time = datetime.now()
            SessionManager.update_job(session_id, job_id, {
                'status': 'running',
                'started_at': job_start_time.isoformat() + 'Z',
                'progress': 10
            })

            # Step 2: Create TMUX session
            tmux_session_name = get_tmux_job_session_name(job_id)
            job['tmux_session'] = tmux_session_name

            session_path = get_session_path(session_id)

            SessionManager.log_event(session_id, "TMUX_HELPER", f"Creating session: {tmux_session_name}")

            if not TmuxHelper.create_session(tmux_session_name, session_path):
                raise RuntimeError(f"Failed to create TMUX session: {tmux_session_name}")

            SessionManager.update_job(session_id, job_id, {
                'tmux_session': tmux_session_name,
                'progress': 30
            })

            # Step 3: Prepare prompt (write to disk)
            SessionManager.log_event(session_id, "PROMPT_PREPARER", f"Preparing prompt for {job['type']}")

            instruction, prompt_path, output_path = JobQueueManager._prepare_prompt(
                session_id, job
            )

            SessionManager.update_job(session_id, job_id, {
                'prompt_path': str(prompt_path),
                'output_path': str(output_path),
                'progress': 50
            })

            # Step 4: Send instruction to Claude
            SessionManager.log_event(session_id, "TMUX_HELPER", f"Sending instruction to Claude")

            if not TmuxHelper.send_instruction(tmux_session_name, instruction):
                raise RuntimeError(f"Failed to send instruction to Claude")

            SessionManager.update_job(session_id, job_id, {
                'progress': 60,
                'job_start_timestamp': job_start_time.isoformat()
            })

            SessionManager.log_event(session_id, "JOB_EXECUTION", f"Waiting for completion...")

            # Step 5: Monitor for completion
            timeout = JOB_TIMEOUTS.get(job['type'], JOB_TIMEOUTS['default'])
            min_wait = JOB_MIN_WAIT_TIMES.get(job['type'], JOB_MIN_WAIT_TIMES['default'])

            completed = JobQueueManager._wait_for_completion(
                session_id,
                job_id,
                output_path,
                job_start_time,
                min_wait,
                timeout
            )

            if completed:
                SessionManager.log_event(session_id, "JOB_EXECUTION", "Job completed successfully")
                SessionManager.update_job(session_id, job_id, {
                    'status': 'completed',
                    'progress': 100,
                    'completed_at': datetime.now().isoformat() + 'Z'
                })

                # Optionally kill TMUX session
                TmuxHelper.kill_session(tmux_session_name)

                return True
            else:
                SessionManager.log_event(session_id, "JOB_EXECUTION", "Job timed out or failed")
                SessionManager.update_job(session_id, job_id, {
                    'status': 'failed',
                    'error': 'Timeout or completion check failed'
                })

                TmuxHelper.kill_session(tmux_session_name)
                return False

        except Exception as e:
            logger.error(f"Error executing job {job_id}: {e}")
            SessionManager.log_event(session_id, "JOB_EXECUTION", f"ERROR: {e}")

            SessionManager.update_job(session_id, job_id, {
                'status': 'failed',
                'error': str(e)
            })

            # Cleanup TMUX session
            if 'tmux_session' in job:
                TmuxHelper.kill_session(job['tmux_session'])

            return False

    @staticmethod
    def _prepare_prompt(session_id: str, job: Dict):
        """Prepare prompt based on job type."""
        job_type = job['type']

        if job_type == 'echo_test':
            message = job.get('message', 'Hello from tmux-builder!')
            return prepare_echo_test_prompt(session_id, message)

        elif job_type == 'file_analysis':
            file_path = job.get('file_path')
            if not file_path:
                raise ValueError("file_path required for file_analysis job")
            return prepare_file_analysis_prompt(session_id, file_path)

        else:
            # Generic job
            prompt_text = job.get('prompt_text', 'No prompt provided')
            return prepare_generic_prompt(session_id, prompt_text, job_type)

    @staticmethod
    def _wait_for_completion(
        session_id: str,
        job_id: str,
        output_path: Path,
        job_start_time: datetime,
        min_wait: int,
        timeout: int
    ) -> bool:
        """
        Wait for job completion using file-based detection.

        Checks:
        1. Output file exists
        2. File mtime > job start time
        3. File size > minimum (100 bytes)

        Args:
            session_id: Session ID
            job_id: Job ID
            output_path: Path to expected output file
            job_start_time: When job started
            min_wait: Minimum seconds to wait before checking
            timeout: Maximum seconds to wait

        Returns:
            True if job completed successfully
        """
        start_time = time.time()

        # Wait minimum time first
        logger.info(f"Waiting {min_wait}s before checking completion...")
        time.sleep(min_wait)

        while True:
            elapsed = time.time() - start_time

            # Check timeout
            if elapsed > timeout:
                logger.warning(f"Job {job_id} timed out after {elapsed:.1f}s")
                return False

            # Check 1: File exists?
            if not output_path.exists():
                logger.debug(f"Output file does not exist yet: {output_path}")
                time.sleep(JOB_CHECK_INTERVAL)
                continue

            # Check 2: File mtime > job start?
            file_mtime = datetime.fromtimestamp(output_path.stat().st_mtime)
            if file_mtime < job_start_time:
                logger.debug(f"Output file is old (mtime < job_start)")
                time.sleep(JOB_CHECK_INTERVAL)
                continue

            # Check 3: File size reasonable?
            file_size = output_path.stat().st_size
            if file_size < 100:
                logger.debug(f"Output file too small ({file_size} bytes)")
                time.sleep(JOB_CHECK_INTERVAL)
                continue

            # All checks passed!
            logger.info(f"Job {job_id} completed! Output file: {output_path}")
            SessionManager.log_event(
                session_id,
                "JOB_MONITOR",
                f"Completion detected - File: {output_path}, Size: {file_size} bytes"
            )

            return True
