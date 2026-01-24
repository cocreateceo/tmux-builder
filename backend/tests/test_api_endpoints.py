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

    return {
        "user_manager": user_manager,
        "session_creator": session_creator,
        "execution_tracker": execution_tracker,
        "injection_engine": injection_engine
    }


@pytest.fixture
def client(mock_managers):
    """Create Flask test client with mocked managers."""
    with patch.dict('sys.modules', {
        'user_manager': MagicMock(),
        'session_creator': MagicMock(),
        'execution_tracker': MagicMock(),
        'injection_engine': MagicMock()
    }):
        from app import app, init_managers

        # Replace managers with mocks
        init_managers(
            mock_managers["user_manager"],
            mock_managers["session_creator"],
            mock_managers["execution_tracker"],
            mock_managers["injection_engine"]
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
