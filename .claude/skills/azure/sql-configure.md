# Azure SQL Configure Skill

## Purpose

Create and configure Azure SQL Database instances for managed relational database hosting with automatic backups, patching, and high availability.

## Prerequisites

- Azure CLI installed and configured (`az login`)
- `sunwaretech` Azure profile/subscription configured
- Resource group created
- Appropriate permissions to create SQL resources

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `server_name` | SQL Server name (globally unique) | Yes | `myapp-sql-server` |
| `database_name` | Database name | Yes | `myapp-db` |
| `resource_group` | Azure resource group | Yes | `my-resource-group` |
| `admin_user` | Server admin username | Yes | `sqladmin` |
| `admin_password` | Server admin password | Yes | (secure password) |
| `location` | Azure region | No | `eastus` |
| `sku` | Database pricing tier | No | `Basic`, `S0`, `GP_Gen5_2` |

## Usage Examples

### Set Azure Subscription

Always set the subscription before running commands:

```bash
az account set --subscription "sunwaretech"
```

### Create SQL Server

```bash
az sql server create \
  --name {server_name} \
  --resource-group {resource_group} \
  --location {location} \
  --admin-user {admin_user} \
  --admin-password "{admin_password}" \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Create SQL Database (Basic Tier)

```bash
az sql db create \
  --name {database_name} \
  --server {server_name} \
  --resource-group {resource_group} \
  --edition Basic \
  --capacity 5 \
  --max-size 2GB \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Create SQL Database (Standard Tier)

```bash
az sql db create \
  --name {database_name} \
  --server {server_name} \
  --resource-group {resource_group} \
  --edition Standard \
  --service-objective S0 \
  --max-size 250GB \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Create SQL Database (General Purpose - vCore)

```bash
az sql db create \
  --name {database_name} \
  --server {server_name} \
  --resource-group {resource_group} \
  --edition GeneralPurpose \
  --family Gen5 \
  --capacity 2 \
  --compute-model Serverless \
  --auto-pause-delay 60 \
  --min-capacity 0.5 \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Create Serverless Database (Cost Optimized)

```bash
az sql db create \
  --name {database_name} \
  --server {server_name} \
  --resource-group {resource_group} \
  --edition GeneralPurpose \
  --family Gen5 \
  --capacity 2 \
  --compute-model Serverless \
  --auto-pause-delay 60 \
  --min-capacity 0.5 \
  --max-size 32GB \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

## Configure Firewall Rules

### Allow Azure Services

```bash
az sql server firewall-rule create \
  --server {server_name} \
  --resource-group {resource_group} \
  --name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

### Allow Specific IP Address

```bash
az sql server firewall-rule create \
  --server {server_name} \
  --resource-group {resource_group} \
  --name AllowMyIP \
  --start-ip-address {your_ip} \
  --end-ip-address {your_ip}
```

### Allow IP Range

```bash
az sql server firewall-rule create \
  --server {server_name} \
  --resource-group {resource_group} \
  --name AllowOfficeRange \
  --start-ip-address 10.0.0.1 \
  --end-ip-address 10.0.0.255
```

## Configure Security

### Enable Azure AD Authentication

```bash
az sql server ad-admin create \
  --server {server_name} \
  --resource-group {resource_group} \
  --display-name "SQL Admin" \
  --object-id {azure_ad_user_object_id}
```

### Enable Transparent Data Encryption

```bash
az sql db tde set \
  --database {database_name} \
  --server {server_name} \
  --resource-group {resource_group} \
  --status Enabled
```

### Enable Auditing

```bash
az sql server audit-policy update \
  --server {server_name} \
  --resource-group {resource_group} \
  --state Enabled \
  --storage-account {storage_account_name} \
  --retention-days 90
```

## Modify Database

### Scale Database

```bash
az sql db update \
  --name {database_name} \
  --server {server_name} \
  --resource-group {resource_group} \
  --service-objective S1
```

### Increase Storage

```bash
az sql db update \
  --name {database_name} \
  --server {server_name} \
  --resource-group {resource_group} \
  --max-size 500GB
```

## Verification

Check database status and get connection string:

```bash
# Get server status
az sql server show \
  --name {server_name} \
  --resource-group {resource_group} \
  --query "state" \
  --output tsv

# Get database status
az sql db show \
  --name {database_name} \
  --server {server_name} \
  --resource-group {resource_group} \
  --query "status" \
  --output tsv

# Get server fully qualified domain name
az sql server show \
  --name {server_name} \
  --resource-group {resource_group} \
  --query "fullyQualifiedDomainName" \
  --output tsv

# Get connection string
az sql db show-connection-string \
  --name {database_name} \
  --server {server_name} \
  --client ado.net \
  --output tsv

# List firewall rules
az sql server firewall-rule list \
  --server {server_name} \
  --resource-group {resource_group} \
  --output table
```

Connection string format:
```
Server=tcp:{server_name}.database.windows.net,1433;Initial Catalog={database_name};Persist Security Info=False;User ID={admin_user};Password={admin_password};MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `ServerNameAlreadyExists` | Server name taken globally | Choose unique server name |
| `LoginFailed` | Wrong credentials | Verify admin user/password |
| `FirewallRuleBlocked` | Client IP not allowed | Add firewall rule for IP |
| `DatabaseAlreadyExists` | Database name exists | Use unique database name |
| `QuotaExceeded` | Subscription limit reached | Request quota increase |

## Notes

- SQL Server names must be globally unique
- Password must meet complexity requirements: 8+ chars, uppercase, lowercase, number, special
- Basic tier is cheapest but has limitations (5 DTU, 2GB max)
- Serverless auto-pauses after inactivity to save costs
- Enable geo-replication for disaster recovery
- Use Azure Key Vault to store connection strings
- Consider elastic pools for multiple databases
- TDE is enabled by default for new databases
- Free tier available: 100,000 vCore seconds/month
