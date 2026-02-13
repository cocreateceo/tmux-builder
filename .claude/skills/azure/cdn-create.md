# Azure CDN Create Skill

## Purpose

Create and configure Azure CDN profiles and endpoints to accelerate content delivery with global edge caching, HTTPS support, and custom domains.

## Prerequisites

- Azure CLI installed and configured (`az login`)
- `cocreate` Azure profile/subscription configured
- Origin server (Storage Account, Web App, etc.) already created
- Appropriate permissions to create CDN resources

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `profile_name` | CDN profile name | Yes | `myapp-cdn-profile` |
| `endpoint_name` | CDN endpoint name (globally unique) | Yes | `myapp-cdn` |
| `resource_group` | Azure resource group | Yes | `my-resource-group` |
| `origin_hostname` | Origin server hostname | Yes | `mystorageaccount.blob.core.windows.net` |
| `origin_path` | Path on origin server | No | `/web` |
| `sku` | CDN pricing tier | No | `Standard_Microsoft` |

## Usage Examples

### Set Azure Subscription

Always set the subscription before running commands:

```bash
az account set --subscription "cocreate"
```

### Create CDN Profile

```bash
az cdn profile create \
  --name {profile_name} \
  --resource-group {resource_group} \
  --location global \
  --sku Standard_Microsoft \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Create CDN Endpoint for Storage Static Website

```bash
az cdn endpoint create \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --origin {origin_hostname} \
  --origin-host-header {origin_hostname} \
  --enable-compression true \
  --query-string-caching-behavior IgnoreQueryString \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Create CDN Endpoint with Custom Origin Path

```bash
az cdn endpoint create \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --origin {origin_hostname} \
  --origin-host-header {origin_hostname} \
  --origin-path {origin_path} \
  --enable-compression true \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Create with HTTPS Only

```bash
az cdn endpoint create \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --origin {origin_hostname} \
  --origin-host-header {origin_hostname} \
  --enable-compression true \
  --query-string-caching-behavior IgnoreQueryString
```

### Create with Web Application Firewall (Premium)

```bash
# Create Premium profile
az cdn profile create \
  --name {profile_name} \
  --resource-group {resource_group} \
  --sku Premium_Verizon \
  --tags Project=tmux-builder

# Create endpoint with WAF
az cdn endpoint create \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --origin {origin_hostname} \
  --origin-host-header {origin_hostname}
```

## Configure Caching Rules

### Add Caching Rule for Static Assets

```bash
az cdn endpoint rule add \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --order 1 \
  --rule-name "CacheStaticAssets" \
  --match-variable UrlFileExtension \
  --operator Equal \
  --match-values js css png jpg jpeg gif ico svg woff woff2 \
  --action-name CacheExpiration \
  --cache-behavior Override \
  --cache-duration "7.00:00:00"
```

### Add Rule for HTML (No Cache)

```bash
az cdn endpoint rule add \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --order 2 \
  --rule-name "NoHtmlCache" \
  --match-variable UrlFileExtension \
  --operator Equal \
  --match-values html htm \
  --action-name CacheExpiration \
  --cache-behavior BypassCache
```

## Custom Domain Configuration

### Add Custom Domain

```bash
az cdn custom-domain create \
  --name my-custom-domain \
  --endpoint-name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --hostname www.example.com
```

### Enable HTTPS on Custom Domain

```bash
az cdn custom-domain enable-https \
  --name my-custom-domain \
  --endpoint-name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group}
```

## Verification

Check CDN profile and endpoint status:

```bash
# Get CDN profile status
az cdn profile show \
  --name {profile_name} \
  --resource-group {resource_group} \
  --query "resourceState" \
  --output tsv

# Get CDN endpoint URL
az cdn endpoint show \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --query "hostName" \
  --output tsv

# Check endpoint provisioning state
az cdn endpoint show \
  --name {endpoint_name} \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --query "provisioningState" \
  --output tsv

# List all endpoints in profile
az cdn endpoint list \
  --profile-name {profile_name} \
  --resource-group {resource_group} \
  --output table
```

The CDN endpoint URL will be: `https://{endpoint_name}.azureedge.net`

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `EndpointNameNotAvailable` | Endpoint name taken globally | Choose unique endpoint name |
| `ProfileNotFound` | CDN profile doesn't exist | Create profile first |
| `OriginNotAccessible` | Cannot reach origin server | Verify origin hostname and firewall |
| `CnameRecordConflict` | Custom domain CNAME conflict | Remove conflicting DNS record |
| `CertificateValidationFailed` | Custom domain validation failed | Verify DNS CNAME points to CDN |

## Notes

- CDN endpoint propagation takes 10-30 minutes globally
- Endpoint names must be globally unique across all Azure customers
- Standard_Microsoft tier is cheapest and sufficient for most use cases
- Premium tiers offer advanced features like real-time analytics and WAF
- Use compression for text-based content (HTML, CSS, JS, JSON)
- Query string caching modes: IgnoreQueryString, UseQueryString, BypassCaching
- CDN automatically handles HTTPS with managed certificates
- Custom domains require CNAME DNS record pointing to CDN endpoint
