# ElastiCache Setup Skill

## Purpose

Create and configure Amazon ElastiCache clusters for in-memory caching using Redis or Memcached to improve application performance.

## Prerequisites

- AWS CLI installed and configured
- `sunwaretech` AWS profile configured with appropriate permissions
- VPC with appropriate subnets for cache placement
- Security group allowing Redis (6379) or Memcached (11211) traffic

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `cluster_id` | Unique cluster identifier | Yes | `myapp-cache-prod` |
| `engine` | Cache engine | Yes | `redis`, `memcached` |
| `node_type` | Node instance type | Yes | `cache.t3.micro` |
| `num_cache_nodes` | Number of nodes (Memcached) | Yes* | `1` |
| `num_node_groups` | Number of shards (Redis cluster) | No | `1` |
| `replicas_per_node_group` | Replicas per shard | No | `1` |
| `cache_subnet_group` | Subnet group name | Yes | `my-cache-subnet-group` |
| `security_group_ids` | Security group IDs | Yes | `sg-12345678` |
| `parameter_group` | Parameter group name | No | `default.redis7` |

## Usage Examples

### Set AWS Profile

Always set the AWS profile before running commands:

```bash
export AWS_PROFILE=sunwaretech
export AWS_DEFAULT_REGION=us-east-1
```

### Create Cache Subnet Group

```bash
export AWS_PROFILE=sunwaretech
aws elasticache create-cache-subnet-group \
  --cache-subnet-group-name {cache_subnet_group} \
  --cache-subnet-group-description "Subnet group for {cluster_id}" \
  --subnet-ids subnet-11111111 subnet-22222222 \
  --tags Key=Project,Value=tmux-builder Key=ManagedBy,Value=claude
```

### Create Redis Cluster (Single Node)

```bash
export AWS_PROFILE=sunwaretech
aws elasticache create-cache-cluster \
  --cache-cluster-id {cluster_id} \
  --engine redis \
  --engine-version 7.0 \
  --cache-node-type {node_type} \
  --num-cache-nodes 1 \
  --cache-subnet-group-name {cache_subnet_group} \
  --security-group-ids {security_group_ids} \
  --tags Key=Project,Value=tmux-builder Key=Environment,Value=production Key=ManagedBy,Value=claude
```

### Create Redis Replication Group (High Availability)

```bash
export AWS_PROFILE=sunwaretech
aws elasticache create-replication-group \
  --replication-group-id {cluster_id} \
  --replication-group-description "Redis replication group for {cluster_id}" \
  --engine redis \
  --engine-version 7.0 \
  --cache-node-type {node_type} \
  --num-node-groups 1 \
  --replicas-per-node-group 1 \
  --cache-subnet-group-name {cache_subnet_group} \
  --security-group-ids {security_group_ids} \
  --automatic-failover-enabled \
  --multi-az-enabled \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled \
  --tags Key=Project,Value=tmux-builder Key=Environment,Value=production Key=ManagedBy,Value=claude
```

### Create Memcached Cluster

```bash
export AWS_PROFILE=sunwaretech
aws elasticache create-cache-cluster \
  --cache-cluster-id {cluster_id} \
  --engine memcached \
  --engine-version 1.6.17 \
  --cache-node-type {node_type} \
  --num-cache-nodes 2 \
  --cache-subnet-group-name {cache_subnet_group} \
  --security-group-ids {security_group_ids} \
  --tags Key=Project,Value=tmux-builder Key=Environment,Value=production Key=ManagedBy,Value=claude
```

### Create Redis Cluster Mode Enabled (Sharding)

```bash
export AWS_PROFILE=sunwaretech
aws elasticache create-replication-group \
  --replication-group-id {cluster_id} \
  --replication-group-description "Redis cluster mode enabled" \
  --engine redis \
  --engine-version 7.0 \
  --cache-node-type cache.t3.medium \
  --num-node-groups 3 \
  --replicas-per-node-group 1 \
  --cache-subnet-group-name {cache_subnet_group} \
  --security-group-ids {security_group_ids} \
  --automatic-failover-enabled \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled \
  --tags Key=Project,Value=tmux-builder Key=Environment,Value=production
```

## Configuration Options

### Create Custom Parameter Group

```bash
export AWS_PROFILE=sunwaretech
aws elasticache create-cache-parameter-group \
  --cache-parameter-group-name my-redis-params \
  --cache-parameter-group-family redis7 \
  --description "Custom Redis parameters" \
  --tags Key=Project,Value=tmux-builder

# Modify parameters
aws elasticache modify-cache-parameter-group \
  --cache-parameter-group-name my-redis-params \
  --parameter-name-values "ParameterName=maxmemory-policy,ParameterValue=allkeys-lru"
```

## Verification

Check cluster status and get connection endpoint:

```bash
export AWS_PROFILE=sunwaretech

# Get cache cluster status
aws elasticache describe-cache-clusters \
  --cache-cluster-id {cluster_id} \
  --query 'CacheClusters[0].CacheClusterStatus' \
  --output text

# Get cache cluster endpoint (single node)
aws elasticache describe-cache-clusters \
  --cache-cluster-id {cluster_id} \
  --show-cache-node-info \
  --query 'CacheClusters[0].CacheNodes[0].Endpoint.[Address,Port]' \
  --output text

# Get replication group endpoint (HA)
aws elasticache describe-replication-groups \
  --replication-group-id {cluster_id} \
  --query 'ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint.[Address,Port]' \
  --output text

# Wait for cluster to be available
aws elasticache wait cache-cluster-available \
  --cache-cluster-id {cluster_id}
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `CacheClusterAlreadyExists` | Cluster ID taken | Use unique cluster identifier |
| `InsufficientCacheClusterCapacity` | Node type unavailable | Try different node type |
| `InvalidCacheSecurityGroupState` | Security group issues | Verify security group configuration |
| `CacheSubnetGroupNotFoundFault` | Subnet group missing | Create subnet group first |
| `ReplicationGroupAlreadyExists` | Replication group exists | Use unique replication group ID |

## Notes

- ElastiCache creation takes 5-15 minutes
- Redis supports persistence, Memcached is volatile only
- Free tier: cache.t3.micro with 750 hours/month
- Use replication groups for production Redis workloads
- Redis cluster mode enables sharding for larger datasets
- Transit encryption requires TLS-enabled clients
- ElastiCache is VPC-only, not publicly accessible
- Consider using ElastiCache Global Datastore for cross-region replication
