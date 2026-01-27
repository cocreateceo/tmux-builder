# AWS CORS Configuration Skill

## Purpose

Properly configure Cross-Origin Resource Sharing (CORS) on AWS S3 buckets and CloudFront distributions to ensure web applications can access assets without browser security blocks.

## When to Use

- Deploying static sites with API calls
- Serving fonts from S3/CloudFront
- Enabling canvas operations on images
- Any cross-origin resource access

## S3 CORS Configuration

### Basic CORS Policy (Allow All Origins)

```json
[
    {
        "AllowedOrigins": ["*"],
        "AllowedMethods": ["GET", "HEAD"],
        "AllowedHeaders": ["*"],
        "ExposeHeaders": [],
        "MaxAgeSeconds": 3600
    }
]
```

### Production CORS Policy (Specific Origins)

```json
[
    {
        "AllowedOrigins": [
            "https://example.com",
            "https://www.example.com",
            "https://*.example.com"
        ],
        "AllowedMethods": ["GET", "HEAD"],
        "AllowedHeaders": ["*"],
        "ExposeHeaders": ["ETag", "Content-Length"],
        "MaxAgeSeconds": 86400
    }
]
```

### Full CRUD API CORS Policy

```json
[
    {
        "AllowedOrigins": ["https://example.com"],
        "AllowedMethods": ["GET", "HEAD", "PUT", "POST", "DELETE"],
        "AllowedHeaders": [
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            "Accept",
            "Origin"
        ],
        "ExposeHeaders": [
            "ETag",
            "x-amz-meta-custom-header"
        ],
        "MaxAgeSeconds": 3600
    }
]
```

### Apply CORS to S3 Bucket

```bash
# Save CORS config to file
cat > cors-config.json << 'EOF'
[
    {
        "AllowedOrigins": ["*"],
        "AllowedMethods": ["GET", "HEAD"],
        "AllowedHeaders": ["*"],
        "MaxAgeSeconds": 3600
    }
]
EOF

# Apply to bucket
export AWS_PROFILE=sunwaretech
aws s3api put-bucket-cors \
    --bucket YOUR_BUCKET_NAME \
    --cors-configuration file://cors-config.json

# Verify configuration
aws s3api get-bucket-cors --bucket YOUR_BUCKET_NAME
```

### Remove CORS from S3 Bucket

```bash
aws s3api delete-bucket-cors --bucket YOUR_BUCKET_NAME
```

## CloudFront CORS Configuration

CloudFront requires additional configuration to pass CORS headers from origin.

### Step 1: Create Response Headers Policy

```bash
export AWS_PROFILE=sunwaretech

# Create CORS response headers policy
aws cloudfront create-response-headers-policy \
    --response-headers-policy-config '{
        "Name": "CORS-Policy",
        "Comment": "Enable CORS headers",
        "CorsConfig": {
            "AccessControlAllowOrigins": {
                "Quantity": 1,
                "Items": ["*"]
            },
            "AccessControlAllowHeaders": {
                "Quantity": 1,
                "Items": ["*"]
            },
            "AccessControlAllowMethods": {
                "Quantity": 2,
                "Items": ["GET", "HEAD"]
            },
            "AccessControlAllowCredentials": false,
            "AccessControlMaxAgeSec": 86400,
            "OriginOverride": true
        }
    }'
```

### Step 2: Create Origin Request Policy (Forward Origin Header)

```bash
# Create policy to forward Origin header to S3
aws cloudfront create-origin-request-policy \
    --origin-request-policy-config '{
        "Name": "Forward-Origin-Header",
        "Comment": "Forward Origin header for CORS",
        "HeadersConfig": {
            "HeaderBehavior": "whitelist",
            "Headers": {
                "Quantity": 1,
                "Items": ["Origin"]
            }
        },
        "CookiesConfig": {
            "CookieBehavior": "none"
        },
        "QueryStringsConfig": {
            "QueryStringBehavior": "none"
        }
    }'
```

### Step 3: Create Cache Policy (Vary on Origin)

```bash
# Create cache policy that varies on Origin header
aws cloudfront create-cache-policy \
    --cache-policy-config '{
        "Name": "Cache-With-Origin",
        "Comment": "Cache based on Origin header for CORS",
        "DefaultTTL": 86400,
        "MaxTTL": 31536000,
        "MinTTL": 0,
        "ParametersInCacheKeyAndForwardedToOrigin": {
            "EnableAcceptEncodingGzip": true,
            "EnableAcceptEncodingBrotli": true,
            "HeadersConfig": {
                "HeaderBehavior": "whitelist",
                "Headers": {
                    "Quantity": 1,
                    "Items": ["Origin"]
                }
            },
            "CookiesConfig": {
                "CookieBehavior": "none"
            },
            "QueryStringsConfig": {
                "QueryStringBehavior": "none"
            }
        }
    }'
```

### Step 4: Update Distribution Behavior

```bash
# Get current distribution config
aws cloudfront get-distribution-config --id DISTRIBUTION_ID > dist-config.json

# Edit dist-config.json to add:
# - ResponseHeadersPolicyId
# - OriginRequestPolicyId
# - CachePolicyId

# Update distribution
aws cloudfront update-distribution \
    --id DISTRIBUTION_ID \
    --distribution-config file://dist-config.json \
    --if-match ETAG_FROM_GET
```

## Quick CloudFront CORS Fix

For simple static sites, use managed policies:

```bash
export AWS_PROFILE=sunwaretech

# List available managed policies
aws cloudfront list-response-headers-policies \
    --query 'ResponseHeadersPolicyList.Items[*].[ResponseHeadersPolicy.Id,ResponseHeadersPolicy.ResponseHeadersPolicyConfig.Name]' \
    --output table

# Common managed policy IDs:
# - CORS-and-SecurityHeadersPolicy: 88a5eaf4-2fd4-4709-b370-b4c650ea3fcf
# - CORS-With-Preflight: 5cc3b908-e619-4b99-88e5-2cf7f45965bd

# Apply managed CORS policy to distribution behavior
# (Requires updating distribution config)
```

## Verification

### Test S3 CORS

```bash
# Test CORS headers from S3
curl -I -H "Origin: https://example.com" \
    https://bucket-name.s3.region.amazonaws.com/file.js

# Should include:
# Access-Control-Allow-Origin: *
# Access-Control-Allow-Methods: GET, HEAD
```

### Test CloudFront CORS

```bash
# Test CORS headers from CloudFront
curl -I -H "Origin: https://example.com" \
    https://d1234567890abc.cloudfront.net/file.js

# Should include same CORS headers
```

### Test Preflight

```bash
# Test OPTIONS preflight request
curl -I -X OPTIONS \
    -H "Origin: https://example.com" \
    -H "Access-Control-Request-Method: GET" \
    https://d1234567890abc.cloudfront.net/file.js
```

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| No CORS headers | S3 CORS not configured | Add CORS configuration to bucket |
| CORS cached wrong | CloudFront not varying on Origin | Add Origin to cache key |
| Preflight fails | OPTIONS not handled | Ensure AllowedMethods includes OPTIONS behavior |
| Credentials rejected | Using * with credentials | Use specific origin instead of * |
| Headers stripped | CloudFront not forwarding | Create origin request policy |

## Font-Specific CORS

Fonts require CORS to load cross-origin:

```json
[
    {
        "AllowedOrigins": ["*"],
        "AllowedMethods": ["GET", "HEAD"],
        "AllowedHeaders": ["*"],
        "MaxAgeSeconds": 86400
    }
]
```

Without this, browsers will block font loading with:
```
Access to font at 'https://...' from origin 'https://...' has been blocked by CORS policy
```

## Integration with Deployment

When deploying static sites:

1. **Before S3 Upload**: Configure CORS on bucket
2. **After CloudFront Create**: Apply response headers policy
3. **Verification**: Run CORS verification skill
4. **Invalidate Cache**: If changing CORS on existing distribution

## Template: Complete S3 + CloudFront CORS Setup

```bash
#!/bin/bash
# setup-cors.sh

BUCKET_NAME="${1:-my-bucket}"
DISTRIBUTION_ID="${2:-EXXXXXXXXXXXXX}"

export AWS_PROFILE=sunwaretech

# 1. Configure S3 CORS
echo "Configuring S3 CORS..."
aws s3api put-bucket-cors --bucket "$BUCKET_NAME" --cors-configuration '[
    {
        "AllowedOrigins": ["*"],
        "AllowedMethods": ["GET", "HEAD"],
        "AllowedHeaders": ["*"],
        "MaxAgeSeconds": 86400
    }
]'

# 2. Get managed CORS policy ID
CORS_POLICY_ID="88a5eaf4-2fd4-4709-b370-b4c650ea3fcf"

# 3. Update CloudFront (manual step - requires editing distribution)
echo ""
echo "S3 CORS configured."
echo "For CloudFront, add ResponseHeadersPolicyId: $CORS_POLICY_ID"
echo "to your distribution's default cache behavior."
echo ""
echo "Then invalidate cache:"
echo "aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths '/*'"
```
