# How to Implement TMUX Integration in Any Project

**A Complete Guide Based on SmartBuild Pattern**

Version: 1.0
Date: 2026-01-23
Author: Based on SmartBuild (https://github.com/GopiSunware/SmartBuild)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Core Concept: File-Based I/O](#core-concept-file-based-io)
3. [Prerequisites](#prerequisites)
4. [Architecture Overview](#architecture-overview)
5. [Step-by-Step Implementation](#step-by-step-implementation)
6. [Critical Patterns](#critical-patterns)
7. [Common Pitfalls](#common-pitfalls)
8. [Testing and Validation](#testing-and-validation)
9. [Production Considerations](#production-considerations)
10. [Complete Code Examples](#complete-code-examples)

---

## Introduction

This guide teaches you how to integrate Claude CLI (or any CLI tool) through TMUX sessions using a **file-based I/O pattern**. This pattern is production-proven in SmartBuild and provides reliable, scalable AI integration.

### Why TMUX + File-Based I/O?

**Traditional Approach (DON'T DO THIS):**
```bash
# Sending prompts directly via stdin
echo "Long prompt here..." | claude
```

**Problems:**
- ❌ Limited prompt size (shell buffer limits)
- ❌ Quote escaping nightmares
- ❌ No context preservation
- ❌ Hard to debug
- ❌ Unreliable on WSL2/Windows

**SmartBuild Approach (DO THIS):**
```bash
# 1. Write prompt to file
echo "Very long prompt..." > prompt.txt

# 2. Tell Claude to read it
tmux send-keys -l "Please read prompt.txt"

# 3. Claude writes output to disk
# 4. Monitor for output file creation
```

**Benefits:**
- ✅ Unlimited prompt size
- ✅ No escaping issues
- ✅ Full context available
- ✅ Easy debugging (prompts saved on disk)
- ✅ Works reliably everywhere

---

## Core Concept: File-Based I/O

### The Pattern

```
┌─────────────────────────────────────────────────────────┐
│ Step 1: WRITE PROMPT TO DISK                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ prompt_file = "prompts/task_20260123.txt"              │
│ with open(prompt_file, 'w') as f:                      │
│     f.write(full_prompt)  # Can be 10,000+ characters   │
│                                                          │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Step 2: SEND INSTRUCTION (NOT THE PROMPT!)             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ instruction = f"Please read {prompt_file}"             │
│ tmux send-keys -t session -l "{instruction}"           │
│                                                          │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Step 3: CLAUDE READS FILE AND PROCESSES                │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ Claude opens prompt_file                                │
│ Claude reads full context                               │
│ Claude generates response                               │
│ Claude writes to output_file                            │
│                                                          │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Step 4: MONITOR FOR OUTPUT FILE                        │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ while not output_file.exists():                         │
│     time.sleep(2)                                       │
│                                                          │
│ if file_mtime > job_start_time:                         │
│     result = output_file.read_text()                    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### System Requirements

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install tmux python3 python3-pip

# macOS
brew install tmux python3

# Check installation
tmux -V          # Should show: tmux 3.x
python3 --version  # Should show: Python 3.8+
claude --version   # Should show: Claude CLI version
```

### Python Packages

```bash
pip install fastapi uvicorn pydantic pathlib
```

---

## Architecture Overview

### Directory Structure

```
your-project/
├── backend/
│   ├── config.py              # Configuration
│   ├── tmux_helper.py         # TMUX operations
│   ├── session_manager.py     # File I/O
│   ├── prompt_preparer.py     # Prompt generation
│   ├── job_queue_manager.py   # Job execution
│   └── main.py                # API server
├── sessions/
│   └── active/
│       └── <session_id>/
│           ├── prompts/       # Prompts written here
│           ├── output/        # Outputs written here
│           ├── logs/          # Session logs
│           └── job_queue.json # Job status
└── tests/
    └── test_integration.py    # Tests
```

### Data Flow

```
User Request → Job Queue → TMUX Session → Claude CLI
                   ↓            ↓              ↓
              Write Prompt → Send Instruction → Read File
                   ↓                            ↓
              Monitor File ← Write Output ← Process
                   ↓
              Return Result → User
```

---

## Step-by-Step Implementation

### Step 1: Configuration (config.py)

```python
"""Configuration for TMUX integration."""

from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.resolve()
SESSIONS_DIR = BASE_DIR.parent / "sessions" / "active"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Claude CLI configuration
CLI_PATH = "claude"
CLI_FLAGS = "--dangerously-skip-permissions"
CLI_COMMAND = f"{CLI_PATH} {CLI_FLAGS}"

# TMUX configuration
TMUX_SESSION_PREFIX = "my_app"

# CRITICAL TIMING (do not modify without testing)
TMUX_SEND_COMMAND_DELAY = 0.3   # After send-keys
TMUX_SEND_ENTER_DELAY = 1.2     # After Enter
TMUX_CLAUDE_INIT_DELAY = 3.0    # After starting Claude

# Job timeouts
JOB_TIMEOUT = 300  # 5 minutes default
JOB_MIN_WAIT = 10  # Minimum seconds before checking

def get_session_path(session_id: str) -> Path:
    """Get session directory path."""
    path = SESSIONS_DIR / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_prompts_dir(session_id: str) -> Path:
    """Get prompts directory."""
    path = get_session_path(session_id) / "prompts"
    path.mkdir(exist_ok=True)
    return path

def get_output_dir(session_id: str) -> Path:
    """Get output directory."""
    path = get_session_path(session_id) / "output"
    path.mkdir(exist_ok=True)
    return path
```

### Step 2: TMUX Helper (tmux_helper.py)

```python
"""TMUX operations - CRITICAL: Follow this pattern exactly."""

import subprocess
import time
import logging
from pathlib import Path

from config import (
    CLI_COMMAND,
    TMUX_SEND_COMMAND_DELAY,
    TMUX_SEND_ENTER_DELAY,
    TMUX_CLAUDE_INIT_DELAY
)

logger = logging.getLogger(__name__)


class TmuxHelper:
    """TMUX command wrapper."""

    @staticmethod
    def session_exists(session_name: str) -> bool:
        """Check if session exists."""
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", session_name],
                capture_output=True
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def create_session(session_name: str, working_dir: Path) -> bool:
        """
        Create TMUX session and start Claude.

        CRITICAL PATTERN - Do not modify!
        """
        try:
            # Create session
            subprocess.run(
                ["tmux", "new-session", "-d", "-s", session_name],
                stderr=subprocess.DEVNULL,
                check=True
            )

            # CD to working directory
            TmuxHelper._send_literal_command(
                session_name,
                f"cd {working_dir}",
                wait_after=0.5
            )

            # Start Claude CLI
            TmuxHelper._send_literal_command(
                session_name,
                CLI_COMMAND,
                wait_after=TMUX_CLAUDE_INIT_DELAY
            )

            # Bypass initial prompts
            for _ in range(3):
                subprocess.run(
                    ["tmux", "send-keys", "-t", session_name, "Enter"],
                    stderr=subprocess.DEVNULL
                )
                time.sleep(0.5)

            logger.info(f"Created session: {session_name}")
            return True

        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return False

    @staticmethod
    def _send_literal_command(
        session_name: str,
        command: str,
        wait_after: float
    ):
        """
        CRITICAL: This is the core pattern!

        Steps:
        1. send-keys with -l flag (literal text)
        2. Wait 0.3 seconds
        3. send-keys Enter
        4. Wait specified time
        """
        # Send literally
        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, "-l", command],
            stderr=subprocess.DEVNULL
        )
        time.sleep(TMUX_SEND_COMMAND_DELAY)

        # Send Enter
        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, "Enter"],
            stderr=subprocess.DEVNULL
        )
        time.sleep(wait_after)

    @staticmethod
    def send_instruction(session_name: str, instruction: str) -> bool:
        """Send instruction to Claude."""
        try:
            TmuxHelper._send_literal_command(
                session_name,
                instruction,
                wait_after=TMUX_SEND_ENTER_DELAY
            )
            return True
        except Exception as e:
            logger.error(f"Error sending instruction: {e}")
            return False

    @staticmethod
    def kill_session(session_name: str):
        """Kill session."""
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            stderr=subprocess.DEVNULL
        )
```

### Step 3: Prompt Preparer (prompt_preparer.py)

```python
"""Prepare prompts and write to disk."""

from pathlib import Path
from datetime import datetime
from typing import Tuple

from config import get_prompts_dir, get_output_dir


def prepare_prompt(
    session_id: str,
    prompt_text: str,
    job_type: str = "task"
) -> Tuple[str, Path, Path]:
    """
    Prepare a prompt (write to disk).

    Returns: (instruction_text, prompt_path, output_path)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Get directories
    prompts_dir = get_prompts_dir(session_id)
    output_dir = get_output_dir(session_id)

    # File paths
    prompt_file = f"{job_type}_{timestamp}.txt"
    output_file = f"{job_type}_output_{timestamp}.txt"

    prompt_path = prompts_dir / prompt_file
    output_path = output_dir / output_file

    # Build full prompt with output instructions
    full_prompt = f"""{prompt_text}

## Output Instructions:
Please write your complete response to: {output_path}

Make sure the file is fully written before returning.
"""

    # Write to disk
    with open(prompt_path, 'w', encoding='utf-8') as f:
        f.write(full_prompt)

    # Build instruction (this gets sent to Claude)
    instruction = (
        f"Please read and process the prompt file at {prompt_path}. "
        f"Write your output to {output_path}."
    )

    return instruction, prompt_path, output_path
```

### Step 4: Job Execution (job_queue_manager.py)

```python
"""Job execution following SmartBuild pattern."""

import time
import logging
from datetime import datetime
from pathlib import Path

from config import JOB_TIMEOUT, JOB_MIN_WAIT, get_session_path
from tmux_helper import TmuxHelper
from prompt_preparer import prepare_prompt

logger = logging.getLogger(__name__)


def execute_job(session_id: str, job_data: dict) -> bool:
    """
    Execute a job.

    Steps:
    1. Create TMUX session
    2. Prepare prompt (write to disk)
    3. Send instruction
    4. Monitor for completion
    """
    try:
        job_id = job_data['id']
        tmux_session = f"app_job_{job_id}"

        # Step 1: Create TMUX session
        session_path = get_session_path(session_id)
        if not TmuxHelper.create_session(tmux_session, session_path):
            return False

        # Step 2: Prepare prompt
        instruction, prompt_path, output_path = prepare_prompt(
            session_id,
            job_data['prompt'],
            job_data.get('type', 'task')
        )

        # Step 3: Send instruction
        if not TmuxHelper.send_instruction(tmux_session, instruction):
            TmuxHelper.kill_session(tmux_session)
            return False

        # Step 4: Monitor for completion
        job_start = datetime.now()

        # Wait minimum time
        time.sleep(JOB_MIN_WAIT)

        # Poll for output
        start_time = time.time()
        while time.time() - start_time < JOB_TIMEOUT:
            # Check file exists
            if not output_path.exists():
                time.sleep(2)
                continue

            # Check file is new
            file_mtime = datetime.fromtimestamp(
                output_path.stat().st_mtime
            )
            if file_mtime < job_start:
                time.sleep(2)
                continue

            # Check file size
            if output_path.stat().st_size < 100:
                time.sleep(2)
                continue

            # Success!
            logger.info(f"Job {job_id} completed!")
            TmuxHelper.kill_session(tmux_session)
            return True

        # Timeout
        logger.error(f"Job {job_id} timed out")
        TmuxHelper.kill_session(tmux_session)
        return False

    except Exception as e:
        logger.error(f"Error executing job: {e}")
        return False
```

---

## Critical Patterns

### Pattern 1: The -l Flag (MUST USE)

```python
# ❌ WRONG - Shell interprets special characters
subprocess.run([
    "tmux", "send-keys", "-t", session, "echo 'hello'"
])

# ✅ CORRECT - Literal text, no interpretation
subprocess.run([
    "tmux", "send-keys", "-t", session, "-l", "echo 'hello'"
])
```

### Pattern 2: Timing Delays (MUST FOLLOW)

```python
# Send command
subprocess.run(["tmux", "send-keys", "-t", session, "-l", cmd])

# ⚠️ CRITICAL: Wait 0.3s (tmux buffer processing)
time.sleep(0.3)

# Send Enter
subprocess.run(["tmux", "send-keys", "-t", session, "Enter"])

# ⚠️ CRITICAL: Wait 1.2s (Claude initialization)
time.sleep(1.2)
```

**Why these specific times?**
- `0.3s`: Tmux internal buffer processing
- `1.2s`: Claude CLI initialization/processing
- `3.0s`: Full Claude startup time

**DO NOT REDUCE THESE VALUES** - Tested on WSL2, Linux, macOS.

### Pattern 3: File Modification Time Check

```python
# ❌ WRONG - Just checking existence
if output_file.exists():
    return True

# ✅ CORRECT - Check mtime is after job start
file_mtime = datetime.fromtimestamp(output_file.stat().st_mtime)
if file_mtime > job_start_time and output_file.stat().st_size > 100:
    return True
```

**Why?** Old files might exist from previous runs!

### Pattern 4: No shell=True

```python
# ❌ WRONG - Security risk, escaping issues
subprocess.run(f"tmux send-keys -t {session} '{command}'", shell=True)

# ✅ CORRECT - List format, no shell interpretation
subprocess.run(["tmux", "send-keys", "-t", session, "-l", command])
```

---

## Common Pitfalls

### Pitfall 1: Sending Full Prompt via TMUX

```python
# ❌ WRONG
prompt = "Very long prompt..." * 1000
subprocess.run(["tmux", "send-keys", "-t", session, "-l", prompt])
```

**Problem:** Exceeds tmux buffer limits, unreliable.

**Solution:** Write to file, send file path!

```python
# ✅ CORRECT
with open("prompt.txt", "w") as f:
    f.write(prompt)

subprocess.run([
    "tmux", "send-keys", "-t", session, "-l",
    f"Please read prompt.txt"
])
```

### Pitfall 2: Ignoring Timing

```python
# ❌ WRONG
subprocess.run(["tmux", "send-keys", "-t", session, "-l", cmd])
subprocess.run(["tmux", "send-keys", "-t", session, "Enter"])
# No delays - unreliable!
```

**Solution:** Always use proper delays!

### Pitfall 3: Not Checking File Mtime

```python
# ❌ WRONG - Reads old file
if output.exists():
    return output.read_text()
```

**Solution:** Always check mtime > job_start!

---

## Testing and Validation

### Test Script

```python
#!/usr/bin/env python3
"""Test TMUX integration."""

import time
from datetime import datetime
from pathlib import Path

from config import get_session_path
from tmux_helper import TmuxHelper
from prompt_preparer import prepare_prompt

def test_basic_integration():
    """Test basic file-based I/O."""
    session_id = f"test_{datetime.now().strftime('%H%M%S')}"
    tmux_session = f"test_session_{session_id}"

    # Create session
    session_path = get_session_path(session_id)
    session_path.mkdir(parents=True, exist_ok=True)

    print(f"Creating TMUX session: {tmux_session}")
    assert TmuxHelper.create_session(tmux_session, session_path)

    # Prepare prompt
    prompt_text = "Please echo back: Hello from TMUX test!"
    instruction, prompt_path, output_path = prepare_prompt(
        session_id,
        prompt_text,
        "test"
    )

    print(f"Prompt written to: {prompt_path}")
    print(f"Expected output at: {output_path}")

    # Send instruction
    print(f"Sending instruction to Claude...")
    assert TmuxHelper.send_instruction(tmux_session, instruction)

    # Wait for output
    print("Waiting for output file...")
    start_time = time.time()
    job_start = datetime.now()

    while time.time() - start_time < 60:
        if output_path.exists():
            file_mtime = datetime.fromtimestamp(
                output_path.stat().st_mtime
            )
            if file_mtime > job_start:
                print("✅ Output file created!")
                print(f"Content: {output_path.read_text()}")
                TmuxHelper.kill_session(tmux_session)
                return True

        time.sleep(2)

    print("❌ Timeout waiting for output")
    TmuxHelper.kill_session(tmux_session)
    return False

if __name__ == "__main__":
    success = test_basic_integration()
    exit(0 if success else 1)
```

### Validation Checklist

- [ ] TMUX session creates successfully
- [ ] Claude CLI starts in session
- [ ] Prompt file written to disk
- [ ] Instruction sent to Claude
- [ ] Output file appears
- [ ] File mtime > job start time
- [ ] File contains expected content
- [ ] Session cleanup works

---

## Production Considerations

### 1. Error Handling

```python
try:
    TmuxHelper.create_session(session, path)
except Exception as e:
    logger.error(f"Session creation failed: {e}")
    # Cleanup and retry logic
```

### 2. Session Cleanup

```python
# Always kill sessions when done
try:
    execute_job(session_id, job)
finally:
    TmuxHelper.kill_session(tmux_session)
```

### 3. Concurrent Jobs

```python
# Limit concurrent TMUX sessions
MAX_CONCURRENT = 4

active_sessions = len(TmuxHelper.list_sessions())
if active_sessions >= MAX_CONCURRENT:
    wait_for_slot()
```

### 4. Logging

```python
# Log everything for debugging
logger.info(f"Creating session: {session}")
logger.debug(f"Prompt: {prompt_path}")
logger.info(f"Waiting for output: {output_path}")
```

### 5. Monitoring

```python
# Monitor session health
if not TmuxHelper.session_exists(session):
    logger.error(f"Session {session} died unexpectedly")
    handle_session_loss()
```

---

## Complete Code Examples

See the `backend/` directory for complete, production-ready implementations:

- `config.py` - Configuration management
- `tmux_helper.py` - TMUX operations
- `session_manager.py` - File I/O and persistence
- `prompt_preparer.py` - Prompt generation
- `job_queue_manager.py` - Job execution
- `test_tmux_integration.py` - Integration tests

---

## Summary: The Five Golden Rules

1. **Write prompts to files, not stdin**
   - Unlimited size, no escaping, easy debugging

2. **Use the `-l` flag with tmux send-keys**
   - Literal text, no shell interpretation

3. **Follow exact timing delays**
   - 0.3s after send-keys, 1.2s after Enter, 3.0s for Claude init

4. **Check file mtime, not just existence**
   - Avoids reading old files from previous runs

5. **Never use `shell=True`**
   - Security risk, escaping nightmares

---

## Next Steps

1. Copy the implementation files to your project
2. Adjust paths in `config.py` for your structure
3. Run `test_tmux_integration.py` to validate
4. Integrate into your application

---

## Support

For questions or issues:
- Check SmartBuild source: https://github.com/GopiSunware/SmartBuild
- Review the implementation: `tmux-builder/backend/`
- Read architecture analysis: `SMARTBUILD_ARCHITECTURE_ANALYSIS.md`

---

**END OF GUIDE**
