#!/bin/bash
#############################################
# DEPLOY SCRIPT - Reads credentials from
# environment variables and AWS CLI profile.
#
# Prerequisites:
#   export ANTHROPIC_API_KEY="your-key"
#   aws configure --profile cocreate
#
# Then run: bash DEPLOY-NOW.sh
#############################################

set -e

echo "============================================"
echo "Starting Lightsail Deployment"
echo "============================================"
echo ""

# Step 1: Validate Environment Variables
echo "Step 1/7: Checking environment variables..."

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY is not set."
    echo "Run: export ANTHROPIC_API_KEY=\"your-key\""
    exit 1
fi

export AWS_PROFILE="cocreate"
export AWS_REGION="us-east-1"
export AWS_ACCOUNT_ID="248825820556"
echo "* ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:0:12}..."
echo "* AWS_PROFILE: $AWS_PROFILE"
echo "* AWS_REGION: $AWS_REGION"

# Step 2: Validate AWS Credentials
echo ""
echo "Step 2/7: Checking AWS credentials..."

if ! aws sts get-caller-identity --profile cocreate > /dev/null 2>&1; then
    echo "ERROR: AWS profile 'cocreate' is not configured or credentials are invalid."
    echo "Run: aws configure --profile cocreate"
    exit 1
fi
echo "* AWS credentials valid"

# Step 3: Check Prerequisites
echo ""
echo "Step 4/7: Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    sudo apt-get update -qq
    sudo apt-get install -y docker.io
    sudo systemctl start docker
    sudo usermod -aG docker $USER
    echo "⚠️  Docker installed - run 'newgrp docker' then run this script again"
    exit 0
else
    echo "✓ Docker found"
fi

# Check jq
if ! command -v jq &> /dev/null; then
    echo "Installing jq..."
    sudo apt-get install -y jq
fi
echo "✓ jq found"

# Step 5: Create DynamoDB Table
echo ""
echo "============================================"
echo "Step 5/7: Creating DynamoDB table..."
echo "============================================"

TABLE_NAME="tmux-builder-sessions"

if aws dynamodb describe-table \
    --table-name "$TABLE_NAME" \
    --region us-east-1 \
    --profile cocreate >/dev/null 2>&1; then
    echo "✓ DynamoDB table already exists"
else
    echo "Creating table..."
    aws dynamodb create-table \
      --table-name "$TABLE_NAME" \
      --attribute-definitions \
        AttributeName=guid,AttributeType=S \
        AttributeName=email,AttributeType=S \
      --key-schema \
        AttributeName=guid,KeyType=HASH \
      --global-secondary-indexes \
        "IndexName=email-index,KeySchema=[{AttributeName=email,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=1,WriteCapacityUnits=1}" \
      --billing-mode PAY_PER_REQUEST \
      --region us-east-1 \
      --profile cocreate

    echo "Waiting for table..."
    aws dynamodb wait table-exists \
        --table-name "$TABLE_NAME" \
        --region us-east-1 \
        --profile cocreate

    echo "✓ DynamoDB table created"
fi

# Step 6: Build and Deploy
echo ""
echo "============================================"
echo "Step 6/7: Building and Deploying..."
echo "============================================"
echo ""
echo "This takes 15-20 minutes. Please wait..."
echo ""

SERVICE_NAME="tmux-builder"
CONTAINER_NAME="tmux-backend"
ECR_REPO="tmux-builder"
IMAGE_TAG="latest"

# Navigate to project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create ECR repository
echo "Checking ECR repository..."
if ! aws ecr describe-repositories \
    --repository-names "$ECR_REPO" \
    --region us-east-1 \
    --profile cocreate >/dev/null 2>&1; then
    echo "Creating ECR repository..."
    aws ecr create-repository \
        --repository-name "$ECR_REPO" \
        --region us-east-1 \
        --profile cocreate
    echo "✓ ECR repository created"
else
    echo "✓ ECR repository exists"
fi

# Build Docker image
echo ""
echo "Building Docker image (5-10 minutes)..."
docker build -t "$ECR_REPO:$IMAGE_TAG" . 2>&1 | grep -E "Step|Successfully|built" || true
echo "✓ Docker image built"

# Login to ECR
echo ""
echo "Logging into ECR..."
aws ecr get-login-password \
    --region us-east-1 \
    --profile cocreate | docker login \
    --username AWS \
    --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com" 2>&1 | grep -i "success" || true

# Tag and push
echo "Pushing image to ECR..."
docker tag "$ECR_REPO:$IMAGE_TAG" \
    "$AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/$ECR_REPO:$IMAGE_TAG"

docker push "$AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/$ECR_REPO:$IMAGE_TAG" 2>&1 | tail -5
echo "✓ Image pushed to ECR"

# Create Lightsail service
echo ""
echo "Checking Lightsail service..."
if ! aws lightsail get-container-services \
    --service-name "$SERVICE_NAME" \
    --region us-east-1 \
    --profile cocreate >/dev/null 2>&1; then
    echo "Creating Lightsail service..."
    aws lightsail create-container-service \
        --service-name "$SERVICE_NAME" \
        --power micro \
        --scale 1 \
        --region us-east-1 \
        --profile cocreate
    echo "Waiting 3 minutes for service..."
    sleep 180
    echo "✓ Service created"
else
    echo "✓ Service exists"
fi

# Deploy container
echo ""
echo "Deploying container..."

cat > /tmp/containers.json <<EOF
{
  "$CONTAINER_NAME": {
    "image": "$AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/$ECR_REPO:$IMAGE_TAG",
    "ports": {
      "8080": "HTTP",
      "8082": "HTTP"
    },
    "environment": {
      "LIGHTSAIL_DEPLOYMENT": "true",
      "AWS_REGION": "us-east-1",
      "DYNAMODB_TABLE": "tmux-builder-sessions",
      "ANTHROPIC_API_KEY": "$ANTHROPIC_API_KEY",
      "BACKEND_PORT": "8080",
      "PROGRESS_WS_PORT": "8082"
    }
  }
}
EOF

cat > /tmp/public-endpoint.json <<EOF
{
  "containerName": "$CONTAINER_NAME",
  "containerPort": 8080,
  "healthCheck": {
    "healthyThreshold": 2,
    "unhealthyThreshold": 2,
    "timeoutSeconds": 10,
    "intervalSeconds": 30,
    "path": "/health",
    "successCodes": "200"
  }
}
EOF

aws lightsail create-container-service-deployment \
    --service-name "$SERVICE_NAME" \
    --containers file:///tmp/containers.json \
    --public-endpoint file:///tmp/public-endpoint.json \
    --region us-east-1 \
    --profile cocreate

# Wait for deployment
echo ""
echo "Waiting for deployment (checking every 10 seconds)..."
for i in {1..30}; do
    STATUS=$(aws lightsail get-container-service-deployments \
        --service-name "$SERVICE_NAME" \
        --region us-east-1 \
        --profile cocreate \
        --query 'deployments[0].state' \
        --output text 2>/dev/null || echo "UNKNOWN")

    printf "[$i/30] Status: %-15s\r" "$STATUS"

    if [ "$STATUS" == "ACTIVE" ]; then
        echo ""
        echo "✓ Deployment successful!"
        break
    elif [ "$STATUS" == "FAILED" ]; then
        echo ""
        echo "❌ Deployment failed!"
        exit 1
    fi

    sleep 10
done

# Step 7: Get URL and Test
echo ""
echo "============================================"
echo "Step 7/7: Testing deployment..."
echo "============================================"

SERVICE_URL=$(aws lightsail get-container-services \
    --service-name "$SERVICE_NAME" \
    --region us-east-1 \
    --profile cocreate \
    --query 'containerServices[0].url' \
    --output text)

echo ""
echo "Waiting 30 seconds for service to fully start..."
sleep 30

echo "Testing health endpoint..."
if curl -f -s "https://$SERVICE_URL/health" > /dev/null; then
    echo "✓ Health check PASSED!"
else
    echo "⚠️  Health check failed (may need more time)"
fi

# Final output
echo ""
echo "============================================"
echo "🎉 DEPLOYMENT COMPLETE!"
echo "============================================"
echo ""
echo "Your Lightsail URL:"
echo "https://$SERVICE_URL"
echo ""
echo "Test it now:"
echo "  curl https://$SERVICE_URL/health"
echo ""
echo "Or open in browser:"
echo "  https://$SERVICE_URL"
echo ""
echo "Next steps:"
echo "1. Test the URL above"
echo "2. Update CloudFront (I'll help you with this)"
echo "3. Stop old EC2 instance"
echo ""
echo "Monthly cost: ~\$12 (down from \$30)"
echo "You're saving \$18/month! 💰"
echo ""
