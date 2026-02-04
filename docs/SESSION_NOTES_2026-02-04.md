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

### Credential Flow (Detailed with File/Line Numbers)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. API Request → main.py:201 initialize_new_session()                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. session_initializer.py:115-131                                       │
│                                                                         │
│    if AWS_PER_USER_IAM_ENABLED:  # config.py:52 (default: true)         │
│        aws_manager = AWSUserManager()                                   │
│        aws_credentials = await aws_manager.get_or_create_credentials()  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. aws_user_manager.py:99-175                                           │
│                                                                         │
│    Using ROOT profile (cocreate):                                       │
│    a) iam.create_user(UserName="tmux-user-{guid[:12]}")                 │
│    b) iam.put_user_policy(PolicyDocument=GUID-scoped policy)            │
│    c) iam.create_access_key() → returns AccessKeyId, SecretAccessKey    │
│    d) Save to: sessions/active/{guid}/.aws_credentials                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. system_prompt_generator.py:33-58                                     │
│                                                                         │
│    generate_system_prompt(session_path, guid, aws_credentials)          │
│                                                                         │
│    Injects into system_prompt.txt:                                      │
│    export AWS_ACCESS_KEY_ID=AKIA...                                     │
│    export AWS_SECRET_ACCESS_KEY=...                                     │
│    export AWS_DEFAULT_REGION=us-east-1                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. Claude CLI uses per-user credentials for all AWS operations          │
│    - NOT using root profile                                             │
│    - Can only access GUID-prefixed resources                            │
└─────────────────────────────────────────────────────────────────────────┘
```

### Credentials Storage

**File Path:** `sessions/active/{guid}/.aws_credentials`

**JSON Structure:**
```json
{
  "user_name": "tmux-user-cba6eaf3633e",
  "access_key_id": "AKIATT3ZMWWG...",
  "secret_access_key": "Z9XsTIRO2tKJ...",
  "region": "us-east-1",
  "guid": "cba6eaf3633edfcf16769fb3dfc56f193ea3230d48d9079fd88929f71b71e83d"
}
```

### How Root Credentials Create Per-User

1. **Root Profile:** `cocreate` (configured in `~/.aws/credentials` on EC2)
2. **Root has IAM permissions** to create/manage `tmux-user-*` users
3. **Per-user gets LIMITED permissions** - can only access `tmux-{their-guid}-*` resources
4. **Isolation:** User A cannot access User B's resources

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

## 8. No Local Deployment - 100% AWS Only

### Enforced Rules in System Prompt

The system prompt explicitly forbids local deployment:

```markdown
### ⚠️ CRITICAL: AWS-ONLY DEPLOYMENT (NON-NEGOTIABLE)

**NEVER deploy locally. ALWAYS deploy to AWS.**

- ❌ NEVER use `npm run dev` or `npm start` for "deployment"
- ❌ NEVER say "running on localhost" as a deployment
- ❌ NEVER serve files with `python -m http.server` or similar
- ✅ ALWAYS deploy to S3 + CloudFront
- ✅ ALWAYS provide a real CloudFront URL (https://dXXXXXX.cloudfront.net)

**Local development is ONLY for building/testing before AWS deployment.**

The task is NOT complete until the site is live on AWS CloudFront.
```

### Location
- **File:** `backend/system_prompt_generator.py`
- **Lines:** 336-348

---

## 9. Skills Imported from Career Builder

### Skills Location
Skills were imported from the career builder project into:
- `.claude/skills/aws/` - AWS deployment skills
- `.claude/skills/testing/` - Testing and verification skills
- `.claude/agents/deployers/` - Deployment agents

### Key Skills
| Skill | Path | Purpose |
|-------|------|---------|
| S3 Upload | `.claude/skills/aws/s3-upload.md` | Upload files to S3 |
| CloudFront Create | `.claude/skills/aws/cloudfront-create.md` | Create CDN distributions |
| CloudFront Invalidate | `.claude/skills/aws/cloudfront-invalidate.md` | Clear CDN cache |
| CORS Configuration | `.claude/skills/aws/cors-configuration.md` | Configure CORS headers |
| AWS S3 Static Deployer | `.claude/agents/deployers/aws-s3-static.md` | Full deployment agent |

### Source
Imported from: `C:\Projects\ai-product-studio` (career builder project)

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
