# Plan Validation - Verify Plan Completeness Before Execution

## Overview

**MANDATORY** after writing any implementation plan and before executing tasks. Catches gaps between design and plan before wasting effort on incomplete implementation.

**Announce at start:** "I'm using plan-validation to verify the plan covers all requirements before execution."

**Core principle:** A beautiful plan that misses critical tasks is worse than no plan. Validate before you execute.

## When to Use

**ALWAYS use:**
- After `writing-plans` skill completes
- Before `subagent-driven-development` or `executing-plans`
- When reviewing someone else's plan
- When plan seems "too simple" for the scope

**Common gaps this catches:**
- Orchestration/job runner missing
- Integration wiring task missing
- Config files reference non-existent components
- API endpoints in design but not in plan
- E2E tests not planned

---

## The Validation Process

```
┌─────────────────────────────────────────────────────────────┐
│  Check 1: Design-to-Plan Coverage                           │
│  Every element in design has a corresponding task           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Check 2: Walking Skeleton Present                          │
│  Task 0 proves E2E flow before module work                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Check 3: Integration Task Present                          │
│  Explicit task wires modules together                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Check 4: Config Reference Validation                       │
│  All config references have creation tasks                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Check 5: API Endpoint Coverage                             │
│  Every API endpoint has implementation task                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Check 6: Acceptance Test Task Present                      │
│  E2E tests for demo scenarios are planned                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Check 7: Dependency Sanity                                 │
│  Task dependencies are explicit and achievable              │
└─────────────────────────────────────────────────────────────┘
```

---

## Check 1: Design-to-Plan Coverage

### Process

1. Open design document
2. List every component/module/file mentioned
3. Verify each has a task in the plan

### Template

```markdown
## Design-to-Plan Coverage Check

| Design Element | Type | Plan Task | Status |
|----------------|------|-----------|--------|
| user_manager.py | Module | Task 1.1 | ✅ |
| job_runner.py | Module | ??? | ❌ MISSING |
| /api/create-user | Endpoint | Task 4.1 | ✅ |
| /api/chat | Endpoint | ??? | ❌ MISSING |
| injection_rules.json | Config | Task 3.3 | ✅ |

### Missing Elements
- job_runner.py - No task creates this
- /api/chat endpoint - No task implements this
```

### Red Flags

- Design mentions module, plan doesn't create it
- Design shows API endpoint, plan doesn't implement it
- Design references config, plan doesn't create it

---

## Check 2: Walking Skeleton Present

### What to Look For

Task 0 or first task should be:
- Minimal E2E implementation
- Proves primary demo scenario
- Executed BEFORE module tasks

### Template

```markdown
## Walking Skeleton Check

**Task 0 exists:** ✅ YES / ❌ NO

**Task 0 description:**
[Copy task description]

**Covers primary demo scenario:** ✅ YES / ❌ NO

**Is first in execution order:** ✅ YES / ❌ NO

**Status:** ✅ PASS / ❌ FAIL
```

### Red Flags

- No Task 0 / Walking skeleton
- Task 0 is just "setup" not E2E
- Module tasks come before walking skeleton

---

## Check 3: Integration Task Present

### What to Look For

Explicit task that:
- Connects modules together
- Creates orchestration layer
- Wires API to background jobs
- Updates status through pipeline

### Template

```markdown
## Integration Task Check

**Integration task exists:** ✅ YES / ❌ NO

**Task number:** [X]

**Task description:**
[Copy task description]

**Covers:**
- [ ] Orchestration/job runner
- [ ] API → background job connection
- [ ] Status update flow
- [ ] Module-to-module calls

**Status:** ✅ PASS / ❌ FAIL
```

### Red Flags

- No explicit integration task
- Integration assumed to happen "automatically"
- Last task is just "API endpoints" with no wiring

---

## Check 4: Config Reference Validation

### Process

1. Find all config files in plan
2. Extract all references from those configs
3. Verify each reference has a creation task

### Template

```markdown
## Config Reference Validation

### Config: injection_rules.json (Task 3.3)

| Reference | Type | Creation Task | Status |
|-----------|------|---------------|--------|
| agents/deployers/aws-s3-static | Agent | Task 5.1 | ✅ |
| agents/utilities/cache-invalidator | Agent | ??? | ❌ |
| skills/aws/s3-upload | Skill | Task 5.2 | ✅ |
| skills/testing/* | Skill | ??? | ❌ |

### Missing Creations
- agents/utilities/cache-invalidator - No task
- skills/testing/* - No task

**Status:** ❌ FAIL - 2 missing
```

### Red Flags

- Config references files no task creates
- Wildcard references (testing/*) with no tasks
- Config created early, references created never

---

## Check 5: API Endpoint Coverage

### Process

1. List all API endpoints from design
2. Verify each has implementation task
3. Check endpoints connect to backend logic

### Template

```markdown
## API Endpoint Coverage

| Endpoint | Method | Purpose | Task | Status |
|----------|--------|---------|------|--------|
| /api/create-user | POST | Create user & start pipeline | Task 4.1 | ✅ |
| /api/status/{id} | GET | Get execution status | Task 4.1 | ✅ |
| /api/chat/{id} | POST | Send message to Claude | ??? | ❌ |
| /api/redeploy/{id} | POST | Force redeploy | ??? | ❌ |

### Missing Endpoints
- /api/chat - Design specifies, no task implements
- /api/redeploy - Design specifies, no task implements

**Status:** ❌ FAIL - 2 missing
```

### Red Flags

- Design shows endpoint, plan omits it
- Endpoint task exists but no connection to backend
- CRUD endpoints partially implemented

---

## Check 6: Acceptance Test Task Present

### What to Look For

Task that:
- Creates E2E tests for demo scenarios
- Runs integration tests (not unit tests)
- Verifies complete user flows

### Template

```markdown
## Acceptance Test Task Check

**E2E test task exists:** ✅ YES / ❌ NO

**Task number:** [X]

**Covers demo scenarios:**
- [ ] Scenario 1: [name]
- [ ] Scenario 2: [name]
- [ ] Scenario 3: [name]

**Test type:** Unit / Integration / E2E

**Status:** ✅ PASS / ❌ FAIL
```

### Red Flags

- No test task at all
- Only unit tests planned, no E2E
- Tests planned but no demo scenario coverage

---

## Check 7: Dependency Sanity

### Process

1. List task dependencies
2. Check for circular dependencies
3. Verify dependencies make sense
4. Check integration task depends on modules

### Template

```markdown
## Dependency Check

### Task Dependency Graph

Task 0: Walking Skeleton (no deps)
Task 1: Module A (no deps)
Task 2: Module B (no deps)
Task 3: Module C (depends: 1)
Task 4: Integration (depends: 1, 2, 3)
Task 5: E2E Tests (depends: 4)

### Sanity Checks
- [ ] No circular dependencies
- [ ] Integration depends on modules
- [ ] E2E tests depend on integration
- [ ] Walking skeleton has no dependencies

**Status:** ✅ PASS / ❌ FAIL
```

---

## Validation Report Template

```markdown
# Plan Validation Report

**Plan:** [plan file path]
**Date:** [YYYY-MM-DD]

## Summary

| Check | Status |
|-------|--------|
| Design-to-Plan Coverage | ✅ / ❌ |
| Walking Skeleton Present | ✅ / ❌ |
| Integration Task Present | ✅ / ❌ |
| Config Reference Validation | ✅ / ❌ |
| API Endpoint Coverage | ✅ / ❌ |
| Acceptance Test Task Present | ✅ / ❌ |
| Dependency Sanity | ✅ / ❌ |

## Verdict: ✅ READY TO EXECUTE / ❌ GAPS FOUND

## Gaps Found

### Must Add Tasks For:
1. [Missing element] - [What task should create it]
2. [Missing element] - [What task should create it]

### Must Fix:
1. [Issue] - [How to fix]

## Recommended Plan Updates

[Specific changes to make to plan before executing]
```

---

## Quick Checklist (Print This)

```
PLAN VALIDATION CHECKLIST

□ Design Coverage
  □ Every module in design has a task
  □ Every endpoint in design has a task
  □ Every config in design has a task

□ Structure
  □ Walking skeleton is Task 0
  □ Integration wiring task exists
  □ E2E acceptance test task exists

□ Config Integrity
  □ All config references have creation tasks
  □ No orphan references

□ Dependencies
  □ Integration depends on all modules
  □ E2E tests depend on integration
  □ No circular dependencies

IF ANY CHECK FAILS → FIX PLAN BEFORE EXECUTING
```

---

## Integration with Other Skills

**Called after:**
- `writing-plans` - Validate the plan it created

**Called before:**
- `subagent-driven-development` - Don't execute invalid plan
- `executing-plans` - Don't execute invalid plan

**If validation fails:**
- Update plan to add missing tasks
- Re-run validation
- Only proceed when all checks pass
