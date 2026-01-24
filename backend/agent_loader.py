"""
Agent Template Loader

Loads agent templates from .claude/agents/*.md files.
These templates provide specialized instructions for different job types.
"""

import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# Default agents directory relative to project root
DEFAULT_AGENTS_DIR = Path(__file__).parent.parent / ".claude" / "agents"


@dataclass
class AgentTemplate:
    """Loaded agent template."""
    name: str
    content: str
    path: Optional[Path]
    exists: bool


class AgentLoader:
    """
    Loads agent templates from .claude/agents/ directory.

    Agent templates are Markdown files that provide specialized
    instructions for different types of jobs (cost analysis,
    code generation, etc.)

    Usage:
        loader = AgentLoader()
        template = loader.load("cost-analyzer")
        prompt = f"{template.content}\\n\\n## Task:\\n{user_task}"
    """

    def __init__(self, agents_dir: Optional[Path] = None):
        self.agents_dir = agents_dir or DEFAULT_AGENTS_DIR

    def load(self, agent_name: str) -> AgentTemplate:
        """
        Load an agent template by name.

        Args:
            agent_name: Name of agent (without .md extension)

        Returns:
            AgentTemplate with content or empty if not found
        """
        agent_file = self.agents_dir / f"{agent_name}.md"

        if not agent_file.exists():
            logger.warning(f"Agent template not found: {agent_file}")
            return AgentTemplate(
                name=agent_name,
                content="",
                path=None,
                exists=False
            )

        try:
            content = agent_file.read_text(encoding='utf-8')
            logger.info(f"Loaded agent template: {agent_name}")

            return AgentTemplate(
                name=agent_name,
                content=content,
                path=agent_file,
                exists=True
            )

        except Exception as e:
            logger.error(f"Error loading agent {agent_name}: {e}")
            return AgentTemplate(
                name=agent_name,
                content="",
                path=agent_file,
                exists=False
            )

    def list_agents(self) -> List[str]:
        """
        List all available agent templates.

        Returns:
            List of agent names (without .md extension)
        """
        if not self.agents_dir.exists():
            return []

        agents = []
        for file in self.agents_dir.glob("*.md"):
            agents.append(file.stem)

        return sorted(agents)

    def get_or_default(self, agent_name: str) -> AgentTemplate:
        """
        Load agent template, falling back to default if not found.

        Args:
            agent_name: Name of desired agent

        Returns:
            AgentTemplate (requested or default)
        """
        template = self.load(agent_name)

        if template.exists:
            return template

        # Try default
        default = self.load("default")
        if default.exists:
            logger.info(f"Using default agent (requested: {agent_name})")
            return default

        # No default either
        logger.warning("No default agent template found")
        return template
