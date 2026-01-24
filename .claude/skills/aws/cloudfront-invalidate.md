# CloudFront Cache Invalidation Skill

## Purpose

Invalidate CloudFront cache after deploying updates to ensure users receive the latest content immediately rather than waiting for cache expiration.

## Prerequisites

- AWS CLI installed and configured
- `sunwaretech` AWS profile configured with appropriate permissions
- Existing CloudFront distribution ID

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `distribution_id` | CloudFront distribution ID | Yes | `E1234567890ABC` |
| `paths` | Paths to invalidate | Yes | `/*` or `/index.html` |

## Usage Examples

### Set AWS Profile

Always set the AWS profile before running commands:

```bash
export AWS_PROFILE=sunwaretech
```

### Invalidate All Files

Invalidate entire distribution cache:

```bash
export AWS_PROFILE=sunwaretech
aws cloudfront create-invalidation \
  --distribution-id {distribution_id} \
  --paths "/*"
```

### Invalidate Specific File

```bash
export AWS_PROFILE=sunwaretech
aws cloudfront create-invalidation \
  --distribution-id {distribution_id} \
  --paths "/index.html"
```

### Invalidate Multiple Paths

```bash
export AWS_PROFILE=sunwaretech
aws cloudfront create-invalidation \
  --distribution-id {distribution_id} \
  --paths "/index.html" "/assets/main.css" "/assets/app.js"
```

### Invalidate Directory

```bash
export AWS_PROFILE=sunwaretech
aws cloudfront create-invalidation \
  --distribution-id {distribution_id} \
  --paths "/assets/*"
```

### Invalidate with Batch File

For many paths, create a JSON file (`invalidation-batch.json`):

```json
{
  "Paths": {
    "Quantity": 3,
    "Items": [
      "/index.html",
      "/assets/*",
      "/api/*"
    ]
  },
  "CallerReference": "invalidation-{timestamp}"
}
```

Then run:

```bash
export AWS_PROFILE=sunwaretech
aws cloudfront create-invalidation \
  --distribution-id {distribution_id} \
  --invalidation-batch file://invalidation-batch.json
```

## Check Invalidation Status

### Get Invalidation Status

```bash
export AWS_PROFILE=sunwaretech
aws cloudfront get-invalidation \
  --distribution-id {distribution_id} \
  --id {invalidation_id}
```

### List Recent Invalidations

```bash
export AWS_PROFILE=sunwaretech
aws cloudfront list-invalidations \
  --distribution-id {distribution_id} \
  --query 'InvalidationList.Items[*].[Id,Status,CreateTime]' \
  --output table
```

## Find Distribution ID

If you don't know the distribution ID:

```bash
export AWS_PROFILE=sunwaretech

# List all distributions with details
aws cloudfront list-distributions \
  --query 'DistributionList.Items[*].[Id,DomainName,Comment,Status]' \
  --output table

# Find by comment/description
aws cloudfront list-distributions \
  --query "DistributionList.Items[?contains(Comment, 'my-site')].Id" \
  --output text
```

## Notes on Invalidation Timing and Costs

### Timing

- Invalidations typically complete within **1-2 minutes**
- Status progresses: `InProgress` -> `Completed`
- All edge locations are updated, but timing may vary slightly by region
- Files remain cached until invalidation completes at each edge

### Costs

- **First 1,000 invalidation paths per month**: FREE
- **Additional paths**: $0.005 per path
- Wildcard (`/*`) counts as **one path** regardless of files matched
- Each specific file path counts as one path

### Cost Optimization Tips

1. **Use wildcards**: `/*` or `/assets/*` count as single paths
2. **Batch invalidations**: Combine multiple paths in one request
3. **Use versioned filenames**: `app.v2.js` instead of `app.js` (no invalidation needed)
4. **Set appropriate TTLs**: Lower TTLs for frequently changing content

### Best Practices

- For full deployments, use `/*` (single path, covers everything)
- For minor updates, invalidate only changed files
- Consider cache-busting filenames for assets (eliminates need for invalidation)
- Wait for `Completed` status before verifying changes
- Don't create redundant invalidations while one is in progress

### Example Deployment Workflow

```bash
export AWS_PROFILE=sunwaretech

# 1. Upload new files to S3
aws s3 sync ./dist/ s3://{bucket_name}/ --delete

# 2. Create invalidation
INVALIDATION_ID=$(aws cloudfront create-invalidation \
  --distribution-id {distribution_id} \
  --paths "/*" \
  --query 'Invalidation.Id' \
  --output text)

echo "Invalidation created: $INVALIDATION_ID"

# 3. Wait for completion (optional)
aws cloudfront wait invalidation-completed \
  --distribution-id {distribution_id} \
  --id $INVALIDATION_ID

echo "Invalidation completed!"
```
