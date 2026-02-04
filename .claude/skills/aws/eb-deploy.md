# Elastic Beanstalk Deploy Skill

## Purpose

Deploy applications to AWS Elastic Beanstalk for managed hosting with automatic scaling, load balancing, and health monitoring.

## Prerequisites

- AWS CLI installed and configured
- `cocreate` AWS profile configured with appropriate permissions
- EB CLI installed (`pip install awsebcli`)
- Application source code ready for deployment
- (Optional) Elastic Beanstalk application already created

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `app_name` | Elastic Beanstalk application name | Yes | `my-web-app` |
| `env_name` | Environment name | Yes | `my-web-app-prod` |
| `platform` | Platform/runtime to use | Yes | `python-3.9`, `node.js-18` |
| `source_dir` | Directory containing application code | Yes | `./source/` |
| `instance_type` | EC2 instance type | No | `t3.micro` |
| `region` | AWS region | No | `us-east-1` |

## Usage Examples

### Set AWS Profile

Always set the AWS profile before running commands:

```bash
export AWS_PROFILE=cocreate
export AWS_DEFAULT_REGION=us-east-1
```

### Initialize Elastic Beanstalk Application

```bash
export AWS_PROFILE=cocreate
cd {source_dir}
eb init {app_name} --platform "{platform}" --region {region}
```

### Create New Environment

```bash
export AWS_PROFILE=cocreate
eb create {env_name} \
  --instance-type {instance_type} \
  --single \
  --tags Project=tmux-builder,Environment=production,ManagedBy=claude
```

### Deploy to Existing Environment

```bash
export AWS_PROFILE=cocreate
eb deploy {env_name}
```

### Deploy with Version Label

```bash
export AWS_PROFILE=cocreate
eb deploy {env_name} --label "v1.0.0-$(date +%Y%m%d%H%M%S)"
```

### Deploy Using AWS CLI (Alternative)

Create application version and deploy:

```bash
export AWS_PROFILE=cocreate

# Create application source bundle
cd {source_dir}
zip -r ../app-bundle.zip . -x "*.git*"

# Upload to S3
aws s3 cp ../app-bundle.zip s3://{bucket_name}/deployments/

# Create application version
aws elasticbeanstalk create-application-version \
  --application-name {app_name} \
  --version-label "v-$(date +%Y%m%d%H%M%S)" \
  --source-bundle S3Bucket={bucket_name},S3Key=deployments/app-bundle.zip

# Update environment
aws elasticbeanstalk update-environment \
  --application-name {app_name} \
  --environment-name {env_name} \
  --version-label "v-$(date +%Y%m%d%H%M%S)"
```

## Environment Configuration

### Set Environment Variables

```bash
export AWS_PROFILE=cocreate
eb setenv KEY1=value1 KEY2=value2 -e {env_name}
```

### Configure Auto Scaling

```bash
export AWS_PROFILE=cocreate
aws elasticbeanstalk update-environment \
  --environment-name {env_name} \
  --option-settings \
    Namespace=aws:autoscaling:asg,OptionName=MinSize,Value=1 \
    Namespace=aws:autoscaling:asg,OptionName=MaxSize,Value=4
```

## Verification

Check environment status and health:

```bash
export AWS_PROFILE=cocreate

# Get environment status
eb status {env_name}

# Get environment health
eb health {env_name}

# Get environment URL
aws elasticbeanstalk describe-environments \
  --environment-names {env_name} \
  --query 'Environments[0].CNAME' \
  --output text
```

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Environment not found` | Environment doesn't exist | Run `eb create` first |
| `Application version failed` | Bad source bundle | Check zip contents and Procfile |
| `Health check failing` | App not responding on port | Verify app listens on correct port |
| `Insufficient capacity` | Instance type unavailable | Try different instance type or AZ |
| `Permission denied` | Missing IAM permissions | Add elasticbeanstalk:* permissions |

## Notes

- Elastic Beanstalk manages EC2, ELB, Auto Scaling automatically
- Use `.ebextensions/` folder for custom configuration
- Include `Procfile` for Python/Node.js apps to define startup command
- Health checks default to HTTP on port 80
- Environment updates cause brief downtime unless using rolling deployments
- Consider using `.ebignore` to exclude files from deployment bundle
- Cost includes underlying EC2, ELB, and other AWS resources used
