# Tmux Builder

A backend system for programmatic interaction with Claude AI through isolated tmux sessions, implementing the **SmartBuild file-based I/O pattern**.

## Architecture

- **Backend**: Pure Python (no web server)
- **Session Management**: tmux (isolated per-job sessions)
- **AI Engine**: Claude CLI
- **Persistence**: File-based (job queues, prompts, outputs)
- **Pattern**: SmartBuild file-based I/O

## How It Works

1. **Create Session**: Initialize session directory with metadata
2. **Add Job**: Queue a job (echo_test, file_analysis, generic)
3. **Execute Job**:
   - Create isolated TMUX session
   - Write prompt to disk (`prompts/` directory)
   - Instruct Claude to read prompt file
   - Claude writes response to disk (`output/` directory)
   - Monitor output file for completion (file existence + mtime + size)
4. **Completion Detection**: File-based monitoring (no stdout parsing)
5. **Cleanup**: Kill TMUX session, job marked complete

## Project Structure

```
tmux-builder/
├── backend/                      # Python backend modules
│   ├── config.py                 # Configuration & path helpers (243 lines)
│   ├── session_manager.py        # Session/job persistence (207 lines)
│   ├── job_queue_manager.py      # Job execution (256 lines)
│   ├── prompt_preparer.py        # Prompt generation (223 lines)
│   ├── tmux_helper.py            # TMUX operations (222 lines)
│   └── test_tmux_integration.py  # Integration tests (165 lines)
└── sessions/                     # Runtime storage (auto-created)
    ├── active/                   # Active sessions
    │   └── <session_id>/
    │       ├── prompts/          # Prompt files
    │       ├── output/           # Claude's responses
    │       ├── logs/             # Session logs
    │       ├── metadata.json     # Session metadata
    │       └── job_queue.json    # Job queue
    └── deleted/                  # Deleted sessions (archived)
```

## Setup

### Requirements

```bash
# System dependencies
sudo apt-get install tmux python3 python3-pip

# Claude CLI (required)
# Install from: https://claude.ai/download
# Verify: claude --version
```

### Backend Setup

```bash
cd backend

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate

# No external dependencies needed (uses Python stdlib only)
```

## Usage

### Running Tests

```bash
cd backend
python3 test_tmux_integration.py
```

### Example Test Output

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
```

### Programmatic Usage

```python
from session_manager import SessionManager
from job_queue_manager import JobQueueManager
from datetime import datetime

# 1. Create session
session_id = f"my_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
SessionManager.create_session(session_id, {
    'description': 'My automation session',
    'created_by': 'my_script'
})

# 2. Add job
job = {
    'id': f"job_{datetime.now().strftime('%H%M%S')}",
    'type': 'echo_test',
    'message': 'Hello from automation!'
}
SessionManager.add_job(session_id, job)

# 3. Execute job
success = JobQueueManager.execute_job(session_id, job['id'])

# 4. Get results
if success:
    job = SessionManager.get_job(session_id, job['id'])
    output_path = job['output_path']

    with open(output_path, 'r') as f:
        result = f.read()
        print(result)
```

## Key Features

### SmartBuild Pattern
- **File-based I/O**: Prompts and outputs via files (not stdout parsing)
- **Atomic completion detection**: File existence + mtime + size checks
- **Persistent artifacts**: All prompts/outputs saved for debugging
- **No terminal buffer limits**: Handle large content

### Reliability
- **Isolated TMUX sessions**: Each job runs in its own session
- **Critical timing patterns**: Proven delays for TMUX command reliability
- **Timeout protection**: All jobs have configurable timeouts
- **Error handling**: Graceful failure with cleanup

### Job Types
1. **echo_test**: Simple echo for testing (60s timeout)
2. **file_analysis**: Analyze files and generate reports (300s timeout)
3. **generic**: Custom prompts with flexible timeouts

### Monitoring & Debugging
- Session logs: Event-based logging per session
- Job queue persistence: Full job history saved
- Output artifacts: All Claude responses preserved
- TMUX session inspection: Attach to live sessions for debugging

## Core Modules

### config.py
- Centralized configuration
- Path management helpers
- Timing constants (CRITICAL - do not modify)
- Validation (check tmux, Claude CLI)

### session_manager.py
- Session/job data persistence
- Job queue management (add, update, get)
- Session logging
- Metadata handling

### job_queue_manager.py
- Job execution orchestration
- TMUX session creation per job
- File-based completion monitoring
- Timeout and error handling

### prompt_preparer.py
- Prompt generation for different job types
- File writing (prompts directory)
- Instruction formatting
- Output path generation

### tmux_helper.py
- Low-level TMUX operations
- Session creation (with Claude CLI init)
- Command sending (with critical timing)
- Pane output capture
- Session cleanup

## Configuration

### Environment Variables

```bash
export USER_ID="my_user"                    # Default: default_user
export CLI_PATH="claude"                    # Default: claude
export CLI_MODEL="sonnet"                   # Default: sonnet
export BACKEND_PORT="8000"                  # Default: 8000
export LOG_LEVEL="INFO"                     # Default: INFO
export SKIP_CONFIG_VALIDATION="true"        # Skip validation (testing)
```

### Timing Configuration (CRITICAL)

```python
# From config.py - DO NOT MODIFY without thorough testing

TMUX_SEND_COMMAND_DELAY = 0.3   # After send-keys
TMUX_SEND_ENTER_DELAY = 1.2     # After Enter key
TMUX_CLAUDE_INIT_DELAY = 3.0    # After starting Claude CLI
```

### Job Timeouts

```python
JOB_TIMEOUTS = {
    'echo_test': 60,        # 1 minute
    'file_analysis': 300,   # 5 minutes
    'code_generation': 600, # 10 minutes
    'default': 300          # 5 minutes
}
```

## Dependencies

### Required
- **Python 3.8+**: Standard library only (no pip packages)
- **tmux**: Terminal multiplexer
- **Claude CLI**: Official CLI tool from Anthropic

### No External Python Packages
Uses only Python standard library:
- `subprocess` - TMUX command execution
- `pathlib` - Path management
- `json` - Data persistence
- `logging` - Event logging
- `datetime` - Timestamps
- `time` - Timing delays

## Completion Detection

### File-Based Strategy

```python
# Monitors output file for completion
while elapsed < timeout:
    # Check 1: File exists?
    if not output_path.exists():
        continue

    # Check 2: File created AFTER job started?
    if file_mtime < job_start_time:
        continue  # Old file from previous run

    # Check 3: File has reasonable content?
    if file_size < 100 bytes:
        continue  # Too small, incomplete

    # All checks passed - job complete!
    return True
```

### Benefits
- No stdout parsing
- Atomic file operations
- Race-condition free (mtime check)
- Handles large content
- Simple and reliable

## Performance

### Typical Job Latency

| Component | Latency |
|-----------|---------|
| Session creation | 3-5s (Claude CLI init) |
| Prompt preparation | 10-50ms (file write) |
| TMUX command send | 100-200ms |
| Claude processing | 1-10s (varies by task) |
| Completion detection | 0-2s (file polling) |

### Job Examples

| Job Type | Min Wait | Timeout | Typical Duration |
|----------|----------|---------|------------------|
| echo_test | 5s | 60s | 10-20s |
| file_analysis | 10s | 300s | 30-90s |
| code_generation | 20s | 600s | 60-300s |

## Scalability

- **Concurrent jobs**: Up to `MAX_CONCURRENT_JOBS` (default: 4)
- **Session isolation**: Each job in its own TMUX session
- **No interference**: Jobs don't affect each other
- **File-based**: Simple, persistent storage

## Future Enhancements

1. **API Server**: Add FastAPI REST API for web frontend
2. **Web UI**: React interface for job management
3. **WebSocket**: Real-time job progress updates
4. **Job Priority Queue**: Priority-based execution
5. **Parallel Execution**: Improved concurrent job handling
6. **Job Retry Logic**: Automatic retry on transient failures
7. **Enhanced Monitoring**: Real-time progress tracking
8. **Job Cancellation**: Cancel running jobs
9. **Session Persistence**: Save/restore sessions across restarts

## Troubleshooting

### Claude CLI Not Found
```bash
# Verify Claude CLI is installed and in PATH
which claude
claude --version

# If not found, install from: https://claude.ai/download
```

### TMUX Not Found
```bash
# Install tmux
sudo apt-get install tmux

# Verify installation
tmux -V
```

### Job Timeouts
- Check `sessions/active/<session_id>/logs/` for detailed logs
- Increase timeout in `config.py` for complex jobs
- Verify Claude CLI is responding (attach to TMUX session)

### Debugging TMUX Sessions
```bash
# List active sessions
tmux list-sessions

# Attach to a job session
tmux attach -t tmux_builder_job_<job_id>

# View pane content
tmux capture-pane -t tmux_builder_job_<job_id> -p
```

## Documentation

All documentation is organized in the `docs/` directory:

### Architecture (`docs/architecture/`)
- **ARCHITECTURE.md** - Detailed technical architecture and design decisions
- **SMARTBUILD_ARCHITECTURE_ANALYSIS.md** - Deep dive into SmartBuild file-based I/O pattern

### Guides (`docs/guides/`)
- **QUICKSTART.md** - Quick start guide for getting up and running
- **SETUP.md** - Detailed setup instructions
- **TESTING_GUIDE.md** - How to test the backend and UI
- **HOW_TO_IMPLEMENT_TMUX_IN_ANY_PROJECT.md** - Pattern guide for implementing tmux in other projects

### Project Documentation (`docs/project/`)
- **PROJECT_STATUS.txt** - Current project status and roadmap
- **PROJECT_SUMMARY.md** - High-level project overview
- **IMPLEMENTATION_SUMMARY.md** - Implementation details and decisions

### Implementation Plans (`docs/plans/`)
- **2026-01-25-autonomous-build-agent.md** - Comprehensive implementation plan for autonomous build agent

### Validation (`docs/validation/`)
- **TEST_VALIDATION_REPORT.md** - Test results and validation status

## License

MIT
