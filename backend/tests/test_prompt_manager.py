import pytest
from pathlib import Path
from prompt_manager import PromptManager

@pytest.fixture
def prompt_manager():
    """Create PromptManager instance for testing."""
    return PromptManager()

def test_prompt_manager_loads_config(prompt_manager):
    """Test that PromptManager loads prompt_config.yaml."""
    assert prompt_manager.config is not None
    assert 'version' in prompt_manager.config
    assert 'variables' in prompt_manager.config
    assert 'system_prompts' in prompt_manager.config

def test_render_system_prompt_with_variables(prompt_manager):
    """Test rendering system prompt with variable substitution."""
    variables = {
        'guid': 'test_guid_123',
        'email': 'test@example.com',
        'phone': '+15551234567',
        'user_request': 'Build a todo app',
        'session_path': '/tmp/test_session',
        'aws_profile': 'sunware'
    }

    result = prompt_manager.render_system_prompt('autonomous_agent', variables)

    # Should contain substituted values
    assert 'test_guid_123' in result
    assert 'test@example.com' in result
    assert 'Build a todo app' in result
    assert 'sunware' in result

def test_render_fails_with_missing_variables(prompt_manager):
    """Test that rendering fails when required variables are missing."""
    incomplete_variables = {
        'guid': 'test_guid_123',
        'email': 'test@example.com'
        # Missing: phone, user_request, session_path, aws_profile
    }

    with pytest.raises(KeyError):
        prompt_manager.render_system_prompt('autonomous_agent', incomplete_variables)

def test_get_available_prompts(prompt_manager):
    """Test getting list of available prompt templates."""
    prompts = prompt_manager.get_available_prompts()

    assert 'autonomous_agent' in prompts
    assert isinstance(prompts, list)
