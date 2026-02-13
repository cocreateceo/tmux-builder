# Cocreateceo Tmux Builder - Complete Setup Guide

> **For Claude:** Execute this on EC2 instance 18.211.207.2 to complete the setup.

## Current Status

| Component | Status |
|-----------|--------|
| EC2 Instance | ✓ Running (18.211.207.2) |
| SSH Key | tmux-builder-key.pem |
| Frontend | ✓ Built |
| Backend | ❌ Not running |
| WebSocket | ❌ Not running |
| PM2 | ❌ Not configured |
| Nginx WSS | ❌ Not configured |
| CloudFront | ❌ Not created |

---

## Step 1: SSH into Server

```bash
ssh -i tmux-builder-key.pem ubuntu@18.211.207.2
```

---

## Step 2: Set Environment Variables

Create environment file:

```bash
sudo tee /etc/environment << 'EOF'
ANTHROPIC_API_KEY="sk-ant-api03-YOUR-KEY-HERE"
EOF

# Load immediately
export ANTHROPIC_API_KEY="sk-ant-api03-YOUR-KEY-HERE"
```

**IMPORTANT:** Replace `sk-ant-api03-YOUR-KEY-HERE` with actual Anthropic API key.

---

## Step 3: Create PM2 Ecosystem File

```bash
cd /home/ubuntu/tmux-builder

cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [
    {
      name: 'tmux-backend',
      cwd: '/home/ubuntu/tmux-builder/backend',
      script: 'venv/bin/python',
      args: 'main.py',
      env: {
        PYTHONPATH: '/home/ubuntu/tmux-builder/backend',
        ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY
      },
      watch: false,
      autorestart: true,
      max_restarts: 10
    },
    {
      name: 'tmux-websocket',
      cwd: '/home/ubuntu/tmux-builder/backend',
      script: 'venv/bin/python',
      args: 'ws_server.py',
      env: {
        PYTHONPATH: '/home/ubuntu/tmux-builder/backend'
      },
      watch: false,
      autorestart: true,
      max_restarts: 10
    },
    {
      name: 'tmux-frontend',
      cwd: '/home/ubuntu/tmux-builder/frontend',
      script: 'npx',
      args: 'serve -s dist -l 3001',
      watch: false,
      autorestart: true
    }
  ]
};
EOF
```

---

## Step 4: Start Services with PM2

```bash
# Start all services
pm2 start ecosystem.config.js

# Save PM2 config (survives reboot)
pm2 save

# Setup PM2 to start on boot
pm2 startup
# Run the command it outputs (starts with sudo env PATH=...)
```

---

## Step 5: Verify Services Running

```bash
pm2 status

# Expected output:
# ┌─────────────────┬────┬─────────┬──────┬───────┐
# │ name            │ id │ status  │ cpu  │ memory│
# ├─────────────────┼────┼─────────┼──────┼───────┤
# │ tmux-backend    │ 0  │ online  │ 0%   │ 50mb  │
# │ tmux-websocket  │ 1  │ online  │ 0%   │ 30mb  │
# │ tmux-frontend   │ 2  │ online  │ 0%   │ 40mb  │
# └─────────────────┴────┴─────────┴──────┴───────┘
```

Check ports:

```bash
sudo lsof -i :3001  # Frontend
sudo lsof -i :8080  # Backend API
sudo lsof -i :8082  # WebSocket
```

---

## Step 6: Setup Nginx for WSS Proxy (SSL WebSocket)

### 6.1 Create Self-Signed SSL Certificate

```bash
sudo mkdir -p /etc/nginx/ssl

sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/server.key \
  -out /etc/nginx/ssl/server.crt \
  -subj "/C=US/ST=State/L=City/O=CoCreate/CN=tmux-builder"
```

### 6.2 Create Nginx Config

```bash
sudo tee /etc/nginx/sites-available/tmux-builder << 'EOF'
# HTTP server - redirect and proxy
server {
    listen 80;
    server_name _;

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # WebSocket (HTTP upgrade)
    location /ws/ {
        proxy_pass http://127.0.0.1:8082;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}

# WSS proxy on port 8443 (SSL WebSocket)
server {
    listen 8443 ssl;
    server_name _;

    ssl_certificate /etc/nginx/ssl/server.crt;
    ssl_certificate_key /etc/nginx/ssl/server.key;

    location / {
        proxy_pass http://127.0.0.1:8082;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
EOF
```

### 6.3 Enable Site and Restart Nginx

```bash
sudo ln -sf /etc/nginx/sites-available/tmux-builder /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test config
sudo nginx -t

# Restart
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

## Step 7: Create CloudFront Distribution

Run from local machine with AWS CLI configured:

```bash
# Create CloudFront distribution
aws cloudfront create-distribution \
  --distribution-config '{
    "CallerReference": "tmux-builder-cocreateceo-'$(date +%s)'",
    "Comment": "Tmux Builder CoCreate",
    "Enabled": true,
    "Origins": {
      "Quantity": 3,
      "Items": [
        {
          "Id": "tmux-frontend",
          "DomainName": "18.211.207.2",
          "CustomOriginConfig": {
            "HTTPPort": 3001,
            "HTTPSPort": 443,
            "OriginProtocolPolicy": "http-only"
          }
        },
        {
          "Id": "tmux-backend",
          "DomainName": "18.211.207.2",
          "CustomOriginConfig": {
            "HTTPPort": 8080,
            "HTTPSPort": 443,
            "OriginProtocolPolicy": "http-only"
          }
        },
        {
          "Id": "tmux-websocket",
          "DomainName": "18.211.207.2",
          "CustomOriginConfig": {
            "HTTPPort": 8082,
            "HTTPSPort": 443,
            "OriginProtocolPolicy": "http-only"
          }
        }
      ]
    },
    "DefaultCacheBehavior": {
      "TargetOriginId": "tmux-frontend",
      "ViewerProtocolPolicy": "redirect-to-https",
      "AllowedMethods": {
        "Quantity": 7,
        "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
        "CachedMethods": {
          "Quantity": 2,
          "Items": ["GET", "HEAD"]
        }
      },
      "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
      "Compress": true
    },
    "CacheBehaviors": {
      "Quantity": 2,
      "Items": [
        {
          "PathPattern": "/api/*",
          "TargetOriginId": "tmux-backend",
          "ViewerProtocolPolicy": "redirect-to-https",
          "AllowedMethods": {
            "Quantity": 7,
            "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
            "CachedMethods": {
              "Quantity": 2,
              "Items": ["GET", "HEAD"]
            }
          },
          "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
          "OriginRequestPolicyId": "216adef6-5c7f-47e4-b989-5492eafa07d3",
          "Compress": true
        },
        {
          "PathPattern": "/ws/*",
          "TargetOriginId": "tmux-websocket",
          "ViewerProtocolPolicy": "redirect-to-https",
          "AllowedMethods": {
            "Quantity": 7,
            "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
            "CachedMethods": {
              "Quantity": 2,
              "Items": ["GET", "HEAD"]
            }
          },
          "CachePolicyId": "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
          "OriginRequestPolicyId": "216adef6-5c7f-47e4-b989-5492eafa07d3",
          "Compress": true
        }
      ]
    },
    "PriceClass": "PriceClass_100"
  }' \
  --query 'Distribution.{Id:Id,DomainName:DomainName,Status:Status}' \
  --output table
```

**Note:** CloudFront takes 10-15 minutes to deploy.

---

## Step 8: Test Deployment

### Test API
```bash
curl http://18.211.207.2:8080/api/health
# Expected: {"status": "ok"}
```

### Test Frontend
```bash
curl -I http://18.211.207.2:3001
# Expected: HTTP/1.1 200 OK
```

### Test WebSocket (from browser console)
```javascript
new WebSocket('ws://18.211.207.2:8082/ws/test')
// Or after CloudFront:
new WebSocket('wss://CLOUDFRONT_URL/ws/test')
```

### Test Full App
Open in browser:
- http://18.211.207.2 (direct)
- https://CLOUDFRONT_DOMAIN (after CloudFront ready)

---

## Summary - Final Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CloudFront (HTTPS)                       │
│                  https://xxxxx.cloudfront.net                │
├─────────────────────────────────────────────────────────────┤
│  /*        → Frontend (3001)                                 │
│  /api/*    → Backend (8080)                                  │
│  /ws/*     → WebSocket (8082)                                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              EC2: 18.211.207.2                               │
├─────────────────────────────────────────────────────────────┤
│  PM2 Services:                                               │
│  ├── tmux-frontend  (port 3001)                             │
│  ├── tmux-backend   (port 8080)                             │
│  └── tmux-websocket (port 8082)                             │
│                                                              │
│  Nginx:                                                      │
│  └── WSS proxy (port 8443) → WebSocket (8082)               │
└─────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### Check PM2 logs
```bash
pm2 logs tmux-backend
pm2 logs tmux-websocket
pm2 logs tmux-frontend
```

### Restart services
```bash
pm2 restart all
```

### Check nginx
```bash
sudo nginx -t
sudo systemctl status nginx
sudo tail -f /var/log/nginx/error.log
```

### Check ports
```bash
sudo lsof -i :3001
sudo lsof -i :8080
sudo lsof -i :8082
sudo lsof -i :8443
```
