"""
Configuration Module for tmux-builder Backend

This module provides centralized configuration following SmartBuild patterns.
All paths, timeouts, and settings are defined here.
"""

import os
from pathlib import Path
from typing import Dict

# ==============================================
# BASE PATHS
# ==============================================

# Base directory (backend folder)
BASE_DIR = Path(__file__).parent.resolve()

# Project root (parent of backend)
PROJECT_ROOT = BASE_DIR.parent

# Sessions directory - Use project directory for easier access
SESSIONS_DIR = PROJECT_ROOT / "sessions"
ACTIVE_SESSIONS_DIR = SESSIONS_DIR / "active"
DELETED_SESSIONS_DIR = SESSIONS_DIR / "deleted"

# Ensure directories exist
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
ACTIVE_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
DELETED_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# ==============================================
# USER CONFIGURATION
# ==============================================

# Default user ID (single user mode for now)
DEFAULT_USER_ID = os.getenv('USER_ID', 'default_user')

# Alias for chat UI compatibility
DEFAULT_USER = DEFAULT_USER_ID

# ==============================================
# CLAUDE CLI CONFIGURATION
# ==============================================

# Claude CLI path and flags
CLI_PATH = os.getenv('CLI_PATH', 'claude')
CLI_FLAGS = '--dangerously-skip-permissions'
CLI_MODEL = os.getenv('CLI_MODEL', 'sonnet')

# Full command template
CLI_COMMAND = f"{CLI_PATH} {CLI_FLAGS}"

# ==============================================
# TMUX CONFIGURATION
# ==============================================

# TMUX session naming
TMUX_SESSION_PREFIX = "tmux_builder"

# Session name formats
TMUX_MAIN_SESSION_FORMAT = "{prefix}_main_{session_id}"
TMUX_JOB_SESSION_FORMAT = "{prefix}_job_{job_id}"

# ==============================================
# TIMING CONFIGURATION (CRITICAL)
# ==============================================

# Delays for TMUX command sending (do not modify without testing)
TMUX_SEND_COMMAND_DELAY = 0.3  # After send-keys
TMUX_SEND_ENTER_DELAY = 1.2    # After Enter key
TMUX_CLAUDE_INIT_DELAY = 3.0   # After starting Claude CLI

# ==============================================
# JOB CONFIGURATION
# ==============================================

# Job timeouts (seconds)
JOB_TIMEOUTS: Dict[str, int] = {
    'echo_test': 60,        # 1 minute
    'file_analysis': 300,   # 5 minutes
    'code_generation': 600, # 10 minutes
    'default': 300          # 5 minutes default
}

# Minimum wait before checking completion
JOB_MIN_WAIT_TIMES: Dict[str, int] = {
    'echo_test': 5,         # 5 seconds
    'file_analysis': 10,    # 10 seconds
    'code_generation': 20,  # 20 seconds
    'default': 10           # 10 seconds default
}

# Job status check intervals
JOB_CHECK_INTERVAL = 2  # Check every 2 seconds

# Maximum concurrent jobs
MAX_CONCURRENT_JOBS = 4

# ==============================================
# CHAT SESSION CONFIGURATION (for UI)
# ==============================================

# Session prefix (for chat-based sessions)
SESSION_PREFIX = TMUX_SESSION_PREFIX

# ==============================================
# PROGRESS WEBSOCKET CONFIGURATION
# ==============================================

# Progress WebSocket port (for real-time updates to UI)
PROGRESS_WS_PORT = int(os.getenv('PROGRESS_WS_PORT', '8001'))

# Protocol timeouts
ACK_TIMEOUT = 30  # seconds to wait for ack from Claude
RESPONSE_TIMEOUT = 300  # seconds to wait for response

# ==============================================
# CHAT SESSION FILES
# ==============================================

# Status file
STATUS_FILE = "status.json"

# Prompt file (backend writes, Claude reads)
PROMPT_FILE = "prompt.txt"

# Chat history file
CHAT_HISTORY_FILE = "chat_history.jsonl"

# ==============================================
# FILE PATHS
# ==============================================

# Job queue filename
JOB_QUEUE_FILENAME = "job_queue.json"

# Session metadata filename
SESSION_METADATA_FILENAME = "metadata.json"

# Session log filename pattern
SESSION_LOG_PATTERN = "session_{session_id}.log"

# Prompt directory name
PROMPTS_DIR_NAME = "prompts"

# Output directory name
OUTPUT_DIR_NAME = "output"

# ==============================================
# SERVER CONFIGURATION
# ==============================================

# Backend server port
BACKEND_PORT = int(os.getenv('BACKEND_PORT', '8000'))

# Aliases for API server compatibility
API_PORT = BACKEND_PORT
API_HOST = os.getenv('API_HOST', '0.0.0.0')

# CORS origins
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

# Logging level
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# ==============================================
# WEBSOCKET CONSTANTS
# ==============================================

# Maximum message history per session (activity log entries)
WS_MAX_MESSAGE_HISTORY = 500

# ==============================================
# LOGGING CONFIGURATION
# ==============================================

LOG_DIR = SESSIONS_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "tmux-builder.log"

def setup_logging():
    """Configure centralized logging to both console and file."""
    import logging
    from logging.handlers import RotatingFileHandler

    # Create formatter
    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL))

    # Clear existing handlers
    root_logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (rotating, max 10MB, keep 5 backups)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10*1024*1024,
        backupCount=5
    )
    file_handler.setLevel(getattr(logging, LOG_LEVEL))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Reduce noise from websockets library - only show WARNING+
    logging.getLogger('websockets').setLevel(logging.WARNING)
    logging.getLogger('websockets.server').setLevel(logging.WARNING)

    logging.info(f"Logging initialized - Console + File: {LOG_FILE}")

# ==============================================
# HELPER FUNCTIONS
# ==============================================

def get_session_path(session_id: str) -> Path:
    """Get the full path to a session directory."""
    return ACTIVE_SESSIONS_DIR / session_id

def get_job_queue_path(session_id: str) -> Path:
    """Get the path to a session's job queue file."""
    return get_session_path(session_id) / JOB_QUEUE_FILENAME

def get_session_metadata_path(session_id: str) -> Path:
    """Get the path to a session's metadata file."""
    return get_session_path(session_id) / SESSION_METADATA_FILENAME

def get_prompts_dir(session_id: str) -> Path:
    """Get the prompts directory for a session."""
    prompts_dir = get_session_path(session_id) / PROMPTS_DIR_NAME
    prompts_dir.mkdir(parents=True, exist_ok=True)
    return prompts_dir

def get_output_dir(session_id: str) -> Path:
    """Get the output directory for a session."""
    output_dir = get_session_path(session_id) / OUTPUT_DIR_NAME
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def get_session_log_path(session_id: str) -> Path:
    """Get the path to a session's log file."""
    logs_dir = get_session_path(session_id) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / SESSION_LOG_PATTERN.format(session_id=session_id)

def get_tmux_main_session_name(session_id: str) -> str:
    """Get the TMUX main session name for a session."""
    return TMUX_MAIN_SESSION_FORMAT.format(
        prefix=TMUX_SESSION_PREFIX,
        session_id=session_id
    )

def get_tmux_job_session_name(job_id: str) -> str:
    """Get the TMUX job session name for a job."""
    return TMUX_JOB_SESSION_FORMAT.format(
        prefix=TMUX_SESSION_PREFIX,
        job_id=job_id
    )

def get_user_session_path(username: str) -> Path:
    """Get the session path for a user (for chat UI)."""
    user_dir = SESSIONS_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

def get_status_file(guid: str) -> Path:
    """Get the path to status.json for a session."""
    return ACTIVE_SESSIONS_DIR / guid / STATUS_FILE


def get_prompt_file(guid: str) -> Path:
    """Get the path to prompt.txt for a session."""
    return ACTIVE_SESSIONS_DIR / guid / PROMPT_FILE

# ==============================================
# VALIDATION
# ==============================================

def validate_config() -> bool:
    """Validate configuration and check dependencies."""
    import shutil
    import subprocess

    # Check tmux availability
    if not shutil.which('tmux'):
        raise RuntimeError(
            "tmux is not installed or not in PATH. "
            "Install it with: sudo apt-get install tmux"
        )

    # Check Claude CLI availability
    if not shutil.which(CLI_PATH):
        raise RuntimeError(
            f"Claude CLI not found at: {CLI_PATH}. "
            "Install it from: https://claude.ai/download"
        )

    # Test Claude CLI
    try:
        result = subprocess.run(
            [CLI_PATH, '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"✓ Claude CLI found: {CLI_PATH}")
            print(f"✓ Using flags: {CLI_FLAGS}")
            return True
    except Exception as e:
        raise RuntimeError(f"Claude CLI not working: {e}")

    return True

def print_config():
    """Print current configuration."""
    print("=" * 60)
    print("tmux-builder Configuration")
    print("=" * 60)
    print(f"Base Directory:      {BASE_DIR}")
    print(f"Sessions Directory:  {SESSIONS_DIR}")
    print(f"CLI Command:         {CLI_COMMAND}")
    print(f"TMUX Prefix:         {TMUX_SESSION_PREFIX}")
    print(f"Max Concurrent Jobs: {MAX_CONCURRENT_JOBS}")
    print(f"Backend Port:        {BACKEND_PORT}")
    print(f"Log Level:           {LOG_LEVEL}")
    print("=" * 60)

# Validate on import (can be disabled with environment variable)
if os.getenv('SKIP_CONFIG_VALIDATION') != 'true':
    try:
        validate_config()
    except Exception as e:
        print(f"⚠️  Configuration validation failed: {e}")
        print("Set SKIP_CONFIG_VALIDATION=true to skip validation")
