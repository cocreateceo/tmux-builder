#!/bin/bash

# Setup DynamoDB table for tmux-builder sessions
set -e

AWS_PROFILE="${AWS_PROFILE:-cocreate}"
AWS_REGION="${AWS_REGION:-us-east-1}"
TABLE_NAME="tmux-builder-sessions"

echo "============================================"
echo "Setting up DynamoDB for tmux-builder"
echo "============================================"
echo "Profile: $AWS_PROFILE"
echo "Region: $AWS_REGION"
echo "Table: $TABLE_NAME"
echo ""

# Check if table exists
echo "Checking if table exists..."
if aws dynamodb describe-table \
    --table-name "$TABLE_NAME" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" >/dev/null 2>&1; then
    echo "✓ Table already exists!"
    echo ""
    aws dynamodb describe-table \
        --table-name "$TABLE_NAME" \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" \
        --query 'Table.[TableName,TableStatus,ItemCount]' \
        --output table
    exit 0
fi

# Create table
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
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"

echo ""
echo "Waiting for table to be active..."
aws dynamodb wait table-exists \
    --table-name "$TABLE_NAME" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE"

echo ""
echo "✓ Table created successfully!"
echo ""
aws dynamodb describe-table \
    --table-name "$TABLE_NAME" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" \
    --query 'Table.[TableName,TableStatus,TableArn]' \
    --output table

echo ""
echo "============================================"
echo "DynamoDB setup complete!"
echo "============================================"
