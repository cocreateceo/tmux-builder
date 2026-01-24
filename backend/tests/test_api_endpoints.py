"""Tests for Flask API endpoints - create-user and status."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_managers():
    """Create mock managers for testing."""
    user_manager = MagicMock()
    session_creator = MagicMock()
    execution_tracker = MagicMock()
    injection_engine = MagicMock()
    tmux_helper = MagicMock()

    return {
        "user_manager": user_manager,
        "session_creator": session_creator,
        "execution_tracker": execution_tracker,
        "injection_engine": injection_engine,
        "tmux_helper": tmux_helper
    }


@pytest.fixture
def client(mock_managers):
    """Create Flask test client with mocked managers."""
    with patch.dict('sys.modules', {
        'user_manager': MagicMock(),
        'session_creator': MagicMock(),
        'execution_tracker': MagicMock(),
        'injection_engine': MagicMock(),
        'tmux_helper': MagicMock()
    }):
        from app import app, init_managers

        # Replace managers with mocks
        init_managers(
            mock_managers["user_manager"],
            mock_managers["session_creator"],
            mock_managers["execution_tracker"],
            mock_managers["injection_engine"],
            mock_managers["tmux_helper"]
        )

        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client, mock_managers


class TestCreateUserEndpoint:
    """Tests for POST /api/create-user endpoint."""

    def test_create_user_returns_execution_id(self, client):
        """Test that create-user returns execution_id in response."""
        test_client, mocks = client

        # Setup mocks
        mocks["user_manager"].create_user.return_value = {
            "user_id": "test-user-123",
            "is_new": True
        }
        mocks["session_creator"].create_session.return_value = "sess_20260124_120000"
        mocks["session_creator"].get_session_path.return_value = "/tmp/test/session"
        mocks["execution_tracker"].create_execution.return_value = "test-user-123_sess_20260124_120000"
        mocks["injection_engine"].inject.return_value = {
            "agents_copied": 2,
            "skills_copied": 3
        }

        response = test_client.post('/api/create-user', json={
            "email": "test@example.com",
            "phone": "1234567890",
            "host_provider": "aws",
            "site_type": "static"
        })

        assert response.status_code == 200
        data = response.get_json()
        assert "execution_id" in data
        assert data["execution_id"] == "test-user-123_sess_20260124_120000"
        assert data["user_id"] == "test-user-123"
        assert data["session_id"] == "sess_20260124_120000"
        assert data["is_new_user"] is True

    def test_create_user_validates_host_provider(self, client):
        """Test that create-user returns 400 for invalid host_provider."""
        test_client, mocks = client

        response = test_client.post('/api/create-user', json={
            "email": "test@example.com",
            "phone": "1234567890",
            "host_provider": "gcp",  # Invalid provider
            "site_type": "static"
        })

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "host_provider" in data["error"].lower()

    def test_create_user_validates_site_type(self, client):
        """Test that create-user returns 400 for invalid site_type."""
        test_client, mocks = client

        response = test_client.post('/api/create-user', json={
            "email": "test@example.com",
            "phone": "1234567890",
            "host_provider": "aws",
            "site_type": "hybrid"  # Invalid site type
        })

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "site_type" in data["error"].lower()


class TestStatusEndpoint:
    """Tests for GET /api/status/<execution_id> endpoint."""

    def test_status_returns_execution_state(self, client):
        """Test that status endpoint returns full status for valid execution_id."""
        test_client, mocks = client

        # Setup mock
        mocks["execution_tracker"].get_status.return_value = {
            "execution_id": "test-user-123_sess_20260124_120000",
            "user_id": "test-user-123",
            "session_id": "sess_20260124_120000",
            "status": "running",
            "current_step": 3,
            "total_steps": 7,
            "created_at": "2026-01-24T12:00:00Z",
            "logs": []
        }

        response = test_client.get('/api/status/test-user-123_sess_20260124_120000')

        assert response.status_code == 200
        data = response.get_json()
        assert data["execution_id"] == "test-user-123_sess_20260124_120000"
        assert data["status"] == "running"
        assert data["current_step"] == 3

    def test_status_not_found(self, client):
        """Test that status endpoint returns 404 for unknown execution_id."""
        test_client, mocks = client

        # Setup mock to return None (not found)
        mocks["execution_tracker"].get_status.return_value = None

        response = test_client.get('/api/status/nonexistent-execution-id')

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data


class TestUserSessionsEndpoint:
    """Tests for GET /api/user/<user_id>/sessions endpoint."""

    def test_list_user_sessions(self, client):
        """Test that user sessions endpoint returns list of sessions."""
        test_client, mocks = client

        # Setup mock
        mocks["session_creator"].list_sessions.return_value = [
            "sess_20260124_100000",
            "sess_20260124_120000",
            "sess_20260124_140000"
        ]

        response = test_client.get('/api/user/test-user-123/sessions')

        assert response.status_code == 200
        data = response.get_json()
        assert "sessions" in data
        assert len(data["sessions"]) == 3
        assert "sess_20260124_100000" in data["sessions"]


class TestCreateUserRequirements:
    """Tests for requirements field in POST /api/create-user endpoint."""

    def test_create_user_stores_requirements(self, client):
        """Test that requirements field is stored in execution metadata."""
        test_client, mocks = client

        # Setup mocks
        mocks["user_manager"].create_user.return_value = {
            "user_id": "test-user-123",
            "is_new": True
        }
        mocks["session_creator"].create_session.return_value = "sess_20260124_120000"
        mocks["session_creator"].get_session_path.return_value = "/tmp/test/session"
        mocks["execution_tracker"].create_execution.return_value = "test-user-123_sess_20260124_120000"
        mocks["injection_engine"].inject.return_value = {
            "agents_copied": 2,
            "skills_copied": 3
        }

        response = test_client.post('/api/create-user', json={
            'email': 'test@example.com',
            'phone': '+1234567890',
            'host_provider': 'aws',
            'site_type': 'static',
            'requirements': 'Build a portfolio website with dark theme'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert 'execution_id' in data

        # Verify update_metadata was called with requirements
        mocks['execution_tracker'].update_metadata.assert_called_once()
        call_args = mocks['execution_tracker'].update_metadata.call_args
        assert call_args[0][1]['requirements'] == 'Build a portfolio website with dark theme'


class TestChatEndpoint:
    """Tests for POST /api/chat/<execution_id> endpoint."""

    def test_chat_endpoint_sends_message(self, client):
        """Test POST /api/chat sends message to tmux session."""
        test_client, mocks = client

        # Setup: execution exists and is running
        mocks['execution_tracker'].get_status.return_value = {
            'execution_id': 'user123_sess456',
            'status': 'running'
        }
        mocks['tmux_helper'].send_instruction.return_value = True

        response = test_client.post('/api/chat/user123_sess456', json={
            'message': 'Add a contact form to the homepage'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'sent'
        assert data['execution_id'] == 'user123_sess456'

        # Verify tmux_helper was called correctly
        mocks['tmux_helper'].send_instruction.assert_called_once_with(
            'exec_user123_sess456',
            'Add a contact form to the homepage'
        )

    def test_chat_endpoint_404_for_missing_execution(self, client):
        """Test POST /api/chat returns 404 for missing execution."""
        test_client, mocks = client

        mocks['execution_tracker'].get_status.return_value = None

        response = test_client.post('/api/chat/nonexistent_exec', json={
            'message': 'Hello'
        })

        assert response.status_code == 404

    def test_chat_endpoint_400_for_wrong_status(self, client):
        """Test POST /api/chat returns 400 if execution not running."""
        test_client, mocks = client

        mocks['execution_tracker'].get_status.return_value = {
            'execution_id': 'user123_sess456',
            'status': 'completed'
        }

        response = test_client.post('/api/chat/user123_sess456', json={
            'message': 'Hello'
        })

        assert response.status_code == 400

    def test_chat_endpoint_accepts_waiting_input_status(self, client):
        """Test POST /api/chat accepts waiting_input status."""
        test_client, mocks = client

        mocks['execution_tracker'].get_status.return_value = {
            'execution_id': 'user123_sess456',
            'status': 'waiting_input'
        }
        mocks['tmux_helper'].send_instruction.return_value = True

        response = test_client.post('/api/chat/user123_sess456', json={
            'message': 'Here is my input'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'sent'

    def test_chat_endpoint_400_for_empty_body(self, client):
        """Test POST /api/chat returns 400 for empty JSON body."""
        test_client, mocks = client

        # Empty dict {} is falsy in Python, so returns 400
        response = test_client.post('/api/chat/user123_sess456', json={})

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_chat_endpoint_415_for_no_json_content_type(self, client):
        """Test POST /api/chat returns 415 if Content-Type not JSON."""
        test_client, mocks = client

        response = test_client.post('/api/chat/user123_sess456')

        # Flask returns 415 when Content-Type isn't application/json
        assert response.status_code == 415

    def test_chat_endpoint_400_for_empty_message(self, client):
        """Test POST /api/chat returns 400 for empty message string."""
        test_client, mocks = client

        mocks['execution_tracker'].get_status.return_value = {
            'execution_id': 'user123_sess456',
            'status': 'running'
        }

        response = test_client.post('/api/chat/user123_sess456', json={
            'message': ''
        })

        assert response.status_code == 400
        assert 'Message is required' in response.get_json()['error']

    def test_chat_endpoint_400_for_whitespace_message(self, client):
        """Test POST /api/chat returns 400 for whitespace-only message."""
        test_client, mocks = client

        mocks['execution_tracker'].get_status.return_value = {
            'execution_id': 'user123_sess456',
            'status': 'running'
        }

        response = test_client.post('/api/chat/user123_sess456', json={
            'message': '   '
        })

        assert response.status_code == 400
        assert 'Message is required' in response.get_json()['error']

    def test_chat_endpoint_500_for_send_failure(self, client):
        """Test POST /api/chat returns 500 if send_instruction fails."""
        test_client, mocks = client

        mocks['execution_tracker'].get_status.return_value = {
            'execution_id': 'user123_sess456',
            'status': 'running'
        }
        mocks['tmux_helper'].send_instruction.return_value = False

        response = test_client.post('/api/chat/user123_sess456', json={
            'message': 'Hello'
        })

        assert response.status_code == 500
        assert 'Failed to send' in response.get_json()['error']


class TestRedeployEndpoint:
    """Tests for POST /api/redeploy/<execution_id>"""

    def test_redeploy_endpoint_resets_to_step_6(self, client):
        """Test POST /api/redeploy resets execution to deploy step."""
        test_client, mocks = client

        mocks['execution_tracker'].get_status.return_value = {
            'execution_id': 'user123_sess456',
            'status': 'completed'
        }

        response = test_client.post('/api/redeploy/user123_sess456')

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'redeploying'

        # Verify status was reset to running at step 6
        mocks['execution_tracker'].update_step.assert_called_with(
            'user123_sess456', 6, 'deploy', 'running'
        )

    def test_redeploy_endpoint_404_for_missing_execution(self, client):
        """Test POST /api/redeploy returns 404 for missing execution."""
        test_client, mocks = client

        mocks['execution_tracker'].get_status.return_value = None

        response = test_client.post('/api/redeploy/nonexistent_exec')

        assert response.status_code == 404


class TestChatHistoryEndpoint:
    """Tests for GET /api/chat/<execution_id>/history"""

    def test_chat_history_returns_tmux_output(self, client):
        """Test GET /api/chat/<id>/history returns tmux pane output."""
        test_client, mocks = client

        mocks['execution_tracker'].get_status.return_value = {
            'execution_id': 'user123_sess456',
            'status': 'running'
        }
        mocks['tmux_helper'].capture_pane_output.return_value = "Claude: Hello!\nUser: Hi there"

        response = test_client.get('/api/chat/user123_sess456/history')

        assert response.status_code == 200
        data = response.get_json()
        assert 'output' in data
        assert 'Claude: Hello!' in data['output']

    def test_chat_history_404_for_missing_execution(self, client):
        """Test GET /api/chat/<id>/history returns 404 for missing execution."""
        test_client, mocks = client

        mocks['execution_tracker'].get_status.return_value = None

        response = test_client.get('/api/chat/nonexistent_exec/history')

        assert response.status_code == 404
