# Quick Start Guide

Get Tmux Builder running in 5 minutes!

## Prerequisites Check

```bash
# Check Python
python3 --version  # Need 3.11+

# Check Node
node --version     # Need 16+

# Check tmux
tmux -V           # Need tmux installed

# Check Claude CLI
claude --version  # Need Claude CLI configured

# Check AWS CLI (optional)
aws --version     # For cloud deployments
```

## Setup & Run

### 1. Backend (Terminal 1)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

**Expected output:**
```
 * Running on http://0.0.0.0:5001
```

### 2. Frontend (Terminal 2)

```bash
cd frontend
npm install
npm start
```

**Expected output:**
```
Compiled successfully!
Local: http://localhost:3000
```

### 3. Test the API

```bash
# Create a user and start deployment
curl -X POST http://localhost:5001/api/create-user \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "phone": "+1234567890",
    "host_provider": "aws",
    "site_type": "static",
    "requirements": "Build a simple landing page"
  }'
```

**Expected response:**
```json
{
  "execution_id": "abc123_sess_20260124",
  "user_id": "abc123",
  "session_id": "sess_20260124",
  "is_new_user": true
}
```

### 4. Check Status

```bash
curl http://localhost:5001/api/status/<execution_id>
```

## Run Tests

```bash
cd backend
python -m pytest -v
```

**Expected:** 134 tests passing

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/create-user` | POST | Create user and start deployment |
| `/api/status/<id>` | GET | Get pipeline execution status |
| `/api/chat/<id>` | POST | Send message to Claude session |
| `/api/chat/<id>/history` | GET | Get session output history |
| `/api/redeploy/<id>` | POST | Trigger redeployment |

## Pipeline Steps

When you create a user, the system executes a 9-step pipeline:

1. **create_user** - Create GUID folder & registry
2. **create_session** - Initialize session structure
3. **gather_requirements** - Parse requirements
4. **create_plan** - Claude creates plan
5. **generate_code** - Claude writes code
6. **deploy** - Deploy to AWS/Azure
7. **health_check** - Verify site is live
8. **screenshot** - Capture visual snapshot
9. **e2e_tests** - Run E2E tests

## Troubleshooting

### "Connection refused on port 5001"
- Ensure backend is running: `python app.py`
- Check if another process is using port 5001

### "Tests failing"
- Ensure all dependencies installed: `pip install -r requirements.txt`
- Run from backend directory: `cd backend && python -m pytest`

### AWS Deployment Errors
- Verify AWS CLI configured: `aws configure list`
- Check profile exists: `aws configure list-profiles | grep sunwaretech`

## Project Structure

```
tmux-builder/
├── backend/
│   ├── app.py              # Flask API (port 5001)
│   ├── job_runner.py       # Pipeline orchestrator
│   ├── execution_tracker.py
│   ├── aws_deployer.py     # S3 + CloudFront
│   ├── aws_ec2_deployer.py # EC2 dynamic
│   ├── azure_deployer.py   # Blob + CDN
│   ├── azure_vm_deployer.py
│   └── tests/              # 134 tests
├── frontend/               # React app (port 3000)
├── users/                  # User GUID folders
├── executions/             # Pipeline status
└── .claude/
    ├── agents/             # Deployment agents
    └── skills/             # Cloud skills
```

## Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- Read [PROJECT_GUIDELINES.md](PROJECT_GUIDELINES.md) for best practices
- Check [SmartBuild Analysis](SMARTBUILD_ARCHITECTURE_ANALYSIS.md) for pattern details

## Stop the Application

1. **Backend**: Press `Ctrl+C` in Terminal 1
2. **Frontend**: Press `Ctrl+C` in Terminal 2
3. **Clean up tmux**: `tmux kill-server` (kills all sessions)
