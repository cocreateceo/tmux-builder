#!/bin/bash
# =============================================================================
# notify.sh - Send progress updates to the UI via WebSocket
# Auto-generated for session: {{GUID}}
#
# Usage: ./notify.sh <type> [data]
#
# Examples:
#   ./notify.sh ack                          # Acknowledge receipt of task
#   ./notify.sh status "Analyzing code..."   # Send status message
#   ./notify.sh working "Refactoring auth"   # What you're working on
#   ./notify.sh progress 50                  # Progress percentage
#   ./notify.sh found "3 bugs in login.py"   # Report findings
#   ./notify.sh deployed "https://xxx.cloudfront.net"  # Report deployed URL
#   ./notify.sh resources '{"s3Bucket":"tmux-xxx","cloudFrontId":"E123"}'  # Report AWS resources
#   ./notify.sh done                         # Task completed
#   ./notify.sh error "Config not found"     # Report error
# =============================================================================

# Send message via Python websockets
# All configuration is embedded in the Python script below
python3 - "$@" << 'PYTHON_SCRIPT'
import asyncio
import json
import sys
from datetime import datetime

async def send_notification():
    try:
        import websockets
    except ImportError:
        print("[notify.sh] ERROR: websockets package not installed", file=sys.stderr)
        sys.exit(1)

    guid = "{{GUID}}"
    ws_url = f"ws://localhost:8082/ws/{guid}"
    msg_type = sys.argv[1] if len(sys.argv) > 1 else "status"
    data = sys.argv[2] if len(sys.argv) > 2 else ""

    message = {
        "guid": guid,
        "type": msg_type,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }

    try:
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps(message))
            # Success logging
            print(f"[notify.sh] Sent: type={msg_type}, data={data[:50] if data else '(none)'}")
    except ConnectionRefusedError:
        print(f"[notify.sh] ERROR: Could not connect to WebSocket server at {ws_url}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[notify.sh] ERROR: WebSocket error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(send_notification())
PYTHON_SCRIPT
