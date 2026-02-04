# Azure Blob Upload Skill

## Purpose

Upload files to Azure Blob Storage containers for static website hosting, file storage, or application data.

## Prerequisites

- Azure CLI installed and configured (`az login`)
- `cocreate` Azure profile/subscription configured
- Storage account created with blob containers
- Appropriate RBAC permissions (Storage Blob Data Contributor)

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `storage_account` | Azure Storage account name | Yes | `mystorageaccount` |
| `container_name` | Blob container name | Yes | `$web` (for static sites) |
| `source_dir` | Local directory or file to upload | Yes | `./dist/` |
| `resource_group` | Azure resource group | Yes | `my-resource-group` |

## Usage Examples

### Set Azure Subscription

Always set the subscription before running commands:

```bash
az account set --subscription "cocreate"
```

### Create Storage Account (if needed)

```bash
az storage account create \
  --name {storage_account} \
  --resource-group {resource_group} \
  --location eastus \
  --sku Standard_LRS \
  --kind StorageV2 \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Enable Static Website Hosting

```bash
az storage blob service-properties update \
  --account-name {storage_account} \
  --static-website \
  --index-document index.html \
  --404-document 404.html
```

### Upload Single File

```bash
az storage blob upload \
  --account-name {storage_account} \
  --container-name {container_name} \
  --file {source_dir}/index.html \
  --name index.html \
  --content-type "text/html"
```

### Upload Directory (Batch)

```bash
az storage blob upload-batch \
  --account-name {storage_account} \
  --destination {container_name} \
  --source {source_dir} \
  --overwrite
```

### Upload with Content Types

```bash
az storage blob upload-batch \
  --account-name {storage_account} \
  --destination {container_name} \
  --source {source_dir} \
  --overwrite \
  --content-type "text/html" \
  --pattern "*.html"

az storage blob upload-batch \
  --account-name {storage_account} \
  --destination {container_name} \
  --source {source_dir} \
  --overwrite \
  --content-type "text/css" \
  --pattern "*.css"

az storage blob upload-batch \
  --account-name {storage_account} \
  --destination {container_name} \
  --source {source_dir} \
  --overwrite \
  --content-type "application/javascript" \
  --pattern "*.js"
```

### Upload with Cache Control

```bash
az storage blob upload-batch \
  --account-name {storage_account} \
  --destination {container_name} \
  --source {source_dir}/assets \
  --destination-path assets \
  --overwrite \
  --content-cache-control "max-age=31536000,public"
```

### Sync Directory (Delete Removed Files)

```bash
az storage blob sync \
  --account-name {storage_account} \
  --container {container_name} \
  --source {source_dir} \
  --delete-destination true
```

## Authentication Options

### Using Connection String

```bash
# Get connection string
CONNECTION_STRING=$(az storage account show-connection-string \
  --name {storage_account} \
  --resource-group {resource_group} \
  --output tsv)

# Use in upload
az storage blob upload-batch \
  --connection-string "$CONNECTION_STRING" \
  --destination {container_name} \
  --source {source_dir}
```

### Using SAS Token

```bash
# Generate SAS token
SAS_TOKEN=$(az storage container generate-sas \
  --account-name {storage_account} \
  --name {container_name} \
  --permissions rwl \
  --expiry $(date -u -d "1 hour" '+%Y-%m-%dT%H:%MZ') \
  --output tsv)

# Use in upload
az storage blob upload-batch \
  --account-name {storage_account} \
  --destination {container_name} \
  --source {source_dir} \
  --sas-token "$SAS_TOKEN"
```

## Verification

Check that files were uploaded successfully:

```bash
# List blobs in container
az storage blob list \
  --account-name {storage_account} \
  --container-name {container_name} \
  --output table

# Get static website URL
az storage account show \
  --name {storage_account} \
  --resource-group {resource_group} \
  --query "primaryEndpoints.web" \
  --output tsv

# Check specific blob exists
az storage blob exists \
  --account-name {storage_account} \
  --container-name {container_name} \
  --name index.html \
  --output tsv
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `AuthorizationPermissionMismatch` | Missing RBAC permissions | Assign Storage Blob Data Contributor role |
| `ContainerNotFound` | Container doesn't exist | Create container first or enable static website |
| `AccountRequiresHttps` | HTTP access disabled | Use HTTPS or enable HTTP in storage settings |
| `BlobAlreadyExists` | Blob exists without overwrite | Add `--overwrite` flag |
| `InvalidResourceName` | Invalid storage account name | Use lowercase letters and numbers only |

## Notes

- Static website container is always named `$web`
- Storage account names must be globally unique
- Use `--dry-run` flag to preview upload without executing
- For large uploads, consider using AzCopy for better performance
- Standard_LRS is cheapest but has no redundancy
- Enable soft delete for production to protect against accidental deletion
- Blob storage supports hot, cool, and archive access tiers
