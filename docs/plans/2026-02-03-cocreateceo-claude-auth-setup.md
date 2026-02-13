# Cocreateceo - Claude Code Authentication Setup

> **For Claude:** Execute this on EC2 instance 18.211.207.2 to set up Claude Code authentication.

## Overview

Tmux Builder uses **Claude Code CLI** to process user requests. Claude Code authenticates via **OAuth** with Claude.ai (not traditional API keys).

## Prerequisites

- Claude.ai account with **Max subscription** (required for Claude Code)
- SSH access to EC2: `ssh -i tmux-builder-key.pem ubuntu@18.211.207.2`

---

## Step 1: Verify Claude Code Installation

```bash
ssh -i tmux-builder-key.pem ubuntu@18.211.207.2

# Check if Claude Code is installed
which claude
claude --version

# Expected output:
# /usr/bin/claude
# 2.x.x (Claude Code)
```

**If not installed:**
```bash
npm install -g @anthropic-ai/claude-code
```

---

## Step 2: Authenticate Claude Code

```bash
# Run login command
claude login
```

This will display:
```
To authenticate, please visit:
https://claude.ai/oauth/authorize?client_id=...&redirect_uri=...

Waiting for authentication...
```

**Steps:**
1. Copy the URL and open in browser
2. Login with Claude.ai account (must have Max subscription)
3. Authorize Claude Code
4. Terminal will show "Authentication successful"

---

## Step 3: Verify Authentication

```bash
# Check credentials file exists
ls -la ~/.claude/.credentials.json

# Verify authentication works
claude --version
```

**Credentials file structure:**
```json
{
  "claudeAiOauth": {
    "accessToken": "sk-ant-oat01-...",
    "refreshToken": "sk-ant-ort01-...",
    "expiresAt": 1770125766907,
    "scopes": [
      "user:inference",
      "user:mcp_servers",
      "user:profile",
      "user:sessions:claude_code"
    ],
    "subscriptionType": "max",
    "rateLimitTier": "default_claude_max_20x"
  }
}
```

---

## Step 4: Test Claude Code

```bash
# Quick test
echo "Hello, what is 2+2?" | claude

# Should respond with answer
```

---

## Step 5: Restart PM2 Services

After authentication, restart the backend services:

```bash
cd /home/ubuntu/tmux-builder
pm2 restart all
pm2 status
```

---

## Step 6: Test Full Flow

1. Open browser: `http://18.211.207.2:3001` (or CloudFront URL)
2. Go to `/client_input` to create new session
3. Submit a project request
4. Check Activity panel for progress
5. Verify Claude processes the request

---

## Troubleshooting

### Authentication Expired

```bash
# Re-authenticate
claude logout
claude login
```

### Credentials Not Found

```bash
# Check file exists
cat ~/.claude/.credentials.json

# If missing, run login again
claude login
```

### Permission Issues

```bash
# Fix permissions
chmod 600 ~/.claude/.credentials.json
```

### PM2 Not Finding Claude

```bash
# Check Claude is in PATH
which claude

# Add to PATH if needed (in ~/.bashrc)
export PATH=$PATH:/usr/bin

# Restart PM2
pm2 restart all
```

---

## Reference: GopiSunware Working Setup

| Component | Value |
|-----------|-------|
| EC2 | 184.73.78.154 |
| Claude Code Version | 2.1.15 |
| Subscription | Max |
| Credentials | `~/.claude/.credentials.json` |

---

## Summary

| Step | Command | Status |
|------|---------|--------|
| 1 | `which claude` | Verify installed |
| 2 | `claude login` | Authenticate with Claude.ai |
| 3 | `ls ~/.claude/.credentials.json` | Verify credentials |
| 4 | `echo "test" \| claude` | Test Claude works |
| 5 | `pm2 restart all` | Restart services |
| 6 | Test in browser | Verify full flow |

---

## Important Notes

- **Max subscription required** - Claude Code only works with Claude Max
- **OAuth tokens auto-refresh** - No manual renewal needed
- **Per-machine auth** - Each EC2 needs separate `claude login`
- **Credentials are sensitive** - Don't share `.credentials.json`
