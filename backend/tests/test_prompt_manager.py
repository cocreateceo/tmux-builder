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

def test_autonomous_agent_prompt_contains_key_sections(prompt_manager):
    """Test that autonomous agent prompt has all required sections."""
    variables = {
        'guid': 'abc123',
        'email': 'user@example.com',
        'phone': '+15551234567',
        'user_request': 'Build a React todo app with API backend',
        'session_path': '/path/to/session',
        'aws_profile': 'sunware'
    }

    result = prompt_manager.render_system_prompt('autonomous_agent', variables)

    # Check for key sections
    assert 'Phase 1' in result or 'PHASE 1' in result
    assert 'Phase 2' in result or 'PHASE 2' in result
    assert 'Phase 3' in result or 'PHASE 3' in result
    assert 'Phase 4' in result or 'PHASE 4' in result

    # Check for parallel execution strategy
    assert 'PARALLEL EXECUTION STRATEGY' in result
    assert 'Dependency Analysis' in result
    assert 'Batch' in result

    # Check for skills mentioned
    assert 'brainstorm' in result.lower() or '/brainstorm' in result
    assert 'writing-plans' in result or '/writing-plans' in result
    assert 'test-driven-development' in result or 'TDD' in result

    # Check for AWS profile
    assert 'sunware' in result

    # Check for user request
    assert 'React todo app' in result
