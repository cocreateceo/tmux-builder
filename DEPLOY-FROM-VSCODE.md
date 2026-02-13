# Deploy to Lightsail from VS Code (WSL Ubuntu)

## ✅ You're in the right place!

Since you opened this project in VS Code from WSL Ubuntu, you can deploy directly from the **VS Code integrated terminal**.

---

## 📋 Prerequisites Check

First, check if you have everything:

```bash
# Check Docker
docker --version

# Check AWS CLI
aws --version

# Check jq
jq --version
```

### If anything is missing:

```bash
# Install Docker
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl start docker
sudo usermod -aG docker $USER

# Install jq
sudo apt-get install -y jq

# Install AWS CLI (if needed)
sudo apt-get install -y awscli
```

**If you installed Docker:** You need to logout/login or run:
```bash
newgrp docker
```

---

## 🚀 Deployment Steps

### Step 1: Configure AWS Credentials

```bash
# Create AWS credentials directory
mkdir -p ~/.aws

# Create credentials file
cat > ~/.aws/credentials << 'EOF'
[cocreate]
aws_access_key_id = YOUR_AWS_ACCESS_KEY_ID
aws_secret_access_key = YOUR_AWS_SECRET_ACCESS_KEY
EOF

# Create config file
cat > ~/.aws/config << 'EOF'
[profile cocreate]
region = us-east-1
output = json
EOF

# Secure the credentials file
chmod 600 ~/.aws/credentials

echo "✓ AWS credentials configured"
```

### Step 2: Test AWS Connection

```bash
# Test AWS access
aws sts get-caller-identity --profile cocreate
```

**Expected output:**
```json
{
    "UserId": "...",
    "Account": "248825820556",
    "Arn": "arn:aws:iam::248825820556:user/..."
}
```

If you see this ✅ your AWS is working!

---

### Step 3: Set Environment Variables

```bash
# Set Anthropic API key (replace with your actual key)
export ANTHROPIC_API_KEY="sk-ant-api03-YOUR_KEY_HERE"

# Set AWS variables
export AWS_PROFILE="cocreate"
export AWS_REGION="us-east-1"
export AWS_ACCOUNT_ID="248825820556"

# Verify
echo "API Key set: ${ANTHROPIC_API_KEY:0:10}..."
echo "AWS Profile: $AWS_PROFILE"
echo "AWS Region: $AWS_REGION"
```

---

### Step 4: Navigate to Deployment Directory

```bash
cd deployment
pwd
# Should show: /mnt/c/Projects/tmux_Builder/tmux-builder/deployment
```

---

### Step 5: Create DynamoDB Table

```bash
# Run DynamoDB setup
bash setup-dynamodb.sh
```

**What happens:**
- Creates table: `tmux-builder-sessions`
- Takes ~2 minutes

**Expected output:**
```
✓ Table created successfully!
Table: tmux-builder-sessions
Status: ACTIVE
```

---

### Step 6: Deploy to Lightsail (Main Deployment)

```bash
# Run full deployment
bash deploy-lightsail.sh
```

**What happens:**
1. Creates ECR repository (30 seconds)
2. Builds Docker image (5 minutes)
3. Pushes to ECR (3 minutes)
4. Creates Lightsail service (3 minutes)
5. Deploys container (5 minutes)

**Total time: ~15-20 minutes**

**Watch for:**
```
Step 1: Checking ECR repository...
✓ ECR repository exists

Step 2: Building Docker image...
[+] Building 234.5s
✓ Image built

Step 3: Pushing to ECR...
latest: digest: sha256:... size: 2345
✓ Image pushed to ECR

Step 4: Checking Lightsail service...
✓ Service exists

Step 5: Creating deployment configuration...
✓ Config created

Step 6: Deploying container...
[1/30] Status: ACTIVATING
[2/30] Status: ACTIVATING
...
[15/30] Status: ACTIVE
✓ Deployment successful!

============================================
Deployment Complete!
============================================

Service URL: https://tmux-builder.xxxxx.us-east-1.cs.amazonlightsail.com
```

**🔥 SAVE THIS URL! You'll need it for the next step!**

---

### Step 7: Test Lightsail Deployment

```bash
# Test health endpoint (replace with YOUR Lightsail URL)
LIGHTSAIL_URL="tmux-builder.xxxxx.us-east-1.cs.amazonlightsail.com"

curl https://$LIGHTSAIL_URL/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "backend": "running",
  "websocket": "check port 8082",
  "timestamp": "2024-02-09T..."
}
```

If you see this ✅ Lightsail is working!

---

### Step 8: Update CloudFront to Use Lightsail

```bash
# Update CloudFront (replace with YOUR Lightsail URL)
bash update-cloudfront.sh tmux-builder.xxxxx.us-east-1.cs.amazonlightsail.com
```

**You'll see:**
```
============================================
Updating CloudFront Distribution
============================================

Step 1: Getting current distribution config...
✓ Current config retrieved

Step 2: Updating origin domain...
✓ Config updated with new origin

Changes:
----------------------------------------
Old origin: 18.211.207.2
New origin: tmux-builder.xxxxx.us-east-1.cs.amazonlightsail.com
----------------------------------------

Proceed with update? (yes/no):
```

**Type:** `yes` and press Enter

```
Step 3: Applying update...
✓ Update applied

Step 4: Creating cache invalidation...
✓ Invalidation created

============================================
CloudFront Update Complete!
============================================
```

---

### Step 9: Wait for CloudFront Propagation

**Wait 5-15 minutes** for CloudFront to update.

During this time, you can:
```bash
# Check invalidation status
aws cloudfront list-invalidations \
  --distribution-id E2FOQ8U2IQP3GC \
  --profile cocreate
```

---

### Step 10: Test Production URL

After 15 minutes:

```bash
# Test CloudFront URL
curl https://d3tfeatcbws1ka.cloudfront.net/health
```

**Or open in browser:**
https://d3tfeatcbws1ka.cloudfront.net/

If you see the site ✅ **Deployment successful!**

---

### Step 11: Stop Old EC2 Instance

**ONLY after verifying everything works!**

```bash
# Stop (don't terminate yet - keep as backup)
aws ec2 stop-instances \
  --instance-ids i-02295df495905ba4b \
  --profile cocreate \
  --region us-east-1

# Verify it stopped
aws ec2 describe-instances \
  --instance-ids i-02295df495905ba4b \
  --profile cocreate \
  --region us-east-1 \
  --query 'Reservations[0].Instances[0].State.Name' \
  --output text
```

**Expected:** `stopped`

---

### Step 12: Monitor for 48 Hours

Monitor Lightsail for 2 days:

```bash
# View live logs
aws lightsail get-container-log \
  --service-name tmux-builder \
  --container-name tmux-backend \
  --region us-east-1 \
  --profile cocreate \
  --start-time $(date -u -d '10 minutes ago' '+%s')

# Check service status
aws lightsail get-container-services \
  --service-name tmux-builder \
  --region us-east-1 \
  --profile cocreate
```

---

### Step 13: Terminate Old EC2 (After 48 Hours)

**Only if everything works perfectly:**

```bash
# Terminate EC2 (PERMANENT!)
aws ec2 terminate-instances \
  --instance-ids i-02295df495905ba4b \
  --profile cocreate \
  --region us-east-1
```

---

## 🎉 Done!

Your new costs will be:
- **Lightsail Container:** $10/month
- **DynamoDB:** ~$1/month
- **CloudFront + S3:** ~$1/month
- **Total:** ~$12/month (down from $30)

**Savings:** $18/month (60%)

---

## 🆘 Troubleshooting

### Issue: "docker: command not found"

```bash
# Install Docker
sudo apt-get update
sudo apt-get install -y docker.io
sudo systemctl start docker
sudo usermod -aG docker $USER

# Then logout/login or run:
newgrp docker
```

### Issue: "Permission denied" on docker commands

```bash
# Add yourself to docker group
sudo usermod -aG docker $USER
newgrp docker

# Or run with sudo (not recommended)
sudo bash deploy-lightsail.sh
```

### Issue: ECR push fails "authentication required"

```bash
# Re-authenticate to ECR
aws ecr get-login-password \
  --region us-east-1 \
  --profile cocreate | docker login \
  --username AWS \
  --password-stdin 248825820556.dkr.ecr.us-east-1.amazonaws.com
```

### Issue: Lightsail deployment stuck on "ACTIVATING"

```bash
# Check logs for errors
aws lightsail get-container-log \
  --service-name tmux-builder \
  --container-name tmux-backend \
  --region us-east-1 \
  --profile cocreate
```

### Issue: Health check fails

```bash
# Check if container is running
aws lightsail get-container-services \
  --service-name tmux-builder \
  --region us-east-1 \
  --profile cocreate \
  --query 'containerServices[0].state'

# View recent logs
aws lightsail get-container-log \
  --service-name tmux-builder \
  --container-name tmux-backend \
  --region us-east-1 \
  --profile cocreate \
  | tail -50
```

### Issue: CloudFront still showing old site

```bash
# Wait 15 minutes - CloudFront takes time to propagate
# Force clear browser cache: Ctrl+F5

# Check invalidation status
aws cloudfront list-invalidations \
  --distribution-id E2FOQ8U2IQP3GC \
  --profile cocreate
```

---

## 🔄 Rollback Procedure

If something goes wrong:

### 1. Start old EC2
```bash
aws ec2 start-instances \
  --instance-ids i-02295df495905ba4b \
  --profile cocreate \
  --region us-east-1
```

### 2. Revert CloudFront
```bash
# Get old EC2 IP
OLD_IP=$(aws ec2 describe-instances \
  --instance-ids i-02295df495905ba4b \
  --profile cocreate \
  --region us-east-1 \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo "Old EC2 IP: $OLD_IP"

# Update CloudFront back to EC2
bash update-cloudfront.sh $OLD_IP
```

### 3. Delete Lightsail (to stop charges)
```bash
aws lightsail delete-container-service \
  --service-name tmux-builder \
  --region us-east-1 \
  --profile cocreate
```

---

## 📊 Monitor Costs

After 1 week:

```bash
# Check current month costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '1 day ago' '+%Y-%m-01'),End=$(date '+%Y-%m-%d') \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --profile cocreate
```

**Expected: ~$12/month**

---

## ✅ Deployment Checklist

- [ ] AWS credentials configured
- [ ] Anthropic API key set
- [ ] Docker installed and running
- [ ] DynamoDB table created
- [ ] Lightsail deployed
- [ ] Lightsail URL tested
- [ ] CloudFront updated
- [ ] Production URL tested
- [ ] Old EC2 stopped
- [ ] Monitored for 48 hours
- [ ] Old EC2 terminated

---

## 📞 Quick Reference

**CloudFront Distribution:** E2FOQ8U2IQP3GC
**Production URL:** https://d3tfeatcbws1ka.cloudfront.net
**DynamoDB Table:** tmux-builder-sessions
**Lightsail Service:** tmux-builder
**Old EC2 ID:** i-02295df495905ba4b

---

**Good luck with your deployment!** 🚀
