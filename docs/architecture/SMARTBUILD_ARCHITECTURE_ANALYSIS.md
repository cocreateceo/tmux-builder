# SmartBuild Architecture - Complete Flow Analysis

**Source Repository**: https://github.com/GopiSunware/SmartBuild
**Platform**: DevGenious Platform v5.16.0
**Analysis Date**: 2026-01-23

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture Overview](#system-architecture-overview)
3. [File-Based I/O Pattern](#file-based-io-pattern)
4. [Complete Data Flow](#complete-data-flow)
5. [TMUX Integration Details](#tmux-integration-details)
6. [Job Queue System](#job-queue-system)
7. [Synchronization Mechanisms](#synchronization-mechanisms)
8. [State Diagrams](#state-diagrams)
9. [Critical Implementation Details](#critical-implementation-details)

---

## Executive Summary

SmartBuild orchestrates Claude CLI through TMUX sessions using a **file-based I/O pattern**. The system writes prompts to disk files, instructs Claude to read them, and monitors output files for completion.

### Key Architectural Patterns

1. **Two-Tier TMUX System**: Main session (persistent) + Job sessions (ephemeral)
2. **File-Based Prompts**: Prompts written to disk, not sent directly via stdin
3. **Completion Detection**: File existence + modification time checking
4. **Queue-Based Processing**: Background monitor manages job execution
5. **Strict Timing**: Precise delays for Claude initialization and command sending

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      USER INTERFACE (Streamlit)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ Requirements │  │  Solutions   │  │  Artifacts (12 types) │ │
│  │     Tab      │  │     Tab      │  │        Tabs           │ │
│  └──────────────┘  └──────────────┘  └───────────────────────┘ │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ├─► User clicks "Analyze" or "Generate"
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    JOB QUEUE MANAGER (Python)                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Job Added to Queue (job_queue.json)                     │  │
│  │  {                                                        │  │
│  │    "id": "job_20250923_120530_abc123",                   │  │
│  │    "type": "cost_analysis",                              │  │
│  │    "status": "pending",  ◄─ States: pending → running →  │  │
│  │    "tmux_session": "smartbuild_ca_xyz_run",              │  │
│  │    "output_path": "/path/to/output"                      │  │
│  │  }                                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ├─► Monitor picks up pending jobs
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              JOB QUEUE MONITOR (Background Process)              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  • Polls job_queue.json every 2 seconds                  │  │
│  │  • Enforces max 4 concurrent jobs                        │  │
│  │  • Creates TMUX sessions                                 │  │
│  │  • Monitors file system for completion                   │  │
│  │  • Updates job status                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ├─► Create/Use TMUX Session
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TMUX SESSION LAYER                          │
│  ┌────────────────────────────┐  ┌──────────────────────────┐  │
│  │ Main Session (Persistent)  │  │ Job Sessions (Ephemeral) │  │
│  │ smartbuild_s_<session_id>  │  │ smartbuild_<job>_<run>   │  │
│  │                            │  │                          │  │
│  │ • Requirements extraction  │  │ • Cost analysis          │  │
│  │ • Solution generation      │  │ • Terraform code         │  │
│  │ • Lives entire session     │  │ • CloudFormation         │  │
│  │                            │  │ • Up to 4 concurrent     │  │
│  └────────────────────────────┘  └──────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ├─► Claude CLI runs in each session
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CLAUDE CLI INSTANCE                           │
│  Command: claude --dangerously-skip-permissions   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  File I/O Pattern:                                        │  │
│  │                                                           │  │
│  │  INPUT:  Read from disk file (prompt_*.txt)              │  │
│  │  OUTPUT: Write to disk file (specified in prompt)        │  │
│  │                                                           │  │
│  │  Claude reads: /path/to/prompts/cost_analysis_*.txt      │  │
│  │  Claude writes: /path/to/artifacts/cost_analysis         │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ├─► Files written to disk
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  FILE SYSTEM (Session Storage)                   │
│                                                                  │
│  smartbuild/sessions/active/<session_id>/                       │
│  ├── metadata.json                                              │
│  ├── requirements.json                                          │
│  ├── runs/<run_id>/                                             │
│  │   ├── job_queue.json  ◄─ Monitor reads this                 │
│  │   └── artifacts/<diagram_id>/                               │
│  │       ├── diagram.drawio                                     │
│  │       ├── cost_analysis  ◄─ Monitor checks this             │
│  │       ├── terraform/                                         │
│  │       ├── cloudformation/                                    │
│  │       └── prompts/                                           │
│  │           ├── cost_analysis_20250923.txt  ◄─ Claude reads   │
│  │           └── terraform_20250923.txt                         │
│  └── logs/                                                      │
│      └── complete_session_*.log                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## File-Based I/O Pattern

### The Core Pattern (CRITICAL)

SmartBuild does **NOT** send prompts directly to Claude via `tmux send-keys`. Instead:

```
┌─────────────────────────────────────────────────────────────┐
│                    PROMPT PREPARATION                        │
│                                                              │
│  1. Build full prompt (5000+ characters)                    │
│     ├─ Load requirements.json                               │
│     ├─ Load architecture diagram (draw.io XML)              │
│     ├─ Load agent template (.claude/agents/*.md)            │
│     └─ Combine with task instructions                       │
│                                                              │
│  2. Write prompt to disk                                    │
│     └─ File: smartbuild/sessions/active/{session}/          │
│               runs/{run}/artifacts/{diagram}/prompts/        │
│               cost_analysis_20250923_120530.txt             │
│                                                              │
│  3. Return INSTRUCTION (not the prompt!)                    │
│     └─ "Please read and process                             │
│         /full/path/to/cost_analysis_20250923_120530.txt.    │
│         Your output should be saved to                      │
│         /full/path/to/cost_analysis"                        │
└─────────────────────────────────────────────────────────────┘
          │
          ├─► Instruction sent via tmux send-keys
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                   TMUX COMMAND SENDING                       │
│                                                              │
│  tmux send-keys -t session -l "Please read and process..."  │
│  sleep 0.3                                                   │
│  tmux send-keys -t session Enter                            │
│  sleep 1.2                                                   │
└─────────────────────────────────────────────────────────────┘
          │
          ├─► Claude receives instruction
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                     CLAUDE PROCESSING                        │
│                                                              │
│  1. Claude reads instruction                                │
│  2. Claude opens /path/to/cost_analysis_*.txt               │
│  3. Claude reads FULL PROMPT from file                      │
│  4. Claude processes (analyzes, generates)                  │
│  5. Claude writes output to specified OUTPUT_PATH           │
└─────────────────────────────────────────────────────────────┘
          │
          ├─► Output file created on disk
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                  COMPLETION DETECTION                        │
│                                                              │
│  Monitor polls every 5 seconds:                             │
│  ├─ Does output file exist?                                 │
│  ├─ Is file mtime > job_start_timestamp?                    │
│  ├─ Is file size > minimum (100 bytes)?                     │
│  └─ If all YES → Mark job COMPLETED                         │
└─────────────────────────────────────────────────────────────┘
```

### Why This Pattern?

1. **Large Prompts**: Prompts can be 5000+ characters (too long for reliable tmux input)
2. **Quote Escaping**: Avoids complex quote escaping in shell commands
3. **Context Preservation**: Full context available to Claude (requirements, diagrams, templates)
4. **Debugging**: Prompts saved on disk for inspection and replay
5. **Reliability**: File I/O is more reliable than piping large text through tmux

---

## Complete Data Flow

### Job Execution Sequence (Step-by-Step)

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: USER ACTION                                         │
├─────────────────────────────────────────────────────────────┤
│ User clicks "Generate Cost Analysis" button                 │
│ Frontend: spa_middleware_dynamic.py                         │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: JOB CREATION                                        │
├─────────────────────────────────────────────────────────────┤
│ job_queue_manager_v2.add_job()                              │
│                                                              │
│ Job Object:                                                 │
│ {                                                           │
│   "id": "job_20250923_120530_abc123",                      │
│   "type": "cost_analysis",                                 │
│   "status": "pending",                                     │
│   "session_id": "session_xyz",                             │
│   "run_id": "run_20250923",                                │
│   "metadata": {                                            │
│     "diagram_path": "/path/to/diagram.drawio",            │
│     "diagram_name": "MyArchitecture"                       │
│   },                                                       │
│   "output_path": "/path/to/cost_analysis",                │
│   "created_at": "2025-09-23T12:05:30.123456"              │
│ }                                                          │
│                                                              │
│ Written to: job_queue.json                                  │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: MONITOR DETECTION                                   │
├─────────────────────────────────────────────────────────────┤
│ Background: job_queue_monitor.py (separate process)        │
│                                                              │
│ • Polls job_queue.json every 2 seconds                     │
│ • Detects new job with status="pending"                    │
│ • Checks concurrency: Currently 2/4 jobs running → OK      │
│ • Marks job as "running"                                   │
│ • Records job_start_timestamp                               │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: TMUX SESSION SETUP                                  │
├─────────────────────────────────────────────────────────────┤
│ tmux_helper.create_or_get_session()                         │
│                                                              │
│ Session Name: smartbuild_ca_xyz_run20250923                │
│                                                              │
│ Commands:                                                   │
│ 1. tmux new-session -d -s smartbuild_ca_xyz_run20250923   │
│ 2. tmux send-keys -t session -l "cd /path/to/session"     │
│    sleep 0.3                                               │
│    tmux send-keys -t session Enter                         │
│    sleep 0.5                                               │
│ 3. tmux send-keys -t session -l "claude --dangerously-..."│
│    sleep 0.3                                               │
│    tmux send-keys -t session Enter                         │
│    sleep 3.0  ◄─ CRITICAL: Wait for Claude to initialize  │
│ 4. Send 3x Enter (bypass any initial prompts)             │
│ 5. Send probe: echo '[PROBE] Claude ready'                │
│ 6. Verify probe appears in captured output                 │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: PROMPT PREPARATION                                  │
├─────────────────────────────────────────────────────────────┤
│ prompt_preparers.prepare_cost_analysis_prompt()            │
│                                                              │
│ Input Sources:                                              │
│ ├─ requirements.json (user requirements)                   │
│ ├─ diagram.drawio (architecture XML)                       │
│ └─ .claude/agents/cost-analyzer.md (agent template)       │
│                                                              │
│ Prompt Structure:                                           │
│ ┌───────────────────────────────────────────────────────┐  │
│ │ You are an AWS Cost Optimization Specialist.          │  │
│ │                                                        │  │
│ │ [AGENT TEMPLATE CONTENT - 2000 chars]                 │  │
│ │                                                        │  │
│ │ ## Project Requirements:                              │  │
│ │ [FULL requirements.json - 1500 chars]                 │  │
│ │                                                        │  │
│ │ ## Architecture Diagram (draw.io XML):                │  │
│ │ [FULL diagram XML - 5000+ chars]                      │  │
│ │                                                        │  │
│ │ ## Your Task:                                         │  │
│ │ Please analyze this AWS architecture and provide      │  │
│ │ TWO cost calculations:                                │  │
│ │ 1. Baseline cost                                      │  │
│ │ 2. Optimized cost                                     │  │
│ │                                                        │  │
│ │ OUTPUT_PATH: /path/to/cost_analysis                   │  │
│ │                                                        │  │
│ │ Write your analysis to OUTPUT_PATH when complete.     │  │
│ └───────────────────────────────────────────────────────┘  │
│                                                              │
│ Write to: /path/to/prompts/cost_analysis_20250923.txt      │
│                                                              │
│ Return: Instruction text (not the full prompt!)            │
│         "Please read and process                           │
│          /path/to/prompts/cost_analysis_20250923.txt"     │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 6: SEND INSTRUCTION TO CLAUDE                          │
├─────────────────────────────────────────────────────────────┤
│ tmux_helper.send_command()                                  │
│                                                              │
│ instruction = "Please read and process                      │
│                /full/path/to/cost_analysis_20250923.txt.    │
│                Your output should be saved to               │
│                /full/path/to/cost_analysis"                 │
│                                                              │
│ Commands:                                                   │
│ 1. tmux send-keys -t session -l "Please read and..."      │
│    └─ Note: -l flag sends LITERALLY (no interpretation)   │
│ 2. sleep 0.3  ◄─ CRITICAL: Give tmux time to process      │
│ 3. tmux send-keys -t session Enter                         │
│ 4. sleep 1.2  ◄─ CRITICAL: Give Claude time to start      │
│                                                              │
│ Job status updated: progress=50%                            │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 7: CLAUDE PROCESSING (Inside TMUX Session)            │
├─────────────────────────────────────────────────────────────┤
│ Claude CLI receives instruction via stdin                   │
│ Claude interprets: "read file at this path"                │
│ Claude opens: /path/to/prompts/cost_analysis_20250923.txt  │
│ Claude reads: FULL prompt (8000+ characters)               │
│ Claude parses:                                              │
│   ├─ Agent instructions                                    │
│   ├─ Project requirements                                  │
│   ├─ Architecture diagram                                  │
│   └─ Task definition                                       │
│ Claude analyzes architecture                                │
│ Claude calculates costs                                     │
│ Claude formats output                                       │
│ Claude writes to: /path/to/cost_analysis                   │
│ Claude returns to prompt (ready for next instruction)      │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 8: COMPLETION DETECTION                                │
├─────────────────────────────────────────────────────────────┤
│ Monitor loop (every 5 seconds):                            │
│                                                              │
│ check_job_completion():                                     │
│ ├─ output_path = Path("/path/to/cost_analysis")           │
│ ├─ Check 1: Does file exist?                              │
│ │   └─ output_path.exists() → YES ✓                       │
│ ├─ Check 2: Is file new (created after job start)?        │
│ │   └─ file_mtime > job_start_timestamp → YES ✓           │
│ ├─ Check 3: Is file size reasonable?                      │
│ │   └─ file_size > 100 bytes → YES ✓                      │
│ └─ All checks passed → Job is COMPLETE!                    │
│                                                              │
│ Update job_queue.json:                                      │
│ {                                                           │
│   "status": "completed",                                   │
│   "progress": 100,                                         │
│   "completed_at": "2025-09-23T12:07:45.345678"            │
│ }                                                          │
│                                                              │
│ Optional: Kill TMUX session (if single-use)                │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 9: UI REFRESH                                          │
├─────────────────────────────────────────────────────────────┤
│ Streamlit polls job_queue.json (every 2 seconds)           │
│ Detects status="completed"                                 │
│ Reads output file: /path/to/cost_analysis                  │
│ Parses content (JSON/Markdown/XML depending on job type)   │
│ Renders in "Cost Analysis" tab:                            │
│   ├─ Baseline costs table                                  │
│   ├─ Optimized costs table                                 │
│   ├─ Savings summary                                       │
│   └─ Recommendations list                                  │
│ User sees results ✓                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## TMUX Integration Details

### TMUX Command Pattern (CRITICAL - MUST FOLLOW EXACTLY)

```python
# Location: utils/tmux_helper.py

def send_command(session_name: str, command: str):
    """
    Send a command to a TMUX session.

    CRITICAL PATTERN - Do not modify timing or structure!
    """

    # Step 1: Send command LITERALLY (-l flag)
    # This prevents shell interpretation of special characters
    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, "-l", command],
        stderr=subprocess.DEVNULL
    )

    # Step 2: Wait for tmux to process
    # CRITICAL: 0.3s is minimum, tested on WSL2 and Linux
    time.sleep(0.3)

    # Step 3: Send Enter separately
    # Sending Enter after delay ensures full command is in buffer
    subprocess.run(
        ["tmux", "send-keys", "-t", session_name, "Enter"],
        stderr=subprocess.DEVNULL
    )

    # Step 4: Wait for command execution
    # CRITICAL: 1.2s for Claude initialization commands
    # Can be shorter (0.5s) for simple commands
    time.sleep(1.2)
```

### Why These Specific Delays?

| Delay | Location | Reason |
|-------|----------|--------|
| **0.3s** | After `send-keys -l` | tmux internal buffer processing time |
| **1.2s** | After `send-keys Enter` | Claude CLI initialization time |
| **3.0s** | After starting Claude | Wait for full Claude startup |
| **0.5s** | After Enter keys (bypass prompts) | Allow prompt to clear |

### TMUX Session Naming Convention

```python
# Main session (persistent, one per user session)
MAIN_SESSION = f"smartbuild_s_{session_short_id}"
# Example: smartbuild_s_20250923_1

# Job session (ephemeral, one per job)
JOB_SESSION = f"smartbuild_{job_prefix}_{session_short}_{run_id}"
# Example: smartbuild_ca_xyz_run20250923
#          ^^^^^^^^^^^ ^^^ ^^^^^^^^^^^^^^ ^^^^^^^^^^^
#          prefix      job session_id    run_id
#                      abbr

# Job type abbreviations:
# ca = cost_analysis
# tf = terraform_code
# cf = cloudformation_template
# sd = solution_designer
# etc.
```

### TMUX Session Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                   MAIN SESSION LIFECYCLE                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  User clicks "New Session"                                  │
│    ↓                                                         │
│  User enters requirements                                   │
│    ↓                                                         │
│  User clicks "Analyze"                                      │
│    ↓                                                         │
│  CREATE MAIN SESSION: smartbuild_s_<session_id>            │
│    └─ Session persists for entire user session              │
│    ↓                                                         │
│  Start Claude in session                                    │
│    ↓                                                         │
│  Run requirements_extraction job                            │
│    ↓                                                         │
│  Session REMAINS ALIVE                                      │
│    ↓                                                         │
│  User clicks "Generate Solutions"                           │
│    ↓                                                         │
│  Reuse SAME session for solution_generation                │
│    ↓                                                         │
│  Session REMAINS ALIVE                                      │
│    ↓                                                         │
│  ...more jobs use same session...                          │
│    ↓                                                         │
│  User closes browser or clicks "Delete Session"             │
│    ↓                                                         │
│  KILL MAIN SESSION                                          │
│    └─ tmux kill-session -t smartbuild_s_<session_id>       │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    JOB SESSION LIFECYCLE                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  User clicks "Generate Cost Analysis"                       │
│    ↓                                                         │
│  Job added to queue with type="cost_analysis"              │
│    ↓                                                         │
│  CREATE JOB SESSION: smartbuild_ca_xyz_run123              │
│    └─ New TMUX session specific to this job                │
│    ↓                                                         │
│  Start Claude in job session                                │
│    ↓                                                         │
│  Send instruction to Claude                                 │
│    ↓                                                         │
│  Monitor waits for output file                              │
│    ↓                                                         │
│  Output file created → Job COMPLETED                        │
│    ↓                                                         │
│  KILL JOB SESSION (cleanup)                                 │
│    └─ tmux kill-session -t smartbuild_ca_xyz_run123        │
│                                                              │
│  OR                                                         │
│    ↓                                                         │
│  REUSE JOB SESSION if configuration allows                  │
│    └─ Session remains for next job of same type            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Job Queue System

### Queue Structure

```json
// File: smartbuild/sessions/active/<session_id>/runs/<run_id>/job_queue.json

[
  {
    "id": "job_20250923_120530_abc123",
    "type": "cost_analysis",
    "status": "completed",
    "progress": 100,
    "progress_message": "✅ Cost analysis completed successfully",

    "session_id": "session_20250923_120000_xyz",
    "run_id": "run_20250923_120530",

    "created_at": "2025-09-23T12:05:30.123456",
    "started_at": "2025-09-23T12:05:35.234567",
    "completed_at": "2025-09-23T12:07:45.345678",

    "tmux_session": "smartbuild_ca_xyz_20250923_120530",

    "metadata": {
      "diagram_path": "smartbuild/sessions/active/session_xyz/runs/run_123/artifacts/diagram_abc/diagram.drawio",
      "diagram_name": "MyArchitecture",
      "requirements_path": "smartbuild/sessions/active/session_xyz/requirements.json"
    },

    "output_path": "smartbuild/sessions/active/session_xyz/runs/run_123/artifacts/diagram_abc/cost_analysis",
    "prompt_save_path": "smartbuild/sessions/active/session_xyz/runs/run_123/artifacts/diagram_abc/prompts/cost_analysis_20250923_120530.txt",

    "job_start_timestamp": "2025-09-23T12:05:35.234567",

    "error": null
  }
]
```

### Job Status States

```
┌─────────────────────────────────────────────────────────────┐
│                     JOB STATUS FSM                          │
│                                                              │
│                     ┌──────────┐                            │
│                     │ PENDING  │                            │
│                     └────┬─────┘                            │
│                          │                                  │
│                          │ Monitor picks up job             │
│                          │ + checks concurrency             │
│                          ▼                                  │
│                     ┌──────────┐                            │
│            ┌────────┤ RUNNING  ├────────┐                  │
│            │        └────┬─────┘        │                  │
│            │             │              │                  │
│    Timeout │             │ Output file  │ Error/Exception  │
│    reached │             │ detected     │ occurred         │
│            │             ▼              │                  │
│            │        ┌──────────┐        │                  │
│            │        │COMPLETED │        │                  │
│            │        └──────────┘        │                  │
│            │                            │                  │
│            └────►┌──────────┐◄──────────┘                  │
│                  │  FAILED  │                              │
│                  └──────────┘                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘

Status Transition Details:

PENDING → RUNNING:
  • Monitor detects job in queue
  • Checks current running jobs < 4
  • Creates/reuses TMUX session
  • Records job_start_timestamp
  • Updates status to "running"

RUNNING → COMPLETED:
  • Output file exists
  • File mtime > job_start_timestamp
  • File size > minimum threshold
  • Updates status to "completed"
  • Records completed_at timestamp
  • Optionally kills TMUX session

RUNNING → FAILED:
  • Job timeout exceeded (5-30 min depending on type)
  • TMUX session crashed
  • Exception during processing
  • Claude returned error
  • Updates status to "failed"
  • Records error message
  • Kills TMUX session
```

### Concurrency Control

```python
# Maximum concurrent jobs
MAX_CONCURRENT_JOBS = 4

# Job Queue Monitor logic:
def process_jobs():
    while True:
        # Get all active sessions
        sessions = get_active_sessions()

        for session in sessions:
            # Load job queue
            queue = load_job_queue(session)

            # Count running jobs
            running_jobs = [j for j in queue if j['status'] == 'running']

            if len(running_jobs) >= MAX_CONCURRENT_JOBS:
                continue  # Skip, at capacity

            # Find pending jobs
            pending_jobs = [j for j in queue if j['status'] == 'pending']

            # How many can we start?
            slots_available = MAX_CONCURRENT_JOBS - len(running_jobs)

            # Start jobs (up to available slots)
            for job in pending_jobs[:slots_available]:
                start_job(job)

        # Sleep before next check
        time.sleep(2)
```

---

## Synchronization Mechanisms

### Completion Detection Algorithm

```python
def check_job_completion(job: Dict) -> bool:
    """
    Check if a job has completed.

    Returns True if job completed successfully, False otherwise.
    """

    # Get job timing
    job_start = datetime.fromisoformat(job['job_start_timestamp'])
    elapsed = (datetime.now() - job_start).total_seconds()

    # Get job type configuration
    min_wait = JOB_MIN_WAIT_TIMES.get(job['type'], 10)  # seconds
    timeout = JOB_TIMEOUTS.get(job['type'], 1800)  # seconds (30 min default)

    # Check 1: Has minimum wait time passed?
    if elapsed < min_wait:
        # Too early to check
        return False

    # Check 2: Has timeout been exceeded?
    if elapsed > timeout:
        # Job timed out
        job['status'] = 'failed'
        job['error'] = f"Job timed out after {elapsed/60:.1f} minutes"
        kill_tmux_session(job['tmux_session'])
        return True  # Considered "complete" (with failure)

    # Check 3: Does output file exist?
    output_path = Path(job['output_path'])
    if not output_path.exists():
        # File not created yet, keep waiting
        return False

    # Check 4: Is file modification time after job start?
    file_mtime = datetime.fromtimestamp(output_path.stat().st_mtime)
    if file_mtime < job_start:
        # File exists but is OLD (from previous run)
        return False

    # Check 5: Is file size reasonable?
    file_size = output_path.stat().st_size
    min_size = 100  # bytes
    if file_size < min_size:
        # File too small (might be incomplete or empty)
        return False

    # All checks passed - job completed successfully!
    job['status'] = 'completed'
    job['progress'] = 100
    job['completed_at'] = datetime.now().isoformat()
    job['progress_message'] = f"✅ {job['type'].replace('_', ' ').title()} completed"

    # Optional: Kill single-use TMUX session
    if should_kill_session(job):
        kill_tmux_session(job['tmux_session'])

    return True
```

### File Modification Time as Synchronization Marker

```
Timeline:

T0: Job created
    └─ job_start_timestamp = 2025-09-23T12:05:30

T1: Output file exists from PREVIOUS run
    └─ file.mtime = 2025-09-22T10:00:00 (yesterday)

T2: Monitor checks file
    └─ file.mtime < job_start_timestamp → Ignore (old file)

T3: Claude completes processing
    └─ Writes new output file

T4: Monitor checks file again
    └─ file.mtime = 2025-09-23T12:07:45
    └─ file.mtime > job_start_timestamp → Valid! Job complete ✓
```

### Session Logging for Debugging

```
Log file: smartbuild/sessions/active/<session>/logs/complete_session_*.log

[12:05:30.123] [JOB_EXECUTION] Starting job job_20250923_120530_abc123
[12:05:30.234] [JOB_EXECUTION] Type: cost_analysis
[12:05:30.345] [JOB_EXECUTION] Session: session_20250923_120000_xyz
[12:05:30.456] [JOB_EXECUTION] Run: run_20250923_120530
[12:05:30.567] [TMUX_HELPER] Creating TMUX session: smartbuild_ca_xyz_run20250923
[12:05:31.678] [TMUX_HELPER] Starting Claude CLI in session
[12:05:34.789] [TMUX_HELPER] Claude CLI initialized successfully
[12:05:34.890] [PROMPT_PREPARERS] Preparing cost analysis prompt
[12:05:35.001] [PROMPT_PREPARERS] Loaded requirements: 1234 chars
[12:05:35.112] [PROMPT_PREPARERS] Loaded diagram: 5678 chars
[12:05:35.223] [PROMPT_PREPARERS] Loaded agent template: 2000 chars
[12:05:35.334] [PROMPT_PREPARERS] Full prompt: 8912 chars
[12:05:35.445] [PROMPT_PREPARERS] Saved prompt to: .../prompts/cost_analysis_20250923.txt
[12:05:35.556] [TMUX_HELPER] Sending instruction to Claude
[12:05:35.667] [JOB_STATUS] Status changed to: running
[12:05:35.778] [JOB_STATUS] Progress: 50%
[12:05:40.889] [JOB_MONITOR] Checking completion (elapsed: 5.1s)
[12:05:40.990] [JOB_MONITOR] Output file does not exist yet
[12:05:45.101] [JOB_MONITOR] Checking completion (elapsed: 10.2s)
[12:05:45.212] [JOB_MONITOR] Output file does not exist yet
...
[12:07:45.323] [JOB_MONITOR] Checking completion (elapsed: 130.4s)
[12:07:45.434] [JOB_MONITOR] Output file found: /path/to/cost_analysis
[12:07:45.545] [JOB_MONITOR] File mtime: 2025-09-23T12:07:44.000000
[12:07:45.656] [JOB_MONITOR] File size: 4567 bytes
[12:07:45.767] [JOB_MONITOR] All checks passed - job complete!
[12:07:45.878] [JOB_STATUS] Status changed to: completed
[12:07:45.989] [JOB_STATUS] Progress: 100%
[12:07:46.090] [JOB_EXECUTION] COMPLETED - Duration: 130.4s
```

---

## State Diagrams

### Application State Machine

```
┌─────────────────────────────────────────────────────────────┐
│               APPLICATION LIFECYCLE FSM                      │
│                                                              │
│  ┌──────────┐                                               │
│  │  START   │                                               │
│  └────┬─────┘                                               │
│       │                                                      │
│       │ Launch app                                          │
│       ▼                                                      │
│  ┌──────────────────┐                                       │
│  │ SPAWN MONITOR    │ Background process                    │
│  │ (job_queue_      │ job_queue_monitor.py                  │
│  │  monitor.py)     │                                       │
│  └────┬─────────────┘                                       │
│       │                                                      │
│       │ Monitor running                                     │
│       ▼                                                      │
│  ┌──────────────────┐                                       │
│  │  LAUNCH UI       │ Main process                          │
│  │  (Streamlit)     │ spa_middleware_dynamic.py             │
│  └────┬─────────────┘                                       │
│       │                                                      │
│       │ UI loaded                                           │
│       ▼                                                      │
│  ┌──────────────────┐                                       │
│  │  IDLE            │ Waiting for user                      │
│  │  (No sessions)   │                                       │
│  └────┬─────────────┘                                       │
│       │                                                      │
│       │ User clicks "New Session"                           │
│       ▼                                                      │
│  ┌──────────────────┐                                       │
│  │ SESSION_CREATED  │ Session directory exists              │
│  │                  │ metadata.json created                 │
│  └────┬─────────────┘                                       │
│       │                                                      │
│       │ User enters requirements                            │
│       │ User clicks "Analyze"                               │
│       ▼                                                      │
│  ┌──────────────────┐                                       │
│  │ PROCESSING       │ Jobs in queue                         │
│  │                  │ TMUX sessions active                  │
│  └────┬─────────────┘                                       │
│       │         ▲                                           │
│       │         │                                           │
│       │         │ User generates more artifacts             │
│       │         │                                           │
│       │         └──────────────┐                            │
│       │                        │                            │
│       │ All jobs complete      │                            │
│       ▼                        │                            │
│  ┌──────────────────┐          │                            │
│  │  READY           │──────────┘                            │
│  │  (View results)  │ User can generate more                │
│  └────┬─────────────┘                                       │
│       │                                                      │
│       │ User clicks "Delete Session"                        │
│       ▼                                                      │
│  ┌──────────────────┐                                       │
│  │ CLEANUP          │ Kill TMUX sessions                    │
│  │                  │ Move to deleted/                      │
│  └────┬─────────────┘                                       │
│       │                                                      │
│       │ Cleanup complete                                    │
│       ▼                                                      │
│  ┌──────────────────┐                                       │
│  │  IDLE            │ Ready for new session                 │
│  │  (No sessions)   │                                       │
│  └──────────────────┘                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Session State Machine

```
┌─────────────────────────────────────────────────────────────┐
│                    SESSION LIFECYCLE FSM                     │
│                                                              │
│     ┌───────────┐                                           │
│     │ CREATED   │ metadata.json exists                      │
│     └─────┬─────┘ session_id assigned                       │
│           │                                                  │
│           │ requirements_extraction job added               │
│           ▼                                                  │
│     ┌───────────────────┐                                   │
│     │ EXTRACTING_REQS   │ Main TMUX session active          │
│     └─────┬─────────────┘ Claude analyzing input            │
│           │                                                  │
│           │ requirements.json created                        │
│           ▼                                                  │
│     ┌───────────────────┐                                   │
│     │ REQUIREMENTS_DONE │ Ready for solution generation     │
│     └─────┬─────────────┘                                   │
│           │                                                  │
│           │ solution_generation job added                   │
│           ▼                                                  │
│     ┌───────────────────┐                                   │
│     │ GENERATING_SOLN   │ Claude creating diagram           │
│     └─────┬─────────────┘                                   │
│           │                                                  │
│           │ diagram.drawio created                          │
│           ▼                                                  │
│     ┌───────────────────┐                                   │
│     │ SOLUTION_READY    │ Diagram available                 │
│     └─────┬─────────────┘ Ready for artifacts               │
│           │                                                  │
│           │ User requests artifacts                         │
│           ▼                                                  │
│     ┌───────────────────┐                                   │
│     │ GENERATING_       │ Multiple jobs running             │
│     │ ARTIFACTS         │ (up to 4 concurrent)              │
│     └─────┬─────────────┘                                   │
│           │         ▲                                        │
│           │         │                                        │
│           │         │ More artifacts requested              │
│           │         │                                        │
│           │         └──────────────┐                         │
│           │                        │                         │
│           │ All artifacts done     │                         │
│           ▼                        │                         │
│     ┌───────────────────┐          │                         │
│     │ ARTIFACTS_READY   │──────────┘                         │
│     └─────┬─────────────┘                                   │
│           │                                                  │
│           │ User clicks "Delete"                            │
│           ▼                                                  │
│     ┌───────────────────┐                                   │
│     │ DELETING          │ Killing TMUX sessions             │
│     └─────┬─────────────┘ Moving files                      │
│           │                                                  │
│           │ Deletion complete                               │
│           ▼                                                  │
│     ┌───────────────────┐                                   │
│     │ DELETED           │ In deleted/ folder                │
│     └───────────────────┘                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Critical Implementation Details

### Quote Escaping in TMUX Commands

```python
# WRONG - Will fail with quotes in text
command = "Please read and process '/path/with spaces/file.txt'"
subprocess.run(f"tmux send-keys -t {session} -l {command}", shell=True)
# ERROR: Shell interprets quotes incorrectly

# CORRECT - Use list format, no shell=True
command = "Please read and process '/path/with spaces/file.txt'"
subprocess.run(
    ["tmux", "send-keys", "-t", session, "-l", command],
    stderr=subprocess.DEVNULL
)
# SUCCESS: -l flag treats entire string literally

# If you MUST use shell=True (not recommended):
command_escaped = command.replace("'", "'\\''")
subprocess.run(
    f"tmux send-keys -t {session} -l '{command_escaped}'",
    shell=True,
    stderr=subprocess.DEVNULL
)
```

### Path Management

```python
# CRITICAL: Always use smartbuild/ prefix for session paths
# This ensures production compatibility

# WRONG:
session_path = Path("sessions") / "active" / session_id

# CORRECT:
from config.app_config import SMARTBUILD_DIR, ACTIVE_SESSIONS_DIR
session_path = ACTIVE_SESSIONS_DIR / session_id

# CORRECT (if importing from app_config):
session_path = Path(f"smartbuild/sessions/active/{session_id}")
```

### Job Type Configuration

```python
# File: config/app_config.py

JOB_TIMEOUTS = {
    'requirements_extraction': 300,      # 5 minutes
    'solution_generation': 600,          # 10 minutes
    'cost_analysis': 300,                # 5 minutes
    'terraform_code': 600,               # 10 minutes
    'cloudformation_template': 600,      # 10 minutes
    'technical_docs': 900,               # 15 minutes
    'project_plan': 1200,                # 20 minutes
    'default': 1800                      # 30 minutes
}

JOB_MIN_WAIT_TIMES = {
    'requirements_extraction': 30,       # 30 seconds
    'solution_generation': 60,           # 1 minute
    'cost_analysis': 20,                 # 20 seconds
    'terraform_code': 30,                # 30 seconds
    'default': 10                        # 10 seconds
}

JOB_CHECK_INTERVALS = {
    'requirements_extraction': 5,        # Check every 5 seconds
    'solution_generation': 10,           # Check every 10 seconds
    'cost_analysis': 5,                  # Check every 5 seconds
    'default': 5                         # Check every 5 seconds
}
```

### Agent Template Loading

```python
# Agent templates stored in: .claude/agents/

def load_agent_template(agent_name: str) -> str:
    """Load agent prompt template from .claude/agents/"""

    agent_file = Path(".claude/agents") / f"{agent_name}.md"

    if not agent_file.exists():
        raise FileNotFoundError(f"Agent template not found: {agent_file}")

    with open(agent_file, 'r', encoding='utf-8') as f:
        template = f.read()

    return template

# Example agents:
# - cost-analyzer.md
# - solution-designer.md
# - terraform-generator.md
# - aws-architect.md
# etc.
```

### Error Recovery Strategies

```python
# Strategy 1: TMUX session lost but files exist
if not tmux_session_exists(job['tmux_session']):
    # Check if output files were created anyway
    if output_file.exists() and output_file.mtime > job_start:
        # Files created successfully despite session loss
        job['status'] = 'completed'
        job['progress_message'] = "✅ Task completed (session terminated)"
    else:
        # No files, actual failure
        job['status'] = 'failed'
        job['error'] = "TMUX session terminated unexpectedly"

# Strategy 2: Stale lock file
lock_age = time.time() - lock_file.stat().st_mtime
if lock_age > STALE_LOCK_TIMEOUT:
    try:
        # Attempt to acquire lock
        with FileLock(lock_file, timeout=1):
            # Successfully acquired, lock was stale
            lock_file.unlink()
    except Timeout:
        # Lock is held by active process, wait

# Strategy 3: Claude returned error in output
if output_file.exists():
    content = output_file.read_text()
    if "Error:" in content or "Exception:" in content:
        # Claude encountered an error
        job['status'] = 'failed'
        job['error'] = f"Claude error: {content[:200]}"
```

---

## Summary of Key Differences from Original Implementation

| Aspect | Original (Builder-CLI) | SmartBuild (Correct Pattern) |
|--------|----------------------|------------------------------|
| **Prompt Delivery** | Send full prompt via tmux | Write prompt to file, send file path |
| **Prompt Size** | Limited by tmux buffer | Unlimited (file-based) |
| **Claude Invocation** | Direct in tmux | File path instruction |
| **Output Detection** | Marker files | File existence + mtime check |
| **Session Management** | Single session | Two-tier (main + job sessions) |
| **Job Queue** | In-memory | Persistent JSON files |
| **Concurrency** | Single job | Up to 4 concurrent jobs |
| **Background Monitor** | Not used | Separate process |
| **Session Persistence** | Until cleared | Main session persists, job sessions ephemeral |

---

## Implementation Checklist

When implementing SmartBuild pattern in tmux-builder:

- [ ] **File-Based Prompts**: Write prompts to disk, not send directly
- [ ] **Instruction Pattern**: Send "read this file" instruction, not full prompt
- [ ] **Two-Tier TMUX**: Main session + job-specific sessions
- [ ] **Job Queue System**: Persistent JSON queue files
- [ ] **Background Monitor**: Separate process monitoring queues
- [ ] **Completion Detection**: File existence + mtime checking
- [ ] **Timing Delays**: 0.3s after send-keys, 1.2s after Enter
- [ ] **TMUX Command Pattern**: Use `-l` flag, list format, no `shell=True`
- [ ] **Path Management**: Always use `smartbuild/sessions/` prefix
- [ ] **Session Logging**: Write to `complete_session_*.log`
- [ ] **Concurrency Control**: Max 4 concurrent jobs
- [ ] **Error Recovery**: Handle TMUX session loss gracefully
- [ ] **Quote Escaping**: Use list format or escape with `'\\''`
- [ ] **Agent Templates**: Load from `.claude/agents/*.md`

---

**END OF DOCUMENT**
