import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_loader import AgentLoader, AgentTemplate


class TestAgentLoader:
    """Test agent template loading."""

    def test_load_default_template(self, tmp_path):
        """Verify default template loads correctly."""
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        template_content = """# Default Agent
You are a helpful assistant.

## Instructions
Follow user requests carefully.
"""
        (agents_dir / "default.md").write_text(template_content)

        loader = AgentLoader(agents_dir)
        template = loader.load("default")

        assert template.name == "default"
        assert "helpful assistant" in template.content
        assert template.exists == True

    def test_template_not_found(self, tmp_path):
        """Verify missing template returns empty with exists=False."""
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        loader = AgentLoader(agents_dir)
        template = loader.load("nonexistent")

        assert template.exists == False
        assert template.content == ""

    def test_list_available_agents(self, tmp_path):
        """Verify listing available agent templates."""
        agents_dir = tmp_path / ".claude" / "agents"
        agents_dir.mkdir(parents=True)

        (agents_dir / "analyzer.md").write_text("# Analyzer")
        (agents_dir / "coder.md").write_text("# Coder")
        (agents_dir / "not_an_agent.txt").write_text("ignore")

        loader = AgentLoader(agents_dir)
        agents = loader.list_agents()

        assert "analyzer" in agents
        assert "coder" in agents
        assert "not_an_agent" not in agents
