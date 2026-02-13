# tmux-builder Lightsail Deployment Guide

## Overview

This guide walks you through deploying tmux-builder to AWS Lightsail Container Service at **$10/month**.

**Total Time:** 30-45 minutes

---

## Prerequisites

Before starting, ensure you have:

- [x] AWS CLI installed and configured
- [x] Docker installed and running
- [x] AWS profile `cocreate` configured
- [x] Anthropic API key
- [x] `jq` installed (for JSON processing)

```bash
# Verify prerequisites
aws --version
docker --version
jq --version
aws sts get-caller-identity --profile cocreate
```

---

## Step-by-Step Deployment

### Step 1: Set Environment Variables

```bash
# Required
export ANTHROPIC_API_KEY="your-anthropic-api-key-here"
export AWS_PROFILE="cocreate"
export AWS_REGION="us-east-1"
export AWS_ACCOUNT_ID="248825820556"

# Verify
echo "API Key: ${ANTHROPIC_API_KEY:0:10}..."
echo "Profile: $AWS_PROFILE"
echo "Region: $AWS_REGION"
```

### Step 2: Test Docker Build Locally (Optional but Recommended)

```bash
cd /mnt/c/Projects/tmux_Builder/tmux-builder

# Make script executable
chmod +x build-and-test-local.sh

# Build and test
./build-and-test-local.sh
```

This will:
- Build the Docker image
- Start a local container
- Test health endpoints
- Show logs

**Test the local deployment:**
- Health: http://localhost:8080/health
- Admin: http://localhost:8080/api/admin/sessions?filter=all

Press `Ctrl+C` to stop logs (container keeps running).

**Stop the test container:**
```bash
docker stop tmux-builder-test
docker rm tmux-builder-test
```

### Step 3: Set Up DynamoDB Table

```bash
cd deployment

# Make scripts executable
chmod +x setup-dynamodb.sh
chmod +x deploy-lightsail.sh
chmod +x update-cloudfront.sh

# Create DynamoDB table
./setup-dynamodb.sh
```

**Expected output:**
```
✓ Table created successfully!
Table: tmux-builder-sessions
Status: ACTIVE
```

### Step 4: Deploy to Lightsail

```bash
# Deploy (takes 5-10 minutes)
./deploy-lightsail.sh
```

**This script will:**
1. Create ECR repository
2. Build Docker image
3. Push to ECR
4. Create Lightsail container service ($10/month)
5. Deploy container
6. Wait for deployment to complete

**Expected output:**
```
✓ Deployment successful!
Service URL: https://tmux-builder.xxxxx.us-east-1.cs.amazonlightsail.com
```

**SAVE THIS URL** - you'll need it for the next step!

### Step 5: Test Lightsail Deployment

```bash
# Replace with your actual Lightsail URL
LIGHTSAIL_URL="tmux-builder.xxxxx.us-east-1.cs.amazonlightsail.com"

# Test health endpoint
curl https://$LIGHTSAIL_URL/health

# Expected: {"status":"healthy",...}

# Test admin endpoint
curl https://$LIGHTSAIL_URL/api/admin/sessions?filter=all

# Expected: {"sessions":[...]}
```

### Step 6: Update CloudFront to Use Lightsail

```bash
# Update CloudFront origin (replace with your Lightsail URL)
./update-cloudfront.sh tmux-builder.xxxxx.us-east-1.cs.amazonlightsail.com
```

**This script will:**
1. Get current CloudFront config
2. Update origin to Lightsail URL
3. Prompt for confirmation
4. Apply update
5. Create cache invalidation

**Confirm the update when prompted:**
```
Proceed with update? (yes/no): yes
```

**Wait 5-15 minutes** for CloudFront to propagate the changes.

### Step 7: Test Production URL

```bash
# Test CloudFront URL (wait 5-15 min after invalidation)
curl https://d3tfeatcbws1ka.cloudfront.net/health

# Expected: {"status":"healthy",...}

# Test in browser
# Open: https://d3tfeatcbws1ka.cloudfront.net/
```

### Step 8: Stop Old EC2 Instance

**Only after verifying everything works!**

```bash
# Stop EC2 (don't terminate yet - keep as backup)
aws ec2 stop-instances \
  --instance-ids i-02295df495905ba4b \
  --profile cocreate \
  --region us-east-1

# Verify stopped
aws ec2 describe-instances \
  --instance-ids i-02295df495905ba4b \
  --profile cocreate \
  --region us-east-1 \
  --query 'Reservations[0].Instances[0].State.Name' \
  --output text
```

### Step 9: Monitor for 48 Hours

Monitor Lightsail for 2 days before terminating EC2:

```bash
# View logs
aws lightsail get-container-log \
  --service-name tmux-builder \
  --container-name tmux-backend \
  --region us-east-1 \
  --profile cocreate

# Check metrics
aws lightsail get-container-service-metric-data \
  --service-name tmux-builder \
  --metric-name CPUUtilization \
  --start-time $(date -u -d '1 day ago' '+%Y-%m-%dT%H:%M:%S') \
  --end-time $(date -u '+%Y-%m-%dT%H:%M:%S') \
  --period 3600 \
  --statistics Average \
  --region us-east-1 \
  --profile cocreate
```

### Step 10: Terminate Old EC2 (After 48 Hours)

**Only if everything is working perfectly:**

```bash
# Terminate EC2 (PERMANENT - cannot be undone!)
aws ec2 terminate-instances \
  --instance-ids i-02295df495905ba4b \
  --profile cocreate \
  --region us-east-1
```

---

## Cost Verification

After 1 week, verify costs:

```bash
# Get Lightsail costs
aws lightsail get-cost-estimate \
  --service-name tmux-builder \
  --region us-east-1 \
  --profile cocreate
```

**Expected Monthly Costs:**
- Lightsail Container (Micro): $10.00
- DynamoDB (on-demand): ~$1.00
- CloudFront: ~$0.50
- S3: ~$0.30
- **Total: ~$11.80/month**

---

## Rollback Procedure

If anything goes wrong:

### Rollback Step 1: Start Old EC2

```bash
aws ec2 start-instances \
  --instance-ids i-02295df495905ba4b \
  --profile cocreate \
  --region us-east-1

# Wait for instance to start (2-3 minutes)
```

### Rollback Step 2: Revert CloudFront

```bash
# Get old EC2 IP
OLD_EC2_IP=$(aws ec2 describe-instances \
  --instance-ids i-02295df495905ba4b \
  --profile cocreate \
  --region us-east-1 \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo "Old EC2 IP: $OLD_EC2_IP"

# Manually update CloudFront origin back to EC2 IP
# Or use backup config: /tmp/cf-config-backup-*.json
```

### Rollback Step 3: Invalidate CloudFront

```bash
aws cloudfront create-invalidation \
  --distribution-id E2FOQ8U2IQP3GC \
  --paths "/*" \
  --profile cocreate
```

### Rollback Step 4: Delete Lightsail Service

```bash
# Stop Lightsail to avoid charges
aws lightsail delete-container-service \
  --service-name tmux-builder \
  --region us-east-1 \
  --profile cocreate
```

---

## Troubleshooting

### Issue: Docker build fails

```bash
# Check Docker is running
docker ps

# Try building with no cache
docker build --no-cache -t tmux-builder:latest .
```

### Issue: ECR push fails

```bash
# Re-authenticate to ECR
aws ecr get-login-password \
  --region us-east-1 \
  --profile cocreate | docker login \
  --username AWS \
  --password-stdin 248825820556.dkr.ecr.us-east-1.amazonaws.com
```

### Issue: Lightsail deployment fails

```bash
# Check deployment status
aws lightsail get-container-service-deployments \
  --service-name tmux-builder \
  --region us-east-1 \
  --profile cocreate

# View logs
aws lightsail get-container-log \
  --service-name tmux-builder \
  --container-name tmux-backend \
  --region us-east-1 \
  --profile cocreate
```

### Issue: Health check fails

```bash
# Check if service is running
aws lightsail get-container-services \
  --service-name tmux-builder \
  --region us-east-1 \
  --profile cocreate

# Check logs for errors
aws lightsail get-container-log \
  --service-name tmux-builder \
  --container-name tmux-backend \
  --region us-east-1 \
  --profile cocreate \
  | tail -50
```

### Issue: CloudFront still showing old site

```bash
# Check invalidation status
aws cloudfront list-invalidations \
  --distribution-id E2FOQ8U2IQP3GC \
  --profile cocreate

# Wait 15 minutes and try again
# CloudFront propagation takes time
```

---

## Useful Commands

### View Lightsail Status

```bash
aws lightsail get-container-services \
  --service-name tmux-builder \
  --region us-east-1 \
  --profile cocreate
```

### View Real-Time Logs

```bash
aws lightsail get-container-log \
  --service-name tmux-builder \
  --container-name tmux-backend \
  --region us-east-1 \
  --profile cocreate \
  --page-token "" \
  | jq -r '.logEvents[] | "\(.createdAt) \(.message)"'
```

### Update Container (After Code Changes)

```bash
# Just run deploy again
./deploy-lightsail.sh
```

### Scale Lightsail Service

```bash
# Scale to 2 containers (2x cost)
aws lightsail update-container-service \
  --service-name tmux-builder \
  --scale 2 \
  --region us-east-1 \
  --profile cocreate
```

---

## Support

If you encounter issues:

1. Check logs: `aws lightsail get-container-log ...`
2. Verify environment variables are set
3. Test locally with `build-and-test-local.sh`
4. Use rollback procedure if needed

---

## Next Steps After Deployment

1. ✅ Monitor for 48 hours
2. ✅ Verify cost in AWS Cost Explorer
3. ✅ Test all features (sessions, chat, WebSocket)
4. ✅ Update documentation with new URLs
5. ✅ Terminate old EC2 instance

**Congratulations! You're now running at $11.80/month instead of $34/month!**
