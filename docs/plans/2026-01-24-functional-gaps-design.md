# Functional Gaps Design Document

**Date**: 2026-01-24
**Status**: Ready for Implementation
**Scope**: Complete missing functionality for multi-user cloud deployment pipeline

---

## Overview

This design addresses the functional gaps identified in the PR review, transforming tmux-builder from a partially-implemented system to a fully functional multi-user deployment pipeline.

**Approach**: Extend existing queue system (`job_queue_manager.py` + `job_queue_monitor.py`) rather than creating new orchestration layer.

---

## 1. Job Runner (`backend/job_runner.py`)

The core orchestrator that executes the 9-step pipeline.

### Pipeline Steps

| Step | Name | Description |
|------|------|-------------|
| 1 | create_user | Create GUID folder & registry entry |
| 2 | create_session | Initialize session folder structure |
| 3 | gather_requirements | Parse & structure requirements from POST body |
| 4 | create_plan | Claude creates implementation plan |
| 5 | generate_code | Claude writes code to source/ |
| 6 | deploy | Deploy to AWS/Azure |
| 7 | health_check | Verify URL returns 200 OK |
| 8 | screenshot | Capture visual snapshot |
| 9 | e2e_tests | Generate & run E2E tests |

### Implementation

```python
class JobRunner:
    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        self.tracker = ExecutionTracker()
        self.tmux = TmuxHelper()
        # Load execution metadata
        execution = self.tracker.get_execution(execution_id)
        self.user_id = execution['user_id']
        self.session_id = execution['session_id']
        self.host_provider = execution['host_provider']
        self.site_type = execution['site_type']
        self.requirements = execution.get('requirements', '')
        self.session_path = f"users/{self.user_id}/sessions/{self.session_id}"
        self.deployed_url = None

    def run_pipeline(self) -> dict:
        """Execute steps 3-9 (steps 1-2 already done by create-user)"""
        steps = [
            (3, "gather_requirements", self._gather_requirements),
            (4, "create_plan", self._create_plan),
            (5, "generate_code", self._generate_code),
            (6, "deploy", self._deploy),
            (7, "health_check", self._health_check),
            (8, "screenshot", self._screenshot),
            (9, "e2e_tests", self._run_e2e_tests),
        ]

        # Start tmux session first
        self._start_claude_session()

        for step_num, step_name, step_fn in steps:
            self.tracker.update_step(self.execution_id, step_num, step_name, "running")
            try:
                result = step_fn()
                self.tracker.log(self.execution_id, "INFO", f"{step_name} completed", step=step_num)
            except Exception as e:
                self.tracker.set_error(self.execution_id, str(e), step=step_num)
                return {"status": "failed", "step": step_name, "error": str(e)}

        self.tracker.set_result(self.execution_id, {
            "status": "completed",
            "url": self.deployed_url
        })
        return {"status": "completed", "url": self.deployed_url}
```

### Skill Invocation Flow

Skills are invoked **inside the Claude tmux session**, not by Python:

| Step | Python Does | Claude Does (in tmux) |
|------|-------------|----------------------|
| 3 | Save requirements to file | - |
| 4 | Send kickoff prompt | Reads `PROJECT_GUIDELINES.md` → Uses `project-inception` skill |
| 5 | Monitor for plan completion | Creates plan → Uses `plan-validation` skill |
| 6 | Monitor for code completion | Writes code to `source/` |
| 7-8 | Call Python deployers/checkers | - |
| 9 | Send E2E test prompt | Uses `integration-verification` skill → Runs tests |

### Kickoff Prompt (Step 4)

```
You are working in session {session_id}.

FIRST: Read docs/PROJECT_GUIDELINES.md - these are mandatory instructions.

THEN: Use the project-inception skill to process these requirements:
---
{requirements_text}
---

Your outputs:
- Plan: Write to output/plan.md
- Code: Write to source/
- Signal completion: Write "PHASE_COMPLETE: {phase_name}" to output/status.txt
```

### Phase Completion Signals

Python monitors `output/status.txt` for:
- `PHASE_COMPLETE: planning` → Move to step 5
- `PHASE_COMPLETE: coding` → Move to step 6 (deploy)
- `PHASE_COMPLETE: verification` → Pipeline done

---

## 2. Tmux Integration

### Session Naming Convention

```
tmux session name: exec_{execution_id}
Example: exec_a1b2c3d4_sess20260124143022
```

### TmuxHelper Usage

```python
def _start_claude_session(self):
    """Start tmux with Claude CLI in session directory"""
    session_path = f"users/{self.user_id}/sessions/{self.session_id}"

    self.tmux.create_session(
        session_name=f"exec_{self.execution_id}",
        working_dir=session_path,
        start_claude=True
    )

    # Wait for Claude to initialize (SmartBuild pattern)
    self.tmux.perform_health_probe(f"exec_{self.execution_id}")

def _send_prompt_and_wait(self, prompt: str, completion_signal: str) -> str:
    """Send prompt to Claude, wait for completion signal"""
    # Write prompt to file (SmartBuild pattern)
    prompt_file = f"{self.session_path}/prompts/current.txt"
    write_file(prompt_file, prompt)

    # Send instruction to Claude
    self.tmux.send_instruction(
        session_name=f"exec_{self.execution_id}",
        instruction=f"Read and execute the prompt in prompts/current.txt"
    )

    # Poll for completion signal
    return self._wait_for_signal(completion_signal, timeout=300)

def _wait_for_signal(self, signal: str, timeout: int) -> str:
    """Poll output/status.txt for completion signal"""
    status_file = f"{self.session_path}/output/status.txt"
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(status_file):
            content = read_file(status_file)
            if signal in content:
                return content
        time.sleep(5)
    raise TimeoutError(f"Timeout waiting for {signal}")
```

---

## 3. API Endpoints

### POST `/api/create-user` (Modified)

Add `requirements` field to request body:

```json
{
  "email": "user@example.com",
  "phone": "+1234567890",
  "host_provider": "aws",
  "site_type": "static",
  "requirements": "Build a portfolio website with dark theme, contact form, and projects gallery"
}
```

```python
@app.route('/api/create-user', methods=['POST'])
def create_user():
    data = request.json
    email = data.get('email')
    phone = data.get('phone')
    host_provider = data.get('host_provider', 'aws')
    site_type = data.get('site_type', 'static')
    requirements = data.get('requirements', '')  # NEW FIELD

    # ... existing user/session creation ...

    # Store requirements in execution metadata
    tracker.update_metadata(execution_id, {"requirements": requirements})

    # Queue the job for background execution
    job_queue.enqueue(execution_id)

    return jsonify({...})
```

### POST `/api/chat/<execution_id>` (New)

```python
@app.route('/api/chat/<execution_id>', methods=['POST'])
def chat(execution_id):
    """Send a message to the Claude session"""
    data = request.json
    message = data.get('message', '')

    execution = tracker.get_execution(execution_id)
    if not execution:
        return jsonify({"error": "Execution not found"}), 404
    if execution['status'] not in ['running', 'waiting_input']:
        return jsonify({"error": f"Cannot chat - status is {execution['status']}"}), 400

    tmux = TmuxHelper()
    tmux.send_instruction(f"exec_{execution_id}", message)

    return jsonify({"status": "sent", "execution_id": execution_id})
```

### POST `/api/redeploy/<execution_id>` (New)

```python
@app.route('/api/redeploy/<execution_id>', methods=['POST'])
def redeploy(execution_id):
    """Trigger redeployment of an existing session"""
    execution = tracker.get_execution(execution_id)
    if not execution:
        return jsonify({"error": "Execution not found"}), 404

    tracker.update_status(execution_id, "running", step=6)
    job_queue.enqueue(execution_id, start_step=6)

    return jsonify({"status": "redeploying", "execution_id": execution_id})
```

### GET `/api/chat/<execution_id>/history` (New)

```python
@app.route('/api/chat/<execution_id>/history', methods=['GET'])
def chat_history(execution_id):
    """Get recent tmux pane output for display"""
    tmux = TmuxHelper()
    output = tmux.capture_pane_output(f"exec_{execution_id}", lines=100)
    return jsonify({"output": output, "execution_id": execution_id})
```

---

## 4. Missing Agents

### Agents to Create

| Agent | Path | Purpose |
|-------|------|---------|
| aws-elastic-beanstalk | `deployers/aws-elastic-beanstalk.md` | Dynamic site deployment to EB |
| azure-blob-static | `deployers/azure-blob-static.md` | Static site to Azure Blob + CDN |
| azure-app-service | `deployers/azure-app-service.md` | Dynamic site to Azure App Service |
| cache-invalidator | `utilities/cache-invalidator.md` | CloudFront/Azure CDN cache purge |
| log-analyzer | `utilities/log-analyzer.md` | Parse deployment logs for errors |

### Agent Template

```markdown
---
name: {agent-name}
description: {one-line description}
---

# {Agent Name}

## Purpose
{What this agent does}

## Prerequisites
- {Required tools/access}

## Process

### Step 1: {First step}
{Instructions}

### Step 2: {Second step}
{Instructions}

## Resource Naming
Pattern: `tmux-{guid_prefix}-{session_short}`

## Required Tags
- Project: tmux-builder
- UserGUID: {user_id}
- SessionID: {session_id}
- ExecutionID: {execution_id}
- SiteType: static|dynamic
- CostCenter: user-sites
- CreatedBy: tmux-builder-automation

## Error Handling
{What to do when things fail}

## Completion
Signal completion by writing to `output/status.txt`:
PHASE_COMPLETE: {phase_name}
```

---

## 5. Missing Skills

### AWS Skills

| Skill | Path | Purpose |
|-------|------|---------|
| eb-deploy | `aws/eb-deploy.md` | Deploy to Elastic Beanstalk |
| rds-configure | `aws/rds-configure.md` | Create/configure RDS database |
| elasticache-setup | `aws/elasticache-setup.md` | Redis/Memcached setup |
| ec2-launch | `aws/ec2-launch.md` | Launch EC2 instance |

### Azure Skills

| Skill | Path | Purpose |
|-------|------|---------|
| blob-upload | `azure/blob-upload.md` | Upload files to Blob Storage |
| cdn-create | `azure/cdn-create.md` | Create Azure CDN profile + endpoint |
| cdn-purge | `azure/cdn-purge.md` | Purge Azure CDN cache |
| app-service-deploy | `azure/app-service-deploy.md` | Deploy to App Service |
| sql-configure | `azure/sql-configure.md` | Azure SQL Database setup |
| redis-setup | `azure/redis-setup.md` | Azure Cache for Redis |

### Testing Skills

| Skill | Path | Purpose |
|-------|------|---------|
| health-check | `testing/health-check.md` | HTTP health verification |
| screenshot-capture | `testing/screenshot-capture.md` | Visual verification |
| e2e-generate | `testing/e2e-generate.md` | Generate E2E test suite |
| e2e-run | `testing/e2e-run.md` | Execute E2E tests |

### Skill Template

```markdown
---
name: {skill-name}
description: {one-line description}
---

# {Skill Name}

## When to Use
{Trigger conditions}

## Prerequisites
- {Required CLI tools, credentials}

## Steps

### 1. {First step}
```bash
{command}
```

### 2. {Second step}
```bash
{command}
```

## Verification
{How to confirm success}

## Common Errors
| Error | Cause | Fix |
|-------|-------|-----|
| {error} | {cause} | {fix} |
```

---

## 6. E2E Test Runner (`backend/e2e_runner.py`)

### Two-Phase Approach

| Phase | Who Does It | What Happens |
|-------|-------------|--------------|
| Generate | Claude (in tmux) | Creates test suite based on deployed site |
| Execute | Python | Runs Playwright tests, collects results |

### Implementation

```python
class E2ERunner:
    def __init__(self, session_path: str, deployed_url: str):
        self.session_path = session_path
        self.deployed_url = deployed_url
        self.test_dir = f"{session_path}/deployment/tests"

    def generate_tests(self, tmux: TmuxHelper, execution_id: str):
        """Ask Claude to generate E2E tests"""
        prompt = f"""
        Generate Playwright E2E tests for the deployed site at: {self.deployed_url}

        Use the testing/e2e-generate skill.

        Write tests to: deployment/tests/e2e_test.py

        Test these scenarios:
        1. Homepage loads successfully
        2. All navigation links work
        3. Forms submit correctly (if any)
        4. Images load without errors
        5. Mobile responsive layout works

        Signal completion: Write "PHASE_COMPLETE: test_generation" to output/status.txt
        """
        tmux.send_instruction(f"exec_{execution_id}", prompt)

    def run_tests(self) -> dict:
        """Execute generated tests with Playwright"""
        test_file = f"{self.test_dir}/e2e_test.py"

        if not os.path.exists(test_file):
            return {"status": "skipped", "reason": "No tests generated"}

        result = subprocess.run(
            ["python", "-m", "pytest", test_file,
             "--tb=short", "-v",
             f"--html={self.test_dir}/report.html"],
            capture_output=True,
            text=True,
            timeout=120
        )

        return {
            "status": "passed" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "report_path": f"{self.test_dir}/report.html"
        }

    def save_results(self, results: dict):
        """Save test results to deployment/tests/results.json"""
        results["timestamp"] = datetime.utcnow().isoformat() + "Z"
        results["url_tested"] = self.deployed_url

        with open(f"{self.test_dir}/results.json", "w") as f:
            json.dump(results, f, indent=2)
```

---

## 7. Status Updates

### Execution Status Values

```python
EXECUTION_STATUSES = [
    "pending",        # Created, waiting in queue
    "running",        # Pipeline actively executing
    "waiting_input",  # Paused, waiting for user chat input
    "completed",      # All steps finished successfully
    "failed",         # Step failed, see error details
    "cancelled",      # User cancelled execution
]
```

### ExecutionTracker Enhancements

```python
class ExecutionTracker:
    def update_step(self, execution_id: str, step: int, step_name: str, status: str = "running"):
        """Update current step with name"""
        execution = self.get_execution(execution_id)
        execution["current_step"] = step
        execution["current_step_name"] = step_name
        execution["status"] = status
        execution["updated_at"] = datetime.utcnow().isoformat() + "Z"
        self._save(execution_id, execution)

    def set_deployed_url(self, execution_id: str, url: str):
        """Store deployed URL after successful deployment"""
        execution = self.get_execution(execution_id)
        execution["deployed_url"] = url
        execution["last_deployed"] = datetime.utcnow().isoformat() + "Z"
        self._save(execution_id, execution)

    def get_progress(self, execution_id: str) -> dict:
        """Return progress summary for frontend"""
        execution = self.get_execution(execution_id)
        return {
            "execution_id": execution_id,
            "status": execution["status"],
            "current_step": execution.get("current_step", 0),
            "current_step_name": execution.get("current_step_name", ""),
            "total_steps": 9,
            "percent_complete": int((execution.get("current_step", 0) / 9) * 100),
            "deployed_url": execution.get("deployed_url"),
            "error": execution.get("error"),
        }
```

### Status Flow

```
POST /api/create-user
    │
    ├─► pending (queued)
    │
    ▼
Job picked up by queue monitor
    │
    ├─► running (step 3: gather_requirements)
    ├─► running (step 4: create_plan)
    ├─► running (step 5: generate_code)
    ├─► running (step 6: deploy)
    ├─► running (step 7: health_check)
    ├─► running (step 8: screenshot)
    ├─► running (step 9: e2e_tests)
    │
    ▼
completed ──or── failed
```

---

## 8. Dynamic Deployers

### AWS EC2 Deployer (`backend/aws_ec2_deployer.py`)

```python
class AWSEC2Deployer:
    def __init__(self, user_id: str, session_id: str):
        self.naming = CloudConfig(user_id, session_id)
        self.ec2 = boto3.client('ec2')
        self.ssm = boto3.client('ssm')

    def deploy(self, source_path: str, site_type: str) -> dict:
        """Deploy dynamic site to EC2"""

        # 1. Launch EC2 instance (or reuse existing)
        instance_id = self._get_or_create_instance()

        # 2. Wait for instance ready
        self._wait_for_instance(instance_id)

        # 3. Upload code via SSM + S3
        self._upload_code(instance_id, source_path)

        # 4. Install dependencies & start app
        self._run_setup_commands(instance_id, site_type)

        # 5. Get public URL
        public_ip = self._get_public_ip(instance_id)

        return {
            "url": f"http://{public_ip}",
            "instance_id": instance_id,
            "provider": "aws",
            "type": "ec2"
        }

    def _get_or_create_instance(self) -> str:
        """Launch t3.micro with Amazon Linux 2"""
        response = self.ec2.run_instances(
            ImageId='ami-0c02fb55956c7d316',
            InstanceType='t3.micro',
            MinCount=1, MaxCount=1,
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': self.naming.get_tags()
            }],
            UserData=self._get_user_data_script(),
            IamInstanceProfile={'Name': 'tmux-builder-ec2-role'}
        )
        return response['Instances'][0]['InstanceId']
```

### Azure VM Deployer (`backend/azure_vm_deployer.py`)

```python
class AzureVMDeployer:
    def __init__(self, user_id: str, session_id: str):
        self.naming = CloudConfig(user_id, session_id)
        self.compute_client = ComputeManagementClient(credential, subscription_id)
        self.network_client = NetworkManagementClient(credential, subscription_id)

    def deploy(self, source_path: str, site_type: str) -> dict:
        """Deploy dynamic site to Azure VM"""

        # 1. Create resource group (if not exists)
        rg_name = self._ensure_resource_group()

        # 2. Create network resources
        nic_id, public_ip = self._create_network_resources(rg_name)

        # 3. Create VM
        vm_name = self.naming.get_resource_name("vm")
        self._create_vm(rg_name, vm_name, nic_id)

        # 4. Upload code and run setup
        self._deploy_code(rg_name, vm_name, source_path, site_type)

        return {
            "url": f"http://{public_ip}",
            "vm_name": vm_name,
            "resource_group": rg_name,
            "provider": "azure",
            "type": "vm"
        }
```

### Site Type Detection

| Site Type | Detected By | Setup Commands |
|-----------|-------------|----------------|
| node | `package.json` exists | `npm install && npm start` |
| python | `requirements.txt` exists | `pip install -r requirements.txt && python app.py` |
| static | Neither exists | Serve with nginx |

### JobRunner Integration

```python
def _deploy(self):
    if self.host_provider == "aws":
        if self.site_type == "static":
            deployer = AWSDeployer(self.user_id, self.session_id)
        else:
            deployer = AWSEC2Deployer(self.user_id, self.session_id)
    else:  # azure
        if self.site_type == "static":
            deployer = AzureDeployer(self.user_id, self.session_id)
        else:
            deployer = AzureVMDeployer(self.user_id, self.session_id)

    result = deployer.deploy(f"{self.session_path}/source", self.site_type)
    self.deployed_url = result["url"]
    self.tracker.set_deployed_url(self.execution_id, result["url"])
    return result
```

---

## Implementation Summary

### New Files (28 total)

**Python Modules (6):**
- `backend/job_runner.py`
- `backend/e2e_runner.py`
- `backend/aws_ec2_deployer.py`
- `backend/azure_vm_deployer.py`

**Modified Python Files (3):**
- `backend/app.py` - Add requirements field + new endpoints
- `backend/execution_tracker.py` - Add step tracking methods
- `backend/job_queue_monitor.py` - Wire up JobRunner

**Agents (5):**
- `.claude/agents/deployers/aws-elastic-beanstalk.md`
- `.claude/agents/deployers/azure-blob-static.md`
- `.claude/agents/deployers/azure-app-service.md`
- `.claude/agents/utilities/cache-invalidator.md`
- `.claude/agents/utilities/log-analyzer.md`

**Skills (14):**
- `.claude/skills/aws/eb-deploy.md`
- `.claude/skills/aws/rds-configure.md`
- `.claude/skills/aws/elasticache-setup.md`
- `.claude/skills/aws/ec2-launch.md`
- `.claude/skills/azure/blob-upload.md`
- `.claude/skills/azure/cdn-create.md`
- `.claude/skills/azure/cdn-purge.md`
- `.claude/skills/azure/app-service-deploy.md`
- `.claude/skills/azure/sql-configure.md`
- `.claude/skills/azure/redis-setup.md`
- `.claude/skills/testing/health-check.md`
- `.claude/skills/testing/screenshot-capture.md`
- `.claude/skills/testing/e2e-generate.md`
- `.claude/skills/testing/e2e-run.md`

---

## Dependencies

### Python Packages (add to requirements.txt)
```
pytest-html>=4.0.0  # E2E test reports
```

### AWS IAM Requirements
- EC2 role: `tmux-builder-ec2-role` with SSM access
- Existing S3/CloudFront permissions

### Azure Requirements
- Service Principal with Contributor access
- Resource group creation permissions

---

## Testing Strategy

1. **Unit tests** for each new module
2. **Integration test** for full pipeline (mock cloud APIs)
3. **E2E test** with real AWS/Azure deployment (manual trigger)
