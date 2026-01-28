#!/bin/bash
#
# AWS Infrastructure Setup Script for Tmux Builder
#
# This script recreates all AWS infrastructure changes required to deploy
# the tmux-builder application. Run with --help for usage information.
#
# Prerequisites:
#   - AWS CLI configured with 'sunwaretech' profile (or modify PROFILE variable)
#   - Sufficient IAM permissions for EC2, CloudFront operations
#
# Created: 2026-01-28
# Last Updated: 2026-01-28

set -e

#------------------------------------------------------------------------------
# Configuration
#------------------------------------------------------------------------------
PROFILE="sunwaretech"
REGION="us-east-1"
INSTANCE_ID="i-07dd29bd83fa7a0a8"
SECURITY_GROUP_ID="sg-03b2164de3520948d"
INSTANCE_TYPE="t3.xlarge"
VOLUME_SIZE=100

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

#------------------------------------------------------------------------------
# Helper Functions
#------------------------------------------------------------------------------
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install it first."
        exit 1
    fi

    if ! aws --profile "$PROFILE" sts get-caller-identity &> /dev/null; then
        log_error "AWS profile '$PROFILE' not configured or invalid credentials."
        exit 1
    fi

    log_info "AWS CLI configured with profile: $PROFILE"
}

usage() {
    cat << EOF
Usage: $0 [OPTIONS] COMMAND

Commands:
  resize-instance     Resize EC2 instance (stop, modify, start)
  add-security-rules  Add required security group rules
  create-cloudfront   Create CloudFront distribution
  setup-all           Run all setup steps
  show-status         Show current infrastructure status

Options:
  --profile PROFILE   AWS profile to use (default: sunwaretech)
  --region REGION     AWS region (default: us-east-1)
  --dry-run           Show what would be done without making changes
  -h, --help          Show this help message

Examples:
  $0 setup-all                    # Run complete setup
  $0 --dry-run resize-instance    # Preview instance resize
  $0 show-status                  # Check current state
EOF
}

#------------------------------------------------------------------------------
# EC2 Instance Resize
#------------------------------------------------------------------------------
resize_instance() {
    log_info "=== Resizing EC2 Instance ==="

    # Get current instance info
    CURRENT_TYPE=$(aws --profile "$PROFILE" --region "$REGION" \
        ec2 describe-instances --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].InstanceType' --output text)

    CURRENT_STATE=$(aws --profile "$PROFILE" --region "$REGION" \
        ec2 describe-instances --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].State.Name' --output text)

    VOLUME_ID=$(aws --profile "$PROFILE" --region "$REGION" \
        ec2 describe-instances --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].BlockDeviceMappings[0].Ebs.VolumeId' --output text)

    log_info "Current instance type: $CURRENT_TYPE"
    log_info "Current state: $CURRENT_STATE"
    log_info "Volume ID: $VOLUME_ID"

    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN: Would resize instance to $INSTANCE_TYPE and volume to ${VOLUME_SIZE}GB"
        return
    fi

    # Stop instance if running
    if [ "$CURRENT_STATE" = "running" ]; then
        log_info "Stopping instance..."
        aws --profile "$PROFILE" --region "$REGION" \
            ec2 stop-instances --instance-ids "$INSTANCE_ID" > /dev/null

        log_info "Waiting for instance to stop..."
        aws --profile "$PROFILE" --region "$REGION" \
            ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"
        log_info "Instance stopped."
    fi

    # Modify instance type
    if [ "$CURRENT_TYPE" != "$INSTANCE_TYPE" ]; then
        log_info "Changing instance type to $INSTANCE_TYPE..."
        aws --profile "$PROFILE" --region "$REGION" \
            ec2 modify-instance-attribute --instance-id "$INSTANCE_ID" \
            --instance-type "{\"Value\": \"$INSTANCE_TYPE\"}"
    fi

    # Modify volume size
    CURRENT_SIZE=$(aws --profile "$PROFILE" --region "$REGION" \
        ec2 describe-volumes --volume-ids "$VOLUME_ID" \
        --query 'Volumes[0].Size' --output text)

    if [ "$CURRENT_SIZE" -lt "$VOLUME_SIZE" ]; then
        log_info "Expanding volume from ${CURRENT_SIZE}GB to ${VOLUME_SIZE}GB..."
        aws --profile "$PROFILE" --region "$REGION" \
            ec2 modify-volume --volume-id "$VOLUME_ID" --size "$VOLUME_SIZE" > /dev/null
    fi

    # Start instance
    log_info "Starting instance..."
    aws --profile "$PROFILE" --region "$REGION" \
        ec2 start-instances --instance-ids "$INSTANCE_ID" > /dev/null

    log_info "Waiting for instance to start..."
    aws --profile "$PROFILE" --region "$REGION" \
        ec2 wait instance-running --instance-ids "$INSTANCE_ID"

    # Get new public IP
    NEW_IP=$(aws --profile "$PROFILE" --region "$REGION" \
        ec2 describe-instances --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

    log_info "Instance resized successfully!"
    log_info "New public IP: $NEW_IP"
    echo ""
    log_warn "IMPORTANT: Update SSH config and application configs with new IP: $NEW_IP"
}

#------------------------------------------------------------------------------
# Security Group Rules
#------------------------------------------------------------------------------
add_security_rules() {
    log_info "=== Adding Security Group Rules ==="

    # Define ports to add
    declare -a PORTS=(
        "3001:Frontend (serve)"
        "8080:Backend API"
        "8082:WebSocket server"
        "8443:Nginx WSS proxy"
    )

    for PORT_DESC in "${PORTS[@]}"; do
        PORT="${PORT_DESC%%:*}"
        DESC="${PORT_DESC#*:}"

        if [ "$DRY_RUN" = true ]; then
            log_warn "DRY RUN: Would add port $PORT ($DESC)"
            continue
        fi

        # Check if rule already exists
        EXISTING=$(aws --profile "$PROFILE" --region "$REGION" \
            ec2 describe-security-groups --group-ids "$SECURITY_GROUP_ID" \
            --query "SecurityGroups[0].IpPermissions[?FromPort==\`$PORT\`]" --output text)

        if [ -n "$EXISTING" ]; then
            log_info "Port $PORT already open ($DESC)"
        else
            log_info "Adding port $PORT ($DESC)..."
            aws --profile "$PROFILE" --region "$REGION" \
                ec2 authorize-security-group-ingress \
                --group-id "$SECURITY_GROUP_ID" \
                --protocol tcp \
                --port "$PORT" \
                --cidr 0.0.0.0/0 > /dev/null
        fi
    done

    log_info "Security group rules configured."
}

#------------------------------------------------------------------------------
# CloudFront Distribution
#------------------------------------------------------------------------------
create_cloudfront() {
    log_info "=== Creating CloudFront Distribution ==="

    # Get EC2 public DNS
    EC2_DNS=$(aws --profile "$PROFILE" --region "$REGION" \
        ec2 describe-instances --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].PublicDnsName' --output text)

    log_info "EC2 DNS: $EC2_DNS"

    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN: Would create CloudFront distribution with origin $EC2_DNS"
        return
    fi

    # Create distribution config
    CALLER_REF="tmux-builder-$(date +%s)"

    cat > /tmp/cf-config.json << EOF
{
    "CallerReference": "$CALLER_REF",
    "Comment": "Tmux Builder Distribution",
    "DefaultCacheBehavior": {
        "TargetOriginId": "tmux-frontend",
        "ViewerProtocolPolicy": "redirect-to-https",
        "AllowedMethods": {
            "Quantity": 2,
            "Items": ["GET", "HEAD"],
            "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}
        },
        "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
        "Compress": true
    },
    "Origins": {
        "Quantity": 3,
        "Items": [
            {
                "Id": "tmux-frontend",
                "DomainName": "$EC2_DNS",
                "CustomOriginConfig": {
                    "HTTPPort": 3001, "HTTPSPort": 443,
                    "OriginProtocolPolicy": "http-only",
                    "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]},
                    "OriginReadTimeout": 30, "OriginKeepaliveTimeout": 5
                }
            },
            {
                "Id": "tmux-backend",
                "DomainName": "$EC2_DNS",
                "CustomOriginConfig": {
                    "HTTPPort": 8080, "HTTPSPort": 443,
                    "OriginProtocolPolicy": "http-only",
                    "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]},
                    "OriginReadTimeout": 60, "OriginKeepaliveTimeout": 60
                }
            },
            {
                "Id": "tmux-websocket",
                "DomainName": "$EC2_DNS",
                "CustomOriginConfig": {
                    "HTTPPort": 8082, "HTTPSPort": 443,
                    "OriginProtocolPolicy": "http-only",
                    "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]},
                    "OriginReadTimeout": 60, "OriginKeepaliveTimeout": 60
                }
            }
        ]
    },
    "CacheBehaviors": {
        "Quantity": 2,
        "Items": [
            {
                "PathPattern": "/ws/*",
                "TargetOriginId": "tmux-websocket",
                "ViewerProtocolPolicy": "https-only",
                "AllowedMethods": {
                    "Quantity": 3, "Items": ["HEAD", "GET", "OPTIONS"],
                    "CachedMethods": {"Quantity": 2, "Items": ["HEAD", "GET"]}
                },
                "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
                "OriginRequestPolicyId": "216adef6-5c7f-47e4-b989-5492eafa07d3",
                "Compress": false
            },
            {
                "PathPattern": "/api/*",
                "TargetOriginId": "tmux-backend",
                "ViewerProtocolPolicy": "redirect-to-https",
                "AllowedMethods": {
                    "Quantity": 7,
                    "Items": ["HEAD", "DELETE", "POST", "GET", "OPTIONS", "PUT", "PATCH"],
                    "CachedMethods": {"Quantity": 2, "Items": ["HEAD", "GET"]}
                },
                "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
                "OriginRequestPolicyId": "216adef6-5c7f-47e4-b989-5492eafa07d3",
                "Compress": true
            }
        ]
    },
    "Enabled": true,
    "PriceClass": "PriceClass_100",
    "HttpVersion": "http2",
    "IsIPV6Enabled": true
}
EOF

    log_info "Creating CloudFront distribution..."
    RESULT=$(aws --profile "$PROFILE" \
        cloudfront create-distribution \
        --distribution-config file:///tmp/cf-config.json \
        --query 'Distribution.{Id:Id,DomainName:DomainName,Status:Status}' \
        --output json)

    echo "$RESULT"
    log_info "CloudFront distribution created!"
    log_warn "Note: Distribution deployment takes 5-15 minutes."

    rm /tmp/cf-config.json
}

#------------------------------------------------------------------------------
# Show Status
#------------------------------------------------------------------------------
show_status() {
    log_info "=== Current Infrastructure Status ==="
    echo ""

    # EC2 Instance
    log_info "EC2 Instance ($INSTANCE_ID):"
    aws --profile "$PROFILE" --region "$REGION" \
        ec2 describe-instances --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].{Type:InstanceType,State:State.Name,PublicIP:PublicIpAddress,PublicDNS:PublicDnsName}' \
        --output table

    # Volume
    VOLUME_ID=$(aws --profile "$PROFILE" --region "$REGION" \
        ec2 describe-instances --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].BlockDeviceMappings[0].Ebs.VolumeId' --output text)

    log_info "EBS Volume ($VOLUME_ID):"
    aws --profile "$PROFILE" --region "$REGION" \
        ec2 describe-volumes --volume-ids "$VOLUME_ID" \
        --query 'Volumes[0].{Size:Size,State:State}' \
        --output table

    # Security Group
    log_info "Security Group Rules ($SECURITY_GROUP_ID):"
    aws --profile "$PROFILE" --region "$REGION" \
        ec2 describe-security-groups --group-ids "$SECURITY_GROUP_ID" \
        --query 'SecurityGroups[0].IpPermissions[*].{Port:FromPort,Protocol:IpProtocol,CIDR:IpRanges[0].CidrIp}' \
        --output table

    # CloudFront
    log_info "CloudFront Distributions:"
    aws --profile "$PROFILE" \
        cloudfront list-distributions \
        --query 'DistributionList.Items[?Comment==`Tmux Builder Distribution`].{Id:Id,Domain:DomainName,Status:Status}' \
        --output table
}

#------------------------------------------------------------------------------
# Main
#------------------------------------------------------------------------------
DRY_RUN=false
COMMAND=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            COMMAND="$1"
            shift
            ;;
    esac
done

if [ -z "$COMMAND" ]; then
    usage
    exit 1
fi

check_aws_cli

case $COMMAND in
    resize-instance)
        resize_instance
        ;;
    add-security-rules)
        add_security_rules
        ;;
    create-cloudfront)
        create_cloudfront
        ;;
    setup-all)
        resize_instance
        add_security_rules
        create_cloudfront
        ;;
    show-status)
        show_status
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac

log_info "Done!"
