# Cocreateceo Tmux Builder - AWS Deployment Plan

> **For Claude:** Execute this plan step-by-step to deploy tmux-builder to AWS.

## Overview

Deploy the tmux-builder application from GitHub to AWS infrastructure.

**Repository:** https://github.com/cocreateceo/tmux-builder
**Branch:** main (or wsocket_ui)

## Prerequisites

Before starting, ensure you have:
- AWS CLI configured with credentials (`aws configure`)
- SSH key pair for EC2 access
- Git access to the repository

---

## Phase 1: Create EC2 Instance

### Step 1.1: Create Security Group

```bash
aws ec2 create-security-group \
  --group-name tmux-builder-sg \
  --description "Security group for Tmux Builder"

# Get the security group ID from output, then add rules:
aws ec2 authorize-security-group-ingress --group-name tmux-builder-sg --protocol tcp --port 22 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-name tmux-builder-sg --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-name tmux-builder-sg --protocol tcp --port 443 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-name tmux-builder-sg --protocol tcp --port 3001 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-name tmux-builder-sg --protocol tcp --port 8080 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-name tmux-builder-sg --protocol tcp --port 8082 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-name tmux-builder-sg --protocol tcp --port 8443 --cidr 0.0.0.0/0
```

### Step 1.2: Create Key Pair (if not exists)

```bash
aws ec2 create-key-pair --key-name tmux-builder-key --query 'KeyMaterial' --output text > tmux-builder-key.pem
chmod 400 tmux-builder-key.pem
```

### Step 1.3: Launch EC2 Instance

```bash
aws ec2 run-instances \
  --image-id ami-0c7217cdde317cfec \
  --instance-type t3.medium \
  --key-name tmux-builder-key \
  --security-groups tmux-builder-sg \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=tmux-builder-cocreateceo}]'
```

### Step 1.4: Allocate Elastic IP

```bash
aws ec2 allocate-address --domain vpc
# Note the AllocationId and PublicIp

aws ec2 associate-address --instance-id <INSTANCE_ID> --allocation-id <ALLOCATION_ID>
```

---

## Phase 2: Configure EC2 Instance

### Step 2.1: SSH into Instance

```bash
ssh -i tmux-builder-key.pem ubuntu@<ELASTIC_IP>
```

### Step 2.2: Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3-pip

# Install other dependencies
sudo apt install -y git tmux nginx

# Install PM2 globally
sudo npm install -g pm2

# Install Claude CLI (Anthropic)
npm install -g @anthropic-ai/claude-code
```

### Step 2.3: Clone Repository

```bash
cd /home/ubuntu
git clone https://github.com/cocreateceo/tmux-builder.git
cd tmux-builder
```

### Step 2.4: Setup Backend

```bash
cd /home/ubuntu/tmux-builder/backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 2.5: Setup Frontend

```bash
cd /home/ubuntu/tmux-builder/frontend
npm install
npm run build
```

---

## Phase 3: Configure Nginx

### Step 3.1: Create Nginx Config

```bash
sudo tee /etc/nginx/sites-available/tmux-builder << 'EOF'
server {
    listen 80;
    server_name _;

    # Frontend
    location / {
        proxy_pass http://localhost:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://localhost:8082;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}

# WSS proxy on port 8443
server {
    listen 8443 ssl;
    server_name _;

    ssl_certificate /etc/nginx/ssl/selfsigned.crt;
    ssl_certificate_key /etc/nginx/ssl/selfsigned.key;

    location / {
        proxy_pass http://localhost:8082;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
EOF
```

### Step 3.2: Create Self-Signed SSL (for WSS)

```bash
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/selfsigned.key \
  -out /etc/nginx/ssl/selfsigned.crt \
  -subj "/C=US/ST=State/L=City/O=Org/CN=localhost"
```

### Step 3.3: Enable Site

```bash
sudo ln -sf /etc/nginx/sites-available/tmux-builder /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

---

## Phase 4: Start Services with PM2

### Step 4.1: Create PM2 Ecosystem File

```bash
cd /home/ubuntu/tmux-builder
tee ecosystem.config.js << 'EOF'
module.exports = {
  apps: [
    {
      name: 'tmux-backend',
      cwd: '/home/ubuntu/tmux-builder/backend',
      script: 'venv/bin/uvicorn',
      args: 'main:app --host 0.0.0.0 --port 8080',
      env: {
        PYTHONPATH: '/home/ubuntu/tmux-builder/backend'
      }
    },
    {
      name: 'tmux-frontend',
      cwd: '/home/ubuntu/tmux-builder/frontend',
      script: 'npx',
      args: 'serve -s dist -l 3001'
    }
  ]
};
EOF
```

### Step 4.2: Start Services

```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup
# Run the command it outputs with sudo
```

### Step 4.3: Start WebSocket Server

```bash
cd /home/ubuntu/tmux-builder/backend
source venv/bin/activate
nohup python ws_server.py > /tmp/ws_server.log 2>&1 &
```

---

## Phase 5: Create CloudFront Distribution

### Step 5.1: Create CloudFront Distribution

```bash
aws cloudfront create-distribution \
  --origin-domain-name <ELASTIC_IP> \
  --default-root-object index.html \
  --query 'Distribution.{Id:Id,DomainName:DomainName}' \
  --output table
```

Or create via AWS Console with these settings:

| Setting | Value |
|---------|-------|
| Origin Domain | EC2 Elastic IP |
| Origin Protocol | HTTP only |
| Viewer Protocol | Redirect HTTP to HTTPS |
| Allowed HTTP Methods | GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE |
| Cache Policy | CachingDisabled (for API) |
| Origin Request Policy | AllViewer |

### Step 5.2: Add WebSocket Behavior

Add a second behavior for `/ws/*`:
- Path Pattern: `/ws/*`
- Origin: Same EC2
- Cache Policy: CachingDisabled
- Origin Request Policy: AllViewer

---

## Phase 6: Verify Deployment

### Step 6.1: Test Endpoints

```bash
# Test frontend
curl -I https://<CLOUDFRONT_URL>/

# Test API
curl https://<CLOUDFRONT_URL>/api/health

# Test WebSocket (from browser console)
# new WebSocket('wss://<CLOUDFRONT_URL>/ws/test')
```

### Step 6.2: Test Client UI

Open in browser:
- `https://<CLOUDFRONT_URL>/` - Admin UI
- `https://<CLOUDFRONT_URL>/client_input` - Client onboarding
- `https://<CLOUDFRONT_URL>/client?guid=<guid>` - Client dashboard

---

## Summary

After completing all phases, you will have:

| Resource | Value |
|----------|-------|
| EC2 Instance | tmux-builder-cocreateceo |
| Elastic IP | (note this) |
| CloudFront URL | https://xxxxx.cloudfront.net |
| Security Group | tmux-builder-sg |

**Ports:**
- 3001: Frontend (serve)
- 8080: Backend API (FastAPI)
- 8082: WebSocket server
- 8443: WSS proxy (Nginx)

---

## Troubleshooting

### Check service status
```bash
pm2 status
pm2 logs tmux-backend
pm2 logs tmux-frontend
```

### Restart services
```bash
pm2 restart all
sudo systemctl restart nginx
```

### Check ports
```bash
sudo lsof -i :3001
sudo lsof -i :8080
sudo lsof -i :8082
```
