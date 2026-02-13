#!/bin/bash
#############################################
# ONE-COMMAND LIGHTSAIL DEPLOYMENT
# Just run: bash DEPLOY-ONE-COMMAND.sh
#############################################

set -e

echo "============================================"
echo "🚀 Starting Automatic Lightsail Deployment"
echo "============================================"
echo ""

# Check if running in WSL
if ! grep -qi microsoft /proc/version 2>/dev/null; then
    echo "⚠️  Warning: Not running in WSL. Please run this in WSL Ubuntu."
    echo "Press Ctrl+C to cancel, or Enter to continue anyway..."
    read
fi

# Step 1: Configure AWS Credentials
echo "Step 1/8: Configuring AWS credentials..."
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

# Step 2: Set Environment Variables
echo ""
echo "Step 2/8: Setting environment variables..."

# Check if Anthropic API key is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo ""
    echo "⚠️  ANTHROPIC_API_KEY not set!"
    echo ""
    echo "Please enter your Anthropic API key:"
    echo "(It will not be displayed as you type)"
    read -s ANTHROPIC_API_KEY
    echo ""

    if [ -z "$ANTHROPIC_API_KEY" ]; then
        echo "❌ Error: API key is required!"
        exit 1
    fi
fi

export ANTHROPIC_API_KEY
export AWS_PROFILE="cocreate"
export AWS_REGION="us-east-1"
export AWS_ACCOUNT_ID="248825820556"

echo "✓ Environment variables set"

# Step 3: Test AWS Connection
echo ""
echo "Step 3/8: Testing AWS connection..."
if aws sts get-caller-identity --profile cocreate > /dev/null 2>&1; then
    echo "✓ AWS connection successful"
else
    echo "❌ AWS connection failed! Check credentials."
    exit 1
fi

# Step 4: Check Prerequisites
echo ""
echo "Step 4/8: Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    sudo apt-get update -qq
    sudo apt-get install -y docker.io
    sudo systemctl start docker
    sudo usermod -aG docker $USER
    echo "✓ Docker installed (you may need to logout/login)"
    echo ""
    echo "After logout/login, run this script again."
    exit 0
else
    echo "✓ Docker found"
fi

# Check jq
if ! command -v jq &> /dev/null; then
    echo "Installing jq..."
    sudo apt-get update -qq
    sudo apt-get install -y jq
    echo "✓ jq installed"
else
    echo "✓ jq found"
fi

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "Installing AWS CLI..."
    sudo apt-get update -qq
    sudo apt-get install -y awscli
    echo "✓ AWS CLI installed"
else
    echo "✓ AWS CLI found"
fi

# Step 5: Navigate to Project
echo ""
echo "Step 5/8: Navigating to project..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
echo "✓ In directory: $(pwd)"

# Step 6: Create DynamoDB Table
echo ""
echo "============================================"
echo "Step 6/8: Creating DynamoDB table..."
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

    echo "Waiting for table to be active..."
    aws dynamodb wait table-exists \
        --table-name "$TABLE_NAME" \
        --region us-east-1 \
        --profile cocreate

    echo "✓ DynamoDB table created"
fi

# Step 7: Deploy to Lightsail
echo ""
echo "============================================"
echo "Step 7/8: Deploying to Lightsail..."
echo "============================================"
echo ""
echo "This will take 15-20 minutes..."
echo ""

SERVICE_NAME="tmux-builder"
CONTAINER_NAME="tmux-backend"
ECR_REPO="tmux-builder"
IMAGE_TAG="latest"

# Create ECR repository if needed
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
echo "Building Docker image (this takes 5-10 minutes)..."
cd "$SCRIPT_DIR/.."
docker build -t "$ECR_REPO:$IMAGE_TAG" .
echo "✓ Docker image built"

# Push to ECR
echo ""
echo "Pushing to ECR..."
aws ecr get-login-password \
    --region us-east-1 \
    --profile cocreate | docker login \
    --username AWS \
    --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com"

docker tag "$ECR_REPO:$IMAGE_TAG" \
    "$AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/$ECR_REPO:$IMAGE_TAG"

docker push "$AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/$ECR_REPO:$IMAGE_TAG"
echo "✓ Image pushed to ECR"

# Create Lightsail service if needed
echo ""
echo "Checking Lightsail service..."
if ! aws lightsail get-container-services \
    --service-name "$SERVICE_NAME" \
    --region us-east-1 \
    --profile cocreate >/dev/null 2>&1; then

    echo "Creating Lightsail container service..."
    aws lightsail create-container-service \
        --service-name "$SERVICE_NAME" \
        --power micro \
        --scale 1 \
        --region us-east-1 \
        --profile cocreate

    echo "Waiting for service to be ready (3 minutes)..."
    sleep 180
    echo "✓ Lightsail service created"
else
    echo "✓ Lightsail service exists"
fi

# Create deployment config
echo ""
echo "Creating deployment configuration..."
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

# Deploy container
echo "Deploying container..."
aws lightsail create-container-service-deployment \
    --service-name "$SERVICE_NAME" \
    --containers file:///tmp/containers.json \
    --public-endpoint file:///tmp/public-endpoint.json \
    --region us-east-1 \
    --profile cocreate

echo ""
echo "Waiting for deployment to complete..."
for i in {1..30}; do
    STATUS=$(aws lightsail get-container-service-deployments \
        --service-name "$SERVICE_NAME" \
        --region us-east-1 \
        --profile cocreate \
        --query 'deployments[0].state' \
        --output text 2>/dev/null || echo "UNKNOWN")

    echo "[$i/30] Status: $STATUS"

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

# Get service URL
SERVICE_URL=$(aws lightsail get-container-services \
    --service-name "$SERVICE_NAME" \
    --region us-east-1 \
    --profile cocreate \
    --query 'containerServices[0].url' \
    --output text)

echo ""
echo "============================================"
echo "🎉 DEPLOYMENT COMPLETE!"
echo "============================================"
echo ""
echo "Lightsail URL: https://$SERVICE_URL"
echo ""
echo "Test endpoints:"
echo "  Health: https://$SERVICE_URL/health"
echo "  Admin:  https://$SERVICE_URL/api/admin/sessions?filter=all"
echo ""

# Step 8: Test deployment
echo "Step 8/8: Testing deployment..."
sleep 10
echo ""
echo "Testing health endpoint..."
if curl -f -s "https://$SERVICE_URL/health" > /dev/null; then
    echo "✓ Health check passed!"
else
    echo "⚠️  Health check failed (may need more time to start)"
fi

echo ""
echo "============================================"
echo "✅ All Done!"
echo "============================================"
echo ""
echo "Your app is running at:"
echo "https://$SERVICE_URL"
echo ""
echo "Next steps:"
echo "1. Test the URL above in your browser"
echo "2. Update CloudFront: cd deployment && bash update-cloudfront.sh $SERVICE_URL"
echo "3. Stop old EC2 instance"
echo ""
echo "Monthly cost: ~$12 (down from $30)"
echo "Annual savings: $216"
echo ""
echo "🎉 Congratulations!"
echo ""
