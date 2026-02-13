"""Manages prompt templates and variable substitution."""

import yaml
from pathlib import Path
from string import Template
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class PromptManager:
    """Manages loading and rendering of prompt templates."""

    def __init__(self, config_path: str = None):
        """
        Initialize PromptManager.

        Args:
            config_path: Path to prompt_config.yaml (default: templates/prompt_config.yaml)
        """
        if config_path is None:
            base_path = Path(__file__).parent
            config_path = base_path / "templates" / "prompt_config.yaml"

        self.config_path = Path(config_path)
        self.base_path = self.config_path.parent.parent
        self.config = self._load_config()

        logger.info(f"PromptManager initialized with config: {self.config_path}")

    def _load_config(self) -> Dict[str, Any]:
        """Load prompt configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded prompt config version {config.get('version')}")
            return config
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config: {e}")
            raise

    def load_template(self, template_file: str) -> str:
        """
        Load template content from file.

        Args:
            template_file: Relative path to template file

        Returns:
            Template content as string
        """
        template_path = self.base_path / template_file

        try:
            with open(template_path, 'r') as f:
                content = f.read()
            logger.debug(f"Loaded template: {template_path}")
            return content
        except FileNotFoundError:
            logger.error(f"Template file not found: {template_path}")
            raise

    def render_system_prompt(self, prompt_type: str, variables: Dict[str, Any]) -> str:
        """
        Render system prompt with variable substitution.

        Args:
            prompt_type: Type of prompt (from config: autonomous_agent, refinement_mode, etc)
            variables: Dictionary of variables to substitute

        Returns:
            Rendered prompt string

        Raises:
            KeyError: If required variables are missing
            ValueError: If prompt_type is not found in config
        """
        if prompt_type not in self.config['system_prompts']:
            available = list(self.config['system_prompts'].keys())
            raise ValueError(f"Unknown prompt type '{prompt_type}'. Available: {available}")

        prompt_config = self.config['system_prompts'][prompt_type]

        # Check for required variables
        required_vars = prompt_config.get('variables_required', [])
        missing_vars = [var for var in required_vars if var not in variables]
        if missing_vars:
            raise KeyError(f"Missing required variables for '{prompt_type}': {missing_vars}")

        # Merge global variables with provided variables (provided takes precedence)
        merged_vars = {**self.config.get('variables', {}), **variables}

        # Load and render template
        template_content = self.load_template(prompt_config['template_file'])
        template = Template(template_content)

        try:
            rendered = template.safe_substitute(merged_vars)
            logger.info(f"Rendered prompt type '{prompt_type}' with {len(merged_vars)} variables")
            return rendered
        except Exception as e:
            logger.error(f"Error rendering template '{prompt_type}': {e}")
            raise

    def get_available_prompts(self) -> List[str]:
        """
        Get list of available prompt types.

        Returns:
            List of prompt type names
        """
        return list(self.config['system_prompts'].keys())

    def get_prompt_info(self, prompt_type: str) -> Dict[str, Any]:
        """
        Get information about a specific prompt type.

        Args:
            prompt_type: Type of prompt

        Returns:
            Dictionary with prompt configuration
        """
        if prompt_type not in self.config['system_prompts']:
            raise ValueError(f"Unknown prompt type: {prompt_type}")

        return self.config['system_prompts'][prompt_type]
