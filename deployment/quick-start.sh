#!/bin/bash

# Quick start menu for tmux-builder Lightsail deployment
set -e

echo "============================================"
echo "tmux-builder Lightsail Deployment"
echo "============================================"
echo ""

# Make all scripts executable
chmod +x setup-dynamodb.sh
chmod +x deploy-lightsail.sh
chmod +x update-cloudfront.sh
chmod +x ../build-and-test-local.sh

# Check prerequisites
echo "Checking prerequisites..."
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "✗ AWS CLI not found"
    echo "  Install: https://aws.amazon.com/cli/"
    exit 1
fi
echo "✓ AWS CLI found"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "✗ Docker not found"
    echo "  Install: https://www.docker.com/get-started"
    exit 1
fi
echo "✓ Docker found"

# Check jq
if ! command -v jq &> /dev/null; then
    echo "✗ jq not found"
    echo "  Install: sudo apt-get install jq"
    exit 1
fi
echo "✓ jq found"

# Check AWS profile
if ! aws sts get-caller-identity --profile cocreate &> /dev/null; then
    echo "✗ AWS profile 'cocreate' not configured"
    echo "  Configure: aws configure --profile cocreate"
    exit 1
fi
echo "✓ AWS profile 'cocreate' configured"

# Check Anthropic API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo ""
    echo "⚠️  ANTHROPIC_API_KEY not set"
    echo ""
    read -p "Enter your Anthropic API key: " API_KEY
    export ANTHROPIC_API_KEY="$API_KEY"
fi
echo "✓ Anthropic API key set"

echo ""
echo "All prerequisites met!"
echo ""

# Set environment
export AWS_PROFILE="cocreate"
export AWS_REGION="us-east-1"
export AWS_ACCOUNT_ID="248825820556"

# Menu
while true; do
    echo "============================================"
    echo "What would you like to do?"
    echo "============================================"
    echo ""
    echo "1) Test Docker build locally"
    echo "2) Set up DynamoDB table"
    echo "3) Deploy to Lightsail (FULL DEPLOYMENT)"
    echo "4) Update CloudFront origin"
    echo "5) View deployment guide"
    echo "6) Exit"
    echo ""
    read -p "Choose option (1-6): " choice

    case $choice in
        1)
            echo ""
            echo "============================================"
            echo "Testing Docker build locally..."
            echo "============================================"
            cd ..
            ./build-and-test-local.sh
            cd deployment
            ;;
        2)
            echo ""
            echo "============================================"
            echo "Setting up DynamoDB..."
            echo "============================================"
            ./setup-dynamodb.sh
            echo ""
            read -p "Press Enter to continue..."
            ;;
        3)
            echo ""
            echo "============================================"
            echo "Deploying to Lightsail..."
            echo "============================================"
            echo ""
            echo "This will:"
            echo "  1. Build Docker image"
            echo "  2. Push to ECR"
            echo "  3. Create/update Lightsail service"
            echo "  4. Deploy container"
            echo ""
            read -p "Continue? (yes/no): " confirm
            if [ "$confirm" == "yes" ]; then
                ./deploy-lightsail.sh
                echo ""
                echo "NEXT STEP: Update CloudFront (option 4)"
                echo ""
                read -p "Press Enter to continue..."
            fi
            ;;
        4)
            echo ""
            echo "============================================"
            echo "Update CloudFront"
            echo "============================================"
            echo ""
            read -p "Enter Lightsail URL (without https://): " ls_url
            ./update-cloudfront.sh "$ls_url"
            echo ""
            read -p "Press Enter to continue..."
            ;;
        5)
            echo ""
            cat DEPLOY.md | head -100
            echo ""
            echo "(Full guide in: deployment/DEPLOY.md)"
            echo ""
            read -p "Press Enter to continue..."
            ;;
        6)
            echo ""
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo ""
            echo "Invalid option. Please choose 1-6."
            echo ""
            ;;
    esac
done
