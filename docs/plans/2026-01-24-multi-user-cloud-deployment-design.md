# Multi-User Cloud Deployment Architecture - Design Document

**Created:** 2026-01-24
**Status:** Approved

## Overview

Transform tmux-builder from single-user to multi-user architecture with cloud deployment capabilities. Each user gets isolated sessions that can deploy websites to AWS or Azure.

## Key Design Decisions

### 1. User Management
- POST /api/create-user receives {email, phone, host_provider, site_type}
- GUID generated for each user (email+phone mapped in registry.json)
- Folder structure: `users/{GUID}/sessions/{session_id}/`

### 2. Execution Model
- Async execution with execution_id = `{GUID}_{session_id}`
- 7-step pipeline with deep logging
- Status polling via GET /api/status/{execution_id}

### 3. Cloud Deployment
- AWS static: S3 + CloudFront
- AWS dynamic: EC2
- Azure static: Blob + CDN
- Azure dynamic: VM
- Resource naming: `tmux-{GUID}-{session_id}` (truncated if needed)
- Mandatory tags on ALL resources for cost tracking

### 4. AWS/Azure Profiles
- AWS: Use `sunwaretech` profile
- Azure: Use `sunwaretech` subscription/profile

### 5. UI Testing
- Health check (200 OK)
- Screenshot capture (Playwright)
- E2E test generation & execution

### 6. Iterative Workflow
- Claude in tmux session is autonomous
- Claude uses injected agents/skills to modify → deploy → test → inform user
- Same URL updates in place (no versioned URLs)

### 7. Skill & Agent Injection
- Master library of 100s of agents/skills in `.claude/`
- Injection engine copies only needed agents/skills to user session
- Based on injection_rules.json matching host_provider + site_type

## Folder Structure

```
tmux-builder/
├── backend/
│   ├── app.py
│   ├── user_manager.py
│   ├── execution_tracker.py
│   ├── job_runner.py
│   ├── aws_deployer.py
│   ├── aws_ec2_deployer.py
│   ├── azure_deployer.py
│   ├── azure_vm_deployer.py
│   ├── cache_manager.py
│   ├── health_checker.py
│   ├── screenshot_capture.py
│   ├── e2e_runner.py
│   └── injection_engine.py
│
├── users/
│   ├── registry.json
│   └── {GUID}/
│       ├── user.json
│       └── sessions/{session_id}/
│           ├── .claude/
│           ├── source/
│           ├── deployment/
│           └── logs/
│
├── executions/
│   └── {execution_id}.json
│
└── .claude/
    ├── agents/
    │   ├── deployers/
    │   ├── testers/
    │   └── utilities/
    └── skills/
        ├── aws/
        ├── azure/
        └── testing/
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/create-user | POST | Create user & start deployment pipeline |
| /api/status/{execution_id} | GET | Get execution status & logs |
| /api/chat/{execution_id} | POST | Send message to Claude session |
| /api/redeploy/{execution_id} | POST | Force redeploy |
| /api/user/{user_id}/sessions | GET | List user's sessions |

## Resource Tagging (Mandatory)

```json
{
  "Project": "tmux-builder",
  "Environment": "production",
  "UserGUID": "{GUID}",
  "SessionID": "{session_id}",
  "ExecutionID": "{execution_id}",
  "SiteType": "static|dynamic",
  "CreatedAt": "{timestamp}",
  "CreatedBy": "tmux-builder-automation",
  "CostCenter": "user-sites"
}
```

## Implementation Phases

1. **Phase 1:** Core Infrastructure (user_manager, execution_tracker, job_runner)
2. **Phase 2:** Cloud Deployment Modules (AWS/Azure static/dynamic)
3. **Phase 3:** Testing Modules (health, screenshot, E2E)
4. **Phase 4:** Skill & Agent Library (injection engine, all agents/skills)
5. **Phase 5:** Integration & API (endpoints, CLAUDE.md generator, integration tests)
