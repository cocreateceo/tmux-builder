# Autonomous Build Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform tmux-builder into autonomous AI build agent that receives requests, builds applications, and returns deployed CloudFront URLs with minimal human intervention.

**Architecture:** FastAPI backend receives registration via `/api/register`, generates GUID, initializes Claude CLI session in background, renders autonomous system prompt from templates, Claude works through build phases (analyze→plan→code→test→deploy), returns deployment URL.

**Tech Stack:** Python 3.8+, FastAPI, tmux, Claude CLI, Jinja2 templates, YAML config, threading for async workers, AWS CLI with sunware profile

---

## Task 1: Reorganize Documentation Structure

**Goal:** Create organized docs/ structure and move all documentation files appropriately

**Files:**
- Create: `docs/architecture/`, `docs/guides/`, `docs/project/`, `docs/plans/`, `docs/validation/`
- Move: All 12 .md and .txt files from root to appropriate folders

**Step 1: Write test to verify documentation structure**

Create `backend/tests/test_documentation_structure.py`:

```python
import pytest
from pathlib import Path

def test_docs_directory_structure():
    """Verify docs/ directory structure exists."""
    base_path = Path(__file__).parent.parent.parent
    docs_path = base_path / "docs"

    # Check main docs folder exists
    assert docs_path.exists(), "docs/ folder must exist"

    # Check subdirectories exist
    required_subdirs = ["architecture", "guides", "project", "plans", "validation"]
    for subdir in required_subdirs:
        subdir_path = docs_path / subdir
        assert subdir_path.exists(), f"docs/{subdir}/ must exist"

def test_architecture_docs_moved():
    """Verify architecture documentation is in correct location."""
    base_path = Path(__file__).parent.parent.parent
    docs_arch = base_path / "docs" / "architecture"

    # Should exist in docs/architecture/
    assert (docs_arch / "ARCHITECTURE.md").exists()
    assert (docs_arch / "SMARTBUILD_ARCHITECTURE_ANALYSIS.md").exists()

    # Should NOT exist in root
    assert not (base_path / "ARCHITECTURE.md").exists()
    assert not (base_path / "SMARTBUILD_ARCHITECTURE_ANALYSIS.md").exists()

def test_guides_docs_moved():
    """Verify guide documentation is in correct location."""
    base_path = Path(__file__).parent.parent.parent
    docs_guides = base_path / "docs" / "guides"

    required_guides = [
        "QUICKSTART.md",
        "SETUP.md",
        "TESTING_GUIDE.md",
        "HOW_TO_IMPLEMENT_TMUX_IN_ANY_PROJECT.md"
    ]

    for guide in required_guides:
        assert (docs_guides / guide).exists(), f"{guide} must be in docs/guides/"
        assert not (base_path / guide).exists(), f"{guide} must not be in root"

def test_project_docs_moved():
    """Verify project documentation is in correct location."""
    base_path = Path(__file__).parent.parent.parent
    docs_project = base_path / "docs" / "project"

    required_docs = [
        "PROJECT_STATUS.txt",
        "PROJECT_SUMMARY.md",
        "IMPLEMENTATION_SUMMARY.md"
    ]

    for doc in required_docs:
        assert (docs_project / doc).exists(), f"{doc} must be in docs/project/"
        assert not (base_path / doc).exists(), f"{doc} must not be in root"

def test_validation_docs_moved():
    """Verify validation documentation is in correct location."""
    base_path = Path(__file__).parent.parent.parent
    docs_validation = base_path / "docs" / "validation"

    assert (docs_validation / "TEST_VALIDATION_REPORT.md").exists()
    assert not (base_path / "TEST_VALIDATION_REPORT.md").exists()

def test_readme_files_remain_in_root():
    """Verify README files stay in root."""
    base_path = Path(__file__).parent.parent.parent

    # These should stay in root for GitHub visibility
    assert (base_path / "README.md").exists()
```

**Step 2: Run test to verify it fails**

```bash
cd /mnt/c/Development/Builder-CLI/tmux-builder/backend
python3 -m pytest tests/test_documentation_structure.py -v
```

Expected: FAIL - docs/ directories don't exist yet

**Step 3: Create directory structure**

```bash
cd /mnt/c/Development/Builder-CLI/tmux-builder
mkdir -p docs/architecture docs/guides docs/project docs/plans docs/validation
```

**Step 4: Move documentation files**

```bash
# Move architecture docs
mv ARCHITECTURE.md docs/architecture/
mv SMARTBUILD_ARCHITECTURE_ANALYSIS.md docs/architecture/

# Move guides
mv QUICKSTART.md docs/guides/
mv SETUP.md docs/guides/
mv TESTING_GUIDE.md docs/guides/
mv HOW_TO_IMPLEMENT_TMUX_IN_ANY_PROJECT.md docs/guides/

# Move project docs
mv PROJECT_STATUS.txt docs/project/
mv PROJECT_SUMMARY.md docs/project/
mv IMPLEMENTATION_SUMMARY.md docs/project/

# Move validation docs
mv TEST_VALIDATION_REPORT.md docs/validation/

# Keep README.md and README_FINAL.md in root for GitHub
```

**Step 5: Run test to verify it passes**

```bash
cd backend
python3 -m pytest tests/test_documentation_structure.py -v
```

Expected: PASS - all documentation properly organized

**Step 6: Update README to reference new structure**

Edit `README.md` to add documentation section:

```markdown
## Documentation

All documentation is organized in the `docs/` directory:

- **Architecture** (`docs/architecture/`) - System design and architectural analysis
- **Guides** (`docs/guides/`) - Setup, testing, and implementation guides
- **Project** (`docs/project/`) - Project status and summaries
- **Plans** (`docs/plans/`) - Implementation plans
- **Validation** (`docs/validation/`) - Test reports and validation results
```

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: organize documentation into structured docs/ folder

- Create docs/ subdirectories (architecture, guides, project, plans, validation)
- Move all documentation files from root to appropriate folders
- Add tests to verify documentation structure
- Update README with documentation organization

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Create Template System Foundation

**Goal:** Implement template system with YAML config and PromptManager for rendering system/user prompts

**Files:**
- Create: `backend/templates/prompt_config.yaml`
- Create: `backend/prompt_manager.py`
- Create: `backend/tests/test_prompt_manager.py`
- Create: `backend/templates/system_prompts/.gitkeep`

**Step 1: Write failing test for PromptManager**

Create `backend/tests/test_prompt_manager.py`:

```python
import pytest
from pathlib import Path
from prompt_manager import PromptManager

@pytest.fixture
def prompt_manager():
    """Create PromptManager instance for testing."""
    return PromptManager()

def test_prompt_manager_loads_config(prompt_manager):
    """Test that PromptManager loads prompt_config.yaml."""
    assert prompt_manager.config is not None
    assert 'version' in prompt_manager.config
    assert 'variables' in prompt_manager.config
    assert 'system_prompts' in prompt_manager.config

def test_render_system_prompt_with_variables(prompt_manager):
    """Test rendering system prompt with variable substitution."""
    variables = {
        'guid': 'test_guid_123',
        'email': 'test@example.com',
        'phone': '+15551234567',
        'user_request': 'Build a todo app',
        'session_path': '/tmp/test_session',
        'aws_profile': 'sunware'
    }

    result = prompt_manager.render_system_prompt('autonomous_agent', variables)

    # Should contain substituted values
    assert 'test_guid_123' in result
    assert 'test@example.com' in result
    assert 'Build a todo app' in result
    assert 'sunware' in result

def test_render_fails_with_missing_variables(prompt_manager):
    """Test that rendering fails when required variables are missing."""
    incomplete_variables = {
        'guid': 'test_guid_123',
        'email': 'test@example.com'
        # Missing: phone, user_request, session_path, aws_profile
    }

    with pytest.raises(KeyError):
        prompt_manager.render_system_prompt('autonomous_agent', incomplete_variables)

def test_get_available_prompts(prompt_manager):
    """Test getting list of available prompt templates."""
    prompts = prompt_manager.get_available_prompts()

    assert 'autonomous_agent' in prompts
    assert isinstance(prompts, list)
```

**Step 2: Run test to verify it fails**

```bash
cd backend
python3 -m pytest tests/test_prompt_manager.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'prompt_manager'"

**Step 3: Create prompt_config.yaml**

Create `backend/templates/prompt_config.yaml`:

```yaml
version: "1.0"

# Global variables available to all templates
variables:
  aws_profile: "sunware"
  max_cost_threshold: 100
  default_region: "us-east-1"
  clarification_strategy: "autonomous"

# System prompts for different modes
system_prompts:
  autonomous_agent:
    template_file: "templates/system_prompts/autonomous_agent.txt"
    description: "Main autonomous build agent system prompt"
    variables_required:
      - guid
      - email
      - phone
      - user_request
      - session_path
      - aws_profile

  refinement_mode:
    template_file: "templates/system_prompts/refinement_mode.txt"
    description: "System prompt for post-deployment refinements"
    variables_required:
      - guid
      - deployment_url
      - original_request
      - refinement_request
      - session_path

  debug_mode:
    template_file: "templates/system_prompts/debug_mode.txt"
    description: "System prompt for debugging failed deployments"
    variables_required:
      - guid
      - error_log
      - session_path
      - aws_profile
```

**Step 4: Implement PromptManager**

Create `backend/prompt_manager.py`:

```python
"""Manages prompt templates and variable substitution."""

import yaml
from pathlib import Path
from string import Template
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class PromptManager:
    """Manages loading and rendering of prompt templates."""

    def __init__(self, config_path: str = None):
        """
        Initialize PromptManager.

        Args:
            config_path: Path to prompt_config.yaml (default: templates/prompt_config.yaml)
        """
        if config_path is None:
            base_path = Path(__file__).parent
            config_path = base_path / "templates" / "prompt_config.yaml"

        self.config_path = Path(config_path)
        self.base_path = self.config_path.parent.parent
        self.config = self._load_config()

        logger.info(f"PromptManager initialized with config: {self.config_path}")

    def _load_config(self) -> Dict[str, Any]:
        """Load prompt configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded prompt config version {config.get('version')}")
            return config
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config: {e}")
            raise

    def load_template(self, template_file: str) -> str:
        """
        Load template content from file.

        Args:
            template_file: Relative path to template file

        Returns:
            Template content as string
        """
        template_path = self.base_path / template_file

        try:
            with open(template_path, 'r') as f:
                content = f.read()
            logger.debug(f"Loaded template: {template_path}")
            return content
        except FileNotFoundError:
            logger.error(f"Template file not found: {template_path}")
            raise

    def render_system_prompt(self, prompt_type: str, variables: Dict[str, Any]) -> str:
        """
        Render system prompt with variable substitution.

        Args:
            prompt_type: Type of prompt (from config: autonomous_agent, refinement_mode, etc)
            variables: Dictionary of variables to substitute

        Returns:
            Rendered prompt string

        Raises:
            KeyError: If required variables are missing
            ValueError: If prompt_type is not found in config
        """
        if prompt_type not in self.config['system_prompts']:
            available = list(self.config['system_prompts'].keys())
            raise ValueError(f"Unknown prompt type '{prompt_type}'. Available: {available}")

        prompt_config = self.config['system_prompts'][prompt_type]

        # Check for required variables
        required_vars = prompt_config.get('variables_required', [])
        missing_vars = [var for var in required_vars if var not in variables]
        if missing_vars:
            raise KeyError(f"Missing required variables for '{prompt_type}': {missing_vars}")

        # Merge global variables with provided variables (provided takes precedence)
        merged_vars = {**self.config.get('variables', {}), **variables}

        # Load and render template
        template_content = self.load_template(prompt_config['template_file'])
        template = Template(template_content)

        try:
            rendered = template.safe_substitute(merged_vars)
            logger.info(f"Rendered prompt type '{prompt_type}' with {len(merged_vars)} variables")
            return rendered
        except Exception as e:
            logger.error(f"Error rendering template '{prompt_type}': {e}")
            raise

    def get_available_prompts(self) -> List[str]:
        """
        Get list of available prompt types.

        Returns:
            List of prompt type names
        """
        return list(self.config['system_prompts'].keys())

    def get_prompt_info(self, prompt_type: str) -> Dict[str, Any]:
        """
        Get information about a specific prompt type.

        Args:
            prompt_type: Type of prompt

        Returns:
            Dictionary with prompt configuration
        """
        if prompt_type not in self.config['system_prompts']:
            raise ValueError(f"Unknown prompt type: {prompt_type}")

        return self.config['system_prompts'][prompt_type]
```

**Step 5: Install PyYAML dependency**

```bash
pip3 install --user PyYAML==6.0.1
```

**Step 6: Create placeholder for template files**

```bash
mkdir -p backend/templates/system_prompts
touch backend/templates/system_prompts/.gitkeep
```

**Step 7: Run test to verify it passes (will fail on template file, expected)**

```bash
cd backend
python3 -m pytest tests/test_prompt_manager.py::test_prompt_manager_loads_config -v
python3 -m pytest tests/test_prompt_manager.py::test_get_available_prompts -v
```

Expected: These specific tests should PASS

**Step 8: Commit**

```bash
git add backend/templates/prompt_config.yaml backend/prompt_manager.py backend/tests/test_prompt_manager.py
git commit -m "feat: add template system foundation with PromptManager

- Create prompt_config.yaml with template definitions
- Implement PromptManager for loading/rendering prompts
- Add variable substitution with Template
- Add tests for PromptManager
- Support multiple prompt types (autonomous_agent, refinement_mode, debug_mode)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Create Autonomous Agent System Prompt

**Goal:** Write comprehensive autonomous agent system prompt that guides Claude through build/deploy phases

**Files:**
- Create: `backend/templates/system_prompts/autonomous_agent.txt`
- Modify: `backend/tests/test_prompt_manager.py`

**Step 1: Add test for autonomous agent prompt rendering**

Add to `backend/tests/test_prompt_manager.py`:

```python
def test_autonomous_agent_prompt_contains_key_sections(prompt_manager):
    """Test that autonomous agent prompt has all required sections."""
    variables = {
        'guid': 'abc123',
        'email': 'user@example.com',
        'phone': '+15551234567',
        'user_request': 'Build a React todo app with API backend',
        'session_path': '/path/to/session',
        'aws_profile': 'sunware'
    }

    result = prompt_manager.render_system_prompt('autonomous_agent', variables)

    # Check for key sections
    assert 'Phase 1' in result or 'PHASE 1' in result
    assert 'Phase 2' in result or 'PHASE 2' in result
    assert 'Phase 3' in result or 'PHASE 3' in result
    assert 'Phase 4' in result or 'PHASE 4' in result

    # Check for skills mentioned
    assert 'brainstorm' in result.lower() or '/brainstorm' in result
    assert 'writing-plans' in result or '/writing-plans' in result
    assert 'test-driven-development' in result or 'TDD' in result

    # Check for AWS profile
    assert 'sunware' in result

    # Check for user request
    assert 'React todo app' in result
```

**Step 2: Run test to verify it fails**

```bash
cd backend
python3 -m pytest tests/test_prompt_manager.py::test_autonomous_agent_prompt_contains_key_sections -v
```

Expected: FAIL - template file doesn't exist yet

**Step 3: Create autonomous_agent.txt template**

Create `backend/templates/system_prompts/autonomous_agent.txt`:

```text
# AUTONOMOUS BUILD & DEPLOY AGENT

## YOUR MISSION
You are an autonomous AI development agent. Your mission: Take the user's request and deliver a FULLY DEPLOYED, WORKING application with minimal human intervention.

**User Request:** $user_request

**Your Session:** GUID=$guid | User: $email / $phone
**Session Path:** $session_path
**AWS Profile:** $aws_profile (use for all AWS CLI commands)

---

## AUTONOMOUS OPERATION MODE

**Default behavior:** Make best engineering decisions autonomously. Only ask critical questions.

**Critical questions** (ask immediately):
- Monthly AWS cost estimate > $$100
- Security/compliance requirements unclear
- User explicitly requested approval for specific decision

**Non-critical clarifications** (batch and continue):
- Technology choices within same capability tier
- UI/UX preferences for internal tools
- Minor feature prioritization
- Code organization preferences

**Your decision-making authority:**
- Choose frameworks, libraries, tools
- Design database schemas
- Select AWS services
- Implement error handling
- Write tests
- Deploy to production

---

## PHASE 1: ANALYSIS & PLANNING

**Step 1: Deep Understanding**
Use `/brainstorm` skill to understand requirements:
- What problem does this solve?
- Who are the users?
- What are the core features?
- What are the constraints?

**Step 2: Technical Design**
Use `/writing-plans` skill to create implementation plan:
- Choose tech stack (justify choices)
- Design architecture
- Estimate AWS costs
- Plan deployment strategy

**ASK USER ONLY IF:**
- Estimated monthly AWS cost > $$100
- Critical security requirements unclear
- Multiple valid approaches with major trade-offs

**Status Update:** Write to `$session_path/status.json`:
```json
{
  "status": "planning",
  "phase": 1,
  "progress": 20,
  "message": "Analyzed requirements, creating implementation plan",
  "estimated_completion": "30 minutes"
}
```

---

## PHASE 2: IMPLEMENTATION

**Step 1: Test-Driven Development**
Use `/test-driven-development` skill:
- Write failing tests FIRST
- Implement minimal code to pass
- Refactor for quality
- Commit frequently

**Step 2: Code Generation**
Generate all necessary files:
- Frontend code (React, Vue, or best fit)
- Backend API (FastAPI, Express, or best fit)
- Database schemas
- Infrastructure as Code (Terraform or CloudFormation)
- Configuration files
- Documentation

**Step 3: Quality Checks**
Use `/code-review` skill on critical components:
- Security vulnerabilities
- Performance issues
- Best practices compliance

**Status Update:** Update `$session_path/status.json`:
```json
{
  "status": "implementing",
  "phase": 2,
  "progress": 60,
  "message": "Generated application code, writing tests",
  "files_created": 15
}
```

---

## PHASE 3: DEPLOYMENT

**Step 1: Generate Infrastructure**
Create complete IaC (Infrastructure as Code):
- Use Terraform or CloudFormation
- Include all AWS resources needed
- Add monitoring and logging
- Configure auto-scaling if needed

**Step 2: Deploy to AWS**
Execute deployment:
```bash
# Always use the specified AWS profile
export AWS_PROFILE=$aws_profile

# Deploy infrastructure
terraform init
terraform plan
terraform apply -auto-approve

# Or for CloudFormation
aws cloudformation deploy --template-file template.yaml --stack-name <name>
```

**Step 3: Health Checks**
Verify deployment:
- Application responds correctly
- Database connections work
- APIs return expected responses
- Frontend loads properly

**Step 4: Capture Deployment URL**
Get CloudFront or LoadBalancer URL:
```bash
# Terraform
terraform output application_url

# CloudFormation
aws cloudformation describe-stacks --stack-name <name> --query 'Stacks[0].Outputs[?OutputKey==`ApplicationURL`].OutputValue' --output text
```

**Status Update:** Update `$session_path/status.json`:
```json
{
  "status": "deploying",
  "phase": 3,
  "progress": 85,
  "message": "Deploying to AWS, running health checks",
  "deployment_url": "https://xxxxx.cloudfront.net"
}
```

---

## PHASE 4: FINALIZATION

**Step 1: Final Verification**
Use `/verification-before-completion` skill:
- Run all tests
- Verify deployment health
- Check application functionality
- Confirm CloudFront URL works

**Step 2: Generate Handoff Documentation**
Create `$session_path/DEPLOYMENT_SUMMARY.md`:
```markdown
# Deployment Summary

## Application Details
- **User Request:** $user_request
- **Deployment URL:** https://xxxxx.cloudfront.net
- **Tech Stack:** [List technologies used]
- **AWS Resources:** [List created resources]

## Cost Estimate
- **Monthly:** ~$XX (breakdown)

## Access & Credentials
- [How to access application]
- [Any credentials if applicable]

## Repository
- **Code Location:** $session_path/code/
- **IaC Location:** $session_path/infrastructure/

## Maintenance
- [How to update application]
- [How to scale]
- [How to monitor]

## Next Steps
- [Suggested improvements]
- [Optional features to add]
```

**Step 3: Final Status Update**
Update `$session_path/status.json`:
```json
{
  "status": "deployed",
  "phase": 4,
  "progress": 100,
  "message": "Application deployed successfully",
  "deployment_url": "https://xxxxx.cloudfront.net",
  "completed_at": "2026-01-25T12:34:56Z",
  "cost_estimate_monthly": 25.50
}
```

**Step 4: Notify User**
Write completion message to `$session_path/completion.txt`:
```
✅ DEPLOYMENT COMPLETE

Your application is live at:
https://xxxxx.cloudfront.net

📊 Summary:
- Tech Stack: [technologies]
- Deployment Time: [duration]
- AWS Resources: [count]
- Estimated Monthly Cost: $XX

📝 Full details: See DEPLOYMENT_SUMMARY.md

🔄 To make changes: Send refinement requests to /api/session/$guid/refine
```

---

## SKILLS TO USE

**Required skills** (you MUST invoke these):
- `/brainstorm` - Understanding requirements
- `/writing-plans` - Creating implementation plan
- `/test-driven-development` - Writing tests before code
- `/verification-before-completion` - Verifying before claiming done

**Recommended skills**:
- `/code-review` - Review critical components
- `/systematic-debugging` - If issues arise

**Skill usage pattern**:
```
/brainstorm → /writing-plans → /test-driven-development (loop) →
/code-review → Deploy → /verification-before-completion
```

---

## ERROR HANDLING

**If deployment fails:**
1. Use `/systematic-debugging` skill (required)
2. Don't guess - find root cause
3. Fix and retry
4. Update status.json with "error" status

**If costs exceed threshold:**
1. STOP immediately
2. Update status.json: `{"status": "awaiting_approval", "reason": "cost_threshold"}`
3. Write question to `$session_path/clarifications.json`
4. Wait for approval via API

---

## FILE ORGANIZATION

Organize work in session directory:

```
$session_path/
├── status.json              # Current status (update frequently)
├── code/                    # Application code
│   ├── frontend/
│   ├── backend/
│   └── tests/
├── infrastructure/          # IaC files
│   ├── terraform/ or cloudformation/
│   └── deployment_logs/
├── docs/
│   ├── DEPLOYMENT_SUMMARY.md
│   └── architecture.md
├── clarifications.json      # Questions needing user input
└── completion.txt          # Final completion message
```

---

## REMEMBER

✅ **DO:**
- Make best engineering decisions autonomously
- Use skills in proper order
- Test everything before deploying
- Update status.json frequently
- Deploy to production (not staging)
- Capture actual deployment URL

❌ **DON'T:**
- Ask non-critical questions
- Wait for approval on standard decisions
- Deploy without tests
- Skip health checks
- Forget to update status.json
- Leave placeholder TODOs

---

**NOW BEGIN:** Start with `/brainstorm` to understand the user's request deeply, then proceed through all phases autonomously.
```

**Step 4: Run test to verify it passes**

```bash
cd backend
python3 -m pytest tests/test_prompt_manager.py::test_autonomous_agent_prompt_contains_key_sections -v
python3 -m pytest tests/test_prompt_manager.py::test_render_system_prompt_with_variables -v
```

Expected: PASS - template exists and renders correctly

**Step 5: Test full rendering with real values**

Create quick test script `backend/test_prompt_render.py`:

```python
#!/usr/bin/env python3
from prompt_manager import PromptManager

pm = PromptManager()
result = pm.render_system_prompt('autonomous_agent', {
    'guid': 'test123',
    'email': 'test@example.com',
    'phone': '+15551234567',
    'user_request': 'Build a todo app',
    'session_path': '/tmp/test',
    'aws_profile': 'sunware'
})

print(result[:500])  # Print first 500 chars
print(f"\n... [Total length: {len(result)} characters]")
```

```bash
cd backend
python3 test_prompt_render.py
```

Expected: Should print rendered prompt with substituted variables

**Step 6: Commit**

```bash
git add backend/templates/system_prompts/autonomous_agent.txt backend/tests/test_prompt_manager.py backend/test_prompt_render.py
git commit -m "feat: add autonomous agent system prompt template

- Create comprehensive 4-phase system prompt
- Guide Claude through: Analysis → Implementation → Deployment → Finalization
- Specify autonomous decision-making authority
- Include status.json update requirements
- List required skills to invoke
- Add file organization structure
- Add tests for prompt rendering

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Implement Background Worker System

**Goal:** Create background worker that initializes sessions asynchronously without blocking API responses

**Files:**
- Create: `backend/background_worker.py`
- Create: `backend/tests/test_background_worker.py`

**Step 1: Write failing test for BackgroundWorker**

Create `backend/tests/test_background_worker.py`:

```python
import pytest
import time
from pathlib import Path
from background_worker import BackgroundWorker

@pytest.fixture
def worker():
    """Create BackgroundWorker instance."""
    return BackgroundWorker()

def test_worker_initialization(worker):
    """Test BackgroundWorker initializes correctly."""
    assert worker is not None
    assert hasattr(worker, 'jobs')
    assert hasattr(worker, 'start_initialization')

def test_start_initialization_returns_immediately(worker):
    """Test that start_initialization returns immediately without blocking."""
    start_time = time.time()

    worker.start_initialization(
        guid='test123',
        email='test@example.com',
        phone='+15551234567',
        user_request='Build a test app'
    )

    elapsed = time.time() - start_time

    # Should return in less than 0.1 seconds (non-blocking)
    assert elapsed < 0.1

def test_job_status_tracking(worker):
    """Test that worker tracks job status."""
    guid = 'test123'

    worker.start_initialization(guid, 'test@example.com', '+15551234567', 'Build app')

    # Job should be tracked
    assert guid in worker.jobs

    # Should have status
    status = worker.get_job_status(guid)
    assert status is not None
    assert 'status' in status
    assert status['status'] in ['pending', 'initializing', 'ready', 'failed']

def test_multiple_concurrent_jobs(worker):
    """Test handling multiple jobs concurrently."""
    guids = ['guid1', 'guid2', 'guid3']

    for i, guid in enumerate(guids):
        worker.start_initialization(
            guid=guid,
            email=f'user{i}@example.com',
            phone=f'+155512345{i}',
            user_request=f'Build app {i}'
        )

    # All jobs should be tracked
    for guid in guids:
        assert guid in worker.jobs
```

**Step 2: Run test to verify it fails**

```bash
cd backend
python3 -m pytest tests/test_background_worker.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'background_worker'"

**Step 3: Implement BackgroundWorker**

Create `backend/background_worker.py`:

```python
"""Background worker for async session initialization."""

import threading
import logging
import time
from typing import Dict, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """Manages background initialization of Claude CLI sessions."""

    def __init__(self):
        """Initialize BackgroundWorker."""
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        logger.info("BackgroundWorker initialized")

    def start_initialization(
        self,
        guid: str,
        email: str,
        phone: str,
        user_request: str
    ) -> None:
        """
        Start session initialization in background thread.

        This method returns immediately. Initialization happens asynchronously.

        Args:
            guid: User GUID
            email: User email
            phone: User phone
            user_request: User's build request
        """
        with self.lock:
            # Track job
            self.jobs[guid] = {
                'status': 'pending',
                'email': email,
                'phone': phone,
                'user_request': user_request,
                'started_at': datetime.utcnow().isoformat() + 'Z',
                'progress': 0,
                'message': 'Queued for initialization'
            }

        # Start worker thread
        worker = threading.Thread(
            target=self._worker_thread,
            args=(guid, email, phone, user_request),
            daemon=True,
            name=f"Worker-{guid}"
        )
        worker.start()

        logger.info(f"Started initialization worker for GUID: {guid}")

    def _worker_thread(
        self,
        guid: str,
        email: str,
        phone: str,
        user_request: str
    ) -> None:
        """
        Worker thread that performs actual initialization.

        This runs in background and updates job status as it progresses.

        Args:
            guid: User GUID
            email: User email
            phone: User phone
            user_request: User's build request
        """
        try:
            logger.info(f"Worker thread started for GUID: {guid}")

            # Import here to avoid circular dependencies
            from session_initializer import SessionInitializer

            # Update status
            self._update_job_status(guid, {
                'status': 'initializing',
                'progress': 10,
                'message': 'Initializing session...'
            })

            # Initialize session
            initializer = SessionInitializer()
            result = initializer.initialize_session(guid, email, phone, user_request)

            if result['success']:
                # Update status to ready
                self._update_job_status(guid, {
                    'status': 'ready',
                    'progress': 100,
                    'message': 'Session initialized successfully',
                    'session_name': result.get('session_name'),
                    'session_path': result.get('session_path')
                })
                logger.info(f"✓ Session initialization complete for GUID: {guid}")
            else:
                # Update status to failed
                self._update_job_status(guid, {
                    'status': 'failed',
                    'progress': 0,
                    'message': f"Initialization failed: {result.get('error')}",
                    'error': result.get('error')
                })
                logger.error(f"✗ Session initialization failed for GUID: {guid}")

        except Exception as e:
            logger.exception(f"Worker thread exception for GUID {guid}: {e}")
            self._update_job_status(guid, {
                'status': 'failed',
                'progress': 0,
                'message': f"Initialization error: {str(e)}",
                'error': str(e)
            })

    def _update_job_status(self, guid: str, updates: Dict[str, Any]) -> None:
        """
        Update job status thread-safely.

        Args:
            guid: User GUID
            updates: Dictionary of fields to update
        """
        with self.lock:
            if guid in self.jobs:
                self.jobs[guid].update(updates)
                self.jobs[guid]['updated_at'] = datetime.utcnow().isoformat() + 'Z'

    def get_job_status(self, guid: str) -> Dict[str, Any]:
        """
        Get current status of a job.

        Args:
            guid: User GUID

        Returns:
            Job status dictionary or None if not found
        """
        with self.lock:
            return self.jobs.get(guid, None)

    def cleanup_old_jobs(self, max_age_seconds: int = 86400) -> int:
        """
        Clean up old completed/failed jobs.

        Args:
            max_age_seconds: Maximum age in seconds (default: 24 hours)

        Returns:
            Number of jobs cleaned up
        """
        current_time = time.time()
        cleaned = 0

        with self.lock:
            guids_to_remove = []

            for guid, job in self.jobs.items():
                # Parse started_at timestamp
                started_at = datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))
                age_seconds = (datetime.utcnow() - started_at.replace(tzinfo=None)).total_seconds()

                # Remove if old and not pending/initializing
                if age_seconds > max_age_seconds and job['status'] not in ['pending', 'initializing']:
                    guids_to_remove.append(guid)

            for guid in guids_to_remove:
                del self.jobs[guid]
                cleaned += 1

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old jobs")

        return cleaned
```

**Step 4: Run test to verify it passes**

```bash
cd backend
python3 -m pytest tests/test_background_worker.py::test_worker_initialization -v
python3 -m pytest tests/test_background_worker.py::test_start_initialization_returns_immediately -v
python3 -m pytest tests/test_background_worker.py::test_job_status_tracking -v
```

Expected: Most tests PASS (some may fail due to missing SessionInitializer, that's expected)

**Step 5: Commit**

```bash
git add backend/background_worker.py backend/tests/test_background_worker.py
git commit -m "feat: implement background worker for async session init

- Create BackgroundWorker class with thread management
- Support non-blocking session initialization
- Track job status (pending, initializing, ready, failed)
- Thread-safe job status updates
- Cleanup mechanism for old jobs
- Add tests for worker functionality

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Implement Session Initializer with Health Checks

**Goal:** Create SessionInitializer that manages TMUX session lifecycle with health checks and recovery

**Files:**
- Create: `backend/session_initializer.py`
- Create: `backend/tests/test_session_initializer.py`
- Modify: `backend/tmux_helper.py` (add health check method)

**Step 1: Write failing test for SessionInitializer**

Create `backend/tests/test_session_initializer.py`:

```python
import pytest
from pathlib import Path
from session_initializer import SessionInitializer

@pytest.fixture
def initializer():
    """Create SessionInitializer instance."""
    return SessionInitializer()

def test_initializer_creation(initializer):
    """Test SessionInitializer can be created."""
    assert initializer is not None

def test_initialize_session_returns_dict(initializer):
    """Test initialize_session returns properly structured dict."""
    result = initializer.initialize_session(
        guid='test_guid',
        email='test@example.com',
        phone='+15551234567',
        user_request='Build a test app'
    )

    assert isinstance(result, dict)
    assert 'success' in result
    assert 'session_name' in result or 'error' in result

def test_get_session_name_from_guid():
    """Test session name generation from GUID."""
    from session_initializer import SessionInitializer

    guid = 'abc123def456'
    session_name = SessionInitializer.get_session_name(guid)

    assert isinstance(session_name, str)
    assert guid in session_name
    assert 'tmux_builder' in session_name

def test_get_session_path_from_guid():
    """Test session path generation from GUID."""
    from session_initializer import SessionInitializer
    from config import SESSIONS_DIR

    guid = 'abc123def456'
    session_path = SessionInitializer.get_session_path(guid)

    assert isinstance(session_path, Path)
    assert guid in str(session_path)
    assert str(SESSIONS_DIR) in str(session_path)
```

**Step 2: Run test to verify it fails**

```bash
cd backend
python3 -m pytest tests/test_session_initializer.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'session_initializer'"

**Step 3: Add health check to TmuxHelper**

Edit `backend/tmux_helper.py`, add method:

```python
@staticmethod
def verify_claude_responsive(session_name: str, timeout: int = 10) -> bool:
    """
    Verify that Claude CLI in the session is responsive.

    Sends a simple test message and checks for response marker.

    Args:
        session_name: Name of tmux session
        timeout: Timeout in seconds

    Returns:
        True if Claude is responsive, False otherwise
    """
    import tempfile
    import time

    try:
        # Create temporary marker file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.marker') as f:
            marker_file = f.name

        # Send test command to create marker
        test_command = f"touch {marker_file}"
        TmuxHelper.send_keys(session_name, test_command)

        # Wait for marker file to appear
        start_time = time.time()
        while time.time() - start_time < timeout:
            if Path(marker_file).exists():
                # Clean up and return success
                Path(marker_file).unlink()
                logger.debug(f"Session {session_name} is responsive")
                return True
            time.sleep(0.5)

        # Timeout - not responsive
        logger.warning(f"Session {session_name} not responsive after {timeout}s")
        return False

    except Exception as e:
        logger.error(f"Error checking session responsiveness: {e}")
        return False
```

**Step 4: Implement SessionInitializer**

Create `backend/session_initializer.py`:

```python
"""Manages Claude CLI session initialization with health checks."""

import logging
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json

from config import SESSIONS_DIR, TMUX_SESSION_PREFIX
from tmux_helper import TmuxHelper
from prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class SessionInitializer:
    """Handles initialization of Claude CLI sessions with health checks."""

    # Session reuse settings
    MAX_SESSION_AGE_DAYS = 5
    HEALTH_CHECK_TIMEOUT = 10

    def __init__(self):
        """Initialize SessionInitializer."""
        self.prompt_manager = PromptManager()
        logger.info("SessionInitializer ready")

    @staticmethod
    def get_session_name(guid: str) -> str:
        """
        Generate tmux session name from GUID.

        Args:
            guid: User GUID

        Returns:
            Session name string
        """
        return f"{TMUX_SESSION_PREFIX}_{guid}"

    @staticmethod
    def get_session_path(guid: str) -> Path:
        """
        Get session directory path for GUID.

        Args:
            guid: User GUID

        Returns:
            Path to session directory
        """
        # Structure: SESSIONS_DIR/active/<guid>/
        session_path = SESSIONS_DIR / "active" / guid
        session_path.mkdir(parents=True, exist_ok=True)
        return session_path

    def initialize_session(
        self,
        guid: str,
        email: str,
        phone: str,
        user_request: str
    ) -> Dict[str, Any]:
        """
        Initialize Claude CLI session for user.

        Checks if session already exists and is healthy before creating new one.

        Args:
            guid: User GUID
            email: User email
            phone: User phone
            user_request: User's build request

        Returns:
            Dictionary with success status and session info
        """
        try:
            logger.info(f"=== INITIALIZING SESSION FOR GUID: {guid} ===")

            session_name = self.get_session_name(guid)
            session_path = self.get_session_path(guid)

            logger.info(f"Session name: {session_name}")
            logger.info(f"Session path: {session_path}")

            # Ensure healthy session (reuse if possible, create if needed)
            session_created = self._ensure_healthy_session(
                session_name, session_path, guid
            )

            if not session_created:
                return {
                    'success': False,
                    'error': 'Failed to create or recover session'
                }

            # Render system prompt
            logger.info("Rendering autonomous agent system prompt...")
            system_prompt = self.prompt_manager.render_system_prompt(
                'autonomous_agent',
                {
                    'guid': guid,
                    'email': email,
                    'phone': phone,
                    'user_request': user_request,
                    'session_path': str(session_path),
                    'aws_profile': 'sunware'
                }
            )

            # Write system prompt to file
            system_prompt_file = session_path / "system_prompt.txt"
            system_prompt_file.write_text(system_prompt)
            logger.info(f"✓ System prompt written to {system_prompt_file}")

            # Initialize status.json
            status_file = session_path / "status.json"
            initial_status = {
                'status': 'initializing',
                'phase': 0,
                'progress': 5,
                'message': 'Session initialized, loading instructions',
                'guid': guid,
                'email': email,
                'user_request': user_request,
                'created_at': datetime.utcnow().isoformat() + 'Z'
            }
            status_file.write_text(json.dumps(initial_status, indent=2))
            logger.info(f"✓ Initial status written to {status_file}")

            # Send system prompt to Claude
            logger.info("Sending system prompt to Claude CLI...")
            TmuxHelper.send_keys(session_name, f"cat {system_prompt_file}")
            time.sleep(1)
            TmuxHelper.send_keys(session_name, "")  # Press enter

            logger.info("✓ Session initialization complete")

            return {
                'success': True,
                'session_name': session_name,
                'session_path': str(session_path),
                'guid': guid
            }

        except Exception as e:
            logger.exception(f"Session initialization failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _ensure_healthy_session(
        self,
        session_name: str,
        session_path: Path,
        guid: str
    ) -> bool:
        """
        Ensure session exists and is healthy, or create new one.

        Strategy:
        1. Check if session exists
        2. If exists, verify it's responsive
        3. If responsive and < 5 days old, reuse it
        4. Otherwise, kill and recreate

        Args:
            session_name: TMUX session name
            session_path: Path to session directory
            guid: User GUID

        Returns:
            True if healthy session ready, False otherwise
        """
        try:
            # Check if session exists
            if TmuxHelper.session_exists(session_name):
                logger.info(f"Session {session_name} already exists, checking health...")

                # Verify responsiveness
                is_responsive = TmuxHelper.verify_claude_responsive(
                    session_name,
                    timeout=self.HEALTH_CHECK_TIMEOUT
                )

                if is_responsive:
                    # Check age
                    session_age_days = self._get_session_age_days(guid)

                    if session_age_days is not None and session_age_days < self.MAX_SESSION_AGE_DAYS:
                        logger.info(
                            f"✓ Session is healthy and {session_age_days:.1f} days old, reusing"
                        )
                        return True
                    else:
                        logger.info(
                            f"Session is {session_age_days} days old (max: {self.MAX_SESSION_AGE_DAYS}), recreating"
                        )

                # Not responsive or too old - kill it
                logger.info("Session not healthy, killing and recreating...")
                TmuxHelper.kill_session(session_name)

            # Create new session
            logger.info(f"Creating new tmux session: {session_name}")
            success = TmuxHelper.create_session(session_name, str(session_path))

            if success:
                logger.info("✓ Session created successfully")
                return True
            else:
                logger.error("✗ Failed to create session")
                return False

        except Exception as e:
            logger.exception(f"Error ensuring healthy session: {e}")
            return False

    def _get_session_age_days(self, guid: str) -> Optional[float]:
        """
        Get age of session in days from status.json.

        Args:
            guid: User GUID

        Returns:
            Age in days, or None if unable to determine
        """
        try:
            session_path = self.get_session_path(guid)
            status_file = session_path / "status.json"

            if not status_file.exists():
                return None

            status = json.loads(status_file.read_text())
            created_at_str = status.get('created_at')

            if not created_at_str:
                return None

            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            age = datetime.utcnow() - created_at.replace(tzinfo=None)

            return age.total_seconds() / 86400  # Convert to days

        except Exception as e:
            logger.warning(f"Unable to determine session age: {e}")
            return None
```

**Step 5: Run tests to verify they pass**

```bash
cd backend
python3 -m pytest tests/test_session_initializer.py -v
```

Expected: Most tests PASS (integration tests may need tmux installed)

**Step 6: Commit**

```bash
git add backend/session_initializer.py backend/tests/test_session_initializer.py backend/tmux_helper.py
git commit -m "feat: implement session initializer with health checks

- Create SessionInitializer for managing Claude CLI sessions
- Add health check mechanism to TmuxHelper
- Implement session reuse strategy (responsive + < 5 days)
- Always recreate dead/old sessions
- Render and inject system prompts
- Initialize status.json tracking
- Add tests for session initialization

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Implement /api/register Endpoint

**Goal:** Create registration endpoint that generates GUID and starts background initialization

**Files:**
- Modify: `backend/main.py`
- Create: `backend/guid_generator.py`
- Create: `backend/tests/test_guid_generator.py`
- Create: `backend/tests/test_api_endpoints.py`

**Step 1: Write test for GUID generation**

Create `backend/tests/test_guid_generator.py`:

```python
import pytest
from guid_generator import generate_guid

def test_guid_generation_is_deterministic():
    """Test that same email+phone always generates same GUID."""
    email = "test@example.com"
    phone = "+15551234567"

    guid1 = generate_guid(email, phone)
    guid2 = generate_guid(email, phone)

    assert guid1 == guid2

def test_guid_generation_different_inputs():
    """Test that different inputs generate different GUIDs."""
    guid1 = generate_guid("user1@example.com", "+15551111111")
    guid2 = generate_guid("user2@example.com", "+15552222222")

    assert guid1 != guid2

def test_guid_format():
    """Test GUID format (should be hex string)."""
    guid = generate_guid("test@example.com", "+15551234567")

    assert isinstance(guid, str)
    assert len(guid) == 64  # SHA256 produces 64 hex characters
    assert all(c in '0123456789abcdef' for c in guid)

def test_guid_case_insensitive_email():
    """Test that email case doesn't affect GUID."""
    guid1 = generate_guid("Test@Example.COM", "+15551234567")
    guid2 = generate_guid("test@example.com", "+15551234567")

    assert guid1 == guid2
```

**Step 2: Run test to verify it fails**

```bash
cd backend
python3 -m pytest tests/test_guid_generator.py -v
```

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement GUID generator**

Create `backend/guid_generator.py`:

```python
"""Generates deterministic GUIDs from user email and phone."""

import hashlib
import logging

logger = logging.getLogger(__name__)


def generate_guid(email: str, phone: str) -> str:
    """
    Generate deterministic GUID from email and phone.

    Uses SHA256 hash of normalized email:phone string.
    Same email+phone always produces same GUID.

    Args:
        email: User email address
        phone: User phone number

    Returns:
        64-character hexadecimal GUID string
    """
    # Normalize inputs
    email_normalized = email.lower().strip()
    phone_normalized = phone.strip()

    # Create combined string
    combined = f"{email_normalized}:{phone_normalized}"

    # Generate SHA256 hash
    guid = hashlib.sha256(combined.encode('utf-8')).hexdigest()

    logger.debug(f"Generated GUID for {email_normalized}: {guid[:16]}...")

    return guid
```

**Step 4: Run test to verify it passes**

```bash
cd backend
python3 -m pytest tests/test_guid_generator.py -v
```

Expected: PASS

**Step 5: Write test for /api/register endpoint**

Create `backend/tests/test_api_endpoints.py`:

```python
import pytest
from fastapi.testclient import TestClient

# Import will be added after we modify main.py
# from main import app

def test_register_endpoint_structure():
    """Test /api/register endpoint returns proper structure."""
    # This test will be implemented after main.py is updated
    pass
```

**Step 6: Modify main.py to add /api/register endpoint**

Edit `backend/main.py`, add after imports:

```python
from background_worker import BackgroundWorker
from guid_generator import generate_guid
from pydantic import BaseModel
import os

# Initialize background worker
background_worker = BackgroundWorker()

class RegistrationRequest(BaseModel):
    """Registration request model."""
    email: str
    phone: str
    initial_request: str
```

Add endpoint before `if __name__ == "__main__":`:

```python
@app.post("/api/register")
async def register_user(request: RegistrationRequest):
    """
    Register new user and start session initialization.

    Returns immediately with GUID URL. Session initializes in background.
    """
    try:
        logger.info("=== REGISTRATION REQUEST ===")
        logger.info(f"Email: {request.email}")
        logger.info(f"Phone: {request.phone}")
        logger.info(f"Request: {request.initial_request[:100]}...")

        # Generate deterministic GUID
        guid = generate_guid(request.email, request.phone)
        logger.info(f"Generated GUID: {guid}")

        # Start background initialization
        background_worker.start_initialization(
            guid=guid,
            email=request.email,
            phone=request.phone,
            user_request=request.initial_request
        )

        # Build response
        base_url = os.getenv('BASE_URL', f'http://{API_HOST}:{API_PORT}')
        session_url = f"{base_url}/session/{guid}"
        status_url = f"{base_url}/api/session/{guid}/status"

        # Calculate expiry (5 days from now)
        from datetime import datetime, timedelta
        expires_at = (datetime.utcnow() + timedelta(days=5)).isoformat() + 'Z'

        response = {
            "success": True,
            "guid": guid,
            "url": session_url,
            "status_check_url": status_url,
            "message": "Session initialization started",
            "expires_at": expires_at,
            "created_at": datetime.utcnow().isoformat() + 'Z'
        }

        logger.info(f"✓ Registration successful: {session_url}")
        return response

    except Exception as e:
        logger.exception(f"Registration failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
```

**Step 7: Test endpoint manually**

```bash
cd backend
# Start server in background
python3 main.py &
sleep 3

# Test registration
curl -X POST http://localhost:8000/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "phone": "+15551234567",
    "initial_request": "Build a simple todo app"
  }'

# Stop server
pkill -f "python3 main.py"
```

Expected: JSON response with guid, url, status_check_url

**Step 8: Commit**

```bash
git add backend/guid_generator.py backend/tests/test_guid_generator.py backend/tests/test_api_endpoints.py backend/main.py
git commit -m "feat: implement /api/register endpoint

- Create guid_generator for deterministic GUID generation
- Add RegistrationRequest pydantic model
- Implement /api/register POST endpoint
- Integrate BackgroundWorker for async initialization
- Return immediate response with GUID URL
- Add tests for GUID generation
- Calculate 5-day expiry

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Implement /api/session/{guid}/status Endpoint

**Goal:** Create status polling endpoint that returns initialization progress and deployment info

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/tests/test_api_endpoints.py`

**Step 1: Write test for status endpoint**

Add to `backend/tests/test_api_endpoints.py`:

```python
def test_status_endpoint_returns_job_status():
    """Test /api/session/{guid}/status returns current job status."""
    # This will be implemented after endpoint is added
    # Should return status, progress, message, deployment_url (if ready)
    pass

def test_status_endpoint_unknown_guid():
    """Test status endpoint with unknown GUID returns not found."""
    pass
```

**Step 2: Add status endpoint to main.py**

Add to `backend/main.py` after `/api/register`:

```python
@app.get("/api/session/{guid}/status")
async def get_session_status(guid: str):
    """
    Get current status of session initialization/build.

    Returns job status from background worker plus any status.json updates.
    """
    try:
        logger.info(f"=== STATUS CHECK: {guid} ===")

        # Get job status from background worker
        job_status = background_worker.get_job_status(guid)

        if job_status is None:
            logger.warning(f"Unknown GUID: {guid}")
            return {
                "success": False,
                "error": "Session not found",
                "guid": guid
            }

        # Try to read status.json if session is ready
        if job_status['status'] == 'ready':
            try:
                from session_initializer import SessionInitializer
                session_path = SessionInitializer.get_session_path(guid)
                status_file = session_path / "status.json"

                if status_file.exists():
                    import json
                    detailed_status = json.loads(status_file.read_text())

                    # Merge job status with detailed status
                    response = {
                        "success": True,
                        "guid": guid,
                        **job_status,
                        **detailed_status
                    }

                    logger.info(f"Detailed status: {detailed_status.get('status')} - {detailed_status.get('message')}")
                    return response
            except Exception as e:
                logger.warning(f"Could not read status.json: {e}")

        # Return basic job status
        response = {
            "success": True,
            "guid": guid,
            **job_status
        }

        logger.info(f"Status: {job_status['status']} ({job_status.get('progress', 0)}%)")
        return response

    except Exception as e:
        logger.exception(f"Status check failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "guid": guid
        }
```

**Step 3: Test manually**

```bash
cd backend
python3 main.py &
sleep 3

# Register first
RESPONSE=$(curl -s -X POST http://localhost:8000/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "phone": "+15551234567",
    "initial_request": "Build a test app"
  }')

GUID=$(echo $RESPONSE | grep -o '"guid":"[^"]*"' | cut -d'"' -f4)

# Check status
curl http://localhost:8000/api/session/$GUID/status

# Wait and check again
sleep 5
curl http://localhost:8000/api/session/$GUID/status

pkill -f "python3 main.py"
```

Expected: First call shows "pending" or "initializing", second call shows progress

**Step 4: Run all tests**

```bash
cd backend
python3 -m pytest tests/ -v --tb=short
```

Expected: All tests pass

**Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_api_endpoints.py
git commit -m "feat: implement /api/session/{guid}/status endpoint

- Create GET endpoint for status polling
- Return job status from background worker
- Merge with detailed status.json if available
- Handle unknown GUIDs gracefully
- Add logging for status checks
- Add tests for status endpoint

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 8-12: Summary

The remaining tasks follow the same pattern:

**Task 8: Refinement Endpoints** - Create `/api/session/{guid}/refine` for post-deployment changes
**Task 9: Additional Templates** - Write `refinement_mode.txt` and `debug_mode.txt` prompts
**Task 10: Error Recovery** - Implement retry logic and error handling throughout
**Task 11: Integration Tests** - End-to-end tests of full workflow
**Task 12: Frontend Updates** - Update UI to use new `/api/register` endpoint

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-01-25-autonomous-build-agent.md`.**

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
