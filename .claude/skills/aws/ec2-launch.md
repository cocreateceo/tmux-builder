# EC2 Launch Skill

## Purpose

Launch and configure Amazon EC2 instances for running applications, servers, or custom workloads with full control over the compute environment.

## Prerequisites

- AWS CLI installed and configured
- `cocreate` AWS profile configured with appropriate permissions
- VPC with appropriate subnets
- Security group configured for required traffic
- SSH key pair created for instance access

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `instance_name` | Name tag for the instance | Yes | `myapp-web-server` |
| `ami_id` | Amazon Machine Image ID | Yes | `ami-0c55b159cbfafe1f0` |
| `instance_type` | Instance size | Yes | `t3.micro` |
| `key_name` | SSH key pair name | Yes | `my-key-pair` |
| `subnet_id` | Subnet to launch in | Yes | `subnet-12345678` |
| `security_group_ids` | Security group IDs | Yes | `sg-12345678` |
| `iam_instance_profile` | IAM role for instance | No | `my-instance-role` |
| `user_data` | Bootstrap script | No | Base64 encoded script |

## Usage Examples

### Set AWS Profile

Always set the AWS profile before running commands:

```bash
export AWS_PROFILE=cocreate
export AWS_DEFAULT_REGION=us-east-1
```

### Find Latest Amazon Linux 2023 AMI

```bash
export AWS_PROFILE=cocreate
aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023*-x86_64" \
            "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text
```

### Find Latest Ubuntu 22.04 AMI

```bash
export AWS_PROFILE=cocreate
aws ec2 describe-images \
  --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
            "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text
```

### Create Key Pair

```bash
export AWS_PROFILE=cocreate
aws ec2 create-key-pair \
  --key-name {key_name} \
  --query 'KeyMaterial' \
  --output text > {key_name}.pem

chmod 400 {key_name}.pem
```

### Launch Basic Instance

```bash
export AWS_PROFILE=cocreate
aws ec2 run-instances \
  --image-id {ami_id} \
  --instance-type {instance_type} \
  --key-name {key_name} \
  --subnet-id {subnet_id} \
  --security-group-ids {security_group_ids} \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value={instance_name}},{Key=Project,Value=tmux-builder},{Key=Environment,Value=production},{Key=ManagedBy,Value=claude}]' \
  --query 'Instances[0].InstanceId' \
  --output text
```

### Launch with User Data (Bootstrap Script)

```bash
export AWS_PROFILE=cocreate

# Create user data script
cat << 'EOF' > user-data.sh
#!/bin/bash
yum update -y
yum install -y httpd
systemctl start httpd
systemctl enable httpd
echo "Hello from EC2" > /var/www/html/index.html
EOF

aws ec2 run-instances \
  --image-id {ami_id} \
  --instance-type {instance_type} \
  --key-name {key_name} \
  --subnet-id {subnet_id} \
  --security-group-ids {security_group_ids} \
  --user-data file://user-data.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value={instance_name}},{Key=Project,Value=tmux-builder}]' \
  --query 'Instances[0].InstanceId' \
  --output text
```

### Launch with IAM Role

```bash
export AWS_PROFILE=cocreate
aws ec2 run-instances \
  --image-id {ami_id} \
  --instance-type {instance_type} \
  --key-name {key_name} \
  --subnet-id {subnet_id} \
  --security-group-ids {security_group_ids} \
  --iam-instance-profile Name={iam_instance_profile} \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value={instance_name}},{Key=Project,Value=tmux-builder}]' \
  --query 'Instances[0].InstanceId' \
  --output text
```

### Launch with EBS Volume

```bash
export AWS_PROFILE=cocreate
aws ec2 run-instances \
  --image-id {ami_id} \
  --instance-type {instance_type} \
  --key-name {key_name} \
  --subnet-id {subnet_id} \
  --security-group-ids {security_group_ids} \
  --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":30,"VolumeType":"gp3","DeleteOnTermination":true,"Encrypted":true}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value={instance_name}},{Key=Project,Value=tmux-builder}]' 'ResourceType=volume,Tags=[{Key=Name,Value={instance_name}-volume},{Key=Project,Value=tmux-builder}]' \
  --query 'Instances[0].InstanceId' \
  --output text
```

### Launch with Public IP

```bash
export AWS_PROFILE=cocreate
aws ec2 run-instances \
  --image-id {ami_id} \
  --instance-type {instance_type} \
  --key-name {key_name} \
  --subnet-id {subnet_id} \
  --security-group-ids {security_group_ids} \
  --associate-public-ip-address \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value={instance_name}},{Key=Project,Value=tmux-builder}]' \
  --query 'Instances[0].InstanceId' \
  --output text
```

## Instance Management

### Stop Instance

```bash
export AWS_PROFILE=cocreate
aws ec2 stop-instances --instance-ids {instance_id}
```

### Start Instance

```bash
export AWS_PROFILE=cocreate
aws ec2 start-instances --instance-ids {instance_id}
```

### Terminate Instance

```bash
export AWS_PROFILE=cocreate
aws ec2 terminate-instances --instance-ids {instance_id}
```

## Verification

Check instance status and get connection details:

```bash
export AWS_PROFILE=cocreate

# Get instance state
aws ec2 describe-instances \
  --instance-ids {instance_id} \
  --query 'Reservations[0].Instances[0].State.Name' \
  --output text

# Get public IP address
aws ec2 describe-instances \
  --instance-ids {instance_id} \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text

# Get private IP address
aws ec2 describe-instances \
  --instance-ids {instance_id} \
  --query 'Reservations[0].Instances[0].PrivateIpAddress' \
  --output text

# Wait for instance to be running
aws ec2 wait instance-running --instance-ids {instance_id}

# Wait for status checks to pass
aws ec2 wait instance-status-ok --instance-ids {instance_id}
```

### SSH Connection

```bash
ssh -i {key_name}.pem ec2-user@{public_ip}     # Amazon Linux
ssh -i {key_name}.pem ubuntu@{public_ip}        # Ubuntu
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `InvalidAMIID.NotFound` | AMI doesn't exist in region | Use correct region-specific AMI |
| `InvalidKeyPair.NotFound` | Key pair doesn't exist | Create key pair first |
| `InsufficientInstanceCapacity` | Instance type unavailable | Try different AZ or instance type |
| `VPCIdNotSpecified` | No default VPC | Specify subnet-id explicitly |
| `UnauthorizedOperation` | Missing EC2 permissions | Add ec2:RunInstances permission |

## Notes

- EC2 instances launch in 30-60 seconds typically
- Free tier: t2.micro or t3.micro with 750 hours/month
- User data scripts run as root on first boot
- Always use encrypted EBS volumes for production
- Consider using Launch Templates for repeated configurations
- Instance metadata available at http://169.254.169.254
- Use Spot Instances for up to 90% cost savings on interruptible workloads
- Enable detailed monitoring for 1-minute CloudWatch metrics
