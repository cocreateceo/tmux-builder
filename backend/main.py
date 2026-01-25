"""FastAPI backend for tmux-builder chat interface."""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

from config import API_HOST, API_PORT, DEFAULT_USER
from session_controller import SessionController

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

# Global session controller (simplified for demo)
session_controller: Optional[SessionController] = None


# Request/Response models
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


@app.post("/api/session/create")
async def create_session():
    """Create a new Claude CLI session."""
    global session_controller

    logger.info("=== CREATE SESSION REQUEST ===")
    logger.info(f"User: {DEFAULT_USER}")

    try:
        # Create new session controller
        logger.info("Creating SessionController...")
        session_controller = SessionController(username=DEFAULT_USER)
        logger.info(f"SessionController created: {session_controller.session_name}")

        # Initialize session
        logger.info("Initializing session...")
        success = session_controller.initialize_session()
        logger.info(f"Session initialization result: {success}")

        if success:
            logger.info(f"✓ Session created successfully: {session_controller.session_name}")
            return {
                "success": True,
                "message": "Session created successfully",
                "session_name": session_controller.session_name
            }
        else:
            logger.error("Failed to initialize session")
            raise HTTPException(status_code=500, detail="Failed to initialize session")

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
        # Send message and wait for response
        logger.info("Sending message to Claude...")
        response = session_controller.send_message(chat_message.message)
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
