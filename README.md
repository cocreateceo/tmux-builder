# Tmux Builder

Web UI for interacting with Claude CLI through isolated tmux sessions with real-time progress updates.

---

## Production Deployment

| Property | Value |
|----------|-------|
| **Deployed Branch** | `wsocket_cli` (also synced to `wsocket_ui`) |
| **Frontend URL** | https://d3r4k77gnvpmzn.cloudfront.net |
| **API URL** | https://d3r4k77gnvpmzn.cloudfront.net/api/ |
| **WebSocket** | wss://d3r4k77gnvpmzn.cloudfront.net/ws/{guid} |
| **Admin Password** | `tmux@admin2026` |
| **EC2 IP** | 184.73.78.154 |
| **SSH** | `ssh ai-product-studio` |

### Admin Access

1. Open https://d3r4k77gnvpmzn.cloudfront.net
2. Click "Admin Login" in header
3. Enter password: `tmux@admin2026`
4. Sidebar with session management appears

### API: Create Client Session

```bash
curl -X POST https://d3r4k77gnvpmzn.cloudfront.net/api/admin/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1-555-123-4567",
    "initial_request": "Build me a landing page"
  }'
```

**Response:**
```json
{
  "success": true,
  "guid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "link": "https://d3r4k77gnvpmzn.cloudfront.net/?guid=...&embed=true"
}
```

Redirect users to `link` - they see their request in chat with Claude processing in activity log.

---

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                     CloudFront                               │
                    │              d3r4k77gnvpmzn.cloudfront.net                   │
                    │                                                              │
                    │  ┌──────────┐  ┌──────────┐  ┌──────────────┐               │
                    │  │ /* (def) │  │ /api/*   │  │ /ws/*        │               │
                    │  └────┬─────┘  └────┬─────┘  └──────┬───────┘               │
                    └───────┼─────────────┼───────────────┼───────────────────────┘
                            │             │               │
                            ▼             ▼               ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                           EC2 Instance (t3.xlarge)                                │
│                           IP: 184.73.78.154                                       │
│                                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                   │
│  │  Frontend       │  │  Backend API    │  │  WebSocket      │                   │
│  │  (serve)        │  │  (FastAPI)      │  │  (ws_server)    │                   │
│  │  Port: 3001     │  │  Port: 8080     │  │  Port: 8082     │                   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

**Dual-channel Communication:**
- **Channel 1 (HTTP)**: REST API for chat - UI ↔ FastAPI ↔ tmux ↔ Claude
- **Channel 2 (WebSocket)**: Progress updates - Claude → notify.sh → ws_server → UI

---

## Project Structure

```
tmux-builder/
├── backend/                      # Python backend
│   ├── main.py                   # FastAPI app, admin API
│   ├── ws_server.py              # WebSocket server (port 8082)
│   ├── session_controller.py     # Message orchestration
│   ├── session_initializer.py    # Creates tmux sessions
│   └── system_prompt_generator.py
├── frontend/                     # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── SplitChatView.jsx # Main UI with admin auth
│   │   │   ├── SessionSidebar.jsx # Session list
│   │   │   └── MessageList.jsx   # Chat with markdown
│   │   ├── hooks/
│   │   │   └── useProgressSocket.js # WebSocket hook
│   │   └── services/
│   │       └── api.js            # API client
│   └── dist/                     # Built frontend
├── deployment/                   # AWS deployment scripts
│   ├── aws-setup.sh              # Infrastructure setup
│   └── ec2-deploy.sh             # Application deployment
├── sessions/                     # Runtime storage
│   ├── active/<guid>/            # Active sessions
│   └── deleted/                  # Archived sessions
└── docs/                         # Documentation
```

---

## Local Development

### Requirements

```bash
# System dependencies
sudo apt-get install tmux python3 python3-pip nodejs npm

# Claude CLI (required)
# Install from: https://claude.ai/download
claude --version
```

### Start Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Access at http://localhost:5173

---

## Deployment to AWS

### Quick Deploy

```bash
# Full deployment (upload, build, restart)
./deployment/ec2-deploy.sh deploy

# Or individual steps
./deployment/ec2-deploy.sh upload      # Upload code only
./deployment/ec2-deploy.sh build       # Build frontend
./deployment/ec2-deploy.sh restart     # Restart PM2 services
./deployment/ec2-deploy.sh status      # Check status
./deployment/ec2-deploy.sh logs        # View logs
./deployment/ec2-deploy.sh invalidate  # Clear CloudFront cache
```

### AWS Resources

| Resource | Details |
|----------|---------|
| EC2 | t3.xlarge, 100GB gp3, us-east-1 |
| CloudFront | E139A6WQVKJXU9 |
| Security Group | Ports: 22, 80, 443, 3001, 8080, 8082, 8443 |

### PM2 Services

```bash
# On EC2
pm2 list                    # Show services
pm2 restart all             # Restart all
pm2 logs                    # View logs
pm2 monit                   # Monitor
```

---

## Session Flow

1. **Create Session**: Admin creates via sidebar or API
2. **Send Message**: User types message → saved to `prompt_{timestamp}.txt`
3. **Claude Processing**: tmux sends prompt path to Claude CLI
4. **Progress Updates**: Claude calls `notify.sh` → WebSocket → UI activity log
5. **Completion**: Claude writes `summary.md` → backend reads → UI displays

### Session Folder Structure

```
sessions/active/<guid>/
├── system_prompt.txt      # Agent instructions
├── notify.sh              # Progress script (GUID baked in)
├── prompt_{timestamp}.txt # User message (unique per message)
├── summary.md             # Formatted completion summary
├── chat_history.jsonl     # Persisted chat
├── activity_log.jsonl     # Activity log
├── status.json            # Session state
└── tmp/                   # Scratch work
```

---

## Key Implementation Patterns

### File-Based I/O (SmartBuild Pattern)

```python
# Write prompt to file, send path to Claude
prompt_path = session_path / f"prompt_{timestamp}.txt"
prompt_path.write_text(user_message)
instruction = f"Read and respond to: {prompt_path}"
```

### Timestamped Prompts (Prevents Caching)

```python
timestamp_ms = int(time.time() * 1000)
prompt_filename = f"prompt_{timestamp_ms}.txt"
```

### Event-Based Waiting (Not Polling)

```python
event = server.get_ack_event(self.guid)
event.clear()
await asyncio.wait_for(event.wait(), timeout=timeout)
```

---

## API Endpoints

### Public

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send message |
| GET | `/api/history?guid=` | Get chat history |
| POST | `/api/clear` | Clear session |
| GET | `/api/status` | Get status |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/sessions?filter=` | List sessions (all/active/completed/deleted) |
| POST | `/api/admin/sessions` | Create session with client info |
| GET | `/api/admin/sessions/{guid}` | Get session details |
| DELETE | `/api/admin/sessions/{guid}` | Delete session |
| POST | `/api/admin/sessions/{guid}/complete` | Mark complete |
| POST | `/api/admin/sessions/{guid}/restore` | Restore deleted |

---

## Troubleshooting

### WebSocket Not Connecting

```bash
# Check ws_server is running
ssh ai-product-studio "pm2 logs tmux-backend"

# Check port 8082 is listening
ssh ai-product-studio "ss -tlnp | grep 8082"
```

### CloudFront Serving Old Content

```bash
# Invalidate cache
./deployment/ec2-deploy.sh invalidate

# Also clear browser cache (Ctrl+Shift+R)
```

### tmux Session Issues

```bash
# List sessions
tmux list-sessions

# Attach to debug
tmux attach -t tmux_builder_<guid>

# Kill all tmux sessions
tmux kill-server
```

### Claude CLI Not Responding

```bash
# Verify Claude CLI
claude --version

# Check if session is stuck
tmux capture-pane -t tmux_builder_<guid> -p
```

---

## Documentation

| File | Description |
|------|-------------|
| `CLAUDE.md` | AI assistant context (key files, patterns, gotchas) |
| `docs/architecture/` | Technical architecture |
| `docs/guides/QUICKSTART.md` | Quick start guide |
| `docs/guides/SETUP.md` | Detailed setup |
| `deployment/README.md` | AWS deployment details |

---

## Cost Estimate (AWS)

| Resource | Monthly |
|----------|---------|
| t3.xlarge | ~$121 |
| 100GB gp3 | ~$8 |
| CloudFront | ~$1-5 |
| **Total** | **~$130-135** |

---

## License

             
  Admin Login                                                                                                                                                                                  
                                                                                                                                                                                               
  Password: tmux@admin2026 
MIT
