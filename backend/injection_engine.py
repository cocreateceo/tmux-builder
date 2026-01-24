"""Injection Engine - copies agents and skills from master library to user sessions.

This module handles copying agent and skill files based on host_provider and site_type
configuration rules.
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional


class InjectionEngine:
    """Engine for injecting agents and skills into user sessions based on rules."""

    def __init__(self, rules_path: Optional[str] = None, library_dir: Optional[str] = None):
        """Initialize the injection engine.

        Args:
            rules_path: Path to injection_rules.json. Defaults to backend/injection_rules.json.
            library_dir: Path to master library (.claude/ directory). Defaults to project root .claude/.
        """
        if rules_path is None:
            rules_path = str(Path(__file__).parent / "injection_rules.json")
        if library_dir is None:
            library_dir = str(Path(__file__).parent.parent / ".claude")

        self.rules_path = Path(rules_path)
        self.library_dir = Path(library_dir)
        self._rules = None

    def _load_rules(self) -> Dict:
        """Load rules from JSON file."""
        if self._rules is None:
            if self.rules_path.exists():
                with open(self.rules_path) as f:
                    self._rules = json.load(f)
            else:
                self._rules = {"rules": []}
        return self._rules

    def match_rule(self, host_provider: str, site_type: str) -> Dict[str, List[str]]:
        """Find matching rule for given host_provider and site_type.

        Args:
            host_provider: Cloud provider (aws, azure, etc.)
            site_type: Site type (static, dynamic)

        Returns:
            Dict with 'agents' and 'skills' lists. Empty lists if no match found.
        """
        rules = self._load_rules()

        for rule in rules.get("rules", []):
            match_criteria = rule.get("match", {})
            if (match_criteria.get("host_provider") == host_provider and
                match_criteria.get("site_type") == site_type):
                inject_config = rule.get("inject", {})
                return {
                    "agents": inject_config.get("agents", []),
                    "skills": inject_config.get("skills", [])
                }

        return {"agents": [], "skills": []}

    def _copy_files(self, patterns: List[str], source_subdir: str, dest_base: Path) -> int:
        """Copy files matching patterns from source to destination.

        Args:
            patterns: List of patterns like "deployers/aws-s3" or "testers/*"
            source_subdir: Subdirectory in library (agents or skills)
            dest_base: Base destination path (.claude in session dir)

        Returns:
            Number of files copied.
        """
        copied_count = 0
        source_base = self.library_dir / source_subdir

        for pattern in patterns:
            if pattern.endswith("/*"):
                # Wildcard pattern - copy all .md files in directory
                dir_name = pattern[:-2]  # Remove "/*"
                source_dir = source_base / dir_name
                dest_dir = dest_base / source_subdir / dir_name

                if source_dir.exists() and source_dir.is_dir():
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    for md_file in source_dir.glob("*.md"):
                        shutil.copy2(md_file, dest_dir / md_file.name)
                        copied_count += 1
            else:
                # Specific file pattern - copy single file
                source_file = source_base / f"{pattern}.md"
                if source_file.exists():
                    dest_dir = dest_base / source_subdir / pattern.rsplit("/", 1)[0] if "/" in pattern else dest_base / source_subdir
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest_file = dest_dir / f"{pattern.rsplit('/', 1)[-1]}.md"
                    shutil.copy2(source_file, dest_file)
                    copied_count += 1

        return copied_count

    def _inject_core_skills(self, claude_dir: Path) -> int:
        """Always inject core methodology skills to every session.

        Core skills are MANDATORY for all sessions:
        - core/project-inception - Project startup methodology
        - core/plan-validation - Plan verification before execution
        - core/integration-verification - E2E verification before completion

        Args:
            claude_dir: Path to session's .claude directory

        Returns:
            Number of core skills copied.
        """
        core_skills = [
            "core/project-inception",
            "core/plan-validation",
            "core/integration-verification"
        ]
        return self._copy_files(core_skills, "skills", claude_dir)

    def inject(self, host_provider: str, site_type: str, session_dir: str) -> Dict[str, int]:
        """Inject agents and skills into session directory based on matching rule.

        Always injects:
        1. Core methodology skills (project-inception, plan-validation, integration-verification)
        2. Provider/type-specific agents and skills from injection_rules.json

        Args:
            host_provider: Cloud provider (aws, azure, etc.)
            site_type: Site type (static, dynamic)
            session_dir: Path to session directory

        Returns:
            Dict with 'agents_copied', 'skills_copied', and 'core_skills_copied' counts.
        """
        rule = self.match_rule(host_provider, site_type)
        session_path = Path(session_dir)
        claude_dir = session_path / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)

        # Always inject core methodology skills first
        core_skills_copied = self._inject_core_skills(claude_dir)

        # Inject provider/type-specific agents and skills
        agents_copied = self._copy_files(rule["agents"], "agents", claude_dir)
        skills_copied = self._copy_files(rule["skills"], "skills", claude_dir)

        return {
            "agents_copied": agents_copied,
            "skills_copied": skills_copied,
            "core_skills_copied": core_skills_copied
        }
