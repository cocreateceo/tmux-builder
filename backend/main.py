"""FastAPI backend for tmux-builder chat interface with WebSocket support."""

import asyncio
import hashlib
import json
import logging
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from background_worker import BackgroundWorker
from config import ACTIVE_SESSIONS_DIR, DELETED_SESSIONS_DIR, API_HOST, API_PORT, DEFAULT_USER, SESSION_PREFIX, setup_logging
from guid_generator import generate_guid
from session_controller import SessionController
from session_initializer import SessionInitializer
from tmux_helper import TmuxHelper
from ws_server import start_progress_server, stop_progress_server

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    logger.info("Starting Progress WebSocket server on port 8082...")
    await start_progress_server(port=8082)
    logger.info("Progress WebSocket server started")
    yield
    logger.info("Stopping Progress WebSocket server...")
    await stop_progress_server()
    logger.info("Progress WebSocket server stopped")


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

# Global state
session_controller: Optional[SessionController] = None
session_controllers: Dict[str, SessionController] = {}  # Cache for multiple sessions
background_worker = BackgroundWorker()


def get_or_create_session_controller(guid: str) -> Optional[SessionController]:
    """Get cached SessionController or create one if session exists."""
    if guid in session_controllers:
        return session_controllers[guid]
    session_path = ACTIVE_SESSIONS_DIR / guid
    if session_path.exists():
        controller = SessionController(guid=guid)
        session_controllers[guid] = controller
        logger.info(f"Created SessionController for existing session: {guid}")
        return controller
    return None


def read_session_status(guid: str) -> Dict:
    """Read current status from status.json."""
    session_path = ACTIVE_SESSIONS_DIR / guid
    status_file = session_path / "status.json"
    status = {"state": "unknown", "progress": 0, "message": "Checking status..."}
    if status_file.exists():
        try:
            status.update(json.loads(status_file.read_text()))
        except json.JSONDecodeError:
            pass
    return status


def get_chat_history(guid: str) -> List[Dict]:
    """Read chat history for GUID."""
    controller = get_or_create_session_controller(guid)
    return controller.get_chat_history() if controller else []


def get_sessions_by_email(email: str) -> List[Dict]:
    """Get all sessions for a client email."""
    sessions = []
    if not ACTIVE_SESSIONS_DIR.exists():
        return sessions

    for session_path in ACTIVE_SESSIONS_DIR.iterdir():
        if not session_path.is_dir():
            continue
        status_file = session_path / "status.json"
        if not status_file.exists():
            continue
        try:
            status = json.loads(status_file.read_text())
            if status.get("email", "").lower() == email.lower():
                # Count messages
                chat_file = session_path / "chat_history.jsonl"
                message_count = 0
                if chat_file.exists():
                    with open(chat_file) as f:
                        message_count = sum(1 for _ in f)

                # Get deployed URL if exists
                deployed_url = status.get("deployed_url")

                sessions.append({
                    "guid": session_path.name,
                    "name": status.get("client_name") or status.get("name") or f"Project {session_path.name[:8]}",
                    "email": status.get("email"),
                    "status": "deployed" if deployed_url else ("completed" if status.get("state") == "completed" else "active"),
                    "message_count": message_count,
                    "initial_request": status.get("initial_request", ""),
                    "deployed_url": deployed_url,
                    "archived": status.get("archived", False),
                    "created_at": status.get("created_at"),
                    "updated_at": status.get("updated_at")
                })
        except (json.JSONDecodeError, IOError):
            continue

    # Sort by updated_at descending
    sessions.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
    return sessions


def get_client_info_from_guid(guid: str) -> Optional[Dict]:
    """Get client info (email, name) from a session GUID."""
    session_path = ACTIVE_SESSIONS_DIR / guid
    status_file = session_path / "status.json"
    if not status_file.exists():
        return None
    try:
        status = json.loads(status_file.read_text())
        return {
            "email": status.get("email"),
            "name": status.get("client_name") or status.get("name"),
            "phone": status.get("phone")
        }
    except (json.JSONDecodeError, IOError):
        return None


def generate_unique_guid(seed_prefix: str) -> str:
    """Generate a unique GUID using seed prefix, timestamp, and UUID."""
    import time
    import uuid
    unique_seed = f"{seed_prefix}:{time.time()}:{uuid.uuid4()}"
    return hashlib.sha256(unique_seed.encode('utf-8')).hexdigest()


async def initialize_new_session(
    guid: str,
    email: str = "",
    phone: str = "0000000000"
) -> Dict:
    """Initialize a new session and return result with SessionController."""
    global session_controller
    initializer = SessionInitializer()
    result = await initializer.initialize_session(guid=guid, email=email, phone=phone)
    if result.get('success'):
        controller = SessionController(guid=guid)
        session_controllers[guid] = controller
        session_controller = controller
        result['controller'] = controller
    return result


# Request/Response models
class RegistrationRequest(BaseModel):
    """Registration request model."""
    email: str
    phone: str
    initial_request: str


class ChatMessage(BaseModel):
    message: str
    guid: Optional[str] = None  # For session re-attachment after server restart
    screenshot: Optional[str] = None
    filePath: Optional[str] = None


class ChatResponse(BaseModel):
    success: bool
    response: str
    timestamp: str
    guid: Optional[str] = None  # Return GUID for frontend to store


class SessionStatus(BaseModel):
    ready: bool
    session_active: bool
    message: str


class HistoryResponse(BaseModel):
    messages: List[Dict]


class ClientProjectCreate(BaseModel):
    email: str
    initial_request: str
    name: Optional[str] = None


class ClientProjectUpdate(BaseModel):
    name: Optional[str] = None
    archived: Optional[bool] = None


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
async def get_session_status_endpoint(guid: str):
    """Get current status of session initialization/build."""
    logger.info(f"=== STATUS CHECK: {guid[:12]}... ===")

    job_status = background_worker.get_job_status(guid)
    if job_status is None:
        return {"success": False, "error": "Session not found", "guid": guid}

    # Merge with status.json if session is ready
    if job_status['status'] == 'ready':
        detailed_status = read_session_status(guid)
        return {"success": True, "guid": guid, **job_status, **detailed_status}

    return {"success": True, "guid": guid, **job_status}


@app.post("/api/session/create")
async def create_session():
    """
    Create a new Claude CLI session (simple chat UI flow).

    This performs a quick health check to verify Claude CLI is alive.
    The full autonomous prompt is sent with the first user message.
    """
    logger.info("=== CREATE SESSION REQUEST ===")
    new_guid = generate_unique_guid(f"{DEFAULT_USER}@demo.local")
    logger.info(f"New unique GUID: {new_guid}")

    result = await initialize_new_session(
        guid=new_guid,
        email=f"{DEFAULT_USER}@demo.local"
    )

    if result.get('success'):
        controller = result['controller']
        logger.info(f"Session created: {controller.session_name}")
        return {
            "success": True,
            "message": "Session ready - send your first message to begin",
            "session_name": controller.session_name,
            "guid": new_guid
        }

    error_msg = result.get('error', 'Unknown error')
    logger.error(f"Failed to initialize session: {error_msg}")
    raise HTTPException(status_code=500, detail=error_msg)


# ==============================================
# ADMIN API ENDPOINTS
# ==============================================

class AdminSessionCreate(BaseModel):
    """Request model for admin session creation."""
    name: str  # Required
    email: str  # Required
    phone: Optional[str] = ""
    initial_request: Optional[str] = ""


class SessionInfo(BaseModel):
    """Session information for admin listing."""
    guid: str
    guid_short: str
    client_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    state: Optional[str] = None
    progress: Optional[int] = 0
    user_request: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    tmux_active: bool = False
    has_chat_history: bool = False
    chat_message_count: int = 0
    activity_log_count: int = 0


@app.get("/api/admin/sessions")
async def list_sessions(filter: str = "all"):
    """
    List all sessions with metadata and tmux status.

    Filter: all, active (with tmux), completed (without tmux), deleted
    """
    logger.info(f"=== ADMIN LIST SESSIONS (filter: {filter}) ===")

    # Handle deleted filter - scan deleted folder instead
    if filter == "deleted":
        if not DELETED_SESSIONS_DIR.exists():
            return {"sessions": [], "total": 0, "filter": filter}
        sessions_dir = DELETED_SESSIONS_DIR
        is_deleted_filter = True
    else:
        if not ACTIVE_SESSIONS_DIR.exists():
            return {"sessions": [], "total": 0, "filter": filter}
        sessions_dir = ACTIVE_SESSIONS_DIR
        is_deleted_filter = False

    # Get active tmux session GUIDs
    active_tmux_guids = set()
    for session_name in TmuxHelper.list_sessions():
        if session_name.startswith(SESSION_PREFIX):
            active_tmux_guids.add(session_name.replace(f"{SESSION_PREFIX}_", ""))

    sessions = []

    for session_dir in sessions_dir.iterdir():
        if not session_dir.is_dir():
            continue

        guid = session_dir.name
        tmux_active = guid in active_tmux_guids

        # Apply filter (skip for deleted filter - we already selected the right folder)
        if not is_deleted_filter:
            if filter == "active" and not tmux_active:
                continue
            if filter == "completed" and tmux_active:
                continue

        # Read session metadata
        status_file = session_dir / "status.json"
        chat_history_file = session_dir / "chat_history.jsonl"
        activity_log_file = session_dir / "activity_log.jsonl"

        session_info = SessionInfo(
            guid=guid,
            guid_short=guid[:12] + "...",
            tmux_active=tmux_active
        )

        # Read status.json
        if status_file.exists():
            try:
                status_data = json.loads(status_file.read_text())
                session_info.client_name = status_data.get("client_name")
                session_info.email = status_data.get("email")
                session_info.phone = status_data.get("phone")
                session_info.state = status_data.get("state")
                session_info.progress = status_data.get("progress", 0)
                session_info.user_request = status_data.get("user_request")
                session_info.updated_at = status_data.get("updated_at")
            except Exception as e:
                logger.warning(f"Could not read status.json for {guid}: {e}")

        # Get folder creation time
        try:
            stat = session_dir.stat()
            session_info.created_at = datetime.fromtimestamp(stat.st_ctime).isoformat() + "Z"
        except Exception:
            pass

        # Count chat history messages
        if chat_history_file.exists():
            session_info.has_chat_history = True
            try:
                with open(chat_history_file) as f:
                    session_info.chat_message_count = sum(1 for _ in f)
            except Exception:
                pass

        # Count activity log entries
        if activity_log_file.exists():
            try:
                with open(activity_log_file) as f:
                    session_info.activity_log_count = sum(1 for _ in f)
            except Exception:
                pass

        sessions.append(session_info)

    # Sort by created_at descending (newest first)
    sessions.sort(key=lambda s: s.created_at or "", reverse=True)

    logger.info(f"Found {len(sessions)} sessions")
    return {
        "sessions": [s.model_dump() for s in sessions],
        "total": len(sessions),
        "filter": filter
    }


@app.post("/api/admin/sessions")
async def create_admin_session(request: AdminSessionCreate):
    """Create a new session for external client with name/email/phone/initial request."""
    logger.info(f"=== CREATE CLIENT SESSION: {request.name} ({request.email}) ===")

    # Base URL for session links (CloudFront production URL)
    BASE_URL = "https://d3r4k77gnvpmzn.cloudfront.net"

    try:
        new_guid = generate_unique_guid(request.email)
        result = await initialize_new_session(
            guid=new_guid,
            email=request.email,
            phone=request.phone or ""
        )

        if not result.get('success'):
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"Failed to create client session: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "guid": None,
                "link": None
            }

        controller = result['controller']
        logger.info(f"Client session created: {controller.session_name}")

        # Save name, email, phone to status.json
        status_file = ACTIVE_SESSIONS_DIR / new_guid / "status.json"
        if status_file.exists():
            status_data = json.loads(status_file.read_text())
            status_data["client_name"] = request.name
            status_data["client_email"] = request.email
            status_data["client_phone"] = request.phone or ""
            if request.initial_request:
                status_data["user_request"] = request.initial_request
            status_file.write_text(json.dumps(status_data, indent=2))

        # If initial_request provided, send it to Claude CLI
        if request.initial_request:
            logger.info(f"Sending initial request to Claude: {request.initial_request[:50]}...")
            # Store controller globally for this session
            global session_controller
            session_controller = controller

            # Send the message (this saves to chat_history and sends to Claude)
            await controller.send_message_async(request.initial_request)
            logger.info("Initial request sent to Claude CLI")

        # Generate session link for client dashboard
        session_link = f"{BASE_URL}/client?guid={new_guid}"

        return {
            "success": True,
            "guid": new_guid,
            "link": session_link
        }

    except Exception as e:
        logger.error(f"Exception creating client session: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "guid": None,
            "link": None
        }


@app.delete("/api/admin/sessions/{guid}")
async def delete_session(guid: str):
    """
    Delete a session by moving it to the deleted folder.
    Also kills the tmux session if active.
    """
    logger.info(f"=== ADMIN DELETE SESSION: {guid[:12]}... ===")

    source_path = ACTIVE_SESSIONS_DIR / guid
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    # Kill tmux session if active
    session_name = f"{SESSION_PREFIX}_{guid}"
    try:
        if TmuxHelper.session_exists(session_name):
            TmuxHelper.kill_session(session_name)
            logger.info(f"Killed tmux session: {session_name}")
    except Exception as e:
        logger.warning(f"Could not kill tmux session: {e}")

    # Remove from session_controllers cache if present
    if guid in session_controllers:
        del session_controllers[guid]
        logger.info(f"Removed from session_controllers cache")

    # Move to deleted folder
    dest_path = DELETED_SESSIONS_DIR / guid
    try:
        if dest_path.exists():
            # If already exists in deleted, remove it first
            shutil.rmtree(dest_path)
        shutil.move(str(source_path), str(dest_path))
        logger.info(f"Moved session to deleted: {dest_path}")
    except Exception as e:
        logger.error(f"Failed to move session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {e}")

    return {
        "success": True,
        "message": "Session deleted successfully",
        "guid": guid
    }


@app.post("/api/admin/sessions/{guid}/complete")
async def complete_session(guid: str):
    """
    Mark a session as completed by killing its tmux session.
    Session folder remains in active directory.
    """
    logger.info(f"=== ADMIN COMPLETE SESSION: {guid[:12]}... ===")

    session_path = ACTIVE_SESSIONS_DIR / guid
    if not session_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    # Kill tmux session if active
    session_name = f"{SESSION_PREFIX}_{guid}"
    was_active = False
    try:
        if TmuxHelper.session_exists(session_name):
            TmuxHelper.kill_session(session_name)
            was_active = True
            logger.info(f"Killed tmux session: {session_name}")
    except Exception as e:
        logger.warning(f"Could not kill tmux session: {e}")

    # Remove from session_controllers cache if present
    if guid in session_controllers:
        del session_controllers[guid]

    return {
        "success": True,
        "message": "Session completed" if was_active else "Session was already completed",
        "guid": guid,
        "was_active": was_active
    }


@app.post("/api/admin/sessions/{guid}/restore")
async def restore_session(guid: str):
    """
    Restore a deleted session by moving it back to the active folder.
    """
    logger.info(f"=== ADMIN RESTORE SESSION: {guid[:12]}... ===")

    source_path = DELETED_SESSIONS_DIR / guid
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Deleted session not found")

    dest_path = ACTIVE_SESSIONS_DIR / guid
    try:
        if dest_path.exists():
            raise HTTPException(status_code=409, detail="Session already exists in active folder")
        shutil.move(str(source_path), str(dest_path))
        logger.info(f"Restored session to active: {dest_path}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restore session: {e}")

    return {
        "success": True,
        "message": "Session restored successfully",
        "guid": guid
    }


@app.get("/api/admin/sessions/{guid}")
async def get_session_details(guid: str):
    """Get detailed information about a specific session."""
    logger.info(f"=== ADMIN GET SESSION DETAILS: {guid[:12]}... ===")

    session_dir = ACTIVE_SESSIONS_DIR / guid
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    session_name = f"{SESSION_PREFIX}_{guid}"
    tmux_active = TmuxHelper.session_exists(session_name)

    result = {
        "guid": guid,
        "guid_short": guid[:12] + "...",
        "tmux_active": tmux_active,
        "session_name": session_name,
        "files": {}
    }

    # Read all metadata files
    for filename in ["status.json", "chat_history.jsonl", "activity_log.jsonl", "prompt.txt"]:
        filepath = session_dir / filename
        if filepath.exists():
            try:
                content = filepath.read_text()
                if filename.endswith(".jsonl"):
                    # Parse JSONL to list
                    result["files"][filename] = [
                        json.loads(line) for line in content.strip().split('\n') if line.strip()
                    ]
                elif filename.endswith(".json"):
                    result["files"][filename] = json.loads(content)
                else:
                    result["files"][filename] = content
            except Exception as e:
                result["files"][filename] = f"Error reading: {e}"

    # List subfolders
    result["folders"] = [d.name for d in session_dir.iterdir() if d.is_dir()]

    return result


# ==============================================
# CLIENT API ENDPOINTS
# ==============================================

@app.get("/api/client/projects")
async def get_client_projects(email: str = None, guid: str = None):
    """Get all projects for a client (by email or lookup from guid)."""
    if not email and not guid:
        raise HTTPException(status_code=400, detail="Either email or guid required")

    if not email and guid:
        client_info = get_client_info_from_guid(guid)
        if not client_info or not client_info.get("email"):
            raise HTTPException(status_code=404, detail="Session not found or no email associated")
        email = client_info["email"]

    projects = get_sessions_by_email(email)
    client_info = get_client_info_from_guid(guid) if guid else None

    return {
        "success": True,
        "projects": projects,
        "client": client_info or {"email": email}
    }


@app.post("/api/client/projects")
async def create_client_project(data: ClientProjectCreate):
    """Create a new project for an existing client."""
    guid = generate_unique_guid(data.email)

    try:
        initializer = SessionInitializer()
        result = await initializer.initialize_session(
            guid=guid,
            email=data.email,
            user_request=data.initial_request
        )

        if not result.get('success'):
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to initialize session'))

        # Update name and initial_request in status.json
        session_path = ACTIVE_SESSIONS_DIR / guid
        status_file = session_path / "status.json"
        if status_file.exists():
            status = json.loads(status_file.read_text())
            if data.name:
                status["name"] = data.name
            status["initial_request"] = data.initial_request
            status_file.write_text(json.dumps(status, indent=2))

        return {
            "success": True,
            "guid": guid,
            "link": f"/?guid={guid}&embed=true"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create client project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/client/projects/{guid}")
async def update_client_project(guid: str, data: ClientProjectUpdate):
    """Update project properties (name, archived status)."""
    session_path = ACTIVE_SESSIONS_DIR / guid
    status_file = session_path / "status.json"

    if not status_file.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        status = json.loads(status_file.read_text())

        if data.name is not None:
            status["name"] = data.name
        if data.archived is not None:
            status["archived"] = data.archived

        status["updated_at"] = datetime.now().isoformat()
        status_file.write_text(json.dumps(status, indent=2))

        return {"success": True, "guid": guid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/client/projects/{guid}/duplicate")
async def duplicate_client_project(guid: str):
    """Duplicate an existing project."""
    session_path = ACTIVE_SESSIONS_DIR / guid
    status_file = session_path / "status.json"

    if not status_file.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        status = json.loads(status_file.read_text())
        email = status.get("email")
        initial_request = status.get("initial_request", "")
        original_name = status.get("name", "Project")

        if not email:
            raise HTTPException(status_code=400, detail="Original project has no email")

        # Create new project
        new_guid = generate_unique_guid(email)
        initializer = SessionInitializer()
        result = await initializer.initialize_session(
            guid=new_guid,
            email=email,
            user_request=initial_request
        )

        if not result.get('success'):
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to initialize session'))

        # Update name to indicate it's a copy
        new_session_path = ACTIVE_SESSIONS_DIR / new_guid
        new_status_file = new_session_path / "status.json"
        if new_status_file.exists():
            new_status = json.loads(new_status_file.read_text())
            new_status["name"] = f"{original_name} (Copy)"
            new_status["initial_request"] = initial_request
            new_status_file.write_text(json.dumps(new_status, indent=2))

        return {
            "success": True,
            "guid": new_guid,
            "link": f"/?guid={new_guid}&embed=true"
        }
    except HTTPException:
        raise
    except Exception as e:
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
    global session_controller

    logger.info(f"=== CHAT: {chat_message.message[:50]}... (GUID: {chat_message.guid or 'none'}) ===")

    # Determine target GUID
    target_guid = chat_message.guid
    if not target_guid:
        target_guid = generate_unique_guid(f"{DEFAULT_USER}@demo.local")
        logger.info(f"Generated new GUID: {target_guid}")

    # Check if we need to switch/create session
    needs_switch = session_controller is None or session_controller.guid != target_guid
    if needs_switch:
        session_name = f"{SESSION_PREFIX}_{target_guid}"
        if TmuxHelper.session_exists(session_name):
            logger.info(f"Re-attaching to existing session: {session_name}")
            session_controller = SessionController(guid=target_guid)
            session_controllers[target_guid] = session_controller
        else:
            logger.info(f"Auto-creating new session: {session_name}")
            result = await initialize_new_session(
                guid=target_guid,
                email=f"{DEFAULT_USER}@demo.local"
            )
            if not result.get('success'):
                raise HTTPException(status_code=500, detail="Failed to create session")

    if not session_controller.is_active():
        raise HTTPException(status_code=400, detail="Session is not active")

    response = await session_controller.send_message_async(chat_message.message)
    if response is None:
        raise HTTPException(status_code=500, detail="Failed to get response")

    return ChatResponse(
        success=True,
        response=response,
        timestamp=datetime.utcnow().isoformat() + "Z",
        guid=session_controller.guid
    )


@app.get("/api/history")
async def get_history(guid: str = None):
    """Get chat history from file (survives server restart)."""
    # Try to get GUID from query param, then from global session_controller
    target_guid = guid
    if not target_guid and session_controller:
        target_guid = session_controller.guid

    if not target_guid:
        return HistoryResponse(messages=[])

    # Read directly from chat_history.jsonl file
    try:
        session_path = ACTIVE_SESSIONS_DIR / target_guid
        history_file = session_path / "chat_history.jsonl"
        summary_file = session_path / "summary.md"

        messages = []

        if history_file.exists():
            with open(history_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        messages.append(json.loads(line))

        # Check if we need to recover assistant response from summary.md
        # If last message is from user and summary.md exists, append it
        if messages and summary_file.exists():
            last_msg = messages[-1]
            has_assistant_after_last_user = False

            # Check if there's already an assistant message after the last user message
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get('role') == 'user':
                    break
                if messages[i].get('role') == 'assistant':
                    has_assistant_after_last_user = True
                    break

            if last_msg.get('role') == 'user' and not has_assistant_after_last_user:
                # Read summary and append as assistant message
                summary_content = summary_file.read_text().strip()
                if summary_content:
                    assistant_msg = {
                        "role": "assistant",
                        "content": summary_content,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    messages.append(assistant_msg)

                    # Persist to chat_history.jsonl for future loads
                    with open(history_file, 'a') as f:
                        f.write(json.dumps(assistant_msg) + '\n')
                    logger.info(f"Recovered assistant response from summary.md for {target_guid}")

        return HistoryResponse(messages=messages)
    except Exception as e:
        logger.error(f"Failed to read chat history: {e}")
        return HistoryResponse(messages=[])


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
