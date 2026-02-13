# RDS Configure Skill

## Purpose

Create and configure Amazon RDS database instances for relational database hosting with automated backups, patching, and high availability options.

## Prerequisites

- AWS CLI installed and configured
- `cocreate` AWS profile configured with appropriate permissions
- VPC with appropriate subnets for database placement
- Security group allowing database traffic

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `db_identifier` | Unique database instance identifier | Yes | `myapp-db-prod` |
| `db_name` | Initial database name | Yes | `myapp` |
| `engine` | Database engine | Yes | `postgres`, `mysql`, `mariadb` |
| `engine_version` | Engine version | No | `15.4`, `8.0.35` |
| `instance_class` | Instance size | Yes | `db.t3.micro` |
| `master_username` | Master username | Yes | `admin` |
| `master_password` | Master password | Yes | (secure password) |
| `allocated_storage` | Storage in GB | No | `20` |
| `vpc_security_group_ids` | Security group IDs | Yes | `sg-12345678` |
| `db_subnet_group` | Subnet group name | Yes | `my-db-subnet-group` |

## Usage Examples

### Set AWS Profile

Always set the AWS profile before running commands:

```bash
export AWS_PROFILE=cocreate
export AWS_DEFAULT_REGION=us-east-1
```

### Create DB Subnet Group

```bash
export AWS_PROFILE=cocreate
aws rds create-db-subnet-group \
  --db-subnet-group-name {db_subnet_group} \
  --db-subnet-group-description "Subnet group for {db_identifier}" \
  --subnet-ids subnet-11111111 subnet-22222222 \
  --tags Key=Project,Value=tmux-builder Key=ManagedBy,Value=claude
```

### Create PostgreSQL Instance

```bash
export AWS_PROFILE=cocreate
aws rds create-db-instance \
  --db-instance-identifier {db_identifier} \
  --db-name {db_name} \
  --engine postgres \
  --engine-version 15.4 \
  --db-instance-class {instance_class} \
  --master-username {master_username} \
  --master-user-password "{master_password}" \
  --allocated-storage 20 \
  --storage-type gp3 \
  --vpc-security-group-ids {vpc_security_group_ids} \
  --db-subnet-group-name {db_subnet_group} \
  --backup-retention-period 7 \
  --no-publicly-accessible \
  --tags Key=Project,Value=tmux-builder Key=Environment,Value=production Key=ManagedBy,Value=claude
```

### Create MySQL Instance

```bash
export AWS_PROFILE=cocreate
aws rds create-db-instance \
  --db-instance-identifier {db_identifier} \
  --db-name {db_name} \
  --engine mysql \
  --engine-version 8.0.35 \
  --db-instance-class {instance_class} \
  --master-username {master_username} \
  --master-user-password "{master_password}" \
  --allocated-storage 20 \
  --storage-type gp3 \
  --vpc-security-group-ids {vpc_security_group_ids} \
  --db-subnet-group-name {db_subnet_group} \
  --backup-retention-period 7 \
  --no-publicly-accessible \
  --tags Key=Project,Value=tmux-builder Key=Environment,Value=production Key=ManagedBy,Value=claude
```

### Create with Multi-AZ for High Availability

```bash
export AWS_PROFILE=cocreate
aws rds create-db-instance \
  --db-instance-identifier {db_identifier} \
  --db-name {db_name} \
  --engine postgres \
  --db-instance-class db.t3.medium \
  --master-username {master_username} \
  --master-user-password "{master_password}" \
  --allocated-storage 50 \
  --multi-az \
  --storage-encrypted \
  --vpc-security-group-ids {vpc_security_group_ids} \
  --db-subnet-group-name {db_subnet_group} \
  --tags Key=Project,Value=tmux-builder Key=Environment,Value=production
```

## Modify Existing Instance

### Scale Instance Class

```bash
export AWS_PROFILE=cocreate
aws rds modify-db-instance \
  --db-instance-identifier {db_identifier} \
  --db-instance-class db.t3.medium \
  --apply-immediately
```

### Increase Storage

```bash
export AWS_PROFILE=cocreate
aws rds modify-db-instance \
  --db-instance-identifier {db_identifier} \
  --allocated-storage 50 \
  --apply-immediately
```

## Verification

Check database instance status and get connection endpoint:

```bash
export AWS_PROFILE=cocreate

# Get instance status
aws rds describe-db-instances \
  --db-instance-identifier {db_identifier} \
  --query 'DBInstances[0].DBInstanceStatus' \
  --output text

# Get connection endpoint
aws rds describe-db-instances \
  --db-instance-identifier {db_identifier} \
  --query 'DBInstances[0].Endpoint.[Address,Port]' \
  --output text

# Wait for instance to be available
aws rds wait db-instance-available \
  --db-instance-identifier {db_identifier}
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `DBInstanceAlreadyExists` | Instance name taken | Use unique identifier |
| `InsufficientDBInstanceCapacity` | Instance type unavailable | Try different instance class |
| `InvalidVPCNetworkStateFault` | VPC/subnet issues | Verify subnet group configuration |
| `StorageTypeNotSupported` | Storage type not valid for engine | Use supported storage type |
| `InvalidParameterValue` | Bad password format | Use alphanumeric password without special chars |

## Notes

- RDS instance creation takes 5-15 minutes
- Store master password securely (use AWS Secrets Manager)
- Enable encryption for production databases
- Free tier: db.t3.micro with 20GB storage (750 hours/month)
- Multi-AZ doubles the cost but provides automatic failover
- Automated backups are free up to the size of the database
- Consider read replicas for read-heavy workloads
- Use parameter groups to customize database settings
