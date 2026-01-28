# Tmux Builder - Deployment Guide

This folder contains scripts and documentation for deploying the Tmux Builder application to AWS.

## Architecture Overview

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                     CloudFront                               │
                    │              d3r4k77gnvpmzn.cloudfront.net                   │
                    │                                                              │
                    │  ┌──────────┐  ┌──────────┐  ┌──────────────┐               │
                    │  │ /* (def) │  │ /api/*   │  │ /ws/* (note) │               │
                    │  └────┬─────┘  └────┬─────┘  └──────────────┘               │
                    └───────┼─────────────┼────────────────────────────────────────┘
                            │             │
                            ▼             ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                           EC2 Instance (t3.xlarge)                                │
│                           IP: 184.73.78.154                                       │
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

**Note:** WebSocket now works through CloudFront (wss://d3r4k77gnvpmzn.cloudfront.net/ws/{guid}). The nginx SSL proxy on port 8443 is available as a fallback but not required.

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

### EC2 Instance

| Property | Value |
|----------|-------|
| Instance ID | `i-07dd29bd83fa7a0a8` |
| Name | ai-product-studio |
| Type | t3.xlarge (4 vCPU, 16GB RAM) |
| Storage | 100GB gp3 |
| Region | us-east-1 |
| Public IP | 184.73.78.154 (changes on stop/start) |

### Security Group Rules

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
| Distribution ID | `E139A6WQVKJXU9` |
| Domain | `d3r4k77gnvpmzn.cloudfront.net` |
| Price Class | PriceClass_100 (US, Canada, Europe) |

**Cache Behaviors:**

| Path Pattern | Origin | Cache Policy | Notes |
|--------------|--------|--------------|-------|
| `/*` (default) | tmux-frontend:3001 | CachingOptimized | Static assets |
| `/api/*` | tmux-backend:8080 | CachingDisabled | API requests |
| `/ws/*` | tmux-websocket:8082 | CachingDisabled | WebSocket (unused*) |

*WebSocket through CloudFront has HTTP/2 upgrade issues. Use nginx proxy instead.

## Application Services

### PM2 Processes

| Name | Script | Port | Description |
|------|--------|------|-------------|
| tmux-backend | `python main.py` | 8080, 8082 | FastAPI + WebSocket server |
| tmux-frontend | `npx serve -s dist` | 3001 | Static file server |

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
| Frontend (CloudFront) | https://d3r4k77gnvpmzn.cloudfront.net |
| Frontend (Direct) | http://184.73.78.154:3001 |
| API | https://d3r4k77gnvpmzn.cloudfront.net/api/* |
| WebSocket (CloudFront) | wss://d3r4k77gnvpmzn.cloudfront.net/ws/{guid} |
| WebSocket (Direct/Fallback) | wss://184.73.78.154:8443/ws/{guid} |

## SSH Access

```bash
# Using SSH config (recommended)
ssh ai-product-studio

# Direct SSH
ssh -i ~/.ssh/ai-product-studio-key-us-east-1.pem ubuntu@184.73.78.154
```

**SSH Config (~/.ssh/config):**
```
Host ai-product-studio
    HostName 184.73.78.154
    User ubuntu
    IdentityFile /Users/sunwa/.ssh/ai-product-studio-key-us-east-1.pem
```

## Common Operations

### Restart Services
```bash
ssh ai-product-studio "pm2 restart all"
```

### View Logs
```bash
ssh ai-product-studio "pm2 logs"
```

### Invalidate CloudFront Cache
```bash
aws --profile sunwaretech cloudfront create-invalidation \
    --distribution-id E139A6WQVKJXU9 --paths "/*"
```

### Check Service Status
```bash
ssh ai-product-studio "pm2 list && ss -tlnp | grep -E '(8080|8082|3001|8443)'"
```

## Troubleshooting

### WebSocket Not Connecting
1. Check nginx is running: `sudo systemctl status nginx`
2. Check port 8443 is open in security group
3. Browser may warn about self-signed cert - accept it first by visiting https://IP:8443

### CloudFront Serving Old Content
```bash
aws --profile sunwaretech cloudfront create-invalidation \
    --distribution-id E139A6WQVKJXU9 --paths "/*"
```

### PM2 Services Not Starting
```bash
ssh ai-product-studio "pm2 delete all && cd ~/tmux-builder && pm2 start ecosystem.config.js"
```

### Instance IP Changed After Restart
1. Get new IP: `./aws-setup.sh show-status`
2. Update SSH config with new IP
3. Update frontend WebSocket URLs and rebuild
4. Invalidate CloudFront cache

## Cost Estimate

| Resource | Hourly | Monthly (730h) |
|----------|--------|----------------|
| t3.xlarge | $0.1664 | ~$121 |
| 100GB gp3 | - | ~$8 |
| CloudFront | - | ~$1-5 (usage based) |
| **Total** | - | **~$130-135** |

## Maintenance Checklist

- [ ] Monitor disk usage (`df -h`)
- [ ] Check PM2 process health (`pm2 monit`)
- [ ] Review backend logs for errors
- [ ] Rotate SSL certificates before expiry
- [ ] Update dependencies periodically
