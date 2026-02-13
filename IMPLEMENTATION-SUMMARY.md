# Lightsail Implementation - Complete! ✅

## What We've Created

All files for Lightsail deployment have been created and are ready to use:

### Core Files
- ✅ `Dockerfile` - Container definition with Node.js, Python, Claude CLI
- ✅ `start.sh` - Container startup script (starts FastAPI + WebSocket)
- ✅ `.dockerignore` - Optimizes Docker build size
- ✅ `backend/config.py` - Updated for Lightsail environment detection

### Deployment Scripts (in `deployment/` folder)
- ✅ `setup-dynamodb.sh` - Creates DynamoDB table for session storage
- ✅ `deploy-lightsail.sh` - Full Lightsail deployment automation
- ✅ `update-cloudfront.sh` - Updates CloudFront to use Lightsail
- ✅ `quick-start.sh` - Interactive menu for all deployment steps
- ✅ `DEPLOY.md` - Complete step-by-step deployment guide

### Testing
- ✅ `build-and-test-local.sh` - Test Docker image locally before deploying

---

## 🚀 Ready to Deploy!

### Option 1: Interactive Menu (Easiest)

```bash
cd C:/Projects/tmux_Builder/tmux-builder/deployment

# Set your API key
export ANTHROPIC_API_KEY="your-key-here"

# Run interactive menu
bash quick-start.sh
```

The menu will guide you through:
1. Testing locally
2. Setting up DynamoDB
3. Deploying to Lightsail
4. Updating CloudFront

---

### Option 2: Manual Step-by-Step

#### Step 1: Set Environment Variables

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
export AWS_PROFILE="cocreate"
export AWS_REGION="us-east-1"
export AWS_ACCOUNT_ID="248825820556"
```

#### Step 2: Test Locally (Optional)

```bash
cd C:/Projects/tmux_Builder/tmux-builder
bash build-and-test-local.sh
```

This builds the Docker image and tests it locally on ports 8080 and 8082.

#### Step 3: Set Up DynamoDB

```bash
cd deployment
bash setup-dynamodb.sh
```

Creates the `tmux-builder-sessions` table for storing session state.

#### Step 4: Deploy to Lightsail

```bash
bash deploy-lightsail.sh
```

This will:
- Create ECR repository
- Build and push Docker image
- Create Lightsail container service
- Deploy the container
- **Takes 5-10 minutes**

**IMPORTANT:** Save the Lightsail URL from the output!

#### Step 5: Test Lightsail Deployment

```bash
# Replace with your actual URL
LIGHTSAIL_URL="tmux-builder.xxxxx.us-east-1.cs.amazonlightsail.com"

curl https://$LIGHTSAIL_URL/health
curl https://$LIGHTSAIL_URL/api/admin/sessions?filter=all
```

#### Step 6: Update CloudFront

```bash
bash update-cloudfront.sh tmux-builder.xxxxx.us-east-1.cs.amazonlightsail.com
```

Type `yes` when prompted to confirm.

Wait **5-15 minutes** for CloudFront to propagate.

#### Step 7: Test Production URL

```bash
curl https://d3tfeatcbws1ka.cloudfront.net/health
```

Open in browser: https://d3tfeatcbws1ka.cloudfront.net/

#### Step 8: Stop Old EC2

**Only after verifying everything works!**

```bash
aws ec2 stop-instances \
  --instance-ids i-02295df495905ba4b \
  --profile cocreate \
  --region us-east-1
```

#### Step 9: Monitor for 48 Hours

```bash
# View logs
aws lightsail get-container-log \
  --service-name tmux-builder \
  --container-name tmux-backend \
  --region us-east-1 \
  --profile cocreate
```

#### Step 10: Terminate EC2 (After 48 Hours)

```bash
aws ec2 terminate-instances \
  --instance-ids i-02295df495905ba4b \
  --profile cocreate \
  --region us-east-1
```

---

## 💰 Expected Cost Savings

### Current Costs
- EC2 t3.medium: $30/month
- EBS: $4/month
- **Total: $34/month**

### New Costs (Lightsail)
- Lightsail Container (Micro): $10/month
- DynamoDB: ~$1/month
- CloudFront: ~$0.50/month
- S3: ~$0.30/month
- **Total: ~$11.80/month**

### Savings
**$22.20/month (65% reduction)**
**$266/year saved**

---

## 📋 Checklist

Before deploying, ensure you have:

- [ ] Docker installed and running
- [ ] AWS CLI installed
- [ ] `jq` installed (for JSON processing)
- [ ] AWS profile `cocreate` configured
- [ ] Anthropic API key ready
- [ ] Backed up important data from EC2

---

## 🆘 Troubleshooting

### Docker Build Fails
```bash
# Try building with no cache
docker build --no-cache -t tmux-builder:latest .
```

### ECR Push Fails
```bash
# Re-authenticate
aws ecr get-login-password --region us-east-1 --profile cocreate | \
  docker login --username AWS --password-stdin \
  248825820556.dkr.ecr.us-east-1.amazonaws.com
```

### Health Check Fails
```bash
# Check logs
aws lightsail get-container-log \
  --service-name tmux-builder \
  --container-name tmux-backend \
  --region us-east-1 \
  --profile cocreate
```

### Need to Rollback?
See **Rollback Procedure** in `deployment/DEPLOY.md`

---

## 📚 Documentation

- **Full Deployment Guide:** `deployment/DEPLOY.md`
- **CloudFront Distribution:** E2FOQ8U2IQP3GC
- **DynamoDB Table:** tmux-builder-sessions
- **Lightsail Service:** tmux-builder
- **Production URL:** https://d3tfeatcbws1ka.cloudfront.net

---

## 🎯 Next Steps

1. **Start with:** `cd deployment && bash quick-start.sh`
2. **Follow the menu** - it will guide you through everything
3. **Test thoroughly** before stopping EC2
4. **Monitor for 48 hours** before terminating EC2
5. **Enjoy 65% cost savings!**

---

## ✅ What's Different from EC2?

| Aspect | EC2 | Lightsail |
|--------|-----|-----------|
| **Management** | You manage OS, security, updates | AWS manages everything |
| **Scaling** | Manual | Automatic |
| **Load Balancer** | $16/month extra | Included free |
| **SSL/TLS** | Configure yourself | Automatic |
| **Pricing** | By the hour | Fixed monthly |
| **Monitoring** | CloudWatch setup needed | Built-in dashboard |

---

## 🔐 Security Notes

- Anthropic API key stored in environment variables (not in code)
- DynamoDB uses on-demand billing (no exposed data at rest)
- Lightsail provides automatic SSL/TLS
- CloudFront provides DDoS protection
- Sessions stored in private DynamoDB table

---

## 📊 Architecture Comparison

### Before (EC2):
```
Browser → CloudFront → EC2 (t3.medium) → Claude CLI
                         ↓
                      DynamoDB
```
**Cost: $34/month**

### After (Lightsail):
```
Browser → CloudFront → Lightsail Container (Micro) → Claude CLI
                              ↓
                          DynamoDB
```
**Cost: $11.80/month**

---

## 🎉 You're Ready!

All files are in place. Just run:

```bash
cd C:/Projects/tmux_Builder/tmux-builder/deployment
export ANTHROPIC_API_KEY="your-key"
bash quick-start.sh
```

**Good luck with your deployment!**
