#!/bin/bash
# Complete Lightsail Deployment Script
# Run this in WSL Ubuntu

set -e

echo "============================================"
echo "Starting Lightsail Deployment"
echo "============================================"
echo ""

# Step 1: Set AWS credentials
echo "Setting up AWS credentials..."
mkdir -p ~/.aws

cat > ~/.aws/credentials << 'EOF'
[cocreate]
aws_access_key_id = YOUR_AWS_ACCESS_KEY_ID
aws_secret_access_key = YOUR_AWS_SECRET_ACCESS_KEY
EOF

cat > ~/.aws/config << 'EOF'
[profile cocreate]
region = us-east-1
output = json
EOF

chmod 600 ~/.aws/credentials
echo "✓ AWS credentials configured"

# Step 2: Set environment variables
echo ""
echo "Enter your Anthropic API key:"
read -s ANTHROPIC_API_KEY
export ANTHROPIC_API_KEY
export AWS_PROFILE="cocreate"
export AWS_REGION="us-east-1"
export AWS_ACCOUNT_ID="248825820556"

# Step 3: Test AWS access
echo ""
echo "Testing AWS access..."
aws sts get-caller-identity --profile cocreate
echo "✓ AWS access confirmed"

# Step 4: Check prerequisites
echo ""
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    sudo apt-get update
    sudo apt-get install -y docker.io
    sudo systemctl start docker
    sudo usermod -aG docker $USER
    echo "⚠️  Docker installed - you may need to logout/login for docker group to take effect"
    echo "After logout/login, run this script again"
    exit 0
fi
echo "✓ Docker found"

if ! command -v jq &> /dev/null; then
    echo "Installing jq..."
    sudo apt-get install -y jq
fi
echo "✓ jq found"

# Step 5: Navigate to project
cd /mnt/c/Projects/tmux_Builder/tmux-builder/deployment

# Step 6: Set up DynamoDB
echo ""
echo "============================================"
echo "Step 1: Creating DynamoDB table"
echo "============================================"
bash setup-dynamodb.sh

# Step 7: Deploy to Lightsail
echo ""
echo "============================================"
echo "Step 2: Deploying to Lightsail"
echo "============================================"
bash deploy-lightsail.sh

echo ""
echo "============================================"
echo "Deployment Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Test the Lightsail URL (shown above)"
echo "2. Update CloudFront (run update-cloudfront.sh)"
echo "3. Test production URL"
echo "4. Stop old EC2 instance"
echo ""
