import pytest
from pathlib import Path
from session_initializer import SessionInitializer

@pytest.fixture
def initializer():
    """Create SessionInitializer instance."""
    return SessionInitializer()

def test_initializer_creation(initializer):
    """Test SessionInitializer can be created."""
    assert initializer is not None

def test_initialize_session_returns_dict(initializer):
    """Test initialize_session returns properly structured dict."""
    result = initializer.initialize_session(
        guid='test_guid',
        email='test@example.com',
        phone='+15551234567',
        user_request='Build a test app'
    )

    assert isinstance(result, dict)
    assert 'success' in result
    assert 'session_name' in result or 'error' in result

def test_get_session_name_from_guid():
    """Test session name generation from GUID."""
    from session_initializer import SessionInitializer

    guid = 'abc123def456'
    session_name = SessionInitializer.get_session_name(guid)

    assert isinstance(session_name, str)
    assert guid in session_name
    assert 'tmux_builder' in session_name

def test_get_session_path_from_guid():
    """Test session path generation from GUID."""
    from session_initializer import SessionInitializer
    from config import SESSIONS_DIR

    guid = 'abc123def456'
    session_path = SessionInitializer.get_session_path(guid)

    assert isinstance(session_path, Path)
    assert guid in str(session_path)
    assert str(SESSIONS_DIR) in str(session_path)
