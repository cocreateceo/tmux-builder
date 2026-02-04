# Azure CDN Purge Skill

## Purpose

Purge cached content from Azure CDN edge nodes to force refresh of updated content, ensuring users receive the latest version of files.

## Prerequisites

- Azure CLI installed and configured (`az login`)
- `cocreate` Azure profile/subscription configured
- Existing CDN profile and endpoint
- Appropriate permissions to manage CDN endpoints

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `profile_name` | CDN profile name | Yes | `myapp-cdn-profile` |
| `endpoint_name` | CDN endpoint name | Yes | `myapp-cdn` |
| `resource_group` | Azure resource group | Yes | `my-resource-group` |
| `content_paths` | Paths to purge | Yes | `/index.html`, `/*` |

## Usage Examples

### Set Azure Subscription

Always set the subscription before running commands:

```bash
az account set --subscription "cocreate"
```

### Purge Single File

```bash
az cdn endpoint purge \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --content-paths "/index.html"
```

### Purge Multiple Files

```bash
az cdn endpoint purge \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --content-paths "/index.html" "/styles.css" "/app.js"
```

### Purge Directory

```bash
az cdn endpoint purge \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --content-paths "/assets/*"
```

### Purge All Content (Full Cache Clear)

```bash
az cdn endpoint purge \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --content-paths "/*"
```

### Purge with Wildcard Patterns

```bash
# Purge all CSS files
az cdn endpoint purge \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --content-paths "/*.css"

# Purge all JS files
az cdn endpoint purge \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --content-paths "/*.js"

# Purge all images
az cdn endpoint purge \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --content-paths "/*.png" "/*.jpg" "/*.gif" "/*.svg"
```

### Purge After Deployment (Typical Workflow)

```bash
# After deploying new content, purge HTML files
az cdn endpoint purge \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --content-paths "/index.html" "/404.html" "/*.html"

# Optional: purge hashed assets if you changed naming
az cdn endpoint purge \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --content-paths "/assets/*"
```

### Load Content (Pre-warm Cache)

Load content to edge nodes before users request it:

```bash
az cdn endpoint load \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --content-paths "/index.html" "/styles.css" "/app.js"
```

## Async Purge with Monitoring

### Start Purge and Track Progress

```bash
# Start purge (returns immediately)
az cdn endpoint purge \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --content-paths "/*" \
  --no-wait

# Check endpoint state
az cdn endpoint show \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --query "resourceState" \
  --output tsv
```

## Verification

Verify purge completion and test content refresh:

```bash
# Check endpoint provisioning state
az cdn endpoint show \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --query "provisioningState" \
  --output tsv

# Get endpoint URL for manual testing
ENDPOINT_URL=$(az cdn endpoint show \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --query "hostName" \
  --output tsv)

echo "Test URL: https://$ENDPOINT_URL/index.html"

# Test with curl (check headers for cache status)
curl -I "https://$ENDPOINT_URL/index.html"
```

### Check Cache Headers

```bash
# Look for X-Cache header (HIT vs MISS)
curl -I "https://{endpoint_name}.azureedge.net/index.html" 2>&1 | grep -i "x-cache"

# MISS indicates content was fetched from origin (purge worked)
# HIT indicates content was served from cache
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `EndpointNotFound` | Endpoint doesn't exist | Verify endpoint name and profile |
| `InvalidPurgePath` | Invalid path format | Paths must start with `/` |
| `TooManyPurgeRequests` | Rate limit exceeded | Wait and retry, or batch paths |
| `PurgeOperationFailed` | General purge failure | Check endpoint status and retry |
| `Forbidden` | Insufficient permissions | Verify RBAC role assignment |

## Notes

- Purge operations take 2-10 minutes to propagate globally
- Maximum 50 paths per purge request for Standard Microsoft tier
- Maximum 100 paths per purge request for Verizon/Akamai tiers
- Wildcard `/*` counts as one path
- Purge is case-insensitive for paths
- Consider using cache-busting (hash in filename) for static assets
- Frequent full purges (`/*`) may impact performance; prefer targeted purges
- Pre-loading (warming) cache is only available on Premium tiers
- Monitor CDN metrics in Azure Portal for cache hit ratio
