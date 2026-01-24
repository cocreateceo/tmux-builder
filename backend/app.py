"""Flask API endpoints for multi-user cloud deployment.

This module provides REST API endpoints for user creation, status checking,
and session management.
"""

from flask import Flask, request, jsonify

from user_manager import UserManager
from session_creator import SessionCreator
from execution_tracker import ExecutionTracker
from injection_engine import InjectionEngine
from tmux_helper import TmuxHelper

app = Flask(__name__)

# Initialize managers (will be replaced by init_managers for testing)
user_manager = UserManager()
session_creator = SessionCreator()
execution_tracker = ExecutionTracker()
injection_engine = InjectionEngine()
tmux_helper = TmuxHelper()

# Valid configuration options
VALID_HOST_PROVIDERS = ["aws", "azure"]
VALID_SITE_TYPES = ["static", "dynamic"]
CHAT_ALLOWED_STATUSES = ['running', 'waiting_input']


def init_managers(um, sc, et, ie, th=None):
    """Initialize managers for testing with mocks.

    Args:
        um: UserManager instance or mock
        sc: SessionCreator instance or mock
        et: ExecutionTracker instance or mock
        ie: InjectionEngine instance or mock
        th: TmuxHelper instance or mock (optional)
    """
    global user_manager, session_creator, execution_tracker, injection_engine, tmux_helper
    user_manager = um
    session_creator = sc
    execution_tracker = et
    injection_engine = ie
    if th is not None:
        tmux_helper = th


@app.route('/api/create-user', methods=['POST'])
def create_user():
    """Create a new user and initialize session.

    Request body:
        {
            "email": string,
            "phone": string,
            "host_provider": string (aws|azure),
            "site_type": string (static|dynamic),
            "requirements": string (optional) - User's site requirements
        }

    Returns:
        {
            "execution_id": string,
            "user_id": string,
            "session_id": string,
            "is_new_user": boolean
        }
    """
    data = request.get_json()

    # Validate required fields
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    email = data.get("email")
    phone = data.get("phone")
    host_provider = data.get("host_provider")
    site_type = data.get("site_type")
    requirements = data.get("requirements", "")

    # Validate host_provider
    if host_provider not in VALID_HOST_PROVIDERS:
        return jsonify({
            "error": f"Invalid host_provider. Must be one of: {VALID_HOST_PROVIDERS}"
        }), 400

    # Validate site_type
    if site_type not in VALID_SITE_TYPES:
        return jsonify({
            "error": f"Invalid site_type. Must be one of: {VALID_SITE_TYPES}"
        }), 400

    # Create user
    user_result = user_manager.create_user(
        email=email,
        phone=phone,
        host_provider=host_provider,
        site_type=site_type
    )
    user_id = user_result["user_id"]
    is_new_user = user_result["is_new"]

    # Create session
    session_id = session_creator.create_session(
        user_id=user_id,
        host_provider=host_provider,
        site_type=site_type
    )

    # Create execution tracking
    execution_id = execution_tracker.create_execution(
        user_id=user_id,
        session_id=session_id
    )

    # Store requirements and config in execution metadata
    execution_tracker.update_metadata(execution_id, {
        "requirements": requirements,
        "host_provider": host_provider,
        "site_type": site_type
    })

    # Inject agents and skills
    session_path = session_creator.get_session_path(user_id, session_id)
    injection_engine.inject(
        host_provider=host_provider,
        site_type=site_type,
        session_dir=str(session_path)
    )

    return jsonify({
        "execution_id": execution_id,
        "user_id": user_id,
        "session_id": session_id,
        "is_new_user": is_new_user
    })


@app.route('/api/status/<execution_id>', methods=['GET'])
def get_status(execution_id):
    """Get execution status by ID.

    Args:
        execution_id: Execution identifier from URL path

    Returns:
        Full execution status dict if found, 404 if not found
    """
    status = execution_tracker.get_status(execution_id)

    if status is None:
        return jsonify({"error": "Execution not found"}), 404

    return jsonify(status)


@app.route('/api/user/<user_id>/sessions', methods=['GET'])
def list_user_sessions(user_id):
    """List all sessions for a user.

    Args:
        user_id: User GUID from URL path

    Returns:
        {"sessions": [...list of session IDs...]}
    """
    sessions = session_creator.list_sessions(user_id)
    return jsonify({"sessions": sessions})


@app.route('/api/chat/<execution_id>', methods=['POST'])
def chat(execution_id):
    """Send a message to the Claude session.

    Request body:
        {
            "message": string
        }

    Returns:
        {"status": "sent", "execution_id": string}
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body is required"}), 400

    message = data.get("message", "")

    if not message or not message.strip():
        return jsonify({"error": "Message is required"}), 400

    # Validate execution exists
    execution = execution_tracker.get_status(execution_id)
    if not execution:
        return jsonify({"error": "Execution not found"}), 404

    # Validate execution is in a state that accepts messages
    if execution.get('status') not in CHAT_ALLOWED_STATUSES:
        return jsonify({
            "error": f"Cannot chat - execution status is {execution.get('status')}"
        }), 400

    # Send message to tmux session
    success = tmux_helper.send_instruction(f"exec_{execution_id}", message)
    if not success:
        return jsonify({"error": "Failed to send message to session"}), 500

    return jsonify({
        "status": "sent",
        "execution_id": execution_id
    })


@app.route('/api/redeploy/<execution_id>', methods=['POST'])
def redeploy(execution_id):
    """Trigger redeployment of an existing session.

    Resets execution to step 6 (deploy) and re-queues the job.

    Returns:
        {"status": "redeploying", "execution_id": string}
    """
    # Validate execution exists
    execution = execution_tracker.get_status(execution_id)
    if not execution:
        return jsonify({"error": "Execution not found"}), 404

    # Reset to deploy step
    execution_tracker.update_step(execution_id, 6, "deploy", "running")

    # TODO: Re-queue job for processing
    # job_queue.enqueue(execution_id, start_step=6)

    return jsonify({
        "status": "redeploying",
        "execution_id": execution_id
    })


@app.route('/api/chat/<execution_id>/history', methods=['GET'])
def chat_history(execution_id):
    """Get recent tmux pane output for display.

    Returns:
        {"output": string, "execution_id": string}
    """
    # Validate execution exists
    execution = execution_tracker.get_status(execution_id)
    if not execution:
        return jsonify({"error": "Execution not found"}), 404

    # Capture tmux output
    output = tmux_helper.capture_pane_output(f"exec_{execution_id}", lines=100)

    return jsonify({
        "output": output,
        "execution_id": execution_id
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
