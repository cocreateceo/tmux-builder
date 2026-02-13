# 1-Click Deploy + DynamoDB Tracking - Implementation Plan

> **For Claude:** Implement this feature in tmux-builder to auto-deploy projects and track AWS resources in DynamoDB.

## Overview

When a user creates a new project in Tmux Builder:
1. Claude Code builds the app
2. **Auto-triggers 1-click-deploy** to create AWS resources
3. Resources named with `{project-guid}` for identification
4. All resource info saved to **DynamoDB**

---

## Architecture

```
User Request → Tmux Builder → Claude Code
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
              Build App                    1-Click Deploy
              (existing)                   (new skill)
                    │                             │
                    │                             ▼
                    │                    Create AWS Resources
                    │                    - S3: tmux-{guid}
                    │                    - CloudFront
                    │                    - ECR, ECS, RDS (optional)
                    │                             │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                            notify.sh resources
                                   │
                                   ▼
                            Backend saves to DynamoDB
                                   │
                                   ▼
                            Client UI shows resources
```

---

## Phase 1: Import 1-Click-Deploy Skills

### Step 1.1: Create Skills Directory

```bash
mkdir -p .claude/skills/1-click-deploy/skills
```

### Step 1.2: Create Main Skill File

**File:** `.claude/skills/1-click-deploy/SKILL.md`

```markdown
# 1-Click Deploy Skill

Deploy the built application to AWS with auto-provisioned resources.

## Trigger

This skill runs automatically after project build completes.

## Process

1. **Validate Build**
   - Check frontend build exists (dist/ or build/)
   - Check backend is runnable

2. **Create AWS Resources**
   - S3 bucket: `tmux-{project-guid}`
   - CloudFront distribution pointing to S3
   - (Optional) ECR, ECS, RDS for full-stack apps

3. **Deploy Code**
   - Upload frontend to S3
   - Invalidate CloudFront cache

4. **Report Resources**
   - Call `./notify.sh resources <json>` with all resource ARNs/URLs

## Resource Naming Convention

All resources use project GUID for identification:
- S3: `tmux-builder-{guid}`
- CloudFront: Comment includes `tmux-{guid}`
- ECR: `tmux-{guid}-backend`, `tmux-{guid}-frontend`

## Commands

### Static Site (S3 + CloudFront)
```bash
# Create S3 bucket
aws s3 mb s3://tmux-builder-{guid} --region us-east-1

# Enable static website hosting
aws s3 website s3://tmux-builder-{guid} --index-document index.html --error-document index.html

# Upload frontend
aws s3 sync ./frontend/dist s3://tmux-builder-{guid} --delete

# Create CloudFront
aws cloudfront create-distribution --origin-domain-name tmux-builder-{guid}.s3.amazonaws.com
```

### Full Stack (ECR + ECS)
See aws-deployment-checklist.md for full infrastructure.

## Output

After deployment, call notify.sh:
```bash
./notify.sh resources '{
  "s3Bucket": "tmux-builder-{guid}",
  "cloudFrontId": "E1234567890",
  "cloudFrontUrl": "https://d123.cloudfront.net",
  "region": "us-east-1"
}'
```
```

### Step 1.3: Create Deployment Checklist

**File:** `.claude/skills/1-click-deploy/aws-deployment-checklist.md`

```markdown
# AWS Deployment Checklist

## Pre-Deployment Checks

- [ ] AWS CLI configured (`aws sts get-caller-identity`)
- [ ] Frontend builds successfully (`npm run build`)
- [ ] Backend runs without errors

## Static Site Deployment

### 1. Create S3 Bucket
```bash
GUID="${PROJECT_GUID}"
BUCKET="tmux-builder-${GUID}"

aws s3 mb s3://${BUCKET} --region us-east-1

aws s3api put-bucket-policy --bucket ${BUCKET} --policy '{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::'${BUCKET}'/*"
  }]
}'

aws s3 website s3://${BUCKET} --index-document index.html --error-document index.html
```

### 2. Upload Frontend
```bash
aws s3 sync ./frontend/dist s3://${BUCKET} --delete --cache-control "max-age=31536000"
aws s3 cp s3://${BUCKET}/index.html s3://${BUCKET}/index.html --cache-control "no-cache"
```

### 3. Create CloudFront Distribution
```bash
aws cloudfront create-distribution \
  --origin-domain-name ${BUCKET}.s3.amazonaws.com \
  --default-root-object index.html \
  --comment "tmux-builder-${GUID}"
```

### 4. Report Resources
```bash
./notify.sh resources '{"s3Bucket":"'${BUCKET}'","cloudFrontUrl":"https://..."}'
```

## Full Stack Deployment

For apps requiring backend:
1. Create ECR repositories
2. Build and push Docker images
3. Deploy ECS/Fargate services
4. Setup RDS database
5. Configure ALB
6. Create CloudFront distribution

See CareerBuilder 1-click-deploy for full Terraform setup.
```

### Step 1.4: Create Sub-Skills

**File:** `.claude/skills/1-click-deploy/skills/static-site-deploy.md`

```markdown
# Static Site Deploy

Deploy frontend-only projects to S3 + CloudFront.

## When to Use
- React/Vue/Angular apps without backend
- Landing pages
- Documentation sites

## Steps
1. Build frontend: `npm run build`
2. Create S3 bucket with website hosting
3. Upload dist/ to S3
4. Create CloudFront distribution
5. Report deployed URL via notify.sh
```

**File:** `.claude/skills/1-click-deploy/skills/fullstack-deploy.md`

```markdown
# Full Stack Deploy

Deploy full applications with backend to ECS + RDS.

## When to Use
- Apps with API backend
- Apps requiring database
- Apps with authentication

## Steps
1. Create ECR repositories
2. Build Docker images
3. Push to ECR
4. Apply Terraform (VPC, ECS, RDS, ALB)
5. Create CloudFront
6. Report all resources via notify.sh
```

---

## Phase 2: Update System Prompt

### Step 2.1: Modify system_prompt_generator.py

**File:** `backend/system_prompt_generator.py`

Add to the system prompt:

```python
# Add after existing instructions

DEPLOY_INSTRUCTIONS = """
## Auto-Deployment

After building the application successfully:

1. **Determine deployment type:**
   - Static site (frontend only) → Use static-site-deploy skill
   - Full stack (frontend + backend) → Use fullstack-deploy skill

2. **Create AWS resources with project GUID:**
   - S3 bucket: `tmux-builder-{guid}`
   - CloudFront distribution
   - Other resources as needed

3. **Report resources after deployment:**
   ```bash
   ./notify.sh resources '{
     "s3Bucket": "bucket-name",
     "cloudFrontId": "distribution-id",
     "cloudFrontUrl": "https://xxx.cloudfront.net",
     "region": "us-east-1"
   }'
   ```

4. **Then call done:**
   ```bash
   ./notify.sh done
   ```

The project GUID is: {guid}
"""
```

### Step 2.2: Update generate_prompt function

```python
def generate_prompt(guid, initial_request, client_info=None):
    # ... existing code ...

    # Add deployment instructions
    prompt += DEPLOY_INSTRUCTIONS.format(guid=guid)

    return prompt
```

---

## Phase 3: Update notify.sh Template

### Step 3.1: Modify notify_template.sh

**File:** `backend/templates/notify_template.sh`

Add new event type:

```bash
#!/bin/bash
# notify.sh - Send progress updates to WebSocket server

GUID="{guid}"
WS_SERVER="http://localhost:8082"

case "$1" in
    ack|status|error|done|summary|deployed)
        curl -s -X POST "$WS_SERVER/notify" \
            -H "Content-Type: application/json" \
            -d "{\"guid\":\"$GUID\",\"type\":\"$1\",\"message\":\"$2\"}"
        ;;
    resources)
        # New: Send AWS resource info as JSON
        curl -s -X POST "$WS_SERVER/notify" \
            -H "Content-Type: application/json" \
            -d "{\"guid\":\"$GUID\",\"type\":\"resources\",\"data\":$2}"
        ;;
    *)
        echo "Usage: $0 {ack|status|error|done|summary|deployed|resources} [message/json]"
        exit 1
        ;;
esac
```

---

## Phase 4: Backend - DynamoDB Integration

### Step 4.1: Create DynamoDB Table

**AWS CLI command:**

```bash
aws dynamodb create-table \
    --table-name tmux-deployments \
    --attribute-definitions \
        AttributeName=userId,AttributeType=S \
        AttributeName=projectId,AttributeType=S \
    --key-schema \
        AttributeName=userId,KeyType=HASH \
        AttributeName=projectId,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

### Step 4.2: Create DynamoDB Client

**File:** `backend/dynamodb_client.py`

```python
import boto3
from datetime import datetime
from typing import Optional, Dict, Any, List

class DynamoDBClient:
    def __init__(self, table_name: str = "tmux-deployments", region: str = "us-east-1"):
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)

    def save_project_resources(
        self,
        user_id: str,
        project_id: str,
        project_name: str,
        aws_resources: Dict[str, Any]
    ) -> bool:
        """Save or update project AWS resources."""
        try:
            self.table.put_item(Item={
                'userId': user_id,
                'projectId': project_id,
                'projectName': project_name,
                'awsResources': aws_resources,
                'createdAt': datetime.utcnow().isoformat(),
                'updatedAt': datetime.utcnow().isoformat()
            })
            return True
        except Exception as e:
            print(f"DynamoDB error: {e}")
            return False

    def get_project_resources(self, user_id: str, project_id: str) -> Optional[Dict]:
        """Get resources for a specific project."""
        try:
            response = self.table.get_item(Key={
                'userId': user_id,
                'projectId': project_id
            })
            return response.get('Item')
        except Exception as e:
            print(f"DynamoDB error: {e}")
            return None

    def get_user_projects(self, user_id: str) -> List[Dict]:
        """Get all projects for a user."""
        try:
            response = self.table.query(
                KeyConditionExpression='userId = :uid',
                ExpressionAttributeValues={':uid': user_id}
            )
            return response.get('Items', [])
        except Exception as e:
            print(f"DynamoDB error: {e}")
            return []

    def update_resources(
        self,
        user_id: str,
        project_id: str,
        aws_resources: Dict[str, Any]
    ) -> bool:
        """Update AWS resources for existing project."""
        try:
            self.table.update_item(
                Key={
                    'userId': user_id,
                    'projectId': project_id
                },
                UpdateExpression='SET awsResources = :res, updatedAt = :upd',
                ExpressionAttributeValues={
                    ':res': aws_resources,
                    ':upd': datetime.utcnow().isoformat()
                }
            )
            return True
        except Exception as e:
            print(f"DynamoDB error: {e}")
            return False
```

### Step 4.3: Update ws_server.py

**File:** `backend/ws_server.py`

Add handler for resources event:

```python
from dynamodb_client import DynamoDBClient

# Initialize DynamoDB client
dynamo = DynamoDBClient()

async def handle_notify(request):
    data = await request.json()
    guid = data.get('guid')
    event_type = data.get('type')

    # ... existing handling ...

    if event_type == 'resources':
        # Save AWS resources to DynamoDB
        resource_data = data.get('data', {})

        # Get user_id from session (need to look up from guid)
        session_info = get_session_info(guid)  # Implement this
        user_id = session_info.get('user_id', 'unknown')
        project_name = session_info.get('project_name', 'Unnamed Project')

        dynamo.save_project_resources(
            user_id=user_id,
            project_id=guid,
            project_name=project_name,
            aws_resources=resource_data
        )

        # Broadcast to WebSocket clients
        await broadcast_to_guid(guid, {
            'type': 'resources',
            'data': resource_data
        })

    # ... rest of handling ...
```

### Step 4.4: Add API Endpoints

**File:** `backend/main.py`

Add new endpoints:

```python
from dynamodb_client import DynamoDBClient

dynamo = DynamoDBClient()

@app.get("/api/projects/{guid}/resources")
async def get_project_resources(guid: str):
    """Get AWS resources for a project."""
    # Get user_id from session
    session = get_session(guid)
    if not session:
        raise HTTPException(status_code=404, detail="Project not found")

    resources = dynamo.get_project_resources(
        user_id=session.get('user_id', 'unknown'),
        project_id=guid
    )

    return {"resources": resources}

@app.get("/api/users/{user_id}/deployments")
async def get_user_deployments(user_id: str):
    """Get all deployments for a user."""
    projects = dynamo.get_user_projects(user_id)
    return {"projects": projects}
```

---

## Phase 5: Client UI - Show Resources

### Step 5.1: Add Resources Panel Component

**File:** `frontend/src/client/components/ResourcesPanel.jsx`

```jsx
import { useState, useEffect } from 'react';
import { Cloud, Database, Globe, Server, ExternalLink } from 'lucide-react';

export function ResourcesPanel({ guid }) {
  const [resources, setResources] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!guid) return;

    fetch(`/api/projects/${guid}/resources`)
      .then(res => res.json())
      .then(data => {
        setResources(data.resources?.awsResources);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [guid]);

  if (loading) return <div>Loading resources...</div>;
  if (!resources) return null;

  return (
    <div className="p-4 rounded-lg border" style={{
      background: 'var(--bg-secondary)',
      borderColor: 'var(--border-color)'
    }}>
      <h3 className="font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>
        AWS Resources
      </h3>

      <div className="space-y-2">
        {resources.s3Bucket && (
          <ResourceItem
            icon={<Database className="w-4 h-4" />}
            label="S3 Bucket"
            value={resources.s3Bucket}
          />
        )}

        {resources.cloudFrontUrl && (
          <ResourceItem
            icon={<Globe className="w-4 h-4" />}
            label="CloudFront"
            value={resources.cloudFrontUrl}
            isLink
          />
        )}

        {resources.ecsCluster && (
          <ResourceItem
            icon={<Server className="w-4 h-4" />}
            label="ECS Cluster"
            value={resources.ecsCluster}
          />
        )}

        {resources.rdsEndpoint && (
          <ResourceItem
            icon={<Database className="w-4 h-4" />}
            label="RDS Database"
            value={resources.rdsEndpoint}
          />
        )}
      </div>
    </div>
  );
}

function ResourceItem({ icon, label, value, isLink }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span style={{ color: 'var(--text-muted)' }}>{icon}</span>
      <span style={{ color: 'var(--text-secondary)' }}>{label}:</span>
      {isLink ? (
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
        >
          {value} <ExternalLink className="w-3 h-3" />
        </a>
      ) : (
        <span style={{ color: 'var(--text-primary)' }}>{value}</span>
      )}
    </div>
  );
}
```

### Step 5.2: Add to Project View

Update `ChatPanel.jsx` or create new view to include ResourcesPanel.

---

## Phase 6: Testing

### Test 1: Skill Loading
```bash
# Verify skills are accessible
ls -la .claude/skills/1-click-deploy/
```

### Test 2: DynamoDB Connection
```python
from dynamodb_client import DynamoDBClient
client = DynamoDBClient()
client.save_project_resources("test-user", "test-project", "Test", {"s3": "test"})
print(client.get_user_projects("test-user"))
```

### Test 3: End-to-End
1. Create new project in UI
2. Watch Activity panel for deployment steps
3. Verify AWS resources created
4. Check DynamoDB for saved resources
5. Verify UI shows resources

---

## Summary

| Component | Change |
|-----------|--------|
| `.claude/skills/1-click-deploy/` | New skill files |
| `backend/system_prompt_generator.py` | Add deploy instructions |
| `backend/templates/notify_template.sh` | Add `resources` event |
| `backend/dynamodb_client.py` | New DynamoDB client |
| `backend/ws_server.py` | Handle resources event |
| `backend/main.py` | Add resources API endpoints |
| `frontend/src/client/components/ResourcesPanel.jsx` | New UI component |

**DynamoDB Table:** `tmux-deployments`
- Partition Key: `userId`
- Sort Key: `projectId`
- Attributes: `projectName`, `awsResources`, `createdAt`, `updatedAt`
