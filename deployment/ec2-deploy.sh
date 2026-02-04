#!/bin/bash
#
# EC2 Application Deployment Script for Tmux Builder
#
# This script deploys the tmux-builder application to an EC2 instance.
# It handles code transfer, dependency installation, and service management.
#
# Prerequisites:
#   - SSH access to EC2 instance configured
#   - Node.js and Python3 installed on EC2
#
# Created: 2026-01-28
# Last Updated: 2026-01-28

set -e

#------------------------------------------------------------------------------
# Configuration
#------------------------------------------------------------------------------
EC2_HOST="ai-product-studio"  # SSH config host name (fallback)
EC2_IP="18.211.207.2"
EC2_KEY="$HOME/tmux-builder-key.pem"  # SSH key path
EC2_USER="ubuntu"
REMOTE_PATH="/home/ubuntu/tmux-builder"
LOCAL_PATH="$(cd "$(dirname "$0")/.." && pwd)"

# CloudFront Distribution ID for cache invalidation
CLOUDFRONT_DIST_ID="E2FOQ8U2IQP3GC"

# Ports
BACKEND_PORT=8080
WEBSOCKET_PORT=8082
FRONTEND_PORT=3001
NGINX_WSS_PORT=8443

# URLs
CLOUDFRONT_URL="https://d3r4k77gnvpmzn.cloudfront.net"
WSS_URL="wss://d3r4k77gnvpmzn.cloudfront.net"  # CloudFront handles WebSocket
WSS_URL_FALLBACK="wss://${EC2_IP}:${NGINX_WSS_PORT}"  # Nginx fallback

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

#------------------------------------------------------------------------------
# Helper Functions
#------------------------------------------------------------------------------
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

ssh_cmd() {
    # Try SSH config first, fallback to direct key
    if ssh -o BatchMode=yes -o ConnectTimeout=5 "$EC2_HOST" true 2>/dev/null; then
        ssh "$EC2_HOST" "$@"
    elif [ -f "$EC2_KEY" ]; then
        ssh -i "$EC2_KEY" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_IP}" "$@"
    else
        log_error "Cannot connect to EC2. Set up SSH config or provide key at $EC2_KEY"
        exit 1
    fi
}

scp_cmd() {
    # Try SSH config first, fallback to direct key
    if ssh -o BatchMode=yes -o ConnectTimeout=5 "$EC2_HOST" true 2>/dev/null; then
        scp "$@" "${EC2_HOST}:~/"
    elif [ -f "$EC2_KEY" ]; then
        scp -i "$EC2_KEY" -o StrictHostKeyChecking=no "$@" "${EC2_USER}@${EC2_IP}:~/"
    else
        log_error "Cannot connect to EC2. Set up SSH config or provide key at $EC2_KEY"
        exit 1
    fi
}

usage() {
    cat << EOF
Usage: $0 COMMAND

Commands:
  deploy          Full deployment (upload, install deps, build, restart)
  quick           Quick deployment (upload, build frontend, restart) - USE THIS FOR CODE CHANGES
  upload          Upload code to EC2 only
  install-deps    Install Python and Node.js dependencies
  build           Build frontend for production
  restart         Restart PM2 services
  setup-nginx     Setup nginx SSL proxy for WebSocket
  status          Show service status
  logs            Show PM2 logs
  invalidate      Invalidate CloudFront cache

Options:
  -h, --help      Show this help message

Examples:
  $0 quick        # Quick deployment (recommended for code changes)
  $0 deploy       # Full deployment (first time or dependency changes)
  $0 restart      # Just restart services
  $0 logs         # View logs
EOF
}

#------------------------------------------------------------------------------
# Deployment Functions
#------------------------------------------------------------------------------
upload_code() {
    log_info "=== Uploading Code to EC2 ==="

    # Create tarball excluding unnecessary files
    log_info "Creating tarball..."
    tar --exclude='.git' \
        --exclude='node_modules' \
        --exclude='venv' \
        --exclude='__pycache__' \
        --exclude='sessions' \
        --exclude='.next' \
        --exclude='dist' \
        --exclude='*.pyc' \
        -czf /tmp/tmux-builder.tar.gz -C "$LOCAL_PATH" .

    # Upload
    log_info "Uploading to EC2..."
    scp_cmd /tmp/tmux-builder.tar.gz

    # Backup sessions and venv before extract
    log_info "Backing up sessions and dependencies..."
    ssh_cmd "
        mkdir -p ~/tmux-backup
        [ -d $REMOTE_PATH/sessions ] && cp -r $REMOTE_PATH/sessions ~/tmux-backup/ || true
        [ -d $REMOTE_PATH/backend/venv ] && cp -r $REMOTE_PATH/backend/venv ~/tmux-backup/ || true
        [ -d $REMOTE_PATH/frontend/node_modules ] && mv $REMOTE_PATH/frontend/node_modules ~/tmux-backup/ || true
    "

    # Extract
    log_info "Extracting on EC2..."
    ssh_cmd "mkdir -p $REMOTE_PATH && tar -xzf ~/tmux-builder.tar.gz -C $REMOTE_PATH"

    # Restore sessions and dependencies
    log_info "Restoring sessions and dependencies..."
    ssh_cmd "
        [ -d ~/tmux-backup/sessions ] && cp -r ~/tmux-backup/sessions $REMOTE_PATH/ || true
        [ -d ~/tmux-backup/venv ] && cp -r ~/tmux-backup/venv $REMOTE_PATH/backend/ || true
        [ -d ~/tmux-backup/node_modules ] && mv ~/tmux-backup/node_modules $REMOTE_PATH/frontend/ || true
        rm -rf ~/tmux-backup
    "

    # Cleanup
    rm /tmp/tmux-builder.tar.gz
    ssh_cmd "rm ~/tmux-builder.tar.gz"

    log_info "Code uploaded successfully!"
}

install_deps() {
    log_info "=== Installing Dependencies ==="

    # Backend (Python)
    log_info "Installing Python dependencies..."
    ssh_cmd "cd $REMOTE_PATH/backend && \
        python3 -m venv venv && \
        source venv/bin/activate && \
        pip install --upgrade pip && \
        pip install -r requirements.txt"

    # Frontend (Node.js)
    log_info "Installing Node.js dependencies..."
    ssh_cmd "cd $REMOTE_PATH/frontend && npm install"

    log_info "Dependencies installed!"
}

update_frontend_urls() {
    log_info "=== Updating Frontend URLs ==="

    # WebSocket through CloudFront (production)
    CF_WSS_URL="wss://d3r4k77gnvpmzn.cloudfront.net"

    ssh_cmd "
        # Update API URL to CloudFront
        sed -i \"s|http://localhost:8000|${CLOUDFRONT_URL}|g\" $REMOTE_PATH/frontend/src/services/api.js
        sed -i \"s|https://d3r4k77gnvpmzn.cloudfront.net|${CLOUDFRONT_URL}|g\" $REMOTE_PATH/frontend/src/services/api.js

        # Update WebSocket URLs to CloudFront WSS (preferred)
        sed -i \"s|ws://localhost:8082|${CF_WSS_URL}|g\" $REMOTE_PATH/frontend/src/hooks/useProgressSocket.js
        sed -i \"s|ws://localhost:8001|${CF_WSS_URL}|g\" $REMOTE_PATH/frontend/src/hooks/useProgressSocket.js
        sed -i \"s|ws://localhost:8000|${CF_WSS_URL}|g\" $REMOTE_PATH/frontend/src/hooks/useWebSocket.js
        sed -i \"s|wss://.*:8443|${CF_WSS_URL}|g\" $REMOTE_PATH/frontend/src/hooks/useProgressSocket.js
        sed -i \"s|wss://.*:8443|${CF_WSS_URL}|g\" $REMOTE_PATH/frontend/src/hooks/useWebSocket.js

        echo 'Frontend URLs updated:'
        grep -E 'API_BASE_URL|MCP_WS_URL|WS_BASE_URL' $REMOTE_PATH/frontend/src/services/api.js $REMOTE_PATH/frontend/src/hooks/*.js || true
    "
}

build_frontend() {
    log_info "=== Building Frontend ==="

    ssh_cmd "cd $REMOTE_PATH/frontend && npm run build"

    log_info "Frontend built!"
}

create_pm2_config() {
    log_info "=== Creating PM2 Configuration ==="

    ssh_cmd "cat > $REMOTE_PATH/ecosystem.config.js << 'EOF'
module.exports = {
  apps: [
    {
      name: 'tmux-backend',
      cwd: '$REMOTE_PATH/backend',
      script: '$REMOTE_PATH/backend/venv/bin/python',
      args: 'main.py',
      env: {
        PYTHONDONTWRITEBYTECODE: '1',
        BACKEND_PORT: '$BACKEND_PORT',
        PROGRESS_WS_PORT: '$WEBSOCKET_PORT'
      },
      error_file: '$REMOTE_PATH/logs/backend-error.log',
      out_file: '$REMOTE_PATH/logs/backend-out.log'
    },
    {
      name: 'tmux-frontend',
      cwd: '$REMOTE_PATH/frontend',
      script: 'npx',
      args: 'serve -s dist -l $FRONTEND_PORT',
      error_file: '$REMOTE_PATH/logs/frontend-error.log',
      out_file: '$REMOTE_PATH/logs/frontend-out.log'
    }
  ]
};
EOF
mkdir -p $REMOTE_PATH/logs"

    log_info "PM2 configuration created!"
}

restart_services() {
    log_info "=== Restarting Services ==="

    ssh_cmd "
        pm2 delete all 2>/dev/null || true
        cd $REMOTE_PATH && pm2 start ecosystem.config.js
        pm2 save
        pm2 list
    "

    log_info "Services restarted!"
}

setup_nginx() {
    log_info "=== Setting up Nginx SSL Proxy (Fallback) ==="
    log_info "Note: CloudFront handles WebSocket in production. Nginx is a fallback option."

    ssh_cmd "
        # Install nginx if needed
        which nginx || sudo apt-get update && sudo apt-get install -y nginx

        # Create SSL directory and self-signed cert
        sudo mkdir -p /etc/nginx/ssl
        if [ ! -f /etc/nginx/ssl/server.crt ]; then
            sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
                -keyout /etc/nginx/ssl/server.key \
                -out /etc/nginx/ssl/server.crt \
                -subj '/CN=tmux-builder/O=tmux-builder'
        fi

        # Create nginx config
        sudo tee /etc/nginx/sites-available/wss << 'NGINX'
server {
    listen $NGINX_WSS_PORT ssl;
    server_name _;

    ssl_certificate /etc/nginx/ssl/server.crt;
    ssl_certificate_key /etc/nginx/ssl/server.key;

    location /ws/ {
        proxy_pass http://127.0.0.1:$WEBSOCKET_PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }
}
NGINX

        # Enable and restart nginx
        sudo ln -sf /etc/nginx/sites-available/wss /etc/nginx/sites-enabled/
        sudo nginx -t && sudo systemctl restart nginx
    "

    log_info "Nginx configured!"
}

update_backend_cors() {
    log_info "=== Updating Backend CORS ==="

    ssh_cmd "
        # Add CloudFront and EC2 IP to CORS origins
        if ! grep -q '$CLOUDFRONT_URL' $REMOTE_PATH/backend/main.py; then
            sed -i 's|\"http://127.0.0.1:5174\",|\"http://127.0.0.1:5174\",\\n        \"$CLOUDFRONT_URL\",\\n        \"http://$EC2_IP:$FRONTEND_PORT\",\\n        \"http://$EC2_IP\",|g' $REMOTE_PATH/backend/main.py
        fi
    "

    log_info "CORS updated!"
}

show_status() {
    log_info "=== Service Status ==="

    ssh_cmd "
        echo '--- PM2 Processes ---'
        pm2 list

        echo ''
        echo '--- Listening Ports ---'
        ss -tlnp | grep -E '($BACKEND_PORT|$WEBSOCKET_PORT|$FRONTEND_PORT|$NGINX_WSS_PORT)' || echo 'No matching ports'

        echo ''
        echo '--- Nginx Status ---'
        sudo systemctl status nginx --no-pager | head -5
    "
}

show_logs() {
    ssh_cmd "pm2 logs --lines 50"
}

invalidate_cache() {
    log_info "=== Invalidating CloudFront Cache ==="

    aws --profile cocreate cloudfront create-invalidation \
        --distribution-id "$CLOUDFRONT_DIST_ID" \
        --paths "/*" \
        --query 'Invalidation.{Id:Id,Status:Status}' \
        --output table

    log_info "Cache invalidation initiated!"
}

quick_deploy() {
    log_info "=== Starting Quick Deployment (skip deps) ==="
    echo ""

    upload_code
    update_frontend_urls
    build_frontend
    restart_services
    invalidate_cache

    echo ""
    log_info "=== Quick Deployment Complete ==="
    echo ""
    echo "Access URL: $CLOUDFRONT_URL"
    echo ""
    show_status
}

full_deploy() {
    log_info "=== Starting Full Deployment ==="
    echo ""

    upload_code
    install_deps
    update_frontend_urls
    update_backend_cors
    build_frontend
    create_pm2_config
    setup_nginx
    restart_services
    invalidate_cache

    echo ""
    log_info "=== Deployment Complete ==="
    echo ""
    echo "Access URLs:"
    echo "  Frontend:  $CLOUDFRONT_URL"
    echo "  API:       $CLOUDFRONT_URL/api/"
    echo "  WebSocket: $WSS_URL/ws/{guid}"
    echo "  WS Fallback: $WSS_URL_FALLBACK/ws/{guid}"
    echo ""
    show_status
}

#------------------------------------------------------------------------------
# Main
#------------------------------------------------------------------------------
COMMAND="${1:-}"

case $COMMAND in
    deploy)
        full_deploy
        ;;
    quick)
        quick_deploy
        ;;
    upload)
        upload_code
        ;;
    install-deps)
        install_deps
        ;;
    build)
        update_frontend_urls
        build_frontend
        ;;
    restart)
        restart_services
        ;;
    setup-nginx)
        setup_nginx
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    invalidate)
        invalidate_cache
        ;;
    -h|--help)
        usage
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        usage
        exit 1
        ;;
esac
