#!/usr/bin/env python3
"""Integration test for MCP-based dual-channel protocol."""

import asyncio
import json
import sys
import time

try:
    import websockets
except ImportError:
    print("ERROR: websockets package not installed. Run: pip install websockets")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("ERROR: requests package not installed. Run: pip install requests")
    sys.exit(1)

API_URL = "http://localhost:8000"
MCP_WS_URL = "ws://localhost:8001"


async def test_mcp_flow():
    print("=" * 60)
    print("MCP Integration Test")
    print("=" * 60)

    # 1. Create session
    print("\n1. Creating session...")
    try:
        resp = requests.post(f"{API_URL}/api/session/create", timeout=30)
        data = resp.json()
    except requests.exceptions.ConnectionError:
        print("   ERROR: Cannot connect to backend at", API_URL)
        print("   Make sure the backend is running: ./start-backend.sh")
        return False

    if not data.get('success'):
        print(f"   ERROR: Failed to create session: {data}")
        return False

    guid = data['guid']
    print(f"   Session created: {guid[:20]}...")

    # 2. Connect to MCP WebSocket
    print("\n2. Connecting to MCP WebSocket (Channel 2)...")
    try:
        ws = await asyncio.wait_for(
            websockets.connect(f"{MCP_WS_URL}/ws/{guid}"),
            timeout=10
        )
        print("   Connected!")
    except Exception as e:
        print(f"   ERROR: Cannot connect to MCP WebSocket: {e}")
        print("   Make sure the MCP server is running on port 8001")
        return False

    try:
        # 3. Send a test message via API
        print("\n3. Sending test message...")
        resp = requests.post(
            f"{API_URL}/api/chat",
            json={"message": "Say hello and confirm you received this."},
            timeout=120
        )
        print(f"   Response status: {resp.status_code}")

        # 4. Collect MCP tool calls
        print("\n4. Collecting MCP tool calls...")
        tool_calls = []
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=60)
                data = json.loads(msg)
                msg_type = data.get('type')

                if msg_type == 'tool_log':
                    tool = data.get('tool', 'unknown')
                    tool_calls.append(tool)
                    args = data.get('args', {})
                    # Truncate long content
                    if 'content' in args and len(str(args.get('content', ''))) > 50:
                        args = {**args, 'content': args['content'][:50] + '...'}
                    print(f"   -> {tool}({args})")

                elif msg_type == 'complete':
                    print("   -> COMPLETE received")
                    break

                elif msg_type == 'ack':
                    print("   -> ACK received")

                elif msg_type == 'progress':
                    print(f"   -> PROGRESS: {data.get('progress', 0)}%")

                elif msg_type == 'error':
                    print(f"   -> ERROR: {data.get('error', 'unknown')}")
                    break

        except asyncio.TimeoutError:
            print("   Timeout waiting for messages (this may be OK)")

        # 5. Verify expected tools were called
        print("\n5. Verifying tool calls...")
        expected = ['notify_ack', 'send_response', 'notify_complete']
        all_passed = True

        for tool in expected:
            if tool in tool_calls:
                print(f"   ✓ {tool}")
            else:
                print(f"   ✗ {tool} - MISSING!")
                all_passed = False

        print(f"\n   Total tool calls received: {len(tool_calls)}")

    finally:
        await ws.close()

    print("\n" + "=" * 60)
    if all_passed:
        print("TEST PASSED!")
    else:
        print("TEST FAILED - Some expected tools were not called")
    print("=" * 60)

    return all_passed


def main():
    """Run the integration test."""
    print("\nMCP Integration Test")
    print("Prerequisites:")
    print("  1. Backend running: ./start-backend.sh")
    print("  2. MCP server registered: ./scripts/setup-mcp.sh")
    print("  3. Frontend running (optional): ./start-frontend.sh")
    print()

    try:
        result = asyncio.run(test_mcp_flow())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted")
        sys.exit(1)


if __name__ == "__main__":
    main()
