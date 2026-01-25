# Tmux Builder Architecture

Detailed technical architecture following SmartBuild file-based I/O patterns.

## System Overview

Tmux Builder is a backend system that enables programmatic interaction with Claude AI through isolated tmux sessions. The architecture implements the **SmartBuild pattern**: file-based I/O with prompt/output directories, TMUX session isolation, and completion detection via file monitoring.

## Current Architecture

**Note**: This is a backend-only implementation. There is no web frontend or API server in the current codebase.

## Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Test Entry Point                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  test_tmux_integration.py                             │  │
│  │  ├─ test_echo_job()                                   │  │
│  │  ├─ test_file_analysis_job()                          │  │
│  │  └─ main()                                            │  │
│  └───────────────────┬───────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────┘
                         │ Python API
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                 Core Backend Modules                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  config.py - Configuration & Path Management          │  │
│  │  ├─ Path helpers (sessions, prompts, output)          │  │
│  │  ├─ Timing constants (TMUX delays)                    │  │
│  │  ├─ Job timeouts and intervals                        │  │
│  │  └─ Validation (check tmux, Claude CLI)              │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  session_manager.py - Data Persistence                │  │
│  │  ├─ create_session(session_id, metadata)             │  │
│  │  ├─ add_job(session_id, job)                          │  │
│  │  ├─ update_job(session_id, job_id, updates)           │  │
│  │  ├─ get_job(session_id, job_id)                       │  │
│  │  └─ log_event(session_id, component, message)         │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  job_queue_manager.py - Job Execution                 │  │
│  │  ├─ execute_job(session_id, job_id)                   │  │
│  │  ├─ _prepare_prompt(session_id, job)                  │  │
│  │  └─ _wait_for_completion(...)                         │  │
│  └───────────────────┬───────────────────────────────────┘  │
│                      │                                       │
│  ┌───────────────────▼───────────────────────────────────┐  │
│  │  prompt_preparer.py - Prompt Generation               │  │
│  │  ├─ prepare_echo_test_prompt(session_id, message)     │  │
│  │  ├─ prepare_file_analysis_prompt(session_id, file)    │  │
│  │  └─ prepare_generic_prompt(session_id, text, type)    │  │
│  └───────────────────┬───────────────────────────────────┘  │
│                      │                                       │
│  ┌───────────────────▼───────────────────────────────────┐  │
│  │  tmux_helper.py - TMUX Operations                     │  │
│  │  ├─ create_session(name, working_dir)                 │  │
│  │  ├─ send_instruction(session_name, instruction)       │  │
│  │  ├─ kill_session(session_name)                        │  │
│  │  └─ capture_pane_output(session_name)                 │  │
│  └───────────────────┬───────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────┘
                         │ subprocess (tmux commands)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    TMUX Session Layer                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Session: tmux_builder_job_<job_id>                   │  │
│  │  ├─ Pane 0: Claude CLI running                        │  │
│  │  └─ Working Dir: /sessions/active/<session_id>/       │  │
│  └───────────────────┬───────────────────────────────────┘  │
└────────────────────────┼───────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Claude CLI Process                      │
│  - Receives instruction via tmux send-keys                  │
│  - Reads prompt file from disk                              │
│  - Processes with Claude AI model                           │
│  - Writes response to output file on disk                   │
│  - Backend detects completion via file mtime monitoring     │
└─────────────────────────────────────────────────────────────┘
```

## SmartBuild Pattern: File-Based I/O

### Core Concept

Instead of capturing stdout or using markers, the SmartBuild pattern uses **files for I/O**:

1. **Write prompt to disk** (in `prompts/` directory)
2. **Instruct Claude to read the file** (via tmux)
3. **Claude writes response to disk** (in `output/` directory)
4. **Monitor output file** for completion (exists + mtime + size)

### Benefits

- **Reliable**: File existence is atomic
- **No parsing**: Don't need to parse stdout or look for markers
- **Handles large content**: No terminal buffer limits
- **Persistent**: Files remain for debugging/auditing
- **Simple**: Standard file operations

## Data Flow: Executing a Job

### Step-by-Step Flow

1. **Create Session**
   ```python
   session_id = f"test_{timestamp}"
   SessionManager.create_session(session_id, metadata)
   # Creates: sessions/active/<session_id>/
   #          ├── prompts/
   #          ├── output/
   #          ├── logs/
   #          ├── metadata.json
   #          └── job_queue.json
   ```

2. **Add Job to Queue**
   ```python
   job = {
       'id': job_id,
       'type': 'echo_test',
       'message': 'Hello from tmux-builder!'
   }
   SessionManager.add_job(session_id, job)
   ```

3. **Execute Job**
   ```python
   JobQueueManager.execute_job(session_id, job_id)
   ```

4. **Create TMUX Session**
   ```python
   tmux_session_name = f"tmux_builder_job_{job_id}"
   TmuxHelper.create_session(tmux_session_name, session_path)
   # Creates isolated tmux session
   # Starts Claude CLI with --dangerously-skip-permissions
   # Waits for initialization (3.0s + probe verification)
   ```

5. **Prepare Prompt (Write to Disk)**
   ```python
   instruction, prompt_path, output_path = prepare_echo_test_prompt(
       session_id,
       message
   )
   # Writes: prompts/echo_test_20260124_123456.txt
   # Returns: instruction = "Please read and process the prompt file at..."
   ```

6. **Send Instruction to Claude**
   ```python
   TmuxHelper.send_instruction(tmux_session_name, instruction)
   # CRITICAL PATTERN:
   #   1. tmux send-keys -l "instruction"  (literal mode)
   #   2. sleep 0.3s (TMUX_SEND_COMMAND_DELAY)
   #   3. tmux send-keys Enter
   #   4. sleep 1.2s (TMUX_SEND_ENTER_DELAY)
   ```

7. **Claude Processes**
   ```
   Claude receives instruction → Reads prompt from disk →
   Processes with AI → Writes response to output file
   ```

8. **Monitor for Completion (File-Based Detection)**
   ```python
   while elapsed < timeout:
       # Check 1: File exists?
       if not output_path.exists():
           continue

       # Check 2: File mtime > job start time?
       if file_mtime < job_start_time:
           continue

       # Check 3: File size reasonable?
       if file_size < 100:
           continue

       # All checks passed - job complete!
       return True
   ```

9. **Update Job Status**
   ```python
   SessionManager.update_job(session_id, job_id, {
       'status': 'completed',
       'progress': 100,
       'completed_at': timestamp
   })
   ```

10. **Cleanup**
    ```python
    TmuxHelper.kill_session(tmux_session_name)
    ```

## File Structure

### Session Directory Layout

```
sessions/
├── active/
│   └── <session_id>/
│       ├── prompts/                    # Prompt files written here
│       │   ├── echo_test_<timestamp>.txt
│       │   ├── file_analysis_<timestamp>.txt
│       │   └── generic_<timestamp>.txt
│       ├── output/                     # Claude writes responses here
│       │   ├── echo_output_<timestamp>.txt
│       │   ├── analysis_output_<timestamp>.md
│       │   └── generic_output_<timestamp>.txt
│       ├── logs/                       # Session event logs
│       │   └── session_<session_id>.log
│       ├── metadata.json               # Session metadata
│       └── job_queue.json              # Job queue (array of jobs)
└── deleted/
    └── <session_id>_<timestamp>/       # Deleted sessions moved here
```

### Job Queue Format (job_queue.json)

```json
[
  {
    "id": "job_123456",
    "type": "echo_test",
    "message": "Hello from tmux-builder!",
    "status": "completed",
    "progress": 100,
    "created_at": "2026-01-24T12:34:56Z",
    "started_at": "2026-01-24T12:34:58Z",
    "completed_at": "2026-01-24T12:35:15Z",
    "tmux_session": "tmux_builder_job_123456",
    "prompt_path": "/path/to/prompts/echo_test_123456.txt",
    "output_path": "/path/to/output/echo_output_123456.txt"
  }
]
```

### Session Log Format (session_<id>.log)

```
[12:34:56.123] [JOB_EXECUTION] Starting job job_123456
[12:34:56.124] [JOB_EXECUTION] Type: echo_test
[12:34:58.456] [TMUX_HELPER] Creating session: tmux_builder_job_123456
[12:35:01.789] [TMUX_HELPER] Claude CLI initialized successfully
[12:35:02.012] [PROMPT_PREPARER] Preparing prompt for echo_test
[12:35:02.345] [TMUX_HELPER] Sending instruction to Claude
[12:35:02.678] [JOB_EXECUTION] Waiting for completion...
[12:35:15.901] [JOB_MONITOR] Completion detected - File: output/echo_output_123456.txt, Size: 234 bytes
[12:35:15.902] [JOB_EXECUTION] Job completed successfully
```

## Job Types

### 1. Echo Test (echo_test)

**Purpose**: Simplest job for testing file-based I/O

```python
prepare_echo_test_prompt(session_id, message)
```

**Timeout**: 60 seconds
**Min Wait**: 5 seconds

### 2. File Analysis (file_analysis)

**Purpose**: Analyze a file and generate report

```python
prepare_file_analysis_prompt(session_id, file_path)
```

**Timeout**: 300 seconds (5 minutes)
**Min Wait**: 10 seconds

### 3. Generic Job (generic)

**Purpose**: Custom prompt text

```python
prepare_generic_prompt(session_id, prompt_text, job_type)
```

**Timeout**: 300 seconds (default)
**Min Wait**: 10 seconds

## Critical Timing Configuration

These values are **CRITICAL** for reliable TMUX operation. Do not modify without thorough testing.

```python
# From config.py

TMUX_SEND_COMMAND_DELAY = 0.3   # After send-keys (text appears in pane)
TMUX_SEND_ENTER_DELAY = 1.2     # After Enter key (command submits)
TMUX_CLAUDE_INIT_DELAY = 3.0    # After starting Claude CLI (ready for input)
```

### Why These Delays Matter

1. **TMUX_SEND_COMMAND_DELAY (0.3s)**
   - Allows tmux to process and display the text in the pane
   - Without this, Enter might be sent before text appears

2. **TMUX_SEND_ENTER_DELAY (1.2s)**
   - Ensures command is fully submitted and processed
   - Claude CLI needs time to start processing input

3. **TMUX_CLAUDE_INIT_DELAY (3.0s)**
   - Claude CLI takes time to initialize
   - Sending commands too early results in them being ignored

## Completion Detection Strategy

### File-Based Detection (Current Implementation)

```python
def _wait_for_completion(output_path, job_start_time, min_wait, timeout):
    # Wait minimum time first
    sleep(min_wait)

    while elapsed < timeout:
        # Check 1: File exists?
        if not output_path.exists():
            continue

        # Check 2: File was created AFTER job started?
        file_mtime = datetime.fromtimestamp(output_path.stat().st_mtime)
        if file_mtime < job_start_time:
            continue  # Old file from previous run

        # Check 3: File has reasonable content?
        if output_path.stat().st_size < 100:
            continue  # Too small, probably incomplete

        # Success!
        return True

    return False  # Timeout
```

### Why This Works

- **Atomic**: File existence checks are atomic operations
- **No parsing**: Don't need to parse output or look for patterns
- **Race-condition free**: mtime comparison ensures new file
- **Size heuristic**: Ensures Claude wrote meaningful content
- **Timeout safety**: Always has maximum wait time

## TMUX Command Pattern

### Critical Pattern: send_instruction()

```python
def send_instruction(session_name: str, instruction: str) -> bool:
    """
    Send instruction to Claude following SmartBuild pattern.

    CRITICAL: This exact pattern is required for reliability.
    DO NOT modify timing or command structure.
    """
    # Step 1: Send text literally
    subprocess.run([
        "tmux", "send-keys",
        "-t", session_name,
        "-l", instruction  # -l = literal mode (no escaping)
    ])

    # Step 2: Wait for text to appear
    time.sleep(TMUX_SEND_COMMAND_DELAY)  # 0.3s

    # Step 3: Send Enter key
    subprocess.run([
        "tmux", "send-keys",
        "-t", session_name,
        "Enter"
    ])

    # Step 4: Wait for processing
    time.sleep(TMUX_SEND_ENTER_DELAY)  # 1.2s

    return True
```

### Why -l (Literal) Flag?

- **No escaping needed**: Special characters handled correctly
- **Long strings**: Doesn't break on newlines or quotes
- **Reliable**: No interpretation by shell

## Configuration Management

### Environment Variables

```bash
# Optional overrides
export USER_ID="custom_user"
export CLI_PATH="claude"
export CLI_MODEL="sonnet"
export BACKEND_PORT="8000"
export LOG_LEVEL="INFO"

# Skip validation (for testing)
export SKIP_CONFIG_VALIDATION="true"
```

### Helper Functions (config.py)

```python
get_session_path(session_id)          # → sessions/active/<session_id>/
get_prompts_dir(session_id)           # → sessions/active/<session_id>/prompts/
get_output_dir(session_id)            # → sessions/active/<session_id>/output/
get_session_log_path(session_id)      # → sessions/active/<session_id>/logs/session_<id>.log
get_job_queue_path(session_id)        # → sessions/active/<session_id>/job_queue.json
get_tmux_job_session_name(job_id)     # → tmux_builder_job_<job_id>
```

## Error Handling

### Job Execution Errors

```python
try:
    JobQueueManager.execute_job(session_id, job_id)
except Exception as e:
    SessionManager.update_job(session_id, job_id, {
        'status': 'failed',
        'error': str(e)
    })
    # Cleanup tmux session
    TmuxHelper.kill_session(job['tmux_session'])
```

### Timeout Handling

```python
if not _wait_for_completion(..., timeout=300):
    SessionManager.update_job(session_id, job_id, {
        'status': 'failed',
        'error': 'Timeout or completion check failed'
    })
    return False
```

### TMUX Session Cleanup

Sessions are always cleaned up after job completion (success or failure):

```python
# After job completes
TmuxHelper.kill_session(tmux_session_name)
```

## Testing

### Running Tests

```bash
cd backend
python3 test_tmux_integration.py
```

### Test Output

```
============================================================
tmux-builder Configuration
============================================================
Base Directory:      /path/to/backend
Sessions Directory:  /path/to/sessions
CLI Command:         claude --dangerously-skip-permissions
TMUX Prefix:         tmux_builder
Max Concurrent Jobs: 4
Backend Port:        8000
Log Level:           INFO
============================================================

============================================================
TEST 1: Echo Test (File-Based I/O)
============================================================
✓ Session created: /path/to/sessions/active/test_20260124_123456
✓ Job created: job_123456

📝 Executing job (this will take ~30-60 seconds)...
   - Creating TMUX session
   - Starting Claude CLI
   - Writing prompt to disk
   - Sending instruction to Claude
   - Waiting for output file...

✅ TEST PASSED!

Job Status: completed
Output Path: /path/to/output/echo_output_123456.txt

📄 Output Content:
==================
Echo Test Response
==================
Original message: Hello from tmux-builder test!
Timestamp: 2026-01-24T12:35:15.123456
Status: SUCCESS
```

## Performance Characteristics

### Latency Sources

| Component | Typical Latency |
|-----------|----------------|
| Session creation | 3-5s (Claude CLI init) |
| Prompt preparation | 10-50ms (file write) |
| TMUX command send | 100-200ms |
| Claude processing | 1-10s (depends on task) |
| Completion detection | 0-2s (file polling) |
| File I/O | <10ms |

### Job Timing Examples

| Job Type | Min Wait | Timeout | Typical Duration |
|----------|----------|---------|------------------|
| echo_test | 5s | 60s | 10-20s |
| file_analysis | 10s | 300s | 30-90s |
| code_generation | 20s | 600s | 60-300s |

## Scalability

### Current Design

- **Single machine**: All sessions run on same host
- **Session isolation**: Each job gets own TMUX session
- **Concurrent jobs**: Can run up to MAX_CONCURRENT_JOBS (4) in parallel
- **File-based**: Persistent storage for debugging

### Multi-Job Execution

```python
# Sessions are isolated by TMUX session name
session_1 = "tmux_builder_job_001"  # Job 1
session_2 = "tmux_builder_job_002"  # Job 2
session_3 = "tmux_builder_job_003"  # Job 3

# Each runs independently
# Each has own prompts/ and output/ directories
# No interference between jobs
```

## Dependencies

### Required

- **Python 3.8+**
- **tmux**: Terminal multiplexer (`sudo apt-get install tmux`)
- **Claude CLI**: Official Claude command-line tool
  - Install from: https://claude.ai/download
  - Must be in PATH as `claude`

### Python Packages

```
# No external packages required
# Uses only Python standard library:
# - subprocess
# - pathlib
# - json
# - logging
# - datetime
```

## Future Enhancements

1. **API Server**: Add FastAPI REST API for web frontend
2. **WebSocket**: Real-time job progress updates
3. **Job Priority Queue**: Handle priority/ordering of jobs
4. **Parallel Execution**: Execute multiple jobs concurrently
5. **Job Retry Logic**: Automatic retry on failures
6. **Enhanced Monitoring**: Better progress tracking
7. **Job Cancellation**: Ability to cancel running jobs
8. **Session Persistence**: Save/restore sessions across restarts

## Key Differences from Typical Chat Interfaces

This implementation is **job-based**, not chat-based:

| Feature | Typical Chat | Tmux Builder |
|---------|--------------|--------------|
| Pattern | Interactive conversation | Batch job execution |
| I/O | stdin/stdout | Files (prompts/output) |
| Persistence | Chat history | Job queue + outputs |
| Session | Long-running | Per-job TMUX sessions |
| Completion | Response parsing | File monitoring |
| Use case | Human interaction | Programmatic automation |

## Conclusion

Tmux Builder implements the **SmartBuild file-based I/O pattern** for reliable, programmatic interaction with Claude AI. By using files for input/output and TMUX for process isolation, it provides a robust foundation for automated AI tasks without the complexity of parsing stdout or managing long-running interactive sessions.

The architecture prioritizes:
- **Reliability**: File-based I/O is atomic and race-condition free
- **Simplicity**: Standard file operations, no complex parsing
- **Debuggability**: All prompts and outputs persisted to disk
- **Isolation**: Each job runs in its own TMUX session
- **Testability**: Easy to test with file system operations
