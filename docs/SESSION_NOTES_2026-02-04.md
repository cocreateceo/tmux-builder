# Session Notes - February 4, 2026

## Overview

This document details all changes, fixes, and new features implemented during the February 4, 2026 session.

---

## 1. AWS Resource Naming Fix (Critical Bug Fix)

### Problem Identified
Multiple projects created in the same session used the **same S3 bucket**, causing newer projects to **overwrite** previous ones.

**Evidence:**
- Tea Shop deployed to: `tmux-cba6eaf3633e-teashop`
- Ship Shop deployed to: `tmux-cba6eaf3633e-teashop` (SAME bucket!)
- Result: Tea Shop was destroyed

### Root Cause
- System prompt lacked explicit instruction for unique resources per project
- Agent docs encouraged reusing existing deployment config
- Naming convention used session ID, not project-specific identifier

### Solution Implemented
**New naming pattern:** `tmux-{guid[:12]}-{project-slug}-{YYYYMMDD}-{HHmmss}`

**Examples:**
```
tmux-cba6eaf3633e-teashop-20260204-073700   (tea shop, Feb 4, 07:37)
tmux-cba6eaf3633e-teashop-20260205-100000   (another tea shop, different day)
tmux-cba6eaf3633e-shipshop-20260204-084700  (ship shop)
```

### Files Changed
| File | Change |
|------|--------|
| `backend/system_prompt_generator.py` | Added "UNIQUE AWS RESOURCES PER PROJECT" section with date+time naming |
| `.claude/agents/deployers/aws-s3-static.md` | Updated resource naming pattern, added NEW vs UPDATE distinction |

---

## 2. Per-User AWS IAM System

### Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                  CoCreate AWS Account (248825820556)         │
│                  Root Profile: cocreate                      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         IAM User: tmux-user-{guid[:12]}              │   │
│  │         Policy: GUID-scoped resources only            │   │
│  │         Credentials: Stored in session folder         │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Resources Created by User:                                  │
│  - S3: tmux-{guid[:12]}-{project}-{date}-{time}             │
│  - CloudFront: Tagged with guid                              │
│  - All tracked in DynamoDB                                   │
└─────────────────────────────────────────────────────────────┘
```

### IAM Policy for Per-User Access
```json
{
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "ManageTmuxUsers",
        "Effect": "Allow",
        "Action": [
            "iam:CreateUser", "iam:DeleteUser", "iam:GetUser",
            "iam:PutUserPolicy", "iam:DeleteUserPolicy",
            "iam:CreateAccessKey", "iam:DeleteAccessKey",
            "iam:ListAccessKeys", "iam:TagUser"
        ],
        "Resource": "arn:aws:iam::248825820556:user/tmux-user-*"
    }]
}
```

### Files Involved
| File | Purpose |
|------|---------|
| `backend/aws_user_manager.py` | Creates/manages IAM users per session |
| `backend/session_initializer.py` | Calls AWS user creation on session init |
| `backend/system_prompt_generator.py` | Injects per-user credentials into system prompt |

### Credential Flow
1. New session created → `aws_user_manager.create_user_for_session(guid)`
2. IAM user created: `tmux-user-{guid[:12]}`
3. Access keys generated and stored in `session/.aws_credentials`
4. System prompt uses these credentials (not root profile)
5. All resources tagged with `guid={guid[:12]}`

---

## 3. DynamoDB Resource Tracking

### Table Structure
- **Table Name:** `tmux-builder-resources`
- **Region:** us-east-1

### Schema
```json
{
  "pk": "USER#{guid}",
  "sk": "RESOURCE#{resource_type}#{resource_id}",
  "guid": "full-guid",
  "resource_type": "s3_bucket|cloudfront|iam_user",
  "resource_id": "resource-identifier",
  "created_at": "ISO timestamp",
  "metadata": { ... }
}
```

### Files
| File | Purpose |
|------|---------|
| `backend/dynamodb_client.py` | DynamoDB operations, table creation |
| `backend/main.py` | Initializes DynamoDB on startup |

---

## 4. User Dashboard Deployments API

### New Endpoint
```
GET /api/deployments?guid={guid}
```

### Response
```json
{
  "success": true,
  "deployments": [
    {
      "project_name": "Tea Shop",
      "url": "https://d3ctqoarnfegtv.cloudfront.net",
      "deployed_at": "2026-02-04T11:39:25Z",
      "status": "deployed"
    }
  ]
}
```

### How It Works
1. Parses `chat_history.jsonl` for CloudFront URLs
2. Extracts project names from markdown headers
3. Returns sorted list (newest first)

### Frontend Integration
- `user-core.js` (cocreateidea.com) calls this API
- Displays project name, URL, and deployment date/time
- Both GUID session and user dashboard use same endpoint

---

## 5. File Upload Feature

### UI Changes
- Attachment button moved to **right side** (between mic and send)
- Supports: `.txt`, `.pdf`, `.doc`, `.docx`, `.jpg`, `.png`
- Max file size: 10MB
- Shows file preview with "Upload & Build" button

### Backend Endpoint
```
POST /api/upload
Content-Type: multipart/form-data

file: <binary>
guid: <session-guid>
```

### Flow
1. User selects file → preview shown
2. Click "Upload & Build"
3. File saved to `session/uploads/{timestamp}_{filename}`
4. Claude receives instruction based on file type:
   - **Image:** "Analyze this image and create a website based on what you see"
   - **PDF:** "Read this PDF and create a website based on its contents"
   - **Text:** "Read this file and create a website based on its contents"
5. Claude builds website automatically

### Files Changed
| File | Change |
|------|--------|
| `frontend/src/client/components/ChatPanel.jsx` | File upload UI, validation, preview |
| `frontend/src/client/ClientApp.jsx` | `handleFileUpload` handler |
| `frontend/src/client/services/clientApi.js` | `uploadFile` API function |
| `backend/main.py` | `/api/upload` endpoint |

---

## 6. Tailwind CSS v3 Enforcement

### Problem
Claude was installing Tailwind v4 by default, which has incompatible syntax causing layout breaks.

### Solution
Added explicit instruction in `system_prompt_generator.py`:

```markdown
### CRITICAL: Tailwind CSS Version (MUST USE v3)

```bash
# ✅ CORRECT - Use v3
npm install -D tailwindcss@3 postcss autoprefixer

# ❌ WRONG - Do NOT use v4
npm install tailwindcss  # Installs v4 - BREAKS LAYOUTS
```
```

---

## 7. AWS Deployment Region

All deployments routed to **us-east-1** region using `cocreate` AWS profile.

### Configuration
```python
# backend/config.py
AWS_ROOT_PROFILE = "cocreate"
AWS_DEFAULT_REGION = "us-east-1"
```

---

## Current Deployment Status

### Session: cba6eaf3633edfcf16769fb3dfc56f193ea3230d48d9079fd88929f71b71e83d

| Project | URL | S3 Bucket | Status |
|---------|-----|-----------|--------|
| Tea Shop | https://d3ctqoarnfegtv.cloudfront.net | tmux-cba6eaf3633e-teashop-20260204-113827 | ✅ Live |
| Ship Shop | https://d28il8hax0qv0d.cloudfront.net | tmux-cba6eaf3633e-shipshop-20260204-* | ✅ Live |
| Juice Shop | https://d3dysd5jwz6xwl.cloudfront.net | tmux-cba6eaf3633e-juiceshop-20260204-122510 | ✅ Live |

---

## File Summary

### Backend Changes
| File | Description |
|------|-------------|
| `main.py` | Added `/api/upload`, `/api/deployments` endpoints |
| `system_prompt_generator.py` | Unique resource naming, Tailwind v3, per-user AWS |
| `aws_user_manager.py` | Per-user IAM management |
| `dynamodb_client.py` | Resource tracking |
| `config.py` | AWS profile and region config |

### Frontend Changes
| File | Description |
|------|-------------|
| `ChatPanel.jsx` | File upload UI with validation |
| `ClientApp.jsx` | File upload handler |
| `clientApi.js` | Upload API function |

### Agent/Skill Changes
| File | Description |
|------|-------------|
| `.claude/agents/deployers/aws-s3-static.md` | New vs Update distinction, date+time naming |

### External (cocreateidea.com)
| File | Description |
|------|-------------|
| `js/user-core.js` | Fetches and displays deployments |

---

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER REQUEST                              │
│   "Create a tea shop website" or Upload file                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     TMUX BUILDER BACKEND                         │
│  1. Validate session (create IAM user if new)                    │
│  2. Save message/file to session folder                          │
│  3. Send instruction to Claude via tmux                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        CLAUDE CLI                                │
│  1. Read system_prompt.txt (with AWS creds, naming rules)        │
│  2. Build website (React + Tailwind v3)                          │
│  3. Create UNIQUE S3 bucket: tmux-{guid}-{project}-{date}-{time} │
│  4. Create CloudFront distribution                               │
│  5. Upload files, configure CORS                                 │
│  6. Write summary.md, call notify.sh done                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DYNAMODB TRACKING                            │
│  - Record: USER#{guid} → RESOURCE#{type}#{id}                    │
│  - Track: S3 buckets, CloudFront, IAM users                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    USER DASHBOARD                                │
│  - /api/deployments returns all projects with unique URLs        │
│  - Each project has its own CloudFront distribution              │
│  - No overwrites, full history preserved                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Testing Checklist

- [x] Create multiple projects in same session → each gets unique bucket
- [x] Same project name twice → different buckets (date+time differs)
- [x] User dashboard shows all deployments with correct URLs
- [x] File upload works (.txt, .pdf, .doc, .docx, .jpg, .png)
- [x] Tailwind v3 enforced (no layout breaks)
- [x] CloudFront distributions deploy correctly
- [x] Per-user IAM credentials work

---

## Known Behaviors

1. **CloudFront deployment takes 5-15 minutes** - URL is shared immediately but may not be accessible until "InProgress" → "Deployed"

2. **Old deployments with same URL** - Historical entries may show same URL if they were created before the fix

---

## Git Commits (This Session)

1. `Fix: Unique AWS resources per project with date+time naming`
2. `Add /api/deployments endpoint for user dashboard`
3. `Add file upload feature to tmux client UI`
