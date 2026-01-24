# Tmux Builder

A multi-user cloud deployment system that uses Claude AI through persistent tmux sessions, featuring the SmartBuild pattern for AI-driven workflows.

## Features

- **Multi-User Support**: GUID-based user isolation with individual session management
- **Cloud Deployment**: Deploy to AWS (S3, CloudFront, EC2) or Azure (Blob, CDN, VMs)
- **9-Step Pipeline**: Automated workflow from requirements to deployed site with E2E tests
- **SmartBuild Pattern**: File-based I/O for LLM-friendly operations
- **Real-time Chat**: Interact with Claude sessions during deployment

## Quick Links

- [Getting Started](docs/QUICKSTART.md)
- [Architecture Details](docs/ARCHITECTURE.md)
- [SmartBuild Pattern](docs/SMARTBUILD_ARCHITECTURE_ANALYSIS.md)
- [API Reference](#api-endpoints)

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   React UI  │────▶│  Flask API  │────▶│   JobRunner │
└─────────────┘     └─────────────┘     └─────────────┘
                           │                    │
                    ┌──────┴──────┐      ┌──────┴──────┐
                    │             │      │             │
              ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
              │  Users/   │ │Executions │ │   Tmux    │
              │ Sessions  │ │  Tracker  │ │  Claude   │
              └───────────┘ └───────────┘ └───────────┘
                                               │
                                    ┌──────────┴──────────┐
                                    │                     │
                              ┌─────▼─────┐        ┌──────▼─────┐
                              │    AWS    │        │   Azure    │
                              │ S3/EC2/CF │        │ Blob/VM/CDN│
                              └───────────┘        └────────────┘
```

### Tech Stack

- **Frontend**: React + Vite + Tailwind CSS
- **Backend**: Flask (Python 3.11+)
- **AI Engine**: Claude CLI in tmux sessions
- **Cloud**: AWS (boto3), Azure (azure-sdk)
- **Testing**: pytest, Playwright

## Project Structure

```
tmux-builder/
├── backend/
│   ├── app.py                 # Flask API server (port 5001)
│   ├── job_runner.py          # 9-step pipeline orchestrator
│   ├── execution_tracker.py   # Pipeline status tracking
│   ├── aws_deployer.py        # AWS S3+CloudFront static
│   ├── aws_ec2_deployer.py    # AWS EC2 dynamic
│   ├── azure_deployer.py      # Azure Blob+CDN static
│   ├── azure_vm_deployer.py   # Azure VM dynamic
│   ├── e2e_runner.py          # E2E test generation/execution
│   └── tests/                 # Test suite (134 tests)
├── frontend/
│   └── src/                   # React application
├── users/                     # User data (GUID folders)
├── executions/                # Pipeline execution status
├── .claude/
│   ├── agents/                # Agent definitions
│   │   ├── deployers/         # Deployment agents
│   │   ├── testers/           # Testing agents
│   │   └── utilities/         # Utility agents
│   └── skills/                # Skill definitions
│       ├── aws/               # AWS skills
│       ├── azure/             # Azure skills
│       ├── core/              # Core methodology skills
│       └── testing/           # Testing skills
└── docs/                      # Documentation
```

## Deployment Pipeline

The system executes a 9-step pipeline for each deployment:

| Step | Name | Description |
|------|------|-------------|
| 1 | create_user | Create GUID folder & registry entry |
| 2 | create_session | Initialize session folder structure |
| 3 | gather_requirements | Parse & structure requirements |
| 4 | create_plan | Claude creates implementation plan |
| 5 | generate_code | Claude writes code to source/ |
| 6 | deploy | Deploy to AWS/Azure |
| 7 | health_check | Verify URL returns 200 OK |
| 8 | screenshot | Capture visual snapshot |
| 9 | e2e_tests | Generate & run E2E tests |

## Setup

### Prerequisites

- Python 3.11+
- Node.js 16+
- tmux installed
- Claude CLI configured
- AWS CLI configured (profile: `sunwaretech`)
- Azure CLI configured (optional)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python app.py  # Starts on port 5001
```

### Frontend

```bash
cd frontend
npm install
npm start  # Starts on port 3000
```

### Run Tests

```bash
cd backend
python -m pytest -v  # 134 tests
```

## API Endpoints

### User & Session Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/create-user` | Create user and start deployment |
| GET | `/api/status/<execution_id>` | Get pipeline execution status |
| GET | `/api/user/<user_id>/sessions` | List user's sessions |

### Chat & Interaction

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/<execution_id>` | Send message to Claude session |
| GET | `/api/chat/<execution_id>/history` | Get tmux pane output |
| POST | `/api/redeploy/<execution_id>` | Trigger redeployment |

### Create User Request

```json
POST /api/create-user
{
  "email": "user@example.com",
  "phone": "+1234567890",
  "host_provider": "aws",      // aws | azure
  "site_type": "static",       // static | dynamic
  "requirements": "Build a portfolio website with dark theme"
}
```

### Response

```json
{
  "execution_id": "abc123_sess_20260124",
  "user_id": "abc123",
  "session_id": "sess_20260124",
  "is_new_user": true
}
```

## Cloud Configuration

### AWS

- **Profile**: `sunwaretech`
- **Region**: `us-east-1`
- **Static Sites**: S3 + CloudFront
- **Dynamic Sites**: EC2

### Azure

- **Profile**: `sunwaretech`
- **Region**: `eastus`
- **Static Sites**: Blob Storage + CDN
- **Dynamic Sites**: Virtual Machines

### Resource Naming

All cloud resources follow the pattern: `tmux-{guid_prefix}-{session_short}`

### Required Tags

```json
{
  "Project": "tmux-builder",
  "UserGUID": "{user_id}",
  "SessionID": "{session_id}",
  "SiteType": "static|dynamic",
  "CreatedBy": "tmux-builder-automation"
}
```

## Documentation

| Document | Description |
|----------|-------------|
| [QUICKSTART.md](docs/QUICKSTART.md) | Quick setup guide |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture |
| [SMARTBUILD_ARCHITECTURE_ANALYSIS.md](docs/SMARTBUILD_ARCHITECTURE_ANALYSIS.md) | SmartBuild pattern details |
| [PROJECT_GUIDELINES.md](docs/PROJECT_GUIDELINES.md) | Development guidelines |

## License

MIT
