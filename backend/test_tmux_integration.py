#!/usr/bin/env python3
"""
Test script for tmux-builder integration.

Tests the SmartBuild pattern implementation:
1. Session creation
2. Prompt preparation (file-based)
3. TMUX command sending
4. Completion detection (file existence + mtime)
"""

import sys
import time
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import modules
from config import print_config, get_session_path
from session_manager import SessionManager
from job_queue_manager import JobQueueManager


def test_echo_job():
    """Test the simplest job: echo test."""
    print("\n" + "="*60)
    print("TEST 1: Echo Test (File-Based I/O)")
    print("="*60)

    # Create session
    session_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"Creating test session: {session_id}")

    session_path = SessionManager.create_session(session_id, {
        'test_type': 'echo',
        'created_by': 'test_script'
    })

    print(f"✓ Session created: {session_path}")

    # Create job
    job_id = f"job_{datetime.now().strftime('%H%M%S')}"
    job = {
        'id': job_id,
        'type': 'echo_test',
        'message': 'Hello from tmux-builder test! This is file-based I/O working correctly.'
    }

    SessionManager.add_job(session_id, job)
    print(f"✓ Job created: {job_id}")

    # Execute job
    print("\n📝 Executing job (this will take ~30-60 seconds)...")
    print("   - Creating TMUX session")
    print("   - Starting Claude CLI")
    print("   - Writing prompt to disk")
    print("   - Sending instruction to Claude")
    print("   - Waiting for output file...")

    success = JobQueueManager.execute_job(session_id, job_id)

    if success:
        print("\n✅ TEST PASSED!")

        # Show results
        job = SessionManager.get_job(session_id, job_id)
        print(f"\nJob Status: {job['status']}")
        print(f"Output Path: {job['output_path']}")

        # Read output
        output_path = Path(job['output_path'])
        if output_path.exists():
            print(f"\n📄 Output Content:")
            print("-" * 60)
            print(output_path.read_text())
            print("-" * 60)

        # Show session log
        log_path = get_session_path(session_id) / "logs" / f"session_{session_id}.log"
        if log_path.exists():
            print(f"\n📋 Session Log:")
            print("-" * 60)
            print(log_path.read_text())
            print("-" * 60)

        return True
    else:
        print("\n❌ TEST FAILED!")
        job = SessionManager.get_job(session_id, job_id)
        print(f"Job Status: {job['status']}")
        print(f"Error: {job.get('error', 'Unknown')}")
        return False


def test_file_analysis():
    """Test file analysis job."""
    print("\n" + "="*60)
    print("TEST 2: File Analysis (More Complex Prompt)")
    print("="*60)

    # Create a test file to analyze
    test_file = Path("/tmp/test_analysis.py")
    test_file.write_text("""#!/usr/bin/env python3
'''
Example Python script for testing file analysis.
'''

def greet(name: str) -> str:
    '''Greet someone by name.'''
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("World"))
""")

    print(f"✓ Created test file: {test_file}")

    # Create session
    session_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}_analysis"
    SessionManager.create_session(session_id, {
        'test_type': 'file_analysis',
        'created_by': 'test_script'
    })

    # Create job
    job_id = f"job_{datetime.now().strftime('%H%M%S')}"
    job = {
        'id': job_id,
        'type': 'file_analysis',
        'file_path': str(test_file)
    }

    SessionManager.add_job(session_id, job)
    print(f"✓ Job created: {job_id}")

    # Execute job
    print("\n📝 Executing job...")
    success = JobQueueManager.execute_job(session_id, job_id)

    if success:
        print("\n✅ TEST PASSED!")

        # Show results
        job = SessionManager.get_job(session_id, job_id)
        output_path = Path(job['output_path'])
        if output_path.exists():
            print(f"\n📄 Analysis Output:")
            print("-" * 60)
            print(output_path.read_text()[:500])  # First 500 chars
            print("...")
            print("-" * 60)

        return True
    else:
        print("\n❌ TEST FAILED!")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("tmux-builder Integration Test Suite")
    print("="*60)

    # Print configuration
    print_config()

    # Run tests
    results = []

    try:
        # Test 1: Echo test (simplest)
        result1 = test_echo_job()
        results.append(("Echo Test", result1))

        # Wait between tests
        time.sleep(2)

        # Test 2: File analysis (more complex)
        result2 = test_file_analysis()
        results.append(("File Analysis", result2))

    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        return 1

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20s} {status}")

    all_passed = all(r[1] for r in results)

    print("="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
