# Quick Start Guide

Get Tmux Builder running in 2 minutes!

## Prerequisites Check

```bash
# Check Python
python3 --version  # Need 3.8+

# Check tmux
tmux -V           # Need tmux installed

# Check Claude CLI
claude --version  # Need Claude CLI configured
```

## Setup & Run

### 1. Navigate to Backend

```bash
cd backend
```

### 2. Run Integration Test

```bash
python3 test_tmux_integration.py
```

**Expected output:**
```
============================================================
tmux-builder Configuration
============================================================
✓ Claude CLI found: claude
✓ Using flags: --dangerously-skip-permissions

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

## What Just Happened?

The test demonstrated the **SmartBuild file-based I/O pattern**:

1. ✅ Created a session directory
2. ✅ Wrote a prompt file to disk
3. ✅ Created an isolated TMUX session with Claude CLI
4. ✅ Sent instruction to Claude to read the prompt file
5. ✅ Claude wrote response to output file
6. ✅ System detected completion via file monitoring
7. ✅ Cleaned up TMUX session

## Programmatic Usage

```python
from session_manager import SessionManager
from job_queue_manager import JobQueueManager

# Create session
session_id = "my_automation_123"
SessionManager.create_session(session_id, {
    'description': 'My automation session'
})

# Add and execute job
job = {
    'id': 'job_1',
    'type': 'echo_test',
    'message': 'Hello from my script!'
}
SessionManager.add_job(session_id, job)
success = JobQueueManager.execute_job(session_id, 'job_1')

# Get output
if success:
    job = SessionManager.get_job(session_id, 'job_1')
    with open(job['output_path'], 'r') as f:
        print(f.read())
```

## Troubleshooting

### "Claude CLI not found"
```bash
# Verify Claude CLI is installed
which claude
claude --version

# If not found, install from: https://claude.ai/download
```

### "tmux is not installed"
```bash
# Install tmux
sudo apt-get install tmux

# Verify installation
tmux -V
```

### Job timeouts
- Check session logs: `sessions/active/<session_id>/logs/session_<id>.log`
- Increase timeout in `backend/config.py` if needed
- Attach to TMUX session to see Claude: `tmux attach -t tmux_builder_job_*`

## What's Happening Behind the Scenes?

```
Job Created
    ↓
TMUX session created (isolated)
    ↓
Prompt written to: prompts/job_<timestamp>.txt
    ↓
Instruction sent via TMUX: "Read prompt file and write output"
    ↓
Claude CLI reads prompt
    ↓
Claude writes response to: output/job_output_<timestamp>.txt
    ↓
System monitors file (exists + mtime + size)
    ↓
Completion detected!
```

## Project Structure

```
tmux-builder/
├── backend/                      # Python backend modules
│   ├── config.py                 # Configuration
│   ├── session_manager.py        # Session/job persistence
│   ├── job_queue_manager.py      # Job execution
│   ├── prompt_preparer.py        # Prompt generation
│   ├── tmux_helper.py            # TMUX operations
│   └── test_tmux_integration.py  # ← ENTRY POINT
└── sessions/                     # Runtime storage (auto-created)
    ├── active/
    │   └── <session_id>/
    │       ├── prompts/          # Prompt files
    │       ├── output/           # Claude's responses
    │       ├── logs/             # Session logs
    │       ├── metadata.json     # Session metadata
    │       └── job_queue.json    # Job queue
    └── deleted/                  # Archived sessions
```

## Next Steps

- Read [README.md](README.md) for overview and usage examples
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for technical deep dive
- Read [SETUP.md](SETUP.md) for detailed setup instructions
- Explore session files in `sessions/active/` to see generated artifacts

## Key Features

✅ **File-based I/O**: Prompts/outputs via files (SmartBuild pattern)
✅ **Isolated TMUX sessions**: Each job runs independently
✅ **No dependencies**: Python stdlib only
✅ **Persistent artifacts**: All prompts/outputs saved
✅ **Reliable completion detection**: File monitoring (no parsing)
✅ **Comprehensive logging**: Session event logs
✅ **WSL2 compatible**: Proven timing patterns

## Inspect Session Artifacts

```bash
# List active sessions
ls sessions/active/

# View session structure
tree sessions/active/test_<timestamp>/

# Read prompt file
cat sessions/active/test_<timestamp>/prompts/echo_test_*.txt

# Read Claude's output
cat sessions/active/test_<timestamp>/output/echo_output_*.txt

# View session log
cat sessions/active/test_<timestamp>/logs/session_*.log
```

## Debug Live TMUX Sessions

```bash
# List active TMUX sessions
tmux list-sessions

# Attach to job session (watch Claude in real-time)
tmux attach -t tmux_builder_job_<job_id>

# Detach from session: Press Ctrl+B then D

# Capture pane output without attaching
tmux capture-pane -t tmux_builder_job_<job_id> -p
```

## Clean Up

```bash
# Kill all TMUX sessions
tmux kill-server

# Delete session directories
rm -rf sessions/active/*
rm -rf sessions/deleted/*
```

## Job Types Available

1. **echo_test**: Simple echo (testing) - 60s timeout
2. **file_analysis**: Analyze files and generate reports - 300s timeout
3. **generic**: Custom prompts - 300s timeout (configurable)

Happy building! 🚀
