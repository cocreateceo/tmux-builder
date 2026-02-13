# Dockerfile for tmux-builder Lightsail Container
FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-venv \
    python3-websockets \
    git \
    curl \
    tmux \
    && rm -rf /var/lib/apt/lists/*

# Install Claude CLI
RUN npm install -g @anthropic-ai/claude-code

# Set working directory
WORKDIR /app

# Copy backend requirements and install
COPY backend/requirements.txt /app/backend/
RUN cd /app/backend && \
    python3.11 -m venv venv && \
    . venv/bin/activate && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir boto3 websockets

# Copy backend code
COPY backend/ /app/backend/

# Copy scripts
COPY scripts/ /app/scripts/

# Create necessary directories
RUN mkdir -p /app/sessions/active && \
    mkdir -p /app/sessions/deleted && \
    mkdir -p /app/sessions/pending && \
    mkdir -p /app/logs

# Copy .claude directory for skills/agents
COPY .claude/ /app/.claude/

# Expose ports
EXPOSE 8080 8082

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Copy and set startup script
COPY start.sh /app/
RUN chmod +x /app/start.sh

# Set environment
ENV PYTHONUNBUFFERED=1
ENV LIGHTSAIL_DEPLOYMENT=true

CMD ["/app/start.sh"]
