# CloudFront Create Skill

## Purpose

Create a CloudFront distribution for serving S3-hosted static websites with global CDN, HTTPS support, and edge caching.

## Prerequisites

- AWS CLI installed and configured
- `cocreate` AWS profile configured with appropriate permissions
- S3 bucket with static website content already uploaded
- (Optional) ACM certificate for custom domain (must be in us-east-1)

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `bucket_name` | Source S3 bucket name | Yes | `my-website-bucket` |
| `bucket_region` | S3 bucket region | Yes | `us-east-1` |
| `comment` | Distribution description | No | `My Website CDN` |
| `default_root_object` | Default file to serve | No | `index.html` |

## Usage Examples

### Set AWS Profile

Always set the AWS profile before running commands:

```bash
export AWS_PROFILE=cocreate
```

### Create Distribution with Full Config

Save this configuration to a file (e.g., `distribution-config.json`):

```json
{
  "CallerReference": "unique-reference-{timestamp}",
  "Comment": "CloudFront distribution for {bucket_name}",
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-{bucket_name}",
    "ViewerProtocolPolicy": "redirect-to-https",
    "TrustedSigners": {
      "Enabled": false,
      "Quantity": 0
    },
    "ForwardedValues": {
      "QueryString": false,
      "Cookies": {
        "Forward": "none"
      }
    },
    "MinTTL": 0,
    "DefaultTTL": 86400,
    "MaxTTL": 31536000,
    "Compress": true,
    "AllowedMethods": {
      "Quantity": 2,
      "Items": ["GET", "HEAD"],
      "CachedMethods": {
        "Quantity": 2,
        "Items": ["GET", "HEAD"]
      }
    }
  },
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "S3-{bucket_name}",
        "DomainName": "{bucket_name}.s3.{bucket_region}.amazonaws.com",
        "S3OriginConfig": {
          "OriginAccessIdentity": ""
        }
      }
    ]
  },
  "Enabled": true,
  "DefaultRootObject": "index.html",
  "PriceClass": "PriceClass_100",
  "HttpVersion": "http2",
  "IsIPV6Enabled": true,
  "CustomErrorResponses": {
    "Quantity": 1,
    "Items": [
      {
        "ErrorCode": 404,
        "ResponsePagePath": "/index.html",
        "ResponseCode": "200",
        "ErrorCachingMinTTL": 300
      }
    ]
  }
}
```

Create the distribution:

```bash
export AWS_PROFILE=cocreate
aws cloudfront create-distribution \
  --distribution-config file://distribution-config.json
```

### Quick Create with Origin Access Control (Recommended)

First, create an Origin Access Control:

```bash
export AWS_PROFILE=cocreate
aws cloudfront create-origin-access-control \
  --origin-access-control-config '{
    "Name": "{bucket_name}-oac",
    "Description": "OAC for {bucket_name}",
    "SigningProtocol": "sigv4",
    "SigningBehavior": "always",
    "OriginAccessControlOriginType": "s3"
  }'
```

Note the `Id` from the response for use in the distribution config.

## Get Distribution Domain Name

After creation, retrieve the CloudFront domain:

```bash
export AWS_PROFILE=cocreate

# List all distributions
aws cloudfront list-distributions \
  --query 'DistributionList.Items[*].[Id,DomainName,Comment]' \
  --output table

# Get specific distribution details
aws cloudfront get-distribution --id {distribution_id} \
  --query 'Distribution.DomainName' \
  --output text
```

The domain will be in format: `d1234567890abc.cloudfront.net`

## Include Tagging

Apply tags during creation or after:

### Tag During Creation

Add to your distribution config JSON:

```json
{
  "Tags": {
    "Items": [
      {"Key": "Project", "Value": "tmux-builder"},
      {"Key": "Environment", "Value": "production"},
      {"Key": "ManagedBy", "Value": "claude"}
    ]
  }
}
```

Then use:

```bash
export AWS_PROFILE=cocreate
aws cloudfront create-distribution-with-tags \
  --distribution-config-with-tags file://distribution-config-with-tags.json
```

### Tag Existing Distribution

```bash
export AWS_PROFILE=cocreate
aws cloudfront tag-resource \
  --resource "arn:aws:cloudfront::{account_id}:distribution/{distribution_id}" \
  --tags 'Items=[{Key=Project,Value=tmux-builder},{Key=Environment,Value=production},{Key=ManagedBy,Value=claude}]'
```

## Verify Distribution Status

Check deployment status (takes 5-15 minutes):

```bash
export AWS_PROFILE=cocreate
aws cloudfront get-distribution --id {distribution_id} \
  --query 'Distribution.Status' \
  --output text
```

Status will be `InProgress` then `Deployed` when ready.

## Notes

- Distribution creation takes 5-15 minutes to deploy globally
- `PriceClass_100` uses only North America and Europe edges (lowest cost)
- `PriceClass_200` adds Asia, Middle East, Africa
- `PriceClass_All` uses all edge locations worldwide
- Custom error response for 404->200 enables SPA routing
- Always use HTTPS (redirect-to-https) for security
- Consider enabling WAF for additional security on production sites
