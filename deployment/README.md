# Tmux Builder - Deployment Guide

This folder contains scripts and documentation for deploying the Tmux Builder application to AWS.

## Architecture Overview

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                     CloudFront                               │
                    │              d3tfeatcbws1ka.cloudfront.net                   │
                    │                                                              │
                    │  ┌──────────┐  ┌──────────┐  ┌──────────────┐               │
                    │  │ /* (def) │  │ /api/*   │  │ /ws/* (note) │               │
                    │  └────┬─────┘  └────┬─────┘  └──────────────┘               │
                    └───────┼─────────────┼────────────────────────────────────────┘
                            │             │
                            ▼             ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                           EC2 Instance (t3.medium)                                │
│                           IP: 18.211.207.2                                        │
│                                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │  Frontend       │  │  Backend API    │  │  WebSocket      │  │  Nginx SSL   │ │
│  │  (serve)        │  │  (FastAPI)      │  │  (ws_server)    │  │  Proxy       │ │
│  │  Port: 3001     │  │  Port: 8080     │  │  Port: 8082     │  │  Port: 8443  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └──────┬───────┘ │
│                                                                        │         │
│                                                   Proxies to ──────────┘         │
│                                                   Port 8082                      │
└───────────────────────────────────────────────────────────────────────────────────┘
```

**Note:** WebSocket now works through CloudFront (wss://d3tfeatcbws1ka.cloudfront.net/ws/{guid}). The nginx SSL proxy on port 8443 is available as a fallback but not required.

## Quick Start

```bash
# 1. Check current status
./aws-setup.sh show-status

# 2. Run complete AWS setup (resize, security rules, CloudFront)
./aws-setup.sh setup-all

# 3. Deploy application to EC2
./ec2-deploy.sh deploy

# 4. Verify deployment
./ec2-deploy.sh status
```

## Files

| File | Description |
|------|-------------|
| `aws-setup.sh` | AWS infrastructure setup (EC2 resize, security groups, CloudFront) |
| `ec2-deploy.sh` | Application deployment to EC2 (code, dependencies, services) |
| `README.md` | This documentation |

## AWS Infrastructure

### AWS Account

| Property | Value |
|----------|-------|
| Account Name | CoCreate |
| Account ID | 248825820556 |
| AWS Profile | `cocreate` |
| Region | us-east-1 |

### EC2 Instance

| Property | Value |
|----------|-------|
| Instance ID | `i-02295df495905ba4b` |
| Name | tmux-builder |
| Type | t3.medium (2 vCPU, 4GB RAM) |
| Region | us-east-1 |
| Public IP | 18.211.207.2 (changes on stop/start) |

### Security Group

| Property | Value |
|----------|-------|
| Group ID | `sg-0efa0764ef31b465b` |
| Group Name | tmux-builder-sg |

**Inbound Rules:**

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 22 | TCP | 0.0.0.0/0 | SSH |
| 80 | TCP | 0.0.0.0/0 | HTTP |
| 443 | TCP | 0.0.0.0/0 | HTTPS |
| 3001 | TCP | 0.0.0.0/0 | Frontend (serve) |
| 8080 | TCP | 0.0.0.0/0 | Backend API |
| 8082 | TCP | 0.0.0.0/0 | WebSocket server |
| 8443 | TCP | 0.0.0.0/0 | Nginx WSS proxy |

### CloudFront Distribution

| Property | Value |
|----------|-------|
| Distribution ID | `E2FOQ8U2IQP3GC` |
| Domain | `d3tfeatcbws1ka.cloudfront.net` |
| Origin | `ec2-18-211-207-2.compute-1.amazonaws.com` |

**Cache Behaviors:**

| Path Pattern | Origin | Cache Policy | Notes |
|--------------|--------|--------------|-------|
| `/*` (default) | tmux-builder-ec2-origin | CachingOptimized | Static assets |
| `/api/*` | tmux-builder-ec2-origin | CachingDisabled | API requests |
| `/ws/*` | tmux-builder-ec2-origin | CachingDisabled | WebSocket |

## Application Services

### PM2 Processes

| Name | Script | Port | Description |
|------|--------|------|-------------|
| tmux-backend | `python main.py` | 8080 | FastAPI REST API |
| tmux-websocket | `python ws_server.py` | 8082 | WebSocket server |
| tmux-frontend | `npx serve -s dist` | 3001 | Static file server |

### ecosystem.config.js

**Important:** The `BACKEND_PORT` environment variable must be set to `8080`:

```javascript
env: {
  PYTHONPATH: '/home/ubuntu/tmux-builder/backend',
  BACKEND_PORT: '8080',
  ANTHROPIC_API_KEY: 'your-api-key'
}
```

### Nginx Configuration

Location: `/etc/nginx/sites-available/wss`

```nginx
server {
    listen 8443 ssl;
    server_name _;

    ssl_certificate /etc/nginx/ssl/server.crt;
    ssl_certificate_key /etc/nginx/ssl/server.key;

    location /ws/ {
        proxy_pass http://127.0.0.1:8082;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

## Access URLs

| Purpose | URL |
|---------|-----|
| Frontend (CloudFront) | https://d3tfeatcbws1ka.cloudfront.net |
| Frontend (Direct) | http://18.211.207.2:3001 |
| API | https://d3tfeatcbws1ka.cloudfront.net/api/* |
| WebSocket (CloudFront) | wss://d3tfeatcbws1ka.cloudfront.net/ws/{guid} |
| WebSocket (Direct/Fallback) | wss://18.211.207.2:8443/ws/{guid} |

## SSH Access

```bash
# Using the PEM key
ssh -i C:\Projects\ai-product-studio\tmux-builder-key.pem ubuntu@18.211.207.2

# Or using AWS SSM (no key needed)
aws ssm start-session --target i-02295df495905ba4b --profile cocreate --region us-east-1
```

**SSH Key Location:** `C:\Projects\ai-product-studio\tmux-builder-key.pem`

## Common Operations

### Restart Services
```bash
ssh -i C:\Projects\ai-product-studio\tmux-builder-key.pem ubuntu@18.211.207.2 "pm2 restart all"
```

### View Logs
```bash
ssh -i C:\Projects\ai-product-studio\tmux-builder-key.pem ubuntu@18.211.207.2 "pm2 logs"
```

### Invalidate CloudFront Cache
```bash
aws cloudfront create-invalidation --profile cocreate \
    --distribution-id E2FOQ8U2IQP3GC --paths "/*"
```

### Check Service Status
```bash
ssh -i C:\Projects\ai-product-studio\tmux-builder-key.pem ubuntu@18.211.207.2 \
    "pm2 list && ss -tlnp | grep -E '(8080|8082|3001|8443)'"
```

### Check Instance Status
```bash
aws ec2 describe-instances --instance-ids i-02295df495905ba4b \
    --profile cocreate --region us-east-1 \
    --query 'Reservations[].Instances[].[State.Name,PublicIpAddress]' --output table
```

## Troubleshooting

### Backend Not Responding on Port 8080
1. Check if `BACKEND_PORT=8080` is set in ecosystem.config.js
2. Restart with: `pm2 delete tmux-backend && pm2 start ecosystem.config.js --only tmux-backend`
3. Verify port is listening: `ss -tlnp | grep 8080`

### WebSocket Not Connecting
1. Check nginx is running: `sudo systemctl status nginx`
2. Check port 8443 is open in security group
3. Browser may warn about self-signed cert - accept it first by visiting https://IP:8443

### CloudFront Serving Old Content
```bash
aws cloudfront create-invalidation --profile cocreate \
    --distribution-id E2FOQ8U2IQP3GC --paths "/*"
```

### PM2 Services Not Starting
```bash
ssh -i C:\Projects\ai-product-studio\tmux-builder-key.pem ubuntu@18.211.207.2 \
    "pm2 delete all && cd ~/tmux-builder && pm2 start ecosystem.config.js"
```

### Instance IP Changed After Restart
1. Get new IP: `aws ec2 describe-instances --instance-ids i-02295df495905ba4b --profile cocreate --region us-east-1 --query 'Reservations[].Instances[].PublicIpAddress' --output text`
2. Update CloudFront origin with new EC2 DNS name
3. Invalidate CloudFront cache

## Cost Estimate

| Resource | Hourly | Monthly (730h) |
|----------|--------|----------------|
| t3.medium | $0.0416 | ~$30 |
| CloudFront | - | ~$1-5 (usage based) |
| **Total** | - | **~$31-35** |

## Maintenance Checklist

- [ ] Monitor disk usage (`df -h`)
- [ ] Check PM2 process health (`pm2 monit`)
- [ ] Review backend logs for errors
- [ ] Rotate SSL certificates before expiry
- [ ] Update dependencies periodically
