"""FastAPI backend for tmux-builder chat interface."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

from config import API_HOST, API_PORT, DEFAULT_USER
from session_controller import SessionController

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
    return {"message": "Tmux Builder API", "version": "1.0.0"}


@app.post("/api/session/create")
async def create_session():
    """Create a new Claude CLI session."""
    global session_controller

    try:
        # Create new session controller
        session_controller = SessionController(username=DEFAULT_USER)

        # Initialize session
        success = session_controller.initialize_session()

        if success:
            return {
                "success": True,
                "message": "Session created successfully",
                "session_name": session_controller.session_name
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to initialize session")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status():
    """Get session status."""
    if session_controller is None:
        return SessionStatus(
            ready=False,
            session_active=False,
            message="No session created"
        )

    is_active = session_controller.is_active()

    return SessionStatus(
        ready=is_active,
        session_active=is_active,
        message="Session ready" if is_active else "Session inactive"
    )


@app.post("/api/chat")
async def chat(chat_message: ChatMessage):
    """Send a message to Claude and get response."""
    if session_controller is None:
        raise HTTPException(status_code=400, detail="No active session")

    if not session_controller.is_active():
        raise HTTPException(status_code=400, detail="Session is not active")

    try:
        # Send message and wait for response
        response = session_controller.send_message(chat_message.message)

        if response is None:
            raise HTTPException(status_code=500, detail="Failed to get response")

        return ChatResponse(
            success=True,
            response=response,
            timestamp=datetime.utcnow().isoformat() + "Z"
        )

    except Exception as e:
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

    print(f"Starting Tmux Builder API on {API_HOST}:{API_PORT}")
    print(f"Frontend CORS: http://localhost:5173")

    uvicorn.run(app, host=API_HOST, port=API_PORT)
