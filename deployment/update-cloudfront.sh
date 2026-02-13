#!/bin/bash

# Update CloudFront distribution to point to Lightsail container
set -e

AWS_PROFILE="${AWS_PROFILE:-cocreate}"
DISTRIBUTION_ID="E2FOQ8U2IQP3GC"
LIGHTSAIL_URL="$1"

if [ -z "$LIGHTSAIL_URL" ]; then
    echo "ERROR: Lightsail URL not provided"
    echo "Usage: $0 <lightsail-url>"
    echo "Example: $0 tmux-builder.xxxxx.us-east-1.cs.amazonlightsail.com"
    exit 1
fi

# Remove https:// if present
LIGHTSAIL_URL=$(echo "$LIGHTSAIL_URL" | sed 's|https://||')

echo "============================================"
echo "Updating CloudFront Distribution"
echo "============================================"
echo "Distribution: $DISTRIBUTION_ID"
echo "New Origin: $LIGHTSAIL_URL"
echo ""

# Step 1: Get current distribution config
echo "Step 1: Getting current distribution config..."
aws cloudfront get-distribution-config \
    --id "$DISTRIBUTION_ID" \
    --profile "$AWS_PROFILE" \
    > /tmp/cf-config-original.json

# Extract ETag and config
ETAG=$(jq -r '.ETag' /tmp/cf-config-original.json)
jq '.DistributionConfig' /tmp/cf-config-original.json > /tmp/cf-config.json

echo "✓ Current config retrieved (ETag: $ETAG)"

# Step 2: Backup original config
cp /tmp/cf-config.json /tmp/cf-config-backup-$(date +%Y%m%d-%H%M%S).json
echo "✓ Backup created"

# Step 3: Update origin domain
echo ""
echo "Step 2: Updating origin domain..."
jq --arg domain "$LIGHTSAIL_URL" \
    '.Origins.Items[0].DomainName = $domain |
     .Origins.Items[0].CustomOriginConfig.OriginProtocolPolicy = "https-only" |
     .Origins.Items[0].CustomOriginConfig.HTTPSPort = 443 |
     .Origins.Items[0].CustomOriginConfig.OriginSSLProtocols.Items = ["TLSv1.2"]' \
    /tmp/cf-config.json > /tmp/cf-config-updated.json

echo "✓ Config updated with new origin"

# Show diff
echo ""
echo "Changes:"
echo "----------------------------------------"
echo "Old origin: $(jq -r '.Origins.Items[0].DomainName' /tmp/cf-config.json)"
echo "New origin: $LIGHTSAIL_URL"
echo "----------------------------------------"
echo ""

# Step 4: Confirm update
read -p "Proceed with update? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Update cancelled"
    exit 0
fi

# Step 5: Apply update
echo ""
echo "Step 3: Applying update..."
aws cloudfront update-distribution \
    --id "$DISTRIBUTION_ID" \
    --if-match "$ETAG" \
    --distribution-config file:///tmp/cf-config-updated.json \
    --profile "$AWS_PROFILE" \
    > /tmp/cf-update-response.json

echo "✓ Update applied"

# Step 6: Create cache invalidation
echo ""
echo "Step 4: Creating cache invalidation..."
INVALIDATION_ID=$(aws cloudfront create-invalidation \
    --distribution-id "$DISTRIBUTION_ID" \
    --paths "/*" \
    --profile "$AWS_PROFILE" \
    --query 'Invalidation.Id' \
    --output text)

echo "✓ Invalidation created (ID: $INVALIDATION_ID)"

echo ""
echo "============================================"
echo "CloudFront Update Complete!"
echo "============================================"
echo ""
echo "Distribution: $DISTRIBUTION_ID"
echo "New Origin: $LIGHTSAIL_URL"
echo "Invalidation: $INVALIDATION_ID"
echo ""
echo "The update is being deployed to edge locations."
echo "This may take 5-15 minutes to complete."
echo ""
echo "Test URL: https://d3tfeatcbws1ka.cloudfront.net/health"
echo ""
echo "Monitor invalidation:"
echo "  aws cloudfront get-invalidation --distribution-id $DISTRIBUTION_ID --id $INVALIDATION_ID --profile $AWS_PROFILE"
echo ""
echo "Rollback (if needed):"
echo "  Use backup config at: /tmp/cf-config-backup-*.json"
echo ""
