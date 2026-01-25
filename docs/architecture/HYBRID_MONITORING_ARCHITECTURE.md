# Hybrid Monitoring Architecture - status.json + Marker Files

**Date:** 2026-01-25
**Decision Type:** Architecture Design
**Status:** ✅ Implemented

---

## Problem Statement

Frontend calling `/api/session/create` resulted in 500 error with "Timeout waiting for initialized marker". Root cause: Instructions sent to Claude appeared in `<system-reminder>` tags, causing Claude to ask "Should I follow these instructions?" instead of executing them.

**Architectural Mismatch:**
- Old architecture: session_controller.py with marker files
- New architecture: session_initializer.py with autonomous agent + status.json
- Frontend calling old endpoint instead of new

---

## Brainstorming Session

### Question 1: Status Tracking Mechanism

**Options presented:**
- **Option A:** status.json only (autonomous agent updates it)
- **Option B:** status.json + marker files (both) ✅ **SELECTED**
- **Option C:** status.json + heartbeat timestamp

**Decision Rationale:**
- status.json provides detailed progress (phase, %, message, deployment_url)
- Marker files provide lifecycle/liveness detection
- Can detect if Claude crashed vs. just working
- Best of both worlds: detailed progress + heartbeat

###Question 2: Marker File Strategy

**Options presented:**
- **Option A:** Marker files mirror status.json states ✅ **SELECTED**
- **Option B:** Marker files as lifecycle checkpoints with heartbeat
- **Option C:** Marker files for each phase

**Decision Rationale:**
- Mirrors status.json for consistent state representation
- `initialized.marker` → session ready
- `processing.marker` → updated whenever status changes (heartbeat)
- `completed.marker` → deployment done (success or failure)
- Backend monitors processing.marker timestamp for liveness

### Question 3: System Prompt + Instructions Integration

**Options presented:**
- **Option A:** System prompt includes marker file instructions
- **Option B:** System prompt + separate initialization instructions
- **Option C:** System prompt with template variables for marker paths ✅ **SELECTED**

**Decision Rationale:**
- Clean, reusable templates
- Explicit paths (no ambiguity)
- PromptManager substitutes actual paths
- Easy to maintain and test

---

## Final Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    /api/register Endpoint                        │
│  - Generate GUID from email:phone                                │
│  - Return GUID URL immediately                                   │
│  - Start BackgroundWorker                                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BackgroundWorker (Threading)                    │
│  - Spawn worker thread                                           │
│  - Non-blocking initialization                                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SessionInitializer                             │
│  1. Check for existing session                                   │
│  2. Verify health (responsive + < 5 days)                        │
│  3. Create/reuse TMUX session                                    │
│  4. Create markers directory                                     │
│  5. Render system prompt with marker paths                       │
│  6. Initialize status.json                                       │
│  7. Send system prompt to Claude                                 │
│  8. WAIT for initialized.marker (60s timeout)                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PromptManager                                 │
│  - Load prompt_config.yaml                                       │
│  - Render autonomous_agent.txt with variables:                   │
│    • $guid, $email, $phone, $user_request                        │
│    • $session_path, $aws_profile                                 │
│    • $initialized_marker (explicit path)                         │
│    • $processing_marker (explicit path)                          │
│    • $completed_marker (explicit path)                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Claude CLI Session (TMUX)                       │
│  System Prompt Contains:                                         │
│  1. STATUS TRACKING PROTOCOL section                             │
│  2. Marker file creation instructions                            │
│  3. status.json update instructions                              │
│  4. Explicit paths to all marker files                           │
│  5. Protocol flow diagram                                        │
│                                                                  │
│  Claude Execution:                                               │
│  Step 1: CREATE initialized.marker immediately                  │
│  Step 2-N: UPDATE status.json + TOUCH processing.marker         │
│  Final Step: UPDATE status.json + CREATE completed.marker       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Backend Monitoring                              │
│  /api/session/{guid}/status endpoint:                            │
│  1. Read status.json for progress details                        │
│  2. Check processing.marker timestamp for liveness               │
│  3. Detect completed.marker for finalization                     │
│  4. Return combined status to frontend                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
sessions/
└── active/
    └── <guid>/
        ├── status.json                 # Detailed progress tracking
        │   {
        │     "status": "planning|implementing|deploying|deployed|failed",
        │     "phase": 0-4,
        │     "progress": 0-100,
        │     "message": "Human-readable status",
        │     "deployment_url": "https://...",
        │     "error": "..." (if failed)
        │   }
        │
        ├── markers/                    # Lifecycle tracking
        │   ├── initialized.marker      # Created once at startup
        │   ├── processing.marker       # Touched whenever status changes
        │   └── completed.marker        # Created at deployment end
        │
        ├── system_prompt.txt           # Rendered autonomous agent prompt
        ├── code/                       # Generated application code
        ├── infrastructure/             # IaC files
        ├── docs/                       # Documentation
        └── completion.txt              # Final completion message
```

---

## Status Tracking Protocol

### 1. Initialization Phase

```bash
# SessionInitializer creates markers directory
mkdir -p $session_path/markers

# Renders system prompt with explicit marker paths
initialized_marker = "$session_path/markers/initialized.marker"
processing_marker = "$session_path/markers/processing.marker"
completed_marker = "$session_path/markers/completed.marker"

# Sends system prompt to Claude
# Waits for initialized.marker (60s timeout)
while not initialized_marker.exists():
    sleep(0.5)
```

### 2. Claude Receives System Prompt

System prompt contains:
```markdown
## CRITICAL: STATUS TRACKING PROTOCOL

### Marker Files (Lifecycle Tracking)

1. **$initialized_marker** - Create this IMMEDIATELY when ready
   touch $initialized_marker

2. **$processing_marker** - Update timestamp whenever status.json changes
   touch $processing_marker

3. **$completed_marker** - Create when deployment complete
   touch $completed_marker

### status.json (Progress Details)

Update frequently with:
{
  "status": "planning|implementing|deploying|deployed|failed",
  "phase": 0-4,
  "progress": 0-100,
  "message": "...",
  "deployment_url": "..." (when ready)
}
```

### 3. Claude Execution Flow

```
┌─────────────────────────────────────────┐
│ Claude receives system prompt           │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│ IMMEDIATELY: touch initialized.marker   │ ← Backend waiting for this!
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│ Phase 1: Analysis & Planning            │
│ - Update status.json                    │
│ - touch processing.marker               │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│ Phase 2: Implementation                 │
│ - Update status.json                    │
│ - touch processing.marker               │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│ Phase 3: Deployment                     │
│ - Update status.json                    │
│ - touch processing.marker               │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│ Phase 4: Finalization                   │
│ - Update status.json (final)            │
│ - touch processing.marker               │
│ - touch completed.marker ← Signals done!│
└─────────────────────────────────────────┘
```

### 4. Backend Monitoring

```python
# GET /api/session/{guid}/status

def get_session_status(guid):
    # 1. Read status.json for detailed progress
    status = json.load(session_path / "status.json")

    # 2. Check processing marker for liveness
    processing_marker = session_path / "markers/processing.marker"
    if processing_marker.exists():
        marker_age = time.time() - processing_marker.stat().st_mtime
        if marker_age > 300:  # 5 minutes
            status['warning'] = 'No recent activity'

    # 3. Check completed marker
    completed_marker = session_path / "markers/completed.marker"
    if completed_marker.exists():
        status['finalized'] = True

    return status
```

---

## Implementation Details

### Modified Files

1. **`backend/templates/prompt_config.yaml`**
   - Added marker path variables to required variables:
     - `initialized_marker`
     - `processing_marker`
     - `completed_marker`

2. **`backend/templates/system_prompts/autonomous_agent.txt`**
   - Added **STATUS TRACKING PROTOCOL** section (66 lines)
   - Marker file creation instructions with explicit paths
   - status.json update format
   - Protocol flow diagram
   - Updated all phase status updates:
     - Phase 1: Write status.json + touch processing marker
     - Phase 2: Write status.json + touch processing marker
     - Phase 3: Write status.json + touch processing marker
     - Phase 4: Write status.json + touch processing marker + create completed marker

3. **`backend/session_initializer.py`**
   - Create markers directory before rendering prompt
   - Define marker file paths
   - Pass marker paths to PromptManager
   - Wait for initialized.marker after sending system prompt (60s timeout)

4. **`backend/tests/test_prompt_manager.py`**
   - Updated tests to include marker path variables
   - Added assertions for STATUS TRACKING PROTOCOL section
   - Verify marker paths appear in rendered prompt

### Test Results

```
20/20 tests passing ✅

- test_prompt_manager: 5/5 ✅
- test_background_worker: 4/4 ✅
- test_session_initializer: 4/4 ✅
- test_guid_generator: 4/4 ✅
- test_api_endpoints: 3/3 ✅
```

---

## Benefits of Hybrid Approach

### status.json Provides:
- ✅ Detailed progress tracking (phase, percentage, message)
- ✅ Deployment URL when ready
- ✅ Error details if failed
- ✅ Parallel execution metrics
- ✅ Cost estimates
- ✅ Human-readable status messages

### Marker Files Provide:
- ✅ Lifecycle state detection (initialized → processing → completed)
- ✅ Liveness/heartbeat monitoring (processing.marker timestamp)
- ✅ Simple file existence checks (fast)
- ✅ Can detect Claude crashes (stale processing.marker)
- ✅ Clear finalization signal (completed.marker)

### Combined:
- ✅ Backend knows **what** Claude is doing (status.json)
- ✅ Backend knows **if** Claude is alive (marker timestamps)
- ✅ Backend knows **when** deployment is complete (completed.marker)
- ✅ Frontend gets rich progress details via `/api/session/{guid}/status`

---

## Comparison with Old Architecture

### Old (session_controller.py):
- ❌ Instructions in system-reminder tags (Claude asks for permission)
- ❌ Manual instructions sent via tmux send-keys
- ❌ Marker files only (no detailed progress)
- ❌ Required user confirmation to execute

### New (session_initializer.py + autonomous_agent.txt):
- ✅ System prompt as autonomous behavior guide
- ✅ Explicit marker paths via template variables
- ✅ Hybrid monitoring (status.json + markers)
- ✅ Claude executes autonomously without confirmation
- ✅ Comprehensive status tracking throughout all phases

---

## Next Steps

**Immediate:**
1. ✅ Update frontend to call `/api/register` instead of `/api/session/create`
2. ✅ Frontend polls `/api/session/{guid}/status` for progress
3. ✅ Display progress bar, phase, and messages in UI

**Future Enhancements:**
- WebSocket for real-time status updates (instead of polling)
- Marker file cleanup strategy (old markers removal)
- Processing marker staleness alerts (email/Slack if > 5min)
- Dashboard to view all active sessions and their status
- Replay/debug mode (view marker file timeline)

---

## Lessons Learned

1. **System-reminder tags are information, not instructions**
   - Claude treats content in system-reminder as context, not commands
   - Use direct system prompts for behavior instructions

2. **Template variables are clearer than constructed paths**
   - `$initialized_marker` > "Create marker at {session_path}/markers/initialized.marker"
   - Eliminates ambiguity and path construction errors

3. **Hybrid monitoring provides redundancy**
   - status.json could be corrupted → marker files still work
   - Marker files could be deleted → status.json still has progress
   - Best of both worlds

4. **Explicit protocol in system prompt is critical**
   - Claude needs to see the full protocol flow
   - Diagrams and examples help Claude understand expectations
   - "IMMEDIATELY" and "CRITICAL" keywords emphasize importance

---

**Architecture Status:** ✅ Implemented and tested
**Commit:** `994aca2` - feat: add marker file tracking + status.json hybrid monitoring
**All Tests:** 20/20 passing
