"""Session Creator - creates session folders with SmartBuild pattern structure."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# Cloud provider profile constants
AWS_PROFILE = "sunwaretech"
AZURE_PROFILE = "sunwaretech"

# Default users directory (can be patched in tests)
USERS_DIR = Path(__file__).parent.parent / "users"


class SessionCreator:
    """Creates and manages session folder structures for users."""

    def __init__(self):
        """Initialize SessionCreator with users directory."""
        # Import dynamically to support patching in tests
        import session_creator
        self._users_dir = session_creator.USERS_DIR

    def _generate_session_id(self) -> str:
        """
        Generate a unique session ID with timestamp.

        Returns:
            Session ID in format: sess_YYYYMMDD_HHMMSS
        """
        now = datetime.now(timezone.utc)
        return f"sess_{now.strftime('%Y%m%d_%H%M%S')}"

    def create_session(
        self,
        user_id: str,
        host_provider: str,
        site_type: str
    ) -> str:
        """
        Create a new session folder with complete structure.

        Args:
            user_id: User's GUID
            host_provider: Cloud provider ('aws' or 'azure')
            site_type: Type of site ('static' or 'dynamic')

        Returns:
            Session ID string (format: sess_YYYYMMDD_HHMMSS)
        """
        session_id = self._generate_session_id()
        session_path = self.get_session_path(user_id, session_id)

        # Create session folder structure
        self._create_folder_structure(session_path)

        # Create deployment config
        self._create_deployment_config(session_path, host_provider, site_type)

        # Create CLAUDE.md
        self._create_claude_md(session_path, user_id, session_id, host_provider, site_type)

        return session_id

    def _create_folder_structure(self, session_path: Path) -> None:
        """
        Create the complete session folder structure.

        Structure:
            {session_id}/
            ├── .claude/
            │   ├── agents/
            │   ├── skills/
            │   └── CLAUDE.md
            ├── source/
            ├── deployment/
            │   ├── config.json
            │   └── tests/
            ├── logs/
            ├── prompts/
            ├── output/
            └── state/
        """
        # Create all directories
        directories = [
            session_path / ".claude" / "agents",
            session_path / ".claude" / "skills",
            session_path / "source",
            session_path / "deployment" / "tests",
            session_path / "logs",
            session_path / "prompts",
            session_path / "output",
            session_path / "state",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def _create_deployment_config(
        self,
        session_path: Path,
        host_provider: str,
        site_type: str
    ) -> None:
        """
        Create deployment/config.json with deployment settings.

        Args:
            session_path: Path to session directory
            host_provider: Cloud provider ('aws' or 'azure')
            site_type: Type of site ('static' or 'dynamic')
        """
        config = {
            "host_provider": host_provider,
            "site_type": site_type,
            "aws_profile": AWS_PROFILE,
            "azure_profile": AZURE_PROFILE,
            "url": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_deployed": None,
            "deploy_count": 0,
        }

        # Add provider-specific configuration section
        if host_provider == "aws":
            config["aws"] = {
                "s3_bucket": None,
                "cloudfront_distribution_id": None,
                "region": "us-east-1",
            }
        elif host_provider == "azure":
            config["azure"] = {
                "storage_account": None,
                "cdn_endpoint": None,
                "resource_group": None,
                "region": "eastus",
            }

        config_path = session_path / "deployment" / "config.json"
        config_path.write_text(json.dumps(config, indent=2))

    def _create_claude_md(
        self,
        session_path: Path,
        user_id: str,
        session_id: str,
        host_provider: str,
        site_type: str,
        execution_id: str = None
    ) -> None:
        """
        Create .claude/CLAUDE.md with session-specific context and core skills.

        Args:
            session_path: Path to session directory
            user_id: User's GUID
            session_id: Session ID
            host_provider: Cloud provider ('aws' or 'azure')
            site_type: Type of site ('static' or 'dynamic')
            execution_id: Optional execution ID for tracking
        """
        # Generate execution_id if not provided
        if execution_id is None:
            execution_id = f"{user_id}_{session_id}"

        # Determine provider-specific agents and skills
        if host_provider == "aws" and site_type == "static":
            deployer_agent = "deployers/aws-s3-static"
            deploy_skills = "aws/s3-upload, aws/cloudfront-create, aws/cloudfront-invalidate"
        elif host_provider == "aws" and site_type == "dynamic":
            deployer_agent = "deployers/aws-ec2"
            deploy_skills = "aws/ec2-deploy, aws/route53-configure"
        elif host_provider == "azure" and site_type == "static":
            deployer_agent = "deployers/azure-blob-static"
            deploy_skills = "azure/blob-upload, azure/cdn-create, azure/cdn-purge"
        else:  # azure dynamic
            deployer_agent = "deployers/azure-app-service"
            deploy_skills = "azure/app-service-deploy, azure/sql-configure"

        content = f"""# Session Context

## Session Information
- **User ID**: {user_id}
- **Session ID**: {session_id}
- **Execution ID**: {execution_id}
- **Host Provider**: {host_provider}
- **Site Type**: {site_type}
- **Created**: {datetime.now(timezone.utc).isoformat()}

## Cloud Profiles
- **AWS Profile**: {AWS_PROFILE}
- **Azure Profile**: {AZURE_PROFILE}

---

## MANDATORY Skills (Core Methodology)

**Before starting ANY new feature or modification, use these skills:**

### 1. Project Inception (`core/project-inception`)
**When:** Starting any new feature or significant change
**Why:** Defines acceptance criteria and ensures walking skeleton first
**How:** Announce "Using project-inception skill" then follow its process

### 2. Plan Validation (`core/plan-validation`)
**When:** After writing any implementation plan
**Why:** Catches missing tasks, broken config references, missing integration
**How:** Run all validation checks before executing any tasks

### 3. Integration Verification (`core/integration-verification`)
**When:** Before claiming work is complete
**Why:** Verifies system works end-to-end, not just individual modules
**How:** Test all demo scenarios, verify all API endpoints, check configs

### Workflow
```
New Feature Request
       ↓
project-inception (define acceptance criteria)
       ↓
brainstorming (design)
       ↓
writing-plans (create plan)
       ↓
plan-validation ← MUST PASS before executing
       ↓
Execute tasks (walking skeleton FIRST)
       ↓
integration-verification ← MUST PASS before completion
       ↓
Done
```

---

## Deployment Workflow

### Step 1: Generate/Modify Code
- Write code to `source/` directory
- Follow user requirements

### Step 2: Deploy
- Use agent: `{deployer_agent}`
- Use skills: `{deploy_skills}`
- Resource naming: `tmux-{{guid_prefix}}-{{session_short}}`

### Step 3: Test Deployment
- Use agent: `testers/health-check` - Verify HTTP 200
- Use agent: `testers/screenshot` - Capture visual proof

### Step 4: Update Status
- Update `deployment/config.json` with URL
- Log results to `logs/`

### Step 5: Inform User
- Report deployed URL
- Report any issues

---

## Available Resources

### Agents (in .claude/agents/)
Injected agents for {host_provider}/{site_type}:
- `{deployer_agent}` - Deployment automation
- `testers/health-check` - HTTP health verification
- `testers/screenshot` - Visual capture with Playwright

### Skills (in .claude/skills/)
Injected skills for {host_provider}/{site_type}:
- {deploy_skills}
- `testing/*` - Test automation utilities

### Core Skills (in .claude/skills/core/)
Methodology skills (always available):
- `core/project-inception` - Project startup methodology
- `core/plan-validation` - Plan verification
- `core/integration-verification` - E2E verification

---

## Directory Structure
```
{session_id}/
├── .claude/
│   ├── agents/           # Deployment and testing agents
│   ├── skills/           # Reusable skill definitions
│   └── CLAUDE.md         # This file
├── source/               # Website source code (YOU WRITE HERE)
├── deployment/
│   ├── config.json       # Deployment configuration
│   ├── screenshots/      # Captured screenshots
│   └── tests/            # E2E test results
├── logs/                 # Execution logs
├── prompts/              # SmartBuild input
├── output/               # SmartBuild output
└── state/                # Session state
```

---

## Resource Naming & Tagging

### Naming Convention
All cloud resources: `tmux-{{guid_first_8}}-{{session_short}}`
- S3 bucket limit: 63 characters
- Azure storage limit: 24 characters (no hyphens)

### MANDATORY Tags (Cost Tracking)
Every cloud resource MUST have:
```json
{{
  "Project": "tmux-builder",
  "Environment": "production",
  "UserGUID": "{user_id}",
  "SessionID": "{session_id}",
  "ExecutionID": "{execution_id}",
  "SiteType": "{site_type}",
  "CostCenter": "user-sites",
  "CreatedBy": "tmux-builder-automation"
}}
```

---

## Quick Reference

### Deploy Command (AWS Static)
```bash
# Uses sunwaretech profile
aws s3 sync source/ s3://{{bucket_name}}/ --profile {AWS_PROFILE}
```

### Deploy Command (Azure Static)
```bash
# Uses sunwaretech profile
az storage blob upload-batch -d '$web' -s source/ --account-name {{storage_account}}
```

### Health Check
```bash
curl -s -o /dev/null -w "%{{http_code}}" https://{{deployed_url}}
# Must return 200
```

---

## Important Notes

1. **Always use core skills** for new features to prevent functional gaps
2. **Walking skeleton first** - prove E2E before building modules
3. **Validate plans** before executing - catch missing tasks early
4. **Verify integration** before completion - ensure modules connect
5. **Tag all resources** - required for cost tracking
6. **Use {AWS_PROFILE if host_provider == 'aws' else AZURE_PROFILE} profile** for all cloud operations
"""

        claude_md_path = session_path / ".claude" / "CLAUDE.md"
        claude_md_path.write_text(content)

    def get_session_path(self, user_id: str, session_id: str) -> Path:
        """
        Get the path to a session directory.

        Args:
            user_id: User's GUID
            session_id: Session ID

        Returns:
            Path to session directory
        """
        return self._users_dir / user_id / "sessions" / session_id

    def list_sessions(self, user_id: str) -> List[str]:
        """
        List all session IDs for a user.

        Args:
            user_id: User's GUID

        Returns:
            List of session ID strings
        """
        sessions_dir = self._users_dir / user_id / "sessions"

        if not sessions_dir.exists():
            return []

        return [
            d.name for d in sessions_dir.iterdir()
            if d.is_dir() and d.name.startswith("sess_")
        ]
