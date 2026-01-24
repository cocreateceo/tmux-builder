# Project Guidelines

**IMPORTANT:** Follow these guidelines for every new project/feature to prevent functional gaps.

---

## Mandatory Workflow

```
1. project-inception      → Define acceptance criteria (demo scenarios)
2. brainstorming          → Design with full context
3. writing-plans          → Create implementation plan
4. plan-validation        → MUST PASS before execution
5. Execute (skeleton first)→ Walking skeleton proves E2E
6. integration-verification→ MUST PASS before completion
7. finishing-branch       → Merge/PR only after verification
```

---

## Plan Validation Checklist

Before executing ANY plan, verify:

| Check | Question |
|-------|----------|
| Design Coverage | Every module/endpoint in design has a task? |
| Walking Skeleton | Task 0 is minimal E2E implementation? |
| Integration Task | Explicit task wires modules together? |
| Config Validation | All config references have creation tasks? |
| API Coverage | Every API endpoint has implementation task? |
| E2E Test Task | Acceptance tests are planned? |

**If any check fails → Fix plan before executing**

---

## Common Pitfalls to Avoid

| Pitfall | Prevention |
|---------|------------|
| Plans miss orchestration/job_runner | Always have explicit integration task |
| Config references non-existent files | Validate config against planned files |
| Modules work in isolation, system fails | Walking skeleton first, integration-verification last |
| Status never updates | Verify data flows through entire pipeline |
| API returns success but nothing happens | Check background jobs are wired and triggered |

---

## Walking Skeleton Requirements

Task 0 must:
1. Be executed FIRST (before any module tasks)
2. Implement primary demo scenario end-to-end
3. Be ugly but functional (no polish needed)
4. Prove data flows from input to output

Example:
```
POST /api/create-user → returns execution_id
Background job starts → does minimal work
Status updates → to "completed"
GET /api/status → returns result
```

---

## Integration Verification Checklist

Before finishing any branch:

- [ ] All demo scenarios work E2E
- [ ] All API endpoints return expected responses
- [ ] All config files reference existing files only
- [ ] Background jobs execute (not just exist)
- [ ] Status updates flow through system
- [ ] Modules actually call each other (not orphaned)

---

## Environment Notes

### Testing
- pytest may have WSL2 conflicts - use `python3 -c "..."` for quick verification
- Quick module test: `python3 -c "from module import Class; print('OK')"`
- Full suite: `cd backend && python3 -m pytest -v`
- Verify imports: `python3 -c "import sys; sys.path.insert(0,'.'); from module import *"`

### Git
- gh CLI may not be available - use manual PR creation
- PR URL format: `https://github.com/{owner}/{repo}/pull/new/{branch}`

### Python Patterns
- Module-level constants (USERS_DIR) for test patching
- Lazy-load cloud clients with @property
- Deterministic GUIDs: `uuid5(NAMESPACE_URL, f"{email}|{phone}")`

---

## Resource Naming

| Resource | Format | Limit |
|----------|--------|-------|
| S3 Bucket | `tmux-{guid8}-{sess8}` | 63 chars |
| Azure Storage | `tmux{guid8}{sess8}` | 24 chars, no hyphens |
| CloudFront | `tmux-{guid8}-{sess8}` | 128 chars |
| Resource Group | `tmux-{guid8}-{sess8}-rg` | 90 chars |

---

## Mandatory Tags (Cost Tracking)

All cloud resources MUST have:
```
Project: tmux-builder
UserGUID: {user_id}
SessionID: {session_id}
ExecutionID: {execution_id}
SiteType: static|dynamic
CostCenter: user-sites
CreatedBy: tmux-builder-automation
```

---

## Quick Reference

### Core Skills Location
```
.claude/skills/core/
├── project-inception.md        # Start of any feature
├── plan-validation.md          # After writing plans
└── integration-verification.md # Before completion
```

### When to Use Each Skill

| Skill | Trigger |
|-------|---------|
| project-inception | "I'm starting a new feature/project" |
| plan-validation | "Plan is written, ready to execute" |
| integration-verification | "All tasks done, ready to finish" |

---

## Red Flags - STOP If You See These

- [ ] "All tasks passed spec review" but no integration test
- [ ] "All unit tests pass" but E2E not verified
- [ ] Config file references files that don't exist
- [ ] API returns success but nothing happens after
- [ ] Status stuck at "pending" forever
- [ ] Background job "defined" but never triggered
