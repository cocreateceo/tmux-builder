"""FastAPI backend for tmux-builder with WebSocket streaming."""

import logging
import os
import asyncio
import json
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timedelta

from config import API_HOST, API_PORT, DEFAULT_USER
from background_worker import BackgroundWorker
from guid_generator import generate_guid
from pty_manager import pty_manager, PTYSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Tmux Builder API", version="1.0.0")

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize background worker
background_worker = BackgroundWorker()


# Request/Response models
class RegistrationRequest(BaseModel):
    """Registration request model."""
    email: str
    phone: str
    initial_request: str


class ChatMessage(BaseModel):
    message: str
    screenshot: Optional[str] = None
    filePath: Optional[str] = None


class ChatResponse(BaseModel):
    success: bool
    response: str
    timestamp: str


class SessionStatus(BaseModel):
    ready: bool
    session_active: bool
    message: str


class HistoryResponse(BaseModel):
    messages: List[Dict]


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    logger.info("Root endpoint called")
    return {"message": "Tmux Builder API", "version": "1.0.0"}


@app.post("/api/register")
async def register_user(request: RegistrationRequest):
    """
    Register new user and start session initialization.

    Returns immediately with GUID URL. Session initializes in background.
    """
    try:
        logger.info("=== REGISTRATION REQUEST ===")
        logger.info(f"Email: {request.email}")
        logger.info(f"Phone: {request.phone}")
        logger.info(f"Request: {request.initial_request[:100]}...")

        # Generate deterministic GUID
        guid = generate_guid(request.email, request.phone)
        logger.info(f"Generated GUID: {guid}")

        # Start background initialization
        background_worker.start_initialization(
            guid=guid,
            email=request.email,
            phone=request.phone,
            user_request=request.initial_request
        )

        # Build response
        base_url = os.getenv('BASE_URL', f'http://{API_HOST}:{API_PORT}')
        session_url = f"{base_url}/session/{guid}"
        status_url = f"{base_url}/api/session/{guid}/status"

        # Calculate expiry (5 days from now)
        expires_at = (datetime.utcnow() + timedelta(days=5)).isoformat() + 'Z'

        response = {
            "success": True,
            "guid": guid,
            "url": session_url,
            "status_check_url": status_url,
            "message": "Session initialization started",
            "expires_at": expires_at,
            "created_at": datetime.utcnow().isoformat() + 'Z'
        }

        logger.info(f"✓ Registration successful: {session_url}")
        return response

    except Exception as e:
        logger.exception(f"Registration failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/session/{guid}/status")
async def get_session_status(guid: str):
    """
    Get current status of session initialization/build.

    Returns job status from background worker plus any status.json updates.
    """
    try:
        logger.info(f"=== STATUS CHECK: {guid} ===")

        # Get job status from background worker
        job_status = background_worker.get_job_status(guid)

        if job_status is None:
            logger.warning(f"Unknown GUID: {guid}")
            return {
                "success": False,
                "error": "Session not found",
                "guid": guid
            }

        # Try to read status.json if session is ready
        if job_status['status'] == 'ready':
            try:
                from session_initializer import SessionInitializer
                session_path = SessionInitializer.get_session_path(guid)
                status_file = session_path / "status.json"

                if status_file.exists():
                    import json
                    detailed_status = json.loads(status_file.read_text())

                    # Merge job status with detailed status
                    response = {
                        "success": True,
                        "guid": guid,
                        **job_status,
                        **detailed_status
                    }

                    logger.info(f"Detailed status: {detailed_status.get('status')} - {detailed_status.get('message')}")
                    return response
            except Exception as e:
                logger.warning(f"Could not read status.json: {e}")

        # Return basic job status
        response = {
            "success": True,
            "guid": guid,
            **job_status
        }

        logger.info(f"Status: {job_status['status']} ({job_status.get('progress', 0)}%)")
        return response

    except Exception as e:
        logger.exception(f"Status check failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "guid": guid
        }


@app.post("/api/session/create")
async def create_session():
    """
    Create a new Claude CLI session (simple chat UI flow).

    NOTE: Chat mode is deprecated. Use Terminal mode with WebSocket streaming instead.
    This endpoint creates a PTY session but Chat functionality is limited.
    For full interactive terminal, connect via WebSocket at /ws/{guid}.
    """
    logger.info("=== CREATE SESSION REQUEST (DEPRECATED CHAT MODE) ===")
    logger.info(f"User: {DEFAULT_USER}")
    logger.warning("Chat mode is deprecated. Use Terminal mode with WebSocket for full functionality.")

    try:
        # Generate a simple GUID for demo mode
        demo_guid = generate_guid(f"{DEFAULT_USER}@demo.local", "0000000000")
        logger.info(f"Demo GUID: {demo_guid}")

        # Create PTY session directly (no tmux/marker-based approach)
        session = pty_manager.get_session(demo_guid)
        if session is None:
            session = pty_manager.create_session(demo_guid)

        if session and session.is_alive():
            logger.info(f"✓ PTY session created: {demo_guid}")
            return {
                "success": True,
                "message": "Session created. Note: Chat mode is deprecated. Use Terminal mode for full interactive experience.",
                "session_name": f"pty_{demo_guid}",
                "guid": demo_guid,
                "websocket_url": f"/ws/{demo_guid}",
                "deprecated": True,
                "recommendation": "Switch to Terminal mode for real-time WebSocket streaming"
            }
        else:
            logger.error("Failed to create PTY session")
            raise HTTPException(status_code=500, detail="Failed to create PTY session")

    except Exception as e:
        logger.error(f"Error creating session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status():
    """Get session status."""
    logger.info("=== STATUS CHECK ===")

    # Check for any active PTY sessions
    active_sessions = pty_manager.list_sessions()

    if not active_sessions:
        logger.info("No active PTY sessions")
        return SessionStatus(
            ready=False,
            session_active=False,
            message="No active sessions. Use Terminal mode for WebSocket streaming."
        )

    logger.info(f"Active PTY sessions: {active_sessions}")
    return SessionStatus(
        ready=True,
        session_active=True,
        message=f"Session ready. {len(active_sessions)} active PTY session(s). Use Terminal mode for best experience."
    )


@app.post("/api/chat")
async def chat(chat_message: ChatMessage):
    """
    Send a message to Claude and get response.

    DEPRECATED: This endpoint uses the old marker-based protocol.
    For real-time interaction, use the Terminal mode with WebSocket at /ws/{guid}.
    """
    logger.info("=== CHAT MESSAGE (DEPRECATED) ===")
    logger.info(f"Message: {chat_message.message[:100]}...")
    logger.warning("Chat endpoint is deprecated. Use Terminal mode with WebSocket for real-time interaction.")

    # Return deprecation notice
    return ChatResponse(
        success=True,
        response=(
            "⚠️ **Chat mode is deprecated.**\n\n"
            "Please switch to **Terminal mode** for full interactive experience:\n"
            "1. Click the 'Terminal' button in the header\n"
            "2. Click 'New Session' to create a terminal session\n"
            "3. Type directly in the terminal for real-time interaction\n\n"
            "Terminal mode provides:\n"
            "- Real-time output streaming\n"
            "- Full terminal control (Ctrl+C, arrow keys, etc.)\n"
            "- WebSocket-based communication (no polling)\n"
        ),
        timestamp=datetime.utcnow().isoformat() + "Z"
    )


@app.get("/api/history")
async def get_history():
    """
    Get chat history.

    DEPRECATED: Chat mode is deprecated. Use Terminal mode instead.
    Returns empty history since chat history is not maintained for PTY sessions.
    """
    return HistoryResponse(messages=[])


@app.post("/api/clear")
async def clear_session():
    """Clear all PTY sessions."""
    try:
        # Kill all PTY sessions
        active_sessions = pty_manager.list_sessions()
        for guid in active_sessions:
            pty_manager.kill_session(guid)

        return {
            "success": True,
            "message": f"Cleared {len(active_sessions)} session(s)",
            "cleared_count": len(active_sessions)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================
# WebSocket Streaming Endpoint
# ==============================================

# Track active WebSocket connections per session
active_connections: Dict[str, List[WebSocket]] = {}


@app.websocket("/ws/{guid}")
async def websocket_terminal(websocket: WebSocket, guid: str):
    """
    WebSocket endpoint for real-time terminal streaming.

    Protocol:
    - Client connects to /ws/{guid}
    - Server streams PTY output to client
    - Client sends input which goes to PTY
    - Supports resize, reconnection with buffer replay
    """
    await websocket.accept()
    logger.info(f"WebSocket connected: {guid}")

    # Track this connection
    if guid not in active_connections:
        active_connections[guid] = []
    active_connections[guid].append(websocket)

    # Get or create PTY session
    session = pty_manager.get_session(guid)
    created_new = False

    if session is None:
        logger.info(f"Creating new PTY session for {guid}")
        session = pty_manager.create_session(guid)
        created_new = True

        if session is None:
            await websocket.send_json({
                "type": "error",
                "message": "Failed to create PTY session"
            })
            await websocket.close()
            return
    else:
        # Send buffered output for reconnection
        buffer = session.get_buffer()
        if buffer:
            await websocket.send_json({
                "type": "output",
                "data": buffer
            })
            logger.info(f"Sent {len(buffer)} bytes of buffered output")

    # Notify client session is ready
    await websocket.send_json({
        "type": "ready",
        "guid": guid,
        "new_session": created_new
    })

    # Start output reading task
    async def read_pty_output():
        """Read PTY output and send to all connected clients."""
        while True:
            try:
                if not session.is_alive():
                    logger.info(f"PTY session ended: {guid}")
                    break

                output = await session.read_output_async()
                if output:
                    # Send to all connected clients for this session
                    for ws in active_connections.get(guid, []):
                        try:
                            await ws.send_json({
                                "type": "output",
                                "data": output
                            })
                        except Exception:
                            pass  # Client disconnected

                await asyncio.sleep(0.01)  # Small delay to prevent busy loop

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error reading PTY output: {e}")
                break

    # Start the output reader
    output_task = asyncio.create_task(read_pty_output())

    try:
        # Handle incoming messages from client
        while True:
            try:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == "input":
                    # Send input to PTY
                    input_data = data.get("data", "")
                    session.send_input(input_data)
                    logger.debug(f"Received input: {len(input_data)} bytes")

                elif msg_type == "resize":
                    # Resize terminal
                    rows = data.get("rows", 40)
                    cols = data.get("cols", 120)
                    session.resize(rows, cols)
                    logger.debug(f"Resized to {rows}x{cols}")

                elif msg_type == "ping":
                    # Keepalive
                    await websocket.send_json({"type": "pong"})

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {guid}")
                break

    except Exception as e:
        logger.error(f"WebSocket error: {e}")

    finally:
        # Cleanup
        output_task.cancel()
        try:
            await output_task
        except asyncio.CancelledError:
            pass

        # Remove from active connections
        if guid in active_connections:
            active_connections[guid] = [
                ws for ws in active_connections[guid] if ws != websocket
            ]
            if not active_connections[guid]:
                del active_connections[guid]

        logger.info(f"WebSocket cleanup complete: {guid}")


@app.post("/api/stream/create/{guid}")
async def create_stream_session(guid: str):
    """
    Create a new PTY streaming session.

    Returns session info for WebSocket connection.
    """
    logger.info(f"Creating stream session: {guid}")

    # Check if session already exists
    existing = pty_manager.get_session(guid)
    if existing and existing.is_alive():
        return {
            "success": True,
            "guid": guid,
            "message": "Session already exists",
            "websocket_url": f"/ws/{guid}"
        }

    # Create new session
    session = pty_manager.create_session(guid)
    if session:
        return {
            "success": True,
            "guid": guid,
            "message": "Session created",
            "websocket_url": f"/ws/{guid}"
        }

    return {
        "success": False,
        "error": "Failed to create session"
    }


@app.delete("/api/stream/{guid}")
async def delete_stream_session(guid: str):
    """Kill a PTY streaming session."""
    logger.info(f"Deleting stream session: {guid}")

    # Close all WebSocket connections for this session
    for ws in active_connections.get(guid, []):
        try:
            await ws.close()
        except Exception:
            pass

    # Kill PTY session
    success = pty_manager.kill_session(guid)

    return {
        "success": success,
        "guid": guid,
        "message": "Session deleted" if success else "Session not found"
    }


@app.get("/api/stream/list")
async def list_stream_sessions():
    """List all active PTY streaming sessions."""
    sessions = pty_manager.list_sessions()
    return {
        "sessions": sessions,
        "count": len(sessions)
    }


# ==============================================
# Server Startup
# ==============================================

if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("TMUX BUILDER BACKEND SERVER")
    print("="*60)
    print(f"Starting API on {API_HOST}:{API_PORT}")
    print(f"WebSocket endpoint: ws://localhost:{API_PORT}/ws/{{guid}}")
    print(f"Frontend CORS: http://localhost:5173")
    print(f"Default User: {DEFAULT_USER}")
    print("="*60 + "\n")

    logger.info("Starting Uvicorn server...")

    uvicorn.run(app, host=API_HOST, port=API_PORT, log_level="info")
