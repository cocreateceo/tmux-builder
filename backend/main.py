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

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from background_worker import BackgroundWorker
from config import ACTIVE_SESSIONS_DIR, DELETED_SESSIONS_DIR, PENDING_REQUESTS_DIR, API_HOST, API_PORT, DEFAULT_USER, SESSION_PREFIX, setup_logging
from guid_generator import generate_guid, is_valid_guid
from session_controller import SessionController
from session_initializer import SessionInitializer
from tmux_helper import TmuxHelper
from ws_server import start_progress_server, stop_progress_server

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Initialize DynamoDB table if needed
    try:
        from dynamodb_client import get_dynamo_client
        dynamo = get_dynamo_client()
        if dynamo.ensure_table_exists():
            logger.info("DynamoDB table ready")
        else:
            logger.warning("DynamoDB table initialization failed - resource tracking may not work")
    except Exception as e:
        logger.warning(f"DynamoDB initialization skipped: {e}")

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
        "https://d3tfeatcbws1ka.cloudfront.net",
        "https://d3r4k77gnvpmzn.cloudfront.net",
        "https://www.cocreateidea.com",
        "https://cocreateidea.com",
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


def validate_guid_or_raise(guid: str) -> str:
    """Validate GUID format and raise HTTPException if invalid.

    This prevents path traversal attacks by ensuring GUID is a valid hex string.

    Args:
        guid: GUID string to validate

    Returns:
        The validated GUID

    Raises:
        HTTPException: If GUID format is invalid
    """
    if not is_valid_guid(guid):
        logger.warning(f"Invalid GUID format rejected: {guid[:50]}...")
        raise HTTPException(status_code=400, detail="Invalid GUID format")
    return guid


def read_session_status(guid: str) -> Dict:
    """Read current status from status.json."""
    validate_guid_or_raise(guid)
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
    """Get client info (email, name, avatarUrl, theme) from a session GUID."""
    session_path = ACTIVE_SESSIONS_DIR / guid
    status_file = session_path / "status.json"
    if not status_file.exists():
        return None
    try:
        status = json.loads(status_file.read_text())
        result = {
            "email": status.get("email"),
            "name": status.get("client_name") or status.get("name"),
            "phone": status.get("phone"),
            "avatarUrl": None,
            "theme": "ember"  # default theme
        }

        # Try to fetch avatar URL and theme from cocreate-applications-data S3 bucket
        try:
            import boto3
            s3 = boto3.client('s3', region_name='us-east-1')
            profile_key = f"users/{guid}/profile.json"
            response = s3.get_object(Bucket='cocreate-applications-data', Key=profile_key)
            profile = json.loads(response['Body'].read().decode('utf-8'))
            if profile.get('avatarUrl'):
                result['avatarUrl'] = profile['avatarUrl']
            if profile.get('theme'):
                result['theme'] = profile['theme']
        except Exception:
            pass  # No avatar or profile found

        return result
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
    phone: str = "0000000000",
    client_name: str = ""
) -> Dict:
    """Initialize a new session and return result with SessionController."""
    global session_controller
    initializer = SessionInitializer()
    result = await initializer.initialize_session(guid=guid, email=email, phone=phone, client_name=client_name)
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


class PendingRequest(BaseModel):
    """Model for submitting a new pending request (from onboarding)."""
    name: str
    email: str
    phone: Optional[str] = ""
    initial_request: str


class PendingRequestInfo(BaseModel):
    """Model for pending request listing."""
    request_id: str
    name: str
    email: str
    phone: Optional[str] = ""
    initial_request: str
    status: str  # pending, approved, rejected
    created_at: str
    updated_at: Optional[str] = None


# ==============================================
# PENDING REQUESTS HELPER FUNCTIONS
# ==============================================

def get_pending_requests(status_filter: str = "all") -> List[Dict]:
    """Get all pending requests, optionally filtered by status."""
    requests = []
    if not PENDING_REQUESTS_DIR.exists():
        return requests

    for request_file in PENDING_REQUESTS_DIR.glob("*.json"):
        try:
            data = json.loads(request_file.read_text())
            if status_filter == "all" or data.get("status") == status_filter:
                requests.append(data)
        except (json.JSONDecodeError, IOError):
            continue

    # Sort by created_at descending
    requests.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return requests


def get_pending_request(request_id: str) -> Optional[Dict]:
    """Get a specific pending request by ID."""
    request_file = PENDING_REQUESTS_DIR / f"{request_id}.json"
    if not request_file.exists():
        return None
    try:
        return json.loads(request_file.read_text())
    except (json.JSONDecodeError, IOError):
        return None


def save_pending_request(request_id: str, data: Dict) -> bool:
    """Save a pending request to disk."""
    request_file = PENDING_REQUESTS_DIR / f"{request_id}.json"
    try:
        request_file.write_text(json.dumps(data, indent=2))
        return True
    except IOError:
        return False


def delete_pending_request(request_id: str) -> bool:
    """Delete a pending request file."""
    request_file = PENDING_REQUESTS_DIR / f"{request_id}.json"
    if request_file.exists():
        request_file.unlink()
        return True
    return False


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

        # Save user to DynamoDB on registration (so they appear in cost reports)
        try:
            from dynamodb_client import get_dynamo_client
            dynamo = get_dynamo_client()
            dynamo.save_project_resources(
                user_id=request.email,
                project_id=guid,
                project_name=request.initial_request[:100] if request.initial_request else "New Project",
                aws_resources={},  # Empty until they deploy
                email=request.email
            )
            logger.info(f"✓ User saved to DynamoDB: {request.email}")
        except Exception as dynamo_error:
            logger.warning(f"Could not save user to DynamoDB: {dynamo_error}")

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
    validate_guid_or_raise(guid)
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
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


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

        # Save name, email, phone, created_at to status.json (use consistent field names)
        status_file = ACTIVE_SESSIONS_DIR / new_guid / "status.json"
        if status_file.exists():
            status_data = json.loads(status_file.read_text())
            status_data["name"] = request.name
            status_data["client_name"] = request.name  # Keep for backwards compatibility
            status_data["email"] = request.email  # Use "email" not "client_email"
            status_data["phone"] = request.phone or ""
            status_data["created_at"] = request.created_at
            if request.initial_request:
                status_data["user_request"] = request.initial_request
                status_data["initial_request"] = request.initial_request  # Also save as initial_request
            status_file.write_text(json.dumps(status_data, indent=2))

        # Save user to DynamoDB on admin session creation
        try:
            from dynamodb_client import get_dynamo_client
            dynamo = get_dynamo_client()
            dynamo.save_project_resources(
                user_id=request.email,
                project_id=new_guid,
                project_name=request.initial_request[:100] if request.initial_request else request.name or "New Project",
                aws_resources={},  # Empty until deployed
                email=request.email
            )
            logger.info(f"✓ Admin session saved to DynamoDB: {request.email}")
        except Exception as dynamo_error:
            logger.warning(f"Could not save admin session to DynamoDB: {dynamo_error}")

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
    validate_guid_or_raise(guid)
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

    # Delete AWS IAM user if per-user IAM was enabled
    try:
        from aws_user_manager import AWSUserManager
        from config import AWS_PER_USER_IAM_ENABLED
        if AWS_PER_USER_IAM_ENABLED:
            aws_manager = AWSUserManager()
            if aws_manager.delete_user(guid):
                logger.info(f"Deleted AWS IAM user for session: {guid[:12]}...")
    except ImportError:
        logger.debug("AWS user manager not available - skipping IAM cleanup")
    except Exception as e:
        logger.warning(f"Could not delete AWS IAM user: {e}")

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

        # Save user to DynamoDB on client project creation
        try:
            from dynamodb_client import get_dynamo_client
            dynamo = get_dynamo_client()
            dynamo.save_project_resources(
                user_id=data.email,
                project_id=guid,
                project_name=data.initial_request[:100] if data.initial_request else data.name or "New Project",
                aws_resources={},  # Empty until deployed
                email=data.email
            )
            logger.info(f"✓ Client project saved to DynamoDB: {data.email}")
        except Exception as dynamo_error:
            logger.warning(f"Could not save client project to DynamoDB: {dynamo_error}")

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


class SaveThemeRequest(BaseModel):
    guid: str
    theme: str


@app.post("/api/client/save-theme")
async def save_client_theme(request: SaveThemeRequest):
    """Save user's theme preference to S3 profile."""
    guid = request.guid
    theme = request.theme

    # Validate theme
    valid_themes = ['ember', 'coral', 'sunset', 'aurora', 'legacy', 'sandstone', 'champagne', 'zoom']
    if theme not in valid_themes:
        raise HTTPException(status_code=400, detail="Invalid theme")

    # Verify guid exists
    session_path = ACTIVE_SESSIONS_DIR / guid
    if not session_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        import boto3
        s3 = boto3.client('s3', region_name='us-east-1')
        bucket = 'cocreate-applications-data'
        profile_key = f"users/{guid}/profile.json"

        # Get existing profile
        profile = {}
        try:
            response = s3.get_object(Bucket=bucket, Key=profile_key)
            profile = json.loads(response['Body'].read().decode('utf-8'))
        except Exception:
            pass  # No profile yet

        # Update theme
        profile['theme'] = theme

        # Save back to S3
        s3.put_object(
            Bucket=bucket,
            Key=profile_key,
            Body=json.dumps(profile),
            ContentType='application/json'
        )

        return {"success": True, "theme": theme}
    except Exception as e:
        logger.error(f"Failed to save theme: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================
# AWS RESOURCES API ENDPOINTS
# ==============================================

@app.get("/api/projects/{guid}/resources")
async def get_project_resources(guid: str):
    """Get AWS resources for a project from DynamoDB."""
    validate_guid_or_raise(guid)
    logger.info(f"=== GET PROJECT RESOURCES: {guid[:12]}... ===")

    try:
        from dynamodb_client import get_dynamo_client

        # First try to get from local status.json (faster)
        session_path = ACTIVE_SESSIONS_DIR / guid
        status_file = session_path / "status.json"

        local_resources = None
        user_id = None

        if status_file.exists():
            status = json.loads(status_file.read_text())
            local_resources = status.get('aws_resources')
            user_id = status.get('email') or status.get('client_name') or guid

        # Also try DynamoDB for the full record
        dynamo = get_dynamo_client()
        db_record = None

        if user_id:
            db_record = dynamo.get_project_resources(user_id, guid)

        if not db_record:
            # Try to find by guid only (scan)
            db_record = dynamo.get_all_resources_by_guid(guid)

        # Merge local and DynamoDB resources
        resources = {}
        if db_record and db_record.get('awsResources'):
            resources = db_record.get('awsResources')
        if local_resources:
            resources.update(local_resources)

        return {
            "success": True,
            "guid": guid,
            "resources": resources,
            "project_name": db_record.get('projectName') if db_record else None,
            "created_at": db_record.get('createdAt') if db_record else None,
            "updated_at": db_record.get('updatedAt') if db_record else None
        }

    except ImportError:
        # DynamoDB client not available, just return local resources
        session_path = ACTIVE_SESSIONS_DIR / guid
        status_file = session_path / "status.json"

        if status_file.exists():
            status = json.loads(status_file.read_text())
            return {
                "success": True,
                "guid": guid,
                "resources": status.get('aws_resources', {}),
                "source": "local"
            }

        return {"success": False, "error": "No resources found", "resources": {}}

    except Exception as e:
        logger.error(f"Failed to get project resources: {e}")
        return {"success": False, "error": str(e), "resources": {}}


@app.get("/api/users/{user_id}/deployments")
async def get_user_deployments(user_id: str):
    """Get all deployments/projects for a user from DynamoDB."""
    logger.info(f"=== GET USER DEPLOYMENTS: {user_id} ===")

    try:
        from dynamodb_client import get_dynamo_client

        dynamo = get_dynamo_client()
        projects = dynamo.get_user_projects(user_id)

        return {
            "success": True,
            "user_id": user_id,
            "projects": projects,
            "total": len(projects)
        }

    except ImportError:
        logger.warning("DynamoDB client not available")
        return {
            "success": False,
            "error": "DynamoDB not configured",
            "projects": []
        }

    except Exception as e:
        logger.error(f"Failed to get user deployments: {e}")
        return {"success": False, "error": str(e), "projects": []}


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


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    guid: str = Form(...)
):
    """Upload a file and trigger Claude to build a website from it."""
    global session_controller

    logger.info(f"=== UPLOAD: {file.filename} (GUID: {guid}) ===")

    # Validate GUID
    validate_guid_or_raise(guid)

    # Validate file type
    allowed_extensions = {'.txt', '.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png'}
    file_ext = '.' + file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Check file size (max 10MB)
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")

    # Save file to session folder
    session_path = ACTIVE_SESSIONS_DIR / guid
    if not session_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    uploads_dir = session_path / "uploads"
    uploads_dir.mkdir(exist_ok=True)

    # Save with timestamp to avoid conflicts
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = uploads_dir / safe_filename

    with open(file_path, 'wb') as f:
        f.write(contents)

    logger.info(f"File saved to: {file_path}")

    # Determine file type for Claude instruction
    if file_ext in {'.jpg', '.jpeg', '.png'}:
        file_type = "image"
        instruction = f"I've uploaded an image file at {file_path}. Please analyze this image and create a website based on what you see. If it's a design mockup, implement it. If it's a logo or product image, create an appropriate website around it."
    elif file_ext == '.pdf':
        file_type = "pdf"
        instruction = f"I've uploaded a PDF file at {file_path}. Please read and analyze this document, then create a website based on its contents. Extract the key information and build an appropriate website."
    elif file_ext in {'.doc', '.docx'}:
        file_type = "document"
        instruction = f"I've uploaded a Word document at {file_path}. Please read and analyze this document, then create a website based on its contents."
    else:  # .txt
        file_type = "text"
        instruction = f"I've uploaded a text file at {file_path}. Please read this file and create a website based on its contents."

    # Re-attach or create session if needed
    target_guid = guid
    needs_switch = session_controller is None or session_controller.guid != target_guid
    if needs_switch:
        session_name = f"{SESSION_PREFIX}_{target_guid}"
        if TmuxHelper.session_exists(session_name):
            logger.info(f"Re-attaching to existing session: {session_name}")
            session_controller = SessionController(guid=target_guid)
            session_controllers[target_guid] = session_controller
        else:
            logger.info(f"Auto-creating new session: {session_name}")
            existing_info = get_client_info_from_guid(target_guid)
            result = await initialize_new_session(
                guid=target_guid,
                email=existing_info.get('email', f"{DEFAULT_USER}@demo.local") if existing_info else f"{DEFAULT_USER}@demo.local",
                client_name=existing_info.get('name', '') if existing_info else ''
            )
            if not result.get('success'):
                raise HTTPException(status_code=500, detail="Failed to create session")

    if not session_controller.is_active():
        raise HTTPException(status_code=400, detail="Session is not active")

    # Send instruction to Claude
    response = await session_controller.send_message_async(instruction)

    return {
        "success": True,
        "filename": safe_filename,
        "file_type": file_type,
        "file_path": str(file_path),
        "message": f"File uploaded. Claude is now building a website from your {file_type}.",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "guid": guid
    }


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
            # Read existing client info if session folder exists (preserves metadata)
            existing_info = get_client_info_from_guid(target_guid)
            result = await initialize_new_session(
                guid=target_guid,
                email=existing_info.get('email', f"{DEFAULT_USER}@demo.local") if existing_info else f"{DEFAULT_USER}@demo.local",
                client_name=existing_info.get('name', '') if existing_info else ''
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


@app.get("/api/deployments")
async def get_deployments(guid: str):
    """
    Get all deployed projects for a session by parsing chat history.
    Returns project name, URL, and deployment timestamp.
    """
    import re

    if not guid:
        return {"success": False, "deployments": [], "error": "GUID required"}

    validate_guid_or_raise(guid)

    try:
        session_path = ACTIVE_SESSIONS_DIR / guid
        history_file = session_path / "chat_history.jsonl"

        deployments = []

        if not history_file.exists():
            return {"success": True, "deployments": []}

        # Parse chat history for deployment info
        with open(history_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Only look at assistant messages
                if msg.get('role') != 'assistant':
                    continue

                content = msg.get('content', '')
                timestamp = msg.get('timestamp', '')

                # Look for CloudFront URLs in the message
                cloudfront_urls = re.findall(r'https://[a-z0-9]+\.cloudfront\.net', content, re.IGNORECASE)

                if not cloudfront_urls:
                    continue

                # Try to extract project name from message
                # Look for patterns like "## ProjectName" or "**ProjectName**" or "# ProjectName"
                project_name = None

                # Pattern 1: ## Title - text or ## Title Complete
                title_match = re.search(r'^##\s+(.+?)(?:\s+-\s+|\s+Complete|\s*$)', content, re.MULTILINE)
                if title_match:
                    project_name = title_match.group(1).strip()

                # Pattern 2: First line with emoji as title
                if not project_name:
                    first_line_match = re.search(r'^#+\s*(.+?)$', content, re.MULTILINE)
                    if first_line_match:
                        project_name = first_line_match.group(1).strip()
                        # Remove common suffixes
                        project_name = re.sub(r'\s*[-–]\s*(Complete|Done|Deployed|MVP).*$', '', project_name, flags=re.IGNORECASE)

                # Fallback: use "Website" if no name found
                if not project_name:
                    project_name = "Website Project"

                # Clean up project name (remove emojis at start)
                project_name = re.sub(r'^[🚀✨🎉💫⭐️🔥💪🌟]+\s*', '', project_name)

                # Add deployment entry (keep all, even same URL - shows build history)
                url = cloudfront_urls[0]  # Use first URL found

                deployments.append({
                    "project_name": project_name,
                    "url": url,
                    "deployed_at": timestamp,
                    "status": "deployed"
                })

        # Sort by timestamp (newest first)
        deployments.sort(key=lambda x: x.get('deployed_at', ''), reverse=True)

        return {"success": True, "deployments": deployments}

    except Exception as e:
        logger.error(f"Failed to get deployments: {e}")
        return {"success": False, "deployments": [], "error": str(e)}


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


# ==============================================
# PENDING REQUESTS API ENDPOINTS
# ==============================================

@app.post("/api/requests")
async def submit_request(data: PendingRequest):
    """
    Submit a new pending request (from onboarding form).
    Request is stored as pending until admin approves.
    """
    try:
        logger.info(f"=== NEW PENDING REQUEST ===")
        logger.info(f"Name: {data.name}, Email: {data.email}")

        # Generate a unique request ID
        request_id = generate_unique_guid(data.email)

        # Create pending request data
        request_data = {
            "request_id": request_id,
            "name": data.name,
            "email": data.email,
            "phone": data.phone or "",
            "initial_request": data.initial_request,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None
        }

        # Save to pending directory
        if not save_pending_request(request_id, request_data):
            raise HTTPException(status_code=500, detail="Failed to save request")

        logger.info(f"Pending request saved: {request_id}")

        return {
            "success": True,
            "request_id": request_id,
            "status": "pending",
            "message": "Your request has been submitted and is pending approval."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/requests")
async def list_pending_requests(status: str = "all"):
    """List all pending requests for admin review."""
    logger.info(f"=== ADMIN LIST REQUESTS (status: {status}) ===")
    requests = get_pending_requests(status)
    return {
        "success": True,
        "requests": requests,
        "total": len(requests)
    }


@app.get("/api/admin/requests/{request_id}")
async def get_request_details(request_id: str):
    """Get details of a specific pending request."""
    request_data = get_pending_request(request_id)
    if not request_data:
        raise HTTPException(status_code=404, detail="Request not found")
    return {
        "success": True,
        "request": request_data
    }


@app.post("/api/admin/requests/{request_id}/approve")
async def approve_request(request_id: str):
    """
    Approve a pending request and create the actual session.
    """
    logger.info(f"=== APPROVE REQUEST: {request_id} ===")

    request_data = get_pending_request(request_id)
    if not request_data:
        raise HTTPException(status_code=404, detail="Request not found")

    if request_data.get("status") != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {request_data.get('status')}")

    try:
        # Generate session GUID
        new_guid = generate_unique_guid(request_data["email"])

        # Initialize the session
        result = await initialize_new_session(
            guid=new_guid,
            email=request_data["email"],
            phone=request_data.get("phone", ""),
            client_name=request_data["name"]
        )

        if not result.get('success'):
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to initialize session'))

        # Update session status.json with initial_request
        session_path = ACTIVE_SESSIONS_DIR / new_guid
        status_file = session_path / "status.json"
        if status_file.exists():
            status = json.loads(status_file.read_text())
            status["initial_request"] = request_data.get("initial_request", "")
            status["approved_from_request"] = request_id
            status_file.write_text(json.dumps(status, indent=2))

        # Save user to DynamoDB on request approval
        try:
            from dynamodb_client import get_dynamo_client
            dynamo = get_dynamo_client()
            dynamo.save_project_resources(
                user_id=request_data["email"],
                project_id=new_guid,
                project_name=request_data.get("initial_request", "")[:100] or request_data["name"] or "New Project",
                aws_resources={},  # Empty until deployed
                email=request_data["email"]
            )
            logger.info(f"✓ Approved request saved to DynamoDB: {request_data['email']}")
        except Exception as dynamo_error:
            logger.warning(f"Could not save approved request to DynamoDB: {dynamo_error}")

        # Update pending request status
        request_data["status"] = "approved"
        request_data["approved_guid"] = new_guid
        request_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_pending_request(request_id, request_data)

        logger.info(f"Request {request_id} approved, session created: {new_guid}")

        return {
            "success": True,
            "guid": new_guid,
            "link": f"/client?guid={new_guid}",
            "message": "Request approved and session created"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/requests/{request_id}/reject")
async def reject_request(request_id: str, reason: str = ""):
    """Reject a pending request."""
    logger.info(f"=== REJECT REQUEST: {request_id} ===")

    request_data = get_pending_request(request_id)
    if not request_data:
        raise HTTPException(status_code=404, detail="Request not found")

    if request_data.get("status") != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {request_data.get('status')}")

    # Update status to rejected
    request_data["status"] = "rejected"
    request_data["rejection_reason"] = reason
    request_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_pending_request(request_id, request_data)

    logger.info(f"Request {request_id} rejected")

    return {
        "success": True,
        "message": "Request rejected"
    }


@app.delete("/api/admin/requests/{request_id}")
async def delete_request(request_id: str):
    """Delete a pending request permanently."""
    logger.info(f"=== DELETE REQUEST: {request_id} ===")

    if not get_pending_request(request_id):
        raise HTTPException(status_code=404, detail="Request not found")

    delete_pending_request(request_id)

    return {
        "success": True,
        "message": "Request deleted"
    }


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
