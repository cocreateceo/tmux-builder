# S3 Upload Skill

## Purpose

Upload files to AWS S3 bucket for static website hosting or general storage.

## Prerequisites

- AWS CLI installed and configured
- `cocreate` AWS profile configured with appropriate permissions
- S3 bucket must exist (create with `aws s3 mb` if needed)

## Parameters

| Parameter | Description | Required | Example |
|-----------|-------------|----------|---------|
| `bucket_name` | Target S3 bucket name | Yes | `my-website-bucket` |
| `source_dir` | Local directory or file to upload | Yes | `./dist/` or `./index.html` |

## Usage Examples

### Set AWS Profile

Always set the AWS profile before running commands:

```bash
export AWS_PROFILE=cocreate
```

### Upload Single File

```bash
export AWS_PROFILE=cocreate
aws s3 cp source/index.html s3://{bucket_name}/
```

### Upload Directory (Sync)

Sync a local directory to S3, removing files that no longer exist locally:

```bash
export AWS_PROFILE=cocreate
aws s3 sync source/ s3://{bucket_name}/ --delete
```

### Upload with Content Type

Specify content type for proper MIME handling:

```bash
export AWS_PROFILE=cocreate
aws s3 cp index.html s3://{bucket_name}/ --content-type "text/html"
```

### Upload with Cache Control

Set cache headers for static assets:

```bash
export AWS_PROFILE=cocreate
aws s3 sync ./assets/ s3://{bucket_name}/assets/ \
  --cache-control "max-age=31536000,public"
```

### Sync with Exclusions

Exclude certain files or patterns:

```bash
export AWS_PROFILE=cocreate
aws s3 sync source/ s3://{bucket_name}/ \
  --delete \
  --exclude "*.md" \
  --exclude ".git/*"
```

## Required Tags Section

Apply tags to S3 objects for cost tracking and organization:

### Tag Individual Object

```bash
export AWS_PROFILE=cocreate
aws s3api put-object-tagging \
  --bucket {bucket_name} \
  --key index.html \
  --tagging 'TagSet=[{Key=Project,Value=tmux-builder},{Key=Environment,Value=production}]'
```

### Tag Bucket

```bash
export AWS_PROFILE=cocreate
aws s3api put-bucket-tagging \
  --bucket {bucket_name} \
  --tagging 'TagSet=[{Key=Project,Value=tmux-builder},{Key=Environment,Value=production},{Key=ManagedBy,Value=claude}]'
```

## Verify Upload

Check that files were uploaded successfully:

```bash
export AWS_PROFILE=cocreate
aws s3 ls s3://{bucket_name}/ --recursive
```

## Notes

- Use `--dryrun` flag to preview changes before executing
- S3 sync only uploads changed files (based on size and timestamp)
- For large uploads, consider using `aws s3 cp` with `--recursive` for better progress visibility
- Bucket must have appropriate permissions for public access if hosting a website
