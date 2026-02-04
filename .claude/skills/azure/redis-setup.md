# Azure Redis Setup Skill

## Purpose

Create and configure Azure Cache for Redis instances for in-memory caching to improve application performance with global availability and enterprise features.

## Prerequisites

- Azure CLI installed and configured (`az login`)
- `cocreate` Azure profile/subscription configured
- Resource group created
- Appropriate permissions to create Redis resources

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `cache_name` | Redis cache name (globally unique) | Yes | `myapp-redis-cache` |
| `resource_group` | Azure resource group | Yes | `my-resource-group` |
| `location` | Azure region | No | `eastus` |
| `sku` | Cache pricing tier | Yes | `Basic`, `Standard`, `Premium` |
| `vm_size` | Cache size | Yes | `C0`, `C1`, `P1` |
| `enable_non_ssl` | Allow non-SSL connections | No | `false` |

## Usage Examples

### Set Azure Subscription

Always set the subscription before running commands:

```bash
az account set --subscription "cocreate"
```

### Create Basic Redis Cache

```bash
az redis create \
  --name {cache_name} \
  --resource-group {resource_group} \
  --location {location} \
  --sku Basic \
  --vm-size C0 \
  --tags Project=tmux-builder Environment=development ManagedBy=claude
```

### Create Standard Redis Cache (Replicated)

```bash
az redis create \
  --name {cache_name} \
  --resource-group {resource_group} \
  --location {location} \
  --sku Standard \
  --vm-size C1 \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Create Premium Redis Cache (Clustering)

```bash
az redis create \
  --name {cache_name} \
  --resource-group {resource_group} \
  --location {location} \
  --sku Premium \
  --vm-size P1 \
  --shard-count 3 \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Create Premium with VNet Integration

```bash
az redis create \
  --name {cache_name} \
  --resource-group {resource_group} \
  --location {location} \
  --sku Premium \
  --vm-size P1 \
  --subnet-id "/subscriptions/{subscription}/resourceGroups/{resource_group}/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/{subnet}" \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

### Create with Specific Redis Version

```bash
az redis create \
  --name {cache_name} \
  --resource-group {resource_group} \
  --location {location} \
  --sku Standard \
  --vm-size C1 \
  --redis-version 6 \
  --tags Project=tmux-builder Environment=production ManagedBy=claude
```

## Configure Redis Settings

### Enable Non-SSL Port (Not Recommended for Production)

```bash
az redis update \
  --name {cache_name} \
  --resource-group {resource_group} \
  --set enableNonSslPort=true
```

### Configure Redis Settings

```bash
az redis update \
  --name {cache_name} \
  --resource-group {resource_group} \
  --set redisConfiguration.maxmemory-policy=allkeys-lru
```

### Set Maxmemory Policy

```bash
az redis update \
  --name {cache_name} \
  --resource-group {resource_group} \
  --set redisConfiguration.maxmemory-policy=volatile-lru
```

### Configure Persistence (Premium Only)

```bash
az redis update \
  --name {cache_name} \
  --resource-group {resource_group} \
  --set redisConfiguration.rdb-backup-enabled=true \
  --set redisConfiguration.rdb-backup-frequency=60 \
  --set redisConfiguration.rdb-storage-connection-string="{storage_connection_string}"
```

## Scale Redis Cache

### Scale Up (Change Size)

```bash
az redis update \
  --name {cache_name} \
  --resource-group {resource_group} \
  --sku Standard \
  --vm-size C2
```

### Add Shards (Premium Only)

```bash
az redis update \
  --name {cache_name} \
  --resource-group {resource_group} \
  --shard-count 5
```

## Firewall Configuration (Premium Only)

### Add Firewall Rule

```bash
az redis firewall-rules create \
  --name {cache_name} \
  --resource-group {resource_group} \
  --rule-name AllowMyIP \
  --start-ip {start_ip} \
  --end-ip {end_ip}
```

### List Firewall Rules

```bash
az redis firewall-rules list \
  --name {cache_name} \
  --resource-group {resource_group} \
  --output table
```

## Verification

Check cache status and get connection details:

```bash
# Get cache provisioning state
az redis show \
  --name {cache_name} \
  --resource-group {resource_group} \
  --query "provisioningState" \
  --output tsv

# Get cache hostname
az redis show \
  --name {cache_name} \
  --resource-group {resource_group} \
  --query "hostName" \
  --output tsv

# Get SSL port
az redis show \
  --name {cache_name} \
  --resource-group {resource_group} \
  --query "sslPort" \
  --output tsv

# Get access keys
az redis list-keys \
  --name {cache_name} \
  --resource-group {resource_group}

# Get primary connection string
az redis show \
  --name {cache_name} \
  --resource-group {resource_group} \
  --query "{host: hostName, port: sslPort}" \
  --output json
```

Connection string format:
```
{cache_name}.redis.cache.windows.net:6380,password={access_key},ssl=True,abortConnect=False
```

### Test Connection with redis-cli

```bash
# Install redis-cli if needed
# apt-get install redis-tools

# Connect to Azure Redis (SSL)
redis-cli -h {cache_name}.redis.cache.windows.net -p 6380 -a {access_key} --tls

# Test basic commands
> PING
PONG
> SET test "hello"
OK
> GET test
"hello"
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `NameNotAvailable` | Cache name taken globally | Choose unique cache name |
| `QuotaExceeded` | Subscription limit reached | Request quota increase |
| `InvalidSku` | Invalid SKU/size combination | Check valid SKU and size options |
| `SubnetNotFound` | VNet subnet doesn't exist | Create subnet or verify ID |
| `AuthenticationFailed` | Wrong access key | Get fresh key with list-keys |

## Notes

- Redis cache creation takes 15-20 minutes
- Cache names must be globally unique
- Basic tier has no SLA and no replication (dev/test only)
- Standard tier includes primary/replica for high availability
- Premium tier adds clustering, VNet, persistence, geo-replication
- Always use SSL port (6380) in production
- Access keys can be regenerated without downtime
- Consider using Azure Private Link for enhanced security
- Monitor cache metrics in Azure Portal (hits, misses, connections)
- Free tier not available; Basic C0 is the cheapest option
