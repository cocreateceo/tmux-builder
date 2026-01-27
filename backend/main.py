"""FastAPI backend for tmux-builder chat interface with WebSocket support."""

import logging
import os
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from pathlib import Path

from config import API_HOST, API_PORT, DEFAULT_USER, ACTIVE_SESSIONS_DIR, setup_logging
from session_controller import SessionController
from background_worker import BackgroundWorker
from guid_generator import generate_guid
from ws_server import start_progress_server, stop_progress_server

# Configure centralized logging (console + file)
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    logger.info("Starting Progress WebSocket server on port 8001...")
    await start_progress_server(port=8001)
    logger.info("Progress WebSocket server started!")

    yield

    # Shutdown
    logger.info("Stopping Progress WebSocket server...")
    await stop_progress_server()
    logger.info("Progress WebSocket server stopped!")


app = FastAPI(title="Tmux Builder API", version="1.0.0", lifespan=lifespan)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global session controller (simplified for demo)
session_controller: Optional[SessionController] = None

# Initialize background worker
background_worker = BackgroundWorker()


# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections per session GUID."""

    def __init__(self):
        # Map: guid -> list of WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Map: guid -> SessionController
        self.session_controllers: Dict[str, SessionController] = {}
        # Map: guid -> last known status (to detect changes)
        self.last_status: Dict[str, Dict] = {}

    async def connect(self, websocket: WebSocket, guid: str):
        """Accept WebSocket connection and register it."""
        await websocket.accept()
        if guid not in self.active_connections:
            self.active_connections[guid] = []
        self.active_connections[guid].append(websocket)
        logger.info(f"WebSocket connected for GUID: {guid} (total: {len(self.active_connections[guid])})")

    def disconnect(self, websocket: WebSocket, guid: str):
        """Remove WebSocket connection."""
        if guid in self.active_connections:
            if websocket in self.active_connections[guid]:
                self.active_connections[guid].remove(websocket)
            if not self.active_connections[guid]:
                del self.active_connections[guid]
        logger.info(f"WebSocket disconnected for GUID: {guid}")

    async def send_to_guid(self, guid: str, message: dict):
        """Send message to all connections for a GUID."""
        if guid in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[guid]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send to WebSocket: {e}")
                    dead_connections.append(connection)
            # Clean up dead connections
            for conn in dead_connections:
                self.active_connections[guid].remove(conn)

    def get_session_controller(self, guid: str) -> Optional[SessionController]:
        """Get or create SessionController for GUID."""
        if guid not in self.session_controllers:
            # Check if session exists
            session_path = ACTIVE_SESSIONS_DIR / guid
            if session_path.exists():
                self.session_controllers[guid] = SessionController(guid=guid)
                logger.info(f"Created SessionController for existing session: {guid}")
            else:
                return None
        return self.session_controllers[guid]

    def set_session_controller(self, guid: str, controller: SessionController):
        """Store SessionController for GUID."""
        self.session_controllers[guid] = controller

    def get_status(self, guid: str) -> Dict:
        """Read current status from status.json and markers."""
        try:
            session_path = ACTIVE_SESSIONS_DIR / guid
            status_file = session_path / "status.json"
            markers_path = session_path / "markers"

            status = {
                "state": "unknown",
                "progress": 0,
                "message": "Checking status...",
                "markers": {}
            }

            # Read status.json
            if status_file.exists():
                try:
                    status.update(json.loads(status_file.read_text()))
                except json.JSONDecodeError:
                    pass

            # Check markers
            if markers_path.exists():
                for marker in ["ready.marker", "ack.marker", "completed.marker"]:
                    marker_file = markers_path / marker
                    status["markers"][marker] = marker_file.exists()

            return status

        except Exception as e:
            logger.error(f"Error reading status: {e}")
            return {"state": "error", "message": str(e)}

    def get_chat_history(self, guid: str) -> List[Dict]:
        """Read chat history for GUID."""
        controller = self.get_session_controller(guid)
        if controller:
            return controller.get_chat_history()
        return []


# Global connection manager
ws_manager = ConnectionManager()


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

    This performs a quick health check to verify Claude CLI is alive.
    The full autonomous prompt is sent with the first user message.

    For the full GUID-based flow, use /api/register instead.
    This endpoint creates a session using a default GUID for demo purposes.
    """
    global session_controller

    logger.info("=== CREATE SESSION REQUEST ===")
    logger.info(f"User: {DEFAULT_USER}")

    try:
        # Generate a simple GUID for demo mode
        demo_guid = generate_guid(f"{DEFAULT_USER}@demo.local", "0000000000")
        logger.info(f"Demo GUID: {demo_guid}")

        # Use SessionInitializer for simple health check
        from session_initializer import SessionInitializer
        initializer = SessionInitializer()

        logger.info("Initializing session (simple health check)...")
        result = await initializer.initialize_session(
            guid=demo_guid,
            email=f"{DEFAULT_USER}@demo.local",
            phone="0000000000"
        )

        if result.get('success'):
            # Create SessionController for message handling
            session_controller = SessionController(guid=demo_guid)
            logger.info(f"✓ Session created successfully: {session_controller.session_name}")
            return {
                "success": True,
                "message": "Session ready - send your first message to begin",
                "session_name": session_controller.session_name,
                "guid": demo_guid
            }
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"Failed to initialize session: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

    except Exception as e:
        logger.error(f"Error creating session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status():
    """Get session status."""
    logger.info("=== STATUS CHECK ===")

    if session_controller is None:
        logger.info("No session controller exists")
        return SessionStatus(
            ready=False,
            session_active=False,
            message="No session created"
        )

    is_active = session_controller.is_active()
    logger.info(f"Session active: {is_active}, Session name: {session_controller.session_name}")

    return SessionStatus(
        ready=is_active,
        session_active=is_active,
        message="Session ready" if is_active else "Session inactive"
    )


@app.post("/api/chat")
async def chat(chat_message: ChatMessage):
    """Send a message to Claude and get response."""
    logger.info("=== CHAT MESSAGE ===")
    logger.info(f"Message: {chat_message.message[:100]}...")

    if session_controller is None:
        logger.error("No active session")
        raise HTTPException(status_code=400, detail="No active session")

    if not session_controller.is_active():
        logger.error("Session is not active")
        raise HTTPException(status_code=400, detail="Session is not active")

    try:
        # Send message and wait for response (use async version)
        logger.info("Sending message to Claude...")
        response = await session_controller.send_message_async(chat_message.message)
        logger.info(f"Got response: {response[:100] if response else 'None'}...")

        if response is None:
            logger.error("Failed to get response")
            raise HTTPException(status_code=500, detail="Failed to get response")

        logger.info("✓ Response sent successfully")
        return ChatResponse(
            success=True,
            response=response,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

    except Exception as e:
        logger.error(f"Error in chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
async def get_history():
    """Get chat history."""
    if session_controller is None:
        return HistoryResponse(messages=[])

    messages = session_controller.get_chat_history()
    return HistoryResponse(messages=messages)


@app.post("/api/clear")
async def clear_session():
    """Clear the current session."""
    global session_controller

    if session_controller is None:
        raise HTTPException(status_code=400, detail="No active session")

    try:
        success = session_controller.clear_session()

        if success:
            session_controller = None
            return {"success": True, "message": "Session cleared"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear session")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WebSocket Endpoints
# ============================================================================

@app.websocket("/ws/{guid}")
async def websocket_endpoint(websocket: WebSocket, guid: str):
    """
    WebSocket endpoint for real-time chat communication.

    Messages from client:
    - {"type": "send_message", "content": "..."} - Send a chat message
    - {"type": "get_status"} - Request current status
    - {"type": "get_history"} - Request chat history
    - {"type": "ping"} - Keepalive ping

    Messages to client:
    - {"type": "connected", "guid": "...", "status": {...}} - Connection established
    - {"type": "status", ...} - Status update
    - {"type": "history", "messages": [...]} - Chat history
    - {"type": "response", "content": "...", "complete": true/false} - Message response
    - {"type": "error", "message": "..."} - Error message
    - {"type": "pong"} - Response to ping
    """
    await ws_manager.connect(websocket, guid)
    status_task = None

    try:
        # Send initial status on connect
        loop = asyncio.get_event_loop()
        status = await loop.run_in_executor(None, ws_manager.get_status, guid)
        history = await loop.run_in_executor(None, ws_manager.get_chat_history, guid)

        await websocket.send_json({
            "type": "connected",
            "guid": guid,
            "status": status,
            "history": history
        })

        # Start background status polling task
        status_task = asyncio.create_task(
            poll_status_updates(websocket, guid)
        )

        # Main message loop
        while True:
            try:
                # Use receive() instead of receive_json() for better error handling
                message = await websocket.receive()

                if message["type"] == "websocket.disconnect":
                    logger.info(f"WebSocket disconnect received: {guid}")
                    break

                if message["type"] == "websocket.receive":
                    if "text" in message:
                        try:
                            data = json.loads(message["text"])
                            await handle_ws_message(websocket, guid, data)
                        except json.JSONDecodeError as e:
                            logger.warning(f"Invalid JSON from client: {e}")
                            await websocket.send_json({
                                "type": "error",
                                "message": "Invalid JSON"
                            })

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {guid}")
                break
            except Exception as e:
                logger.error(f"Error in message loop: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected during setup: {guid}")
    except Exception as e:
        logger.error(f"WebSocket error for {guid}: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        # Clean up status task
        if status_task:
            status_task.cancel()
            try:
                await status_task
            except asyncio.CancelledError:
                pass
        ws_manager.disconnect(websocket, guid)


async def poll_status_updates(websocket: WebSocket, guid: str):
    """Background task to poll status.json and send updates."""
    last_status_json = None

    while True:
        try:
            await asyncio.sleep(2)  # Poll every 2 seconds (reduced frequency)

            # Run synchronous file I/O in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            current_status = await loop.run_in_executor(
                None,
                ws_manager.get_status,
                guid
            )

            # Compare as JSON string to detect actual changes
            current_status_json = json.dumps(current_status, sort_keys=True)
            if current_status_json != last_status_json:
                try:
                    await websocket.send_json({
                        "type": "status",
                        **current_status
                    })
                    last_status_json = current_status_json
                except Exception as send_error:
                    # WebSocket might be closed, exit gracefully
                    logger.debug(f"Status send failed (connection may be closed): {send_error}")
                    break

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Status poll error: {e}")
            break


async def handle_ws_message(websocket: WebSocket, guid: str, data: dict):
    """Handle incoming WebSocket message."""
    global session_controller

    msg_type = data.get("type")
    logger.info(f"WebSocket message from {guid}: {msg_type}")

    if msg_type == "send_message":
        content = data.get("content", "").strip()
        if not content:
            await websocket.send_json({
                "type": "error",
                "message": "Empty message"
            })
            return

        # Get or create session controller
        controller = ws_manager.get_session_controller(guid)
        if not controller:
            # Try to create session first
            await websocket.send_json({
                "type": "error",
                "message": "No session found. Please create a session first."
            })
            return

        # Also update global session_controller for backwards compatibility
        session_controller = controller

        # Send acknowledgment that we're processing
        await websocket.send_json({
            "type": "status",
            "state": "processing",
            "progress": 10,
            "message": "Processing your message..."
        })

        # Process message in background to avoid blocking
        asyncio.create_task(
            process_message_async(websocket, guid, controller, content)
        )

    elif msg_type == "get_status":
        status = ws_manager.get_status(guid)
        await websocket.send_json({
            "type": "status",
            **status
        })

    elif msg_type == "get_history":
        history = ws_manager.get_chat_history(guid)
        await websocket.send_json({
            "type": "history",
            "messages": history
        })

    elif msg_type == "create_session":
        # Create session via WebSocket
        await create_session_ws(websocket, guid)

    elif msg_type == "ping":
        # Keepalive ping
        await websocket.send_json({"type": "pong"})

    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown message type: {msg_type}"
        })


async def process_message_async(
    websocket: WebSocket,
    guid: str,
    controller: SessionController,
    content: str
):
    """Process a chat message asynchronously."""
    try:
        # Use async version directly
        response = await controller.send_message_async(content)

        # Send response back
        await websocket.send_json({
            "type": "response",
            "content": response or "No response received",
            "complete": True,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

        # Send updated status
        status = ws_manager.get_status(guid)
        await websocket.send_json({
            "type": "status",
            **status
        })

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })


async def create_session_ws(websocket: WebSocket, guid: str):
    """Create session via WebSocket."""
    global session_controller

    try:
        await websocket.send_json({
            "type": "status",
            "state": "initializing",
            "progress": 10,
            "message": "Creating session..."
        })

        # Run initialization in thread pool
        from session_initializer import SessionInitializer
        initializer = SessionInitializer()

        result = await initializer.initialize_session(
            guid=guid,
            email=f"{DEFAULT_USER}@demo.local",
            phone="0000000000"
        )

        if result.get('success'):
            controller = SessionController(guid=guid)
            ws_manager.set_session_controller(guid, controller)
            session_controller = controller  # Backwards compatibility

            await websocket.send_json({
                "type": "session_created",
                "success": True,
                "message": "Session ready - send your first message",
                "guid": guid,
                "session_name": controller.session_name
            })

            # Send status update
            status = ws_manager.get_status(guid)
            await websocket.send_json({
                "type": "status",
                **status
            })
        else:
            await websocket.send_json({
                "type": "error",
                "message": result.get('error', 'Failed to create session')
            })

    except Exception as e:
        logger.error(f"Error creating session via WS: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })


if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("TMUX BUILDER BACKEND SERVER")
    print("="*60)
    print(f"Starting API on {API_HOST}:{API_PORT}")
    print(f"Frontend CORS: http://localhost:5173")
    print(f"Default User: {DEFAULT_USER}")
    print("="*60 + "\n")

    logger.info("Starting Uvicorn server...")

    uvicorn.run(app, host=API_HOST, port=API_PORT, log_level="info")
