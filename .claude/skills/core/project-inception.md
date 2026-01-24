# Project Inception - Core System Build Criteria

## Overview

**MANDATORY SKILL** for starting any new feature or project. Ensures end-to-end thinking from day one, preventing functional gaps between design and implementation.

**Announce at start:** "I'm using project-inception to ensure we build a complete, working system."

**Core principle:** A system of perfect modules that don't connect is a failed system. Always verify end-to-end flow.

## When to Use

**ALWAYS use when:**
- Starting a new feature
- Starting a new project
- Major architectural changes
- Multi-module implementations

**The cost of skipping this:** Functional gaps discovered at the end, modules that don't integrate, config files referencing non-existent components.

## The Process

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: ACCEPTANCE CRITERIA (Before brainstorming)        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: BRAINSTORM + DESIGN                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: PLAN WITH VALIDATION                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PHASE 4: EXECUTE WITH WALKING SKELETON FIRST               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PHASE 5: INTEGRATION VERIFICATION                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PHASE 6: FINISH                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Acceptance Criteria

**Before any design work, define "done" with concrete demo scenarios.**

### Template

```markdown
## Definition of Done

### Demo Scenario 1: [Primary Use Case]
1. User does X
2. System responds with Y
3. Result: Z is visible/accessible

### Demo Scenario 2: [Secondary Use Case]
...

### Demo Scenario N: [Edge Case]
...

## Non-Functional Requirements
- Performance: [specific metrics]
- Security: [requirements]
- Scalability: [requirements]
```

### Example

```markdown
## Definition of Done

### Demo Scenario 1: New User Deploys Static Site
1. POST /api/create-user with {email, phone, aws, static}
2. Returns execution_id within 1 second
3. Within 5 minutes, GET /api/status/{id} shows "completed" with CloudFront URL
4. Visiting the URL shows a working website

### Demo Scenario 2: User Modifies Site
1. POST /api/chat/{id} with "change the title to Hello World"
2. Within 2 minutes, site updates at same URL
3. Screenshot captured showing new title

### Demo Scenario 3: User Checks Progress
1. GET /api/status/{id} during deployment
2. Shows current step (1-7) and logs
```

### Validation Checklist

- [ ] Every API endpoint has a demo scenario
- [ ] Every user-facing feature has a demo scenario
- [ ] Success criteria are measurable (not vague)
- [ ] Time expectations are defined

---

## Phase 2: Brainstorm + Design

Use `superpowers:brainstorming` skill, but add these constraints:

### Design Document Must Include

1. **Component Diagram** - What modules exist
2. **Data Flow** - How data moves between modules
3. **API Specification** - All endpoints with request/response
4. **Integration Points** - How modules connect
5. **Configuration Files** - What configs exist and their contents

### Critical Check: Config-to-Implementation Mapping

For every config file in the design:

```markdown
## Config Validation Table

| Config File | References | Task That Creates It |
|-------------|------------|---------------------|
| injection_rules.json | agents/deployers/aws-s3-static | Task 5.1 |
| injection_rules.json | skills/aws/s3-upload | Task 5.2 |
| injection_rules.json | agents/utilities/cache-invalidator | Task 5.4 |
```

**If a config references something, a task MUST create it.**

---

## Phase 3: Plan with Validation

Use `superpowers:writing-plans` skill, but enforce these additions:

### Mandatory Task Structure

```markdown
### Task 0: Walking Skeleton (ALWAYS FIRST)

Minimal end-to-end implementation proving architecture works.

**Scope:**
- Simplest possible implementation of primary demo scenario
- No edge cases, no error handling, no polish
- Just prove data flows from input to output

**Success Criteria:**
- Demo Scenario 1 works (may be ugly, but works)

---

### Tasks 1-N: Individual Modules

[Standard module tasks]

---

### Task N+1: Integration Wiring

Connect all modules into working system.

**Scope:**
- Orchestration layer (job runner, pipeline executor)
- API endpoints call the right modules
- Background jobs trigger correctly
- Status updates flow through system

---

### Task N+2: E2E Acceptance Tests

Automated tests for all demo scenarios.

**Scope:**
- Test for each demo scenario in acceptance criteria
- Integration tests, not unit tests
- Run against real (or realistic mock) infrastructure
```

### Plan Validation Checklist

Before executing ANY task, verify:

| Check | Question | Status |
|-------|----------|--------|
| **Acceptance coverage** | Does every demo scenario have tasks that implement it? | |
| **Walking skeleton** | Is Task 0 a minimal E2E implementation? | |
| **Integration task** | Is there a task that wires modules together? | |
| **E2E test task** | Is there a task for acceptance test automation? | |
| **API completeness** | Does every API endpoint have an implementation task? | |
| **Config validation** | Do all config references have corresponding creation tasks? | |
| **Dependency clarity** | Are task dependencies explicit? | |

### Dependency Graph Template

```markdown
## Task Dependencies

Task 0: Walking Skeleton (no deps)
    ↓
Task 1: Module A (no deps, can parallel with 2,3)
Task 2: Module B (no deps)
Task 3: Module C (no deps)
    ↓
Task 4: Integration Wiring ← DEPENDS ON 1, 2, 3
    ↓
Task 5: E2E Acceptance Tests ← DEPENDS ON 4
```

---

## Phase 4: Execute with Walking Skeleton First

### Walking Skeleton Requirements

**The walking skeleton MUST:**
1. Be the FIRST task executed
2. Implement primary demo scenario end-to-end
3. Be ugly but functional
4. Prove the architecture before building modules

**Example Walking Skeleton:**

```markdown
### Task 0: Walking Skeleton

1. POST /api/create-user
   - Hardcode user creation (no UserManager yet)
   - Hardcode session creation (no SessionCreator yet)
   - Return execution_id

2. Background job starts
   - Create tmux session (use existing tmux_helper)
   - Send hardcoded prompt to Claude
   - Wait for response

3. Deploy
   - Hardcoded S3 upload (no AWSDeployer yet)
   - Return S3 URL (no CloudFront yet)

4. Update status
   - Write "completed" + URL to execution file

5. GET /api/status/{id}
   - Return the status

**Test:**
curl -X POST .../api/create-user -d '{"email":"test@test.com"...}'
# Wait 60 seconds
curl .../api/status/{execution_id}
# Should show completed with URL
# Visit URL - should show a page
```

### Execution Order

```
1. Execute Task 0 (Walking Skeleton)
2. Verify primary demo scenario works
3. Execute Tasks 1-N (Modules) - can be parallel
4. Execute Integration Wiring task
5. Execute E2E Acceptance Tests task
6. Verify ALL demo scenarios work
```

---

## Phase 5: Integration Verification

**BEFORE using finishing-a-development-branch, complete this verification.**

### Integration Verification Checklist

```markdown
## Pre-Completion Verification

### Demo Scenario Verification
- [ ] Demo Scenario 1: [describe] - WORKS / FAILS
- [ ] Demo Scenario 2: [describe] - WORKS / FAILS
- [ ] Demo Scenario N: [describe] - WORKS / FAILS

### API Endpoint Verification
- [ ] POST /api/endpoint1 - Returns expected response
- [ ] GET /api/endpoint2 - Returns expected response
- [ ] [All endpoints listed and verified]

### Config File Verification
- [ ] config1.json - All references exist
- [ ] config2.json - All references exist

### Integration Points Verification
- [ ] Module A calls Module B correctly
- [ ] Background jobs trigger correctly
- [ ] Status updates flow through system

### E2E Test Results
- [ ] All acceptance tests pass
```

### Red Flags - STOP if Any Are True

- [ ] Any demo scenario doesn't work
- [ ] Any API endpoint returns error
- [ ] Any config references non-existent files
- [ ] Status never updates from "pending"
- [ ] Background jobs never execute

---

## Phase 6: Finish

Only after Phase 5 verification passes:

1. Use `superpowers:finishing-a-development-branch`
2. Include verification results in PR description

---

## Anti-Patterns to Avoid

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| "Modules first, integration later" | Integration never happens | Walking skeleton first |
| "Config with placeholders" | Placeholders never filled | Config validation table |
| "Unit tests are enough" | System doesn't work E2E | E2E acceptance tests |
| "Subagents will figure it out" | Nobody owns integration | Explicit integration task |
| "We'll wire it up at the end" | Wiring is the hard part | Walking skeleton proves wiring early |
| "Design is comprehensive" | Plan missed items | Plan validation checklist |

---

## Quick Reference Card

```
PROJECT INCEPTION CHECKLIST

□ Phase 1: Acceptance Criteria
  □ Demo scenarios defined
  □ Success criteria measurable

□ Phase 2: Design
  □ Config-to-implementation mapping complete
  □ All integration points documented

□ Phase 3: Plan
  □ Task 0 is walking skeleton
  □ Integration wiring task exists
  □ E2E test task exists
  □ All config references have creation tasks
  □ All API endpoints have tasks

□ Phase 4: Execute
  □ Walking skeleton works FIRST
  □ Primary demo scenario verified early

□ Phase 5: Verify
  □ All demo scenarios work
  □ All API endpoints verified
  □ All configs validated
  □ E2E tests pass

□ Phase 6: Finish
  □ Verification results in PR
```

---

## Integration with Other Skills

**This skill wraps and extends:**
- `superpowers:brainstorming` - Adds acceptance criteria phase
- `superpowers:writing-plans` - Adds validation checklist
- `superpowers:subagent-driven-development` - Adds walking skeleton first
- `superpowers:finishing-a-development-branch` - Adds integration verification

**Call order:**
1. `project-inception` (this skill) - Start here
2. `brainstorming` - For design phase
3. `writing-plans` - For plan phase
4. `subagent-driven-development` - For execution
5. `integration-verification` - Before finishing
6. `finishing-a-development-branch` - To complete
