# Claude Code Context

## Project Overview

tmux-builder is a multi-user tmux session management system with SmartBuild pattern for AI-driven workflows. Each user gets isolated sessions that can deploy websites to AWS or Azure.

## Architecture

- **Backend**: Python Flask API (`backend/app.py`)
- **Frontend**: React SPA (`frontend/src/`)
- **SmartBuild**: File-based I/O pattern for LLM-friendly operations
- **Multi-User**: GUID-based user isolation with cloud deployment

## Core Skills (MANDATORY)

**Every new project/feature MUST use these skills in order:**

### 1. Project Inception (`core/project-inception.md`)
**Use at START of any new feature/project**
- Defines acceptance criteria (demo scenarios)
- Ensures walking skeleton first
- Wraps brainstorming and planning

### 2. Plan Validation (`core/plan-validation.md`)
**Use AFTER writing plan, BEFORE execution**
- Validates design-to-plan coverage
- Checks config references have creation tasks
- Verifies API endpoint coverage
- Ensures integration task exists

### 3. Integration Verification (`core/integration-verification.md`)
**Use BEFORE finishing development branch**
- Tests all demo scenarios E2E
- Verifies API endpoints work
- Checks config file integrity
- Validates modules are connected

### Workflow

```
START → project-inception → brainstorming → writing-plans
                                              ↓
                               plan-validation (MUST PASS)
                                              ↓
                               subagent-driven-development
                                              ↓
                               integration-verification (MUST PASS)
                                              ↓
                               finishing-a-development-branch → DONE
```

---

## Multi-User Session Creation

### When POST /api/create-user is received:

```
Step 1: Create user GUID folder
        users/{GUID}/
        users/{GUID}/user.json
        users/{GUID}/sessions/

Step 2: Create session folder
        users/{GUID}/sessions/{session_id}/
        ├── .claude/
        │   ├── agents/      (injected based on host_provider + site_type)
        │   ├── skills/      (injected based on host_provider + site_type)
        │   └── CLAUDE.md    (session-specific context - SEE BELOW)
        ├── source/
        ├── deployment/
        │   ├── config.json
        │   └── tests/
        ├── logs/
        ├── prompts/
        ├── output/
        └── state/

Step 3: Inject agents/skills based on injection_rules.json

Step 4: Generate session CLAUDE.md (CRITICAL)
        - Contains session context
        - Contains core skills references
        - Contains deployment instructions

Step 5: Create execution tracking entry

Step 6: Start tmux session with Claude CLI

Step 7: Begin pipeline execution
```

### Session CLAUDE.md Template

The session CLAUDE.md MUST be generated with this content:

```markdown
# Session Context

## Session Information
- **User ID**: {user_id}
- **Session ID**: {session_id}
- **Execution ID**: {execution_id}
- **Host Provider**: {host_provider}
- **Site Type**: {site_type}

## Cloud Profiles
- **AWS Profile**: sunwaretech
- **Azure Profile**: sunwaretech

## MANDATORY Skills

Before starting ANY work, use these skills:

1. **For new features**: Use `core/project-inception`
2. **After planning**: Use `core/plan-validation`
3. **Before completion**: Use `core/integration-verification`

## Deployment Workflow

1. Generate/modify code in `source/`
2. Deploy using agents in `.claude/agents/deployers/`
3. Test using agents in `.claude/agents/testers/`
4. Update status in `deployment/config.json`
5. Inform user of result

## Available Resources

### Agents (in .claude/agents/)
[Injected based on host_provider + site_type]

### Skills (in .claude/skills/)
[Injected based on host_provider + site_type]

## Directory Structure
- `source/` - Website source code
- `deployment/` - Deployment config and test results
- `logs/` - Session execution logs
- `prompts/` - SmartBuild input prompts
- `output/` - SmartBuild output results
- `state/` - Session state files

## Resource Naming
- AWS/Azure resources: `tmux-{guid_prefix}-{session_short}`
- All resources MUST have cost tracking tags

## Commands

### Deploy to AWS (static)
Use agent: `deployers/aws-s3-static`
Use skills: `aws/s3-upload`, `aws/cloudfront-create`

### Deploy to Azure (static)
Use agent: `deployers/azure-blob-static`
Use skills: `azure/blob-upload`, `azure/cdn-create`

### Test Deployment
Use agents: `testers/health-check`, `testers/screenshot`
```

---

## Key Commands

### Development
- `python3 backend/app.py` - Start Flask backend (port 5001)
- `npm start` - Start React frontend in `frontend/` directory (port 3000)

### Testing
- `cd backend && python3 -m pytest -v` - Run all tests
- `python3 backend/test_smartbuild.py` - Test SmartBuild with file-based I/O

### API Endpoints
- `POST /api/create-user` - Create user and start deployment pipeline
- `GET /api/status/{execution_id}` - Get pipeline execution status
- `GET /api/user/{user_id}/sessions` - List user's sessions

## Project Structure

```
tmux-builder/
├── backend/
│   ├── app.py                 # Flask API server
│   ├── user_manager.py        # User GUID generation
│   ├── session_creator.py     # Session folder creation
│   ├── execution_tracker.py   # Pipeline status tracking
│   ├── injection_engine.py    # Agent/skill injection
│   ├── aws_deployer.py        # AWS S3+CloudFront deployment
│   ├── azure_deployer.py      # Azure Blob+CDN deployment
│   ├── health_checker.py      # HTTP health checks
│   ├── screenshot_capture.py  # Playwright screenshots
│   └── tests/                 # Test suite
├── frontend/
│   └── src/                   # React application
├── users/                     # User data (GUID folders)
│   ├── registry.json          # Email+phone → GUID mapping
│   └── {GUID}/
│       ├── user.json
│       └── sessions/
├── executions/                # Pipeline execution status
├── .claude/
│   ├── agents/                # Master agent library
│   │   ├── deployers/
│   │   └── testers/
│   └── skills/
│       ├── aws/
│       ├── azure/
│       └── core/              # MANDATORY methodology skills
│           ├── project-inception.md
│           ├── plan-validation.md
│           └── integration-verification.md
└── docs/                      # All project documentation
```

## Cloud Configuration

### AWS
- Profile: `sunwaretech`
- Default region: `us-east-1`
- Static: S3 + CloudFront
- Dynamic: EC2 (planned)

### Azure
- Profile: `sunwaretech`
- Default region: `eastus`
- Static: Blob Storage + CDN
- Dynamic: App Service (planned)

### Resource Tagging (MANDATORY)
All cloud resources MUST have these tags:
- Project: tmux-builder
- UserGUID: {user_id}
- SessionID: {session_id}
- ExecutionID: {execution_id}
- SiteType: static|dynamic
- CostCenter: user-sites
- CreatedBy: tmux-builder-automation

## Documentation

See `docs/` folder:
- `QUICKSTART.md` - Getting started guide
- `ARCHITECTURE.md` - System design
- `SMARTBUILD_ARCHITECTURE_ANALYSIS.md` - SmartBuild pattern details
- `plans/` - Design and implementation plans

## Important Notes

- SmartBuild uses **file-based I/O** - no CLI prompts during execution
- Each user gets isolated GUID folder under `users/`
- Each session gets isolated folder with injected agents/skills
- **Always use core skills** for new features to prevent functional gaps
- Backend runs on port 5001 to avoid conflicts
