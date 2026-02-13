#!/bin/bash

# Deploy tmux-builder to AWS Lightsail Container Service
set -e

# Configuration
AWS_PROFILE="${AWS_PROFILE:-cocreate}"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-248825820556}"
SERVICE_NAME="tmux-builder"
CONTAINER_NAME="tmux-backend"
ECR_REPO="tmux-builder"
IMAGE_TAG="latest"

echo "============================================"
echo "Deploying tmux-builder to Lightsail"
echo "============================================"
echo "Profile: $AWS_PROFILE"
echo "Region: $AWS_REGION"
echo "Service: $SERVICE_NAME"
echo ""

# Check required environment variables
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY environment variable not set"
    echo "Please set it with: export ANTHROPIC_API_KEY=your-key"
    exit 1
fi

# Step 1: Create ECR repository if it doesn't exist
echo "Step 1: Checking ECR repository..."
if ! aws ecr describe-repositories \
    --repository-names "$ECR_REPO" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" >/dev/null 2>&1; then

    echo "Creating ECR repository..."
    aws ecr create-repository \
        --repository-name "$ECR_REPO" \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE"
    echo "✓ ECR repository created"
else
    echo "✓ ECR repository exists"
fi

# Step 2: Build and push Docker image
echo ""
echo "Step 2: Building Docker image..."
cd "$(dirname "$0")/.."
docker build -t "$ECR_REPO:$IMAGE_TAG" .

echo ""
echo "Step 3: Pushing to ECR..."
# Get ECR login
aws ecr get-login-password \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" | docker login \
    --username AWS \
    --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Tag and push
docker tag "$ECR_REPO:$IMAGE_TAG" \
    "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"

docker push "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"

echo "✓ Image pushed to ECR"

# Step 4: Create Lightsail container service if it doesn't exist
echo ""
echo "Step 4: Checking Lightsail service..."
if ! aws lightsail get-container-services \
    --service-name "$SERVICE_NAME" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" >/dev/null 2>&1; then

    echo "Creating Lightsail container service..."
    aws lightsail create-container-service \
        --service-name "$SERVICE_NAME" \
        --power micro \
        --scale 1 \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE"

    echo "Waiting for service to be ready (this takes 2-3 minutes)..."
    sleep 180
    echo "✓ Service created"
else
    echo "✓ Service exists"
fi

# Step 5: Create deployment configuration
echo ""
echo "Step 5: Creating deployment configuration..."

cat > /tmp/containers.json <<EOF
{
  "$CONTAINER_NAME": {
    "image": "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG",
    "ports": {
      "8080": "HTTP",
      "8082": "HTTP"
    },
    "environment": {
      "LIGHTSAIL_DEPLOYMENT": "true",
      "AWS_REGION": "$AWS_REGION",
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

# Step 6: Deploy container
echo ""
echo "Step 6: Deploying container..."
aws lightsail create-container-service-deployment \
    --service-name "$SERVICE_NAME" \
    --containers file:///tmp/containers.json \
    --public-endpoint file:///tmp/public-endpoint.json \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE"

echo ""
echo "✓ Deployment initiated!"
echo ""
echo "Monitoring deployment status..."
echo "(This may take 3-5 minutes)"
echo ""

# Wait for deployment
for i in {1..30}; do
    STATUS=$(aws lightsail get-container-service-deployments \
        --service-name "$SERVICE_NAME" \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" \
        --query 'deployments[0].state' \
        --output text 2>/dev/null || echo "UNKNOWN")

    echo "[$i/30] Status: $STATUS"

    if [ "$STATUS" == "ACTIVE" ]; then
        echo ""
        echo "✓ Deployment successful!"
        break
    elif [ "$STATUS" == "FAILED" ]; then
        echo ""
        echo "✗ Deployment failed!"
        exit 1
    fi

    sleep 10
done

# Get service URL
echo ""
echo "============================================"
echo "Deployment Complete!"
echo "============================================"
echo ""

SERVICE_URL=$(aws lightsail get-container-services \
    --service-name "$SERVICE_NAME" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" \
    --query 'containerServices[0].url' \
    --output text)

echo "Service URL: https://$SERVICE_URL"
echo ""
echo "Test endpoints:"
echo "  Health: https://$SERVICE_URL/health"
echo "  Admin:  https://$SERVICE_URL/api/admin/sessions?filter=all"
echo ""
echo "Next steps:"
echo "  1. Test the service URLs above"
echo "  2. Update CloudFront origin to point to: $SERVICE_URL"
echo "  3. Run: ./update-cloudfront.sh $SERVICE_URL"
echo ""
echo "Monitor logs:"
echo "  aws lightsail get-container-log --service-name $SERVICE_NAME --container-name $CONTAINER_NAME --region $AWS_REGION --profile $AWS_PROFILE"
echo ""
