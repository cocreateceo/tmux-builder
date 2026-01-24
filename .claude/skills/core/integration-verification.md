# Integration Verification - Pre-Completion System Validation

## Overview

**MANDATORY** before finishing any development branch. Verifies the system works end-to-end, not just individual modules.

**Announce at start:** "I'm using integration-verification to ensure the system works end-to-end before completion."

**Core principle:** Passing unit tests and completed tasks don't mean the system works. Verify every user-facing flow.

## When to Use

**ALWAYS use:**
- Before `finishing-a-development-branch`
- After all implementation tasks are "complete"
- Before creating a PR
- Before claiming work is done

**Never skip because:**
- "All tasks passed spec review" - Spec review checks individual tasks, not integration
- "All tests pass" - Unit tests don't verify E2E flows
- "Subagent said it works" - Subagents work in isolation

---

## The Process

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Gather Acceptance Criteria                         │
│  - Find the demo scenarios from project inception           │
│  - List all API endpoints from design                       │
│  - List all config files created                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Verify Demo Scenarios                              │
│  - Attempt each scenario manually or with test              │
│  - Document PASS/FAIL with evidence                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Verify API Endpoints                               │
│  - Call each endpoint                                       │
│  - Verify response matches specification                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Verify Config Integrity                            │
│  - Check all referenced files exist                         │
│  - Validate JSON/YAML syntax                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 5: Verify Integration Points                          │
│  - Check module A calls module B                            │
│  - Check data flows through system                          │
│  - Check async jobs execute                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 6: Generate Verification Report                       │
│  - Summary of all checks                                    │
│  - List of gaps found                                       │
│  - Recommendation: PASS / FAIL                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 1: Gather Acceptance Criteria

**Find and list:**

1. **Demo scenarios** from design document or project inception
2. **API endpoints** from design document
3. **Config files** created during implementation
4. **Integration points** from architecture

### Template

```markdown
## Verification Scope

### Demo Scenarios to Verify
1. [Scenario name]: [Brief description]
2. [Scenario name]: [Brief description]

### API Endpoints to Verify
- [METHOD] /api/endpoint1 - [Purpose]
- [METHOD] /api/endpoint2 - [Purpose]

### Config Files to Verify
- path/to/config1.json
- path/to/config2.json

### Integration Points to Verify
- [Module A] → [Module B]: [What should happen]
- [API] → [Background Job]: [What should trigger]
```

---

## Step 2: Verify Demo Scenarios

**For each demo scenario:**

1. Attempt to perform the scenario
2. Document exact steps taken
3. Document result: PASS or FAIL
4. If FAIL, document what went wrong

### Template

```markdown
## Demo Scenario Verification

### Scenario 1: [Name]

**Steps:**
1. [What I did]
2. [What I did]
3. [What I did]

**Expected Result:**
[What should happen]

**Actual Result:**
[What actually happened]

**Status:** ✅ PASS / ❌ FAIL

**Evidence:**
[Screenshot, curl output, logs, etc.]

---

### Scenario 2: [Name]
...
```

### Common Failure Patterns

| Symptom | Likely Cause |
|---------|--------------|
| API returns data but nothing happens | Missing orchestration/job runner |
| Status never updates | No code updates execution status |
| Background job never runs | Job not triggered or not connected |
| Config error on startup | Missing or malformed config file |
| Module not found | Import path wrong or module not created |

---

## Step 3: Verify API Endpoints

**For each API endpoint:**

```bash
# Test each endpoint
curl -X [METHOD] http://localhost:[PORT]/api/[endpoint] \
  -H "Content-Type: application/json" \
  -d '[request body]'
```

### Template

```markdown
## API Endpoint Verification

### [METHOD] /api/endpoint1

**Request:**
```bash
curl -X POST http://localhost:5001/api/create-user \
  -H "Content-Type: application/json" \
  -d '{"email": "test@test.com", "phone": "+1234567890", "host_provider": "aws", "site_type": "static"}'
```

**Expected Response:**
```json
{
  "execution_id": "...",
  "user_id": "...",
  "session_id": "...",
  "is_new_user": true
}
```

**Actual Response:**
```json
[paste actual response]
```

**Status:** ✅ PASS / ❌ FAIL

---
```

---

## Step 4: Verify Config Integrity

**For each config file:**

1. Check file exists
2. Validate syntax (JSON/YAML)
3. Check all references resolve

### Template

```markdown
## Config File Verification

### path/to/config.json

**Exists:** ✅ YES / ❌ NO

**Syntax Valid:** ✅ YES / ❌ NO

**References Check:**
| Reference | Type | Exists |
|-----------|------|--------|
| agents/deployers/aws-s3-static | Agent | ✅ / ❌ |
| skills/aws/s3-upload | Skill | ✅ / ❌ |
| utilities/cache-invalidator | Agent | ✅ / ❌ |

**Status:** ✅ PASS / ❌ FAIL

**Missing References:**
- [List any missing files]

---
```

### Config Reference Checker Command

```bash
# For injection_rules.json, check all referenced files exist
cat backend/injection_rules.json | jq -r '.rules[].inject.agents[]' | while read agent; do
  file=".claude/agents/${agent}.md"
  if [ -f "$file" ]; then
    echo "✅ $file"
  else
    echo "❌ MISSING: $file"
  fi
done
```

---

## Step 5: Verify Integration Points

**Check that modules actually connect:**

### Template

```markdown
## Integration Points Verification

### [Source Module] → [Target Module]

**Expected Flow:**
1. [Source] does X
2. [Target] receives Y
3. Result: Z

**Verification Method:**
[How to verify - logs, debug output, manual trace]

**Result:**
[What actually happens]

**Status:** ✅ CONNECTED / ❌ DISCONNECTED

---

### API → Background Job

**Expected Flow:**
1. POST /api/create-user returns execution_id
2. Background job starts for that execution_id
3. Job runs pipeline steps
4. Status updates to "completed"

**Verification:**
1. Called POST /api/create-user
2. Checked for background process: [command]
3. Waited 60 seconds
4. Checked GET /api/status/{id}

**Result:**
- Background job started: ✅ / ❌
- Status updated: ✅ / ❌

**Status:** ✅ WORKS / ❌ BROKEN

---
```

### Integration Failure Patterns

| Pattern | Symptom | Cause |
|---------|---------|-------|
| Dead End | API returns success but nothing happens after | No orchestration connecting API to jobs |
| Orphan Module | Module exists but never called | Import missing or call never made |
| Status Stuck | Status stays "pending" forever | Nothing updates execution tracker |
| Silent Failure | No errors but no results | Exception swallowed or wrong code path |

---

## Step 6: Generate Verification Report

### Template

```markdown
# Integration Verification Report

**Date:** [YYYY-MM-DD]
**Project:** [Project name]
**Branch:** [Branch name]

## Summary

| Category | Passed | Failed | Total |
|----------|--------|--------|-------|
| Demo Scenarios | X | Y | Z |
| API Endpoints | X | Y | Z |
| Config Files | X | Y | Z |
| Integration Points | X | Y | Z |
| **TOTAL** | X | Y | Z |

## Verdict: ✅ READY TO MERGE / ❌ GAPS FOUND

## Gaps Found

### Critical (Blocks Merge)
1. [Gap description] - [Impact]
2. [Gap description] - [Impact]

### Important (Should Fix)
1. [Gap description] - [Impact]

### Minor (Nice to Fix)
1. [Gap description] - [Impact]

## Detailed Results

[Include detailed verification from steps 2-5]

## Recommendations

1. [What needs to be done to fix gaps]
2. [Additional tasks needed]
```

---

## Red Flags - STOP and Fix

**Do NOT proceed to finishing-a-development-branch if:**

- [ ] Any demo scenario fails
- [ ] Any required API endpoint returns error
- [ ] Any config references non-existent files
- [ ] Background jobs never execute
- [ ] Status never updates from initial state
- [ ] Modules exist but are never called

---

## Quick Verification Commands

```bash
# Check all referenced agents exist
find .claude/agents -name "*.md" | sort

# Check all referenced skills exist
find .claude/skills -name "*.md" | sort

# Check API is running
curl -s http://localhost:5001/health || echo "API not running"

# Check for orphan imports (Python)
grep -r "^from .* import" backend/*.py | grep -v test | sort

# Check execution status
curl -s http://localhost:5001/api/status/{execution_id} | jq .status
```

---

## Integration with Other Skills

**Called by:**
- `project-inception` - Phase 5

**Called before:**
- `finishing-a-development-branch` - ALWAYS run this first

**If gaps found, use:**
- `subagent-driven-development` - To implement fixes
- `systematic-debugging` - To diagnose issues
