import pytest
import time
from pathlib import Path
from background_worker import BackgroundWorker

@pytest.fixture
def worker():
    """Create BackgroundWorker instance."""
    return BackgroundWorker()

def test_worker_initialization(worker):
    """Test BackgroundWorker initializes correctly."""
    assert worker is not None
    assert hasattr(worker, 'jobs')
    assert hasattr(worker, 'start_initialization')

def test_start_initialization_returns_immediately(worker):
    """Test that start_initialization returns immediately without blocking."""
    start_time = time.time()

    worker.start_initialization(
        guid='test123',
        email='test@example.com',
        phone='+15551234567',
        user_request='Build a test app'
    )

    elapsed = time.time() - start_time

    # Should return in less than 0.1 seconds (non-blocking)
    assert elapsed < 0.1

def test_job_status_tracking(worker):
    """Test that worker tracks job status."""
    guid = 'test123'

    worker.start_initialization(guid, 'test@example.com', '+15551234567', 'Build app')

    # Job should be tracked
    assert guid in worker.jobs

    # Should have status
    status = worker.get_job_status(guid)
    assert status is not None
    assert 'status' in status
    assert status['status'] in ['pending', 'initializing', 'ready', 'failed']

def test_multiple_concurrent_jobs(worker):
    """Test handling multiple jobs concurrently."""
    guids = ['guid1', 'guid2', 'guid3']

    for i, guid in enumerate(guids):
        worker.start_initialization(
            guid=guid,
            email=f'user{i}@example.com',
            phone=f'+155512345{i}',
            user_request=f'Build app {i}'
        )

    # All jobs should be tracked
    for guid in guids:
        assert guid in worker.jobs
