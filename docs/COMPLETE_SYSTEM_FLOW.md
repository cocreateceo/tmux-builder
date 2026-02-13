# Tmux Builder - Complete System Flow

## Table of Contents
1. [User/Member Creation Flow](#1-usermember-creation-flow)
2. [Admin to User Data Flow](#2-admin-to-user-data-flow)
3. [User Session Login Flow](#3-user-session-login-flow)
4. [Project Creation Flow](#4-project-creation-flow)
5. [AWS Resource Creation Flow](#5-aws-resource-creation-flow)
6. [Complete Resource Location Reference](#6-complete-resource-location-reference)
7. [System Prompt Generator - Central Source](#7-system-prompt-generator---central-source)
8. [File Upload Feature](#8-file-upload-feature)
9. [Activity Panel & WebSocket Filtering](#9-activity-panel--websocket-filtering)
10. [Important Rules & Constraints](#10-important-rules--constraints)

---

## 1. User/Member Creation Flow

### Entry Points

| Entry Point | URL | Purpose |
|-------------|-----|---------|
| Client Onboarding | `/client_input` or `/onboard` | New user fills form |
| Admin Creates Session | `/api/admin/sessions` | Admin creates for user |
| Direct Session | `/client?guid=xxx` | Access existing session |

### Step-by-Step: New User from Onboarding

```
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 1: User fills onboarding form                                      │
│                                                                         │
│ URL: https://d3tfeatcbws1ka.cloudfront.net/client_input                 │
│ Component: frontend/src/client/ClientOnboarding.jsx                     │
│                                                                         │
│ Form Fields:                                                            │
│   - name (client name)                                                  │
│   - email                                                               │
│   - phone                                                               │
│   - initial_request (what they want to build)                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 2: API call to create session                                      │
│                                                                         │
│ Endpoint: POST /api/admin/sessions                                      │
│ File: backend/main.py:401-450                                           │
│                                                                         │
│ Request Body:                                                           │
│ {                                                                       │
│   "email": "user@example.com",                                          │
│   "phone": "1234567890",                                                │
│   "initial_request": "create a tea shop website",                       │
│   "client_name": "John Doe"                                             │
│ }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Generate unique GUID                                            │
│                                                                         │
│ File: backend/guid_generator.py                                         │
│ Function: generate_guid(email)                                          │
│                                                                         │
│ Creates: SHA256 hash of email + timestamp + random                      │
│ Example: cba6eaf3633edfcf16769fb3dfc56f193ea3230d48d9079fd88929f71b71e83d│
│                                                                         │
│ WHERE SAVED: Only in memory at this point                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 4: Initialize session                                              │
│                                                                         │
│ File: backend/session_initializer.py:60-180                             │
│ Function: initialize_session(guid, email, client_name, ...)             │
│                                                                         │
│ Creates session folder and all subfolders (see Step 5)                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 5: Session folder created                                          │
│                                                                         │
│ LOCATION: EC2 server                                                    │
│ PATH: /home/ubuntu/tmux-builder/sessions/active/{guid}/                 │
│                                                                         │
│ Structure:                                                              │
│ sessions/active/{guid}/                                                 │
│ ├── system_prompt.txt      # Claude instructions                        │
│ ├── notify.sh              # WebSocket notification script              │
│ ├── status.json            # Session state                              │
│ ├── chat_history.jsonl     # All messages                               │
│ ├── .aws_credentials       # Per-user AWS keys                          │
│ ├── tmp/                   # Temporary files                            │
│ ├── code/                  # Generated code                             │
│ ├── infrastructure/        # IaC files                                  │
│ ├── docs/                  # Documentation                              │
│ └── uploads/               # User uploaded files                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 6: User redirected to session                                      │
│                                                                         │
│ URL: https://d3tfeatcbws1ka.cloudfront.net/client?guid={guid}           │
│ Component: frontend/src/client/ClientApp.jsx                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Admin to User Data Flow

### Admin Portal

| Item | Location |
|------|----------|
| Admin URL | https://d3tfeatcbws1ka.cloudfront.net/ |
| Admin Component | `frontend/src/components/SplitChatView.jsx` |
| Session List | `frontend/src/components/SessionSidebar.jsx` |

### Admin Creates Session for User

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ADMIN PORTAL                                                            │
│                                                                         │
│ URL: https://d3tfeatcbws1ka.cloudfront.net/                             │
│ File: frontend/src/components/SplitChatView.jsx                         │
│                                                                         │
│ Admin clicks "New Session" → enters user details                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ API: POST /api/admin/sessions                                           │
│                                                                         │
│ File: backend/main.py:401-450                                           │
│                                                                         │
│ Request:                                                                │
│ {                                                                       │
│   "email": "client@example.com",                                        │
│   "phone": "555-1234",                                                  │
│   "initial_request": "Build me an e-commerce site",                     │
│   "client_name": "Client Name"                                          │
│ }                                                                       │
│                                                                         │
│ Response:                                                               │
│ {                                                                       │
│   "success": true,                                                      │
│   "guid": "abc123...",                                                  │
│   "session_url": "https://d3tfeatcbws1ka.cloudfront.net/client?guid=..."│
│ }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ DATA SAVED TO: status.json                                              │
│                                                                         │
│ Path: sessions/active/{guid}/status.json                                │
│                                                                         │
│ Content:                                                                │
│ {                                                                       │
│   "state": "ready",                                                     │
│   "guid": "cba6eaf3633e...",                                            │
│   "email": "client@example.com",                                        │
│   "phone": "555-1234",                                                  │
│   "client_name": "Client Name",                                         │
│   "user_request": "Build me an e-commerce site",                        │
│   "created_at": "2026-02-04T07:25:31Z",                                 │
│   "deployed_url": null,                                                 │
│   "aws_resources": {}                                                   │
│ }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Admin Lists All Sessions

```
API: GET /api/admin/sessions?filter=all|active|completed

File: backend/main.py:460-520

Response:
{
  "success": true,
  "sessions": [
    {
      "guid": "abc123...",
      "email": "user@example.com",
      "client_name": "John",
      "state": "ready",
      "created_at": "2026-02-04T07:25:31Z",
      "deployed_url": "https://d3ctqoarnfegtv.cloudfront.net"
    }
  ]
}

DATA SOURCE: Reads from sessions/active/*/status.json
```

---

## 3. User Session Login Flow

### Access Methods

| Method | URL | How It Works |
|--------|-----|--------------|
| Direct GUID link | `/client?guid=xxx` | GUID in URL |
| Email lookup | `/client?email=xxx` | Finds session by email |
| User Dashboard | `cocreateidea.com/user.id=xxx` | Authenticated user |

### Direct GUID Access Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│ USER CLICKS LINK                                                        │
│                                                                         │
│ URL: https://d3tfeatcbws1ka.cloudfront.net/client?guid={guid}           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ FRONTEND LOADS                                                          │
│                                                                         │
│ File: frontend/src/client/ClientApp.jsx                                 │
│ Hook: useClientSession.js                                               │
│                                                                         │
│ 1. Extract GUID from URL params                                         │
│ 2. Store GUID in localStorage                                           │
│ 3. Call API to validate session                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ API: GET /api/client/projects?guid={guid}                               │
│                                                                         │
│ File: backend/main.py:550-600                                           │
│                                                                         │
│ Validates GUID exists in: sessions/active/{guid}/                       │
│ Returns session info from: sessions/active/{guid}/status.json           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ WEBSOCKET CONNECTION                                                    │
│                                                                         │
│ URL: wss://d3tfeatcbws1ka.cloudfront.net/ws/{guid}                      │
│ Server: backend/ws_server.py:8082                                       │
│                                                                         │
│ Purpose: Real-time progress updates from Claude                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ LOAD CHAT HISTORY                                                       │
│                                                                         │
│ API: GET /api/history?guid={guid}                                       │
│ File: backend/main.py:1136-1200                                         │
│                                                                         │
│ Data Source: sessions/active/{guid}/chat_history.jsonl                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Project Creation Flow

### User Sends Message to Create Website

```
┌─────────────────────────────────────────────────────────────────────────┐
│ USER TYPES: "Create a tea shop website"                                 │
│                                                                         │
│ Component: frontend/src/client/components/ChatPanel.jsx                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ API: POST /api/chat                                                     │
│                                                                         │
│ File: backend/main.py:1088-1133                                         │
│                                                                         │
│ Request:                                                                │
│ {                                                                       │
│   "guid": "cba6eaf3633e...",                                            │
│   "message": "Create a tea shop website"                                │
│ }                                                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ MESSAGE SAVED                                                           │
│                                                                         │
│ File: backend/session_controller.py                                     │
│                                                                         │
│ SAVED TO: sessions/active/{guid}/chat_history.jsonl                     │
│                                                                         │
│ Format:                                                                 │
│ {"role": "user", "content": "Create a tea shop website",                │
│  "timestamp": "2026-02-04T07:26:09Z"}                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PROMPT FILE CREATED                                                     │
│                                                                         │
│ File: backend/session_controller.py                                     │
│                                                                         │
│ SAVED TO: sessions/active/{guid}/prompt_{timestamp_ms}.txt              │
│ Example: sessions/active/{guid}/prompt_1707034567890.txt                │
│                                                                         │
│ Content: "Create a tea shop website"                                    │
│                                                                         │
│ WHY TIMESTAMP: Prevents Claude from caching/reusing old prompts         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ INSTRUCTION SENT TO CLAUDE VIA TMUX                                     │
│                                                                         │
│ File: backend/tmux_helper.py                                            │
│                                                                         │
│ Tmux Session: tmux_builder_{guid}                                       │
│ Location: Running on EC2 server                                         │
│                                                                         │
│ Instruction sent:                                                       │
│ "Read {full_path}/prompt_{timestamp}.txt and complete the task"         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ CLAUDE READS SYSTEM PROMPT                                              │
│                                                                         │
│ File: sessions/active/{guid}/system_prompt.txt                          │
│                                                                         │
│ Contains:                                                               │
│ - AWS credentials (per-user)                                            │
│ - Resource naming rules                                                 │
│ - Deployment instructions                                               │
│ - Available skills/agents                                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ CLAUDE BUILDS WEBSITE                                                   │
│                                                                         │
│ Code generated in: sessions/active/{guid}/code/                         │
│                                                                         │
│ Example structure:                                                      │
│ code/                                                                   │
│ ├── package.json                                                        │
│ ├── vite.config.js                                                      │
│ ├── tailwind.config.js                                                  │
│ ├── index.html                                                          │
│ └── src/                                                                │
│     ├── main.jsx                                                        │
│     ├── App.jsx                                                         │
│     └── components/                                                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ CLAUDE DEPLOYS TO AWS (See Section 5)                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ CLAUDE WRITES SUMMARY                                                   │
│                                                                         │
│ SAVED TO: sessions/active/{guid}/summary.md                             │
│                                                                         │
│ Contains:                                                               │
│ - Project name                                                          │
│ - Features built                                                        │
│ - Live URL                                                              │
│ - AWS resources created                                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ CLAUDE CALLS NOTIFY.SH                                                  │
│                                                                         │
│ Commands:                                                               │
│ ./notify.sh summary    # Triggers summary read                          │
│ ./notify.sh done       # Marks task complete                            │
│                                                                         │
│ Script location: sessions/active/{guid}/notify.sh                       │
│ Sends to: WebSocket server on port 8082                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ RESPONSE SAVED TO CHAT HISTORY                                          │
│                                                                         │
│ SAVED TO: sessions/active/{guid}/chat_history.jsonl                     │
│                                                                         │
│ Format:                                                                 │
│ {"role": "assistant", "content": "## Tea Shop - Complete\n...",         │
│  "timestamp": "2026-02-04T07:37:19Z"}                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. AWS Resource Creation Flow

### Per-User IAM Creation

```
┌─────────────────────────────────────────────────────────────────────────┐
│ TRIGGER: New session initialization                                     │
│                                                                         │
│ File: backend/session_initializer.py:115-131                            │
│ Condition: if AWS_PER_USER_IAM_ENABLED (config.py:52, default=true)     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ IAM USER CREATED                                                        │
│                                                                         │
│ File: backend/aws_user_manager.py:99-175                                │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────┐     │
│ │ WHAT: IAM User                                                  │     │
│ │ NAME: tmux-user-{guid[:12]}                                     │     │
│ │ EXAMPLE: tmux-user-cba6eaf3633e                                 │     │
│ │                                                                 │     │
│ │ WHERE CREATED: AWS IAM (CoCreate account 248825820556)          │     │
│ │ CREATED BY: Root profile "cocreate"                             │     │
│ │ API CALL: iam.create_user(UserName="tmux-user-xxx")             │     │
│ │                                                                 │     │
│ │ HOW TO VIEW:                                                    │     │
│ │ aws iam get-user --user-name tmux-user-cba6eaf3633e             │     │
│ │   --profile cocreate                                            │     │
│ └─────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ IAM POLICY ATTACHED                                                     │
│                                                                         │
│ File: backend/aws_user_manager.py:131-142                               │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────┐     │
│ │ WHAT: Inline IAM Policy                                         │     │
│ │ NAME: tmux-policy-{guid[:12]}                                   │     │
│ │ EXAMPLE: tmux-policy-cba6eaf3633e                               │     │
│ │                                                                 │     │
│ │ WHERE CREATED: Attached to IAM user in AWS                      │     │
│ │ TEMPLATE: backend/scripts/user_policy_template.json             │     │
│ │ API CALL: iam.put_user_policy(...)                              │     │
│ │                                                                 │     │
│ │ PERMISSIONS: Only resources prefixed with tmux-{guid[:12]}-*    │     │
│ └─────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ ACCESS KEYS CREATED                                                     │
│                                                                         │
│ File: backend/aws_user_manager.py:145-168                               │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────┐     │
│ │ WHAT: AWS Access Key + Secret Key                               │     │
│ │                                                                 │     │
│ │ WHERE CREATED: AWS IAM                                          │     │
│ │ API CALL: iam.create_access_key(UserName="tmux-user-xxx")       │     │
│ │                                                                 │     │
│ │ WHERE SAVED: EC2 local file                                     │     │
│ │ PATH: sessions/active/{guid}/.aws_credentials                   │     │
│ │                                                                 │     │
│ │ FILE CONTENT:                                                   │     │
│ │ {                                                               │     │
│ │   "user_name": "tmux-user-cba6eaf3633e",                        │     │
│ │   "access_key_id": "AKIATT3ZMWWG...",                           │     │
│ │   "secret_access_key": "Z9XsTIRO2tKJ...",                       │     │
│ │   "region": "us-east-1",                                        │     │
│ │   "guid": "cba6eaf3633e..."                                     │     │
│ │ }                                                               │     │
│ └─────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ CREDENTIALS INJECTED INTO SYSTEM PROMPT                                 │
│                                                                         │
│ File: backend/system_prompt_generator.py:33-58                          │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────┐     │
│ │ WHERE SAVED: sessions/active/{guid}/system_prompt.txt           │     │
│ │                                                                 │     │
│ │ CONTENT ADDED:                                                  │     │
│ │ ```bash                                                         │     │
│ │ export AWS_ACCESS_KEY_ID=AKIATT3ZMWWG...                        │     │
│ │ export AWS_SECRET_ACCESS_KEY=Z9XsTIRO2tKJ...                    │     │
│ │ export AWS_DEFAULT_REGION=us-east-1                             │     │
│ │ ```                                                             │     │
│ └─────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

### S3 Bucket Creation (by Claude)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ CLAUDE CREATES S3 BUCKET                                                │
│                                                                         │
│ Skill: .claude/skills/aws/s3-upload.md                                  │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────┐     │
│ │ WHAT: S3 Bucket                                                 │     │
│ │ NAME: tmux-{guid[:12]}-{project}-{YYYYMMDD}-{HHmmss}            │     │
│ │ EXAMPLE: tmux-cba6eaf3633e-teashop-20260204-113827              │     │
│ │                                                                 │     │
│ │ WHERE CREATED: AWS S3 (us-east-1)                               │     │
│ │ CREATED BY: Per-user credentials (NOT root)                     │     │
│ │ API CALL: aws s3 mb s3://tmux-xxx-teashop-xxx                   │     │
│ │                                                                 │     │
│ │ HOW TO VIEW:                                                    │     │
│ │ aws s3 ls | grep tmux-cba6eaf3633e                              │     │
│ │                                                                 │     │
│ │ CONTAINS: Built website files (HTML, CSS, JS, assets)           │     │
│ └─────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

### CloudFront Distribution Creation (by Claude)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ CLAUDE CREATES CLOUDFRONT DISTRIBUTION                                  │
│                                                                         │
│ Skill: .claude/skills/aws/cloudfront-create.md                          │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────┐     │
│ │ WHAT: CloudFront Distribution                                   │     │
│ │ DOMAIN: dXXXXXXXXXXX.cloudfront.net                             │     │
│ │ EXAMPLE: d3ctqoarnfegtv.cloudfront.net                          │     │
│ │                                                                 │     │
│ │ WHERE CREATED: AWS CloudFront (global)                          │     │
│ │ CREATED BY: Per-user credentials                                │     │
│ │ API CALL: aws cloudfront create-distribution ...                │     │
│ │                                                                 │     │
│ │ ORIGIN: Points to S3 bucket                                     │     │
│ │ TAGS: guid={guid[:12]}, created-by=tmux-builder                 │     │
│ │                                                                 │     │
│ │ HOW TO VIEW:                                                    │     │
│ │ aws cloudfront list-distributions --query                       │     │
│ │   "DistributionList.Items[?contains(Origins.Items[0].DomainName,│     │
│ │   'tmux-cba6eaf3633e')]"                                        │     │
│ └─────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

### DynamoDB Resource Tracking

```
┌─────────────────────────────────────────────────────────────────────────┐
│ RESOURCES TRACKED IN DYNAMODB                                           │
│                                                                         │
│ File: backend/dynamodb_client.py                                        │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────┐     │
│ │ WHAT: DynamoDB Table                                            │     │
│ │ NAME: tmux-builder-resources                                    │     │
│ │ REGION: us-east-1                                               │     │
│ │                                                                 │     │
│ │ WHERE: AWS DynamoDB                                             │     │
│ │                                                                 │     │
│ │ RECORD STRUCTURE:                                               │     │
│ │ {                                                               │     │
│ │   "pk": "USER#cba6eaf3633e...",                                 │     │
│ │   "sk": "RESOURCE#s3_bucket#tmux-cba6eaf3633e-teashop-xxx",     │     │
│ │   "resource_type": "s3_bucket",                                 │     │
│ │   "resource_id": "tmux-cba6eaf3633e-teashop-20260204-113827",   │     │
│ │   "created_at": "2026-02-04T11:39:25Z",                         │     │
│ │   "metadata": {                                                 │     │
│ │     "region": "us-east-1",                                      │     │
│ │     "cloudfront_id": "E1X1A8BU292ZJ9",                          │     │
│ │     "cloudfront_url": "https://d3ctqoarnfegtv.cloudfront.net"   │     │
│ │   }                                                             │     │
│ │ }                                                               │     │
│ └─────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Complete Resource Location Reference

### Local Files (EC2 Server: 18.211.207.2)

| Resource | Path | Purpose |
|----------|------|---------|
| **Session Folder** | `/home/ubuntu/tmux-builder/sessions/active/{guid}/` | All session data |
| **System Prompt** | `sessions/active/{guid}/system_prompt.txt` | Claude instructions |
| **AWS Credentials** | `sessions/active/{guid}/.aws_credentials` | Per-user keys (JSON) |
| **Chat History** | `sessions/active/{guid}/chat_history.jsonl` | All messages |
| **Status** | `sessions/active/{guid}/status.json` | Session state |
| **Notify Script** | `sessions/active/{guid}/notify.sh` | WebSocket notifications |
| **Summary** | `sessions/active/{guid}/summary.md` | Deployment summary |
| **Uploads** | `sessions/active/{guid}/uploads/` | User uploaded files |
| **Generated Code** | `sessions/active/{guid}/code/` | Website source |
| **Built Files** | `sessions/active/{guid}/code/dist/` | Production build |

### AWS Resources (CoCreate Account: 248825820556)

| Resource | Location | Naming Pattern | Example |
|----------|----------|----------------|---------|
| **IAM User** | AWS IAM | `tmux-user-{guid[:12]}` | tmux-user-cba6eaf3633e |
| **IAM Policy** | Attached to user | `tmux-policy-{guid[:12]}` | tmux-policy-cba6eaf3633e |
| **S3 Bucket** | AWS S3 (us-east-1) | `tmux-{guid[:12]}-{project}-{date}-{time}` | tmux-cba6eaf3633e-teashop-20260204-113827 |
| **CloudFront** | AWS CloudFront | Auto-generated domain | d3ctqoarnfegtv.cloudfront.net |
| **DynamoDB Table** | AWS DynamoDB (us-east-1) | `tmux-builder-resources` | Single table |

### URLs

| Service | URL | Purpose |
|---------|-----|---------|
| **Tmux Builder (CloudFront)** | https://d3tfeatcbws1ka.cloudfront.net | Main app |
| **Admin Portal** | https://d3tfeatcbws1ka.cloudfront.net/ | Admin UI |
| **Client Portal** | https://d3tfeatcbws1ka.cloudfront.net/client?guid=xxx | User session |
| **Onboarding** | https://d3tfeatcbws1ka.cloudfront.net/client_input | New user form |
| **WebSocket** | wss://d3tfeatcbws1ka.cloudfront.net/ws/{guid} | Real-time updates |
| **User Dashboard** | https://www.cocreateidea.com/user.id=xxx | External dashboard |
| **Backend API (EC2)** | http://18.211.207.2:8000 | Direct API (behind CF) |
| **WebSocket Server (EC2)** | ws://18.211.207.2:8082 | Direct WS (behind CF) |

### Configuration Files

| Config | Path | Key Settings |
|--------|------|--------------|
| **Backend Config** | `backend/config.py` | AWS_ROOT_PROFILE, AWS_DEFAULT_REGION, AWS_PER_USER_IAM_ENABLED |
| **Policy Template** | `backend/scripts/user_policy_template.json` | Per-user IAM permissions |
| **S3 Skill** | `.claude/skills/aws/s3-upload.md` | S3 upload instructions |
| **CloudFront Skill** | `.claude/skills/aws/cloudfront-create.md` | CDN creation |
| **Deployer Agent** | `.claude/agents/deployers/aws-s3-static.md` | Full deployment flow |

---

## Quick Reference Commands

### Check IAM User
```bash
aws iam get-user --user-name tmux-user-{guid[:12]} --profile cocreate
```

### List S3 Buckets for User
```bash
aws s3 ls | grep tmux-{guid[:12]}
```

### Check CloudFront Distributions
```bash
aws cloudfront list-distributions --profile cocreate \
  --query "DistributionList.Items[?contains(Origins.Items[0].DomainName, 'tmux-{guid[:12]}')]"
```

### View Session Credentials (on EC2)
```bash
cat /home/ubuntu/tmux-builder/sessions/active/{guid}/.aws_credentials
```

### View Session Status (on EC2)
```bash
cat /home/ubuntu/tmux-builder/sessions/active/{guid}/status.json
```

### Check Tmux Session
```bash
tmux list-sessions | grep {guid[:12]}
```

### View Claude Output (on EC2)
```bash
tmux capture-pane -t tmux_builder_{guid} -p | tail -50
```

---

## 7. System Prompt Generator - Central Source

### Critical Understanding

**`backend/system_prompt_generator.py` is the SINGLE SOURCE OF TRUTH for all Claude instructions.**

Any change made to this file affects:
- ✅ All NEW sessions created after the change
- ✅ All FUTURE projects in those sessions
- ❌ Does NOT affect existing sessions (their system_prompt.txt is already generated)

### How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. User creates new session                                             │
│    (via /client_input or /api/admin/sessions)                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. session_initializer.py calls system_prompt_generator.py              │
│                                                                         │
│    generate_system_prompt(session_path, guid, aws_credentials)          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. system_prompt.txt is GENERATED and SAVED to session folder           │
│                                                                         │
│    Location: sessions/active/{guid}/system_prompt.txt                   │
│                                                                         │
│    This file is STATIC once created - never regenerated                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. Claude CLI reads system_prompt.txt at session start                  │
│                                                                         │
│    All instructions, rules, and credentials come from this file         │
└─────────────────────────────────────────────────────────────────────────┘
```

### What system_prompt_generator.py Contains

| Section | Purpose |
|---------|---------|
| **AWS Credentials** | Per-user access keys injected at generation time |
| **Resource Naming Rules** | `tmux-{guid[:12]}-{project}-{YYYYMMDD}-{HHmmss}` |
| **Tailwind v3 Enforcement** | MUST use `tailwindcss@3` not v4 |
| **AWS-Only Deployment** | Never use localhost, always S3+CloudFront |
| **Unique Resources Per Project** | Each project gets new bucket+CDN |
| **Skills/Agents References** | Available deployment skills |

### Key File Locations

| File | Purpose |
|------|---------|
| `backend/system_prompt_generator.py` | **THE SOURCE** - edit this to change ALL future sessions |
| `sessions/active/{guid}/system_prompt.txt` | Generated output - static per session |

### Updating Instructions for Future Sessions

To change Claude's behavior for all future sessions:

1. Edit `backend/system_prompt_generator.py`
2. Deploy to EC2 (`./deployment/ec2-deploy.sh deploy`)
3. All NEW sessions will have the updated instructions
4. Existing sessions keep their original instructions

**WARNING:** To update an existing session, you must either:
- Delete and recreate the session, OR
- Manually edit `sessions/active/{guid}/system_prompt.txt` on EC2

---

## 8. File Upload Feature

### Overview

Users can upload files (images, PDFs, documents) and Claude will analyze them to build websites.

### Supported File Types

| Type | Extensions | Max Size |
|------|------------|----------|
| Images | `.jpg`, `.png` | 10MB |
| Documents | `.pdf`, `.doc`, `.docx` | 10MB |
| Text | `.txt` | 10MB |

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. USER SELECTS FILE                                                    │
│                                                                         │
│ Component: frontend/src/client/components/ChatPanel.jsx                 │
│ UI Element: Attachment button (right side, between mic and send)        │
│                                                                         │
│ Validation:                                                             │
│ - File type check (allowed extensions only)                             │
│ - Size check (max 10MB)                                                 │
│ - Shows preview with "Upload & Build" button                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. FILE UPLOADED TO BACKEND                                             │
│                                                                         │
│ Handler: frontend/src/client/ClientApp.jsx:handleFileUpload()           │
│ API: frontend/src/client/services/clientApi.js:uploadFile()             │
│                                                                         │
│ Request:                                                                │
│   POST /api/upload                                                      │
│   Content-Type: multipart/form-data                                     │
│   Body: { file: <binary>, guid: <session-guid> }                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. BACKEND SAVES FILE                                                   │
│                                                                         │
│ Endpoint: backend/main.py /api/upload                                   │
│                                                                         │
│ File saved to: sessions/active/{guid}/uploads/{timestamp}_{filename}    │
│ Example: sessions/active/abc123/uploads/1707034567890_design.png        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. INSTRUCTION SENT TO CLAUDE                                           │
│                                                                         │
│ Based on file type:                                                     │
│                                                                         │
│ IMAGE (.jpg, .png):                                                     │
│   "Analyze this image and create a website based on what you see"       │
│                                                                         │
│ PDF (.pdf):                                                             │
│   "Read this PDF and create a website based on its contents"            │
│                                                                         │
│ DOCUMENT/TEXT (.doc, .docx, .txt):                                      │
│   "Read this file and create a website based on its contents"           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. CLAUDE BUILDS WEBSITE                                                │
│                                                                         │
│ - Analyzes uploaded file                                                │
│ - Generates React + Tailwind code                                       │
│ - Deploys to AWS S3 + CloudFront                                        │
│ - Returns summary with live URL                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Activity Panel & WebSocket Filtering

### Overview

The Activity Panel shows real-time progress updates. Raw technical data (AWS JSON) is filtered out to show user-friendly messages only.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│ CLAUDE CLI                                                              │
│                                                                         │
│ Sends raw messages via notify.sh:                                       │
│   ./notify.sh status "Creating S3 bucket..."                            │
│   ./notify.sh status '{"s3_bucket":"tmux-xxx","cloudfront_id":"E1X"}'   │
│   ./notify.sh progress "75"                                             │
│   ./notify.sh done                                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ WEBSOCKET SERVER (ws_server.py:8082)                                    │
│                                                                         │
│ Broadcasts all messages to connected clients                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ FRONTEND HOOK: useProgressSocket.js                                     │
│                                                                         │
│ ┌─────────────────────────────────────────────────────────────────┐     │
│ │ formatActivityMessage(msg) - FILTERS AND FORMATS                │     │
│ │                                                                 │     │
│ │ FILTERED OUT (returns null):                                    │     │
│ │ - Messages containing "s3_bucket", "cloudfront_id"              │     │
│ │ - Messages containing "cloudfront_url", "region"                │     │
│ │ - Raw JSON starting with { containing "tmux-" or "cloudfront"   │     │
│ │                                                                 │     │
│ │ TRANSFORMED:                                                    │     │
│ │ - "creating s3 bucket" → "Creating storage bucket..."           │     │
│ │ - "s3 bucket created" → "Storage bucket ready"                  │     │
│ │ - "creating cloudfront" → "Setting up CDN..."                   │     │
│ │ - "npm install" → "Installing dependencies..."                  │     │
│ │ - "npm run build" → "Building project..."                       │     │
│ │ - "deployment complete" → "Deployment complete!"                │     │
│ │ - Progress "75" → "75%"                                         │     │
│ └─────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ ACTIVITY PANEL UI                                                       │
│                                                                         │
│ Component: frontend/src/client/components/ActivityPanel.jsx             │
│                                                                         │
│ Shows:                                                                  │
│ ✅ "Creating storage bucket..."                                         │
│ ✅ "Setting up CDN..."                                                  │
│ ✅ "75%"                                                                │
│ ✅ "Deployment complete!"                                               │
│                                                                         │
│ Does NOT show:                                                          │
│ ❌ {"s3_bucket":"tmux-abc123-teashop-20260204-113827"...}               │
│ ❌ Raw CloudFront distribution IDs                                      │
│ ❌ Technical AWS region information                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key File

| File | Purpose |
|------|---------|
| `frontend/src/hooks/useProgressSocket.js` | Contains `formatActivityMessage()` filter function |

### Message Type Flow

| Type | Raw Example | Displayed As |
|------|-------------|--------------|
| `progress` | `75` | `75%` |
| `status` | `creating s3 bucket` | `Creating storage bucket...` |
| `status` | `cloudfront created` | `CDN configured` |
| `status` | `{"s3_bucket":"..."}` | *(filtered out)* |
| `done` | - | `Complete` |
| `error` | `Failed to deploy` | `Failed to deploy` |

---

## 10. Important Rules & Constraints

### Tailwind CSS v3 Enforcement

**CRITICAL:** Claude MUST use Tailwind v3, NOT v4.

```bash
# ✅ CORRECT - Use v3
npm install -D tailwindcss@3 postcss autoprefixer

# ❌ WRONG - Do NOT use v4
npm install tailwindcss  # Installs v4 - BREAKS LAYOUTS
```

**Why:** Tailwind v4 has incompatible syntax that breaks layouts. This is enforced in `system_prompt_generator.py`.

### AWS-Only Deployment (Non-Negotiable)

**NEVER deploy locally. ALWAYS deploy to AWS.**

| ❌ FORBIDDEN | ✅ REQUIRED |
|--------------|-------------|
| `npm run dev` as "deployment" | S3 + CloudFront deployment |
| `npm start` as "deployment" | Real CloudFront URL |
| `python -m http.server` | `https://dXXXXX.cloudfront.net` |
| "Running on localhost:3000" | Full AWS infrastructure |

**Why:** Users expect live websites, not localhost URLs they can't access.

### Unique AWS Resources Per Project

Each project in a session MUST get unique AWS resources:

**Naming Pattern:** `tmux-{guid[:12]}-{project-slug}-{YYYYMMDD}-{HHmmss}`

**Examples:**
```
tmux-cba6eaf3633e-teashop-20260204-073700   (tea shop)
tmux-cba6eaf3633e-teashop-20260205-100000   (another tea shop, different day)
tmux-cba6eaf3633e-shipshop-20260204-084700  (ship shop)
```

**Why:** Without date+time, same project name would overwrite previous deployment.

### CloudFront Deployment Delay

**Important:** CloudFront distributions take 5-15 minutes to become accessible.

- URL is generated and shared immediately
- Status shows "InProgress" during deployment
- Website not accessible until status changes to "Deployed"
- Users may see 403 errors during this period - this is normal

### Historical Data Note

Old deployments (before Feb 4, 2026 fix) may show duplicate URLs because they were created before unique naming was implemented. These are historical artifacts.
