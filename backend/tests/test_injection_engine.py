"""Tests for InjectionEngine - copies agents/skills to user sessions."""

import pytest
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from injection_engine import InjectionEngine


class TestInjectionEngine:
    """Test injection engine for copying agents and skills to sessions."""

    def test_match_rule_aws_static(self, tmp_path):
        """Verify correct rule matches for AWS static site configuration."""
        # Create rules file
        rules_path = tmp_path / "injection_rules.json"
        rules = {
            "rules": [
                {
                    "match": {"host_provider": "aws", "site_type": "static"},
                    "inject": {
                        "agents": ["deployers/aws-s3-static", "testers/health-check"],
                        "skills": ["aws/s3-upload", "aws/cloudfront-create"]
                    }
                },
                {
                    "match": {"host_provider": "azure", "site_type": "static"},
                    "inject": {
                        "agents": ["deployers/azure-blob"],
                        "skills": ["azure/blob-upload"]
                    }
                }
            ]
        }
        rules_path.write_text(json.dumps(rules))

        # Create library directory
        library_dir = tmp_path / ".claude"
        library_dir.mkdir()

        engine = InjectionEngine(rules_path=str(rules_path), library_dir=str(library_dir))
        result = engine.match_rule("aws", "static")

        assert result["agents"] == ["deployers/aws-s3-static", "testers/health-check"]
        assert result["skills"] == ["aws/s3-upload", "aws/cloudfront-create"]

    def test_inject_copies_files(self, tmp_path):
        """Verify inject method copies agent and skill files to session directory."""
        # Create rules file
        rules_path = tmp_path / "injection_rules.json"
        rules = {
            "rules": [
                {
                    "match": {"host_provider": "aws", "site_type": "static"},
                    "inject": {
                        "agents": ["deployers/aws-s3-static"],
                        "skills": ["aws/s3-upload"]
                    }
                }
            ]
        }
        rules_path.write_text(json.dumps(rules))

        # Create library directory with agent and skill files
        library_dir = tmp_path / ".claude"
        agents_dir = library_dir / "agents" / "deployers"
        skills_dir = library_dir / "skills" / "aws"
        agents_dir.mkdir(parents=True)
        skills_dir.mkdir(parents=True)

        (agents_dir / "aws-s3-static.md").write_text("# AWS S3 Static Deployer Agent")
        (skills_dir / "s3-upload.md").write_text("# S3 Upload Skill")

        # Create session directory
        session_dir = tmp_path / "sessions" / "session-001"
        session_dir.mkdir(parents=True)

        engine = InjectionEngine(rules_path=str(rules_path), library_dir=str(library_dir))
        result = engine.inject("aws", "static", str(session_dir))

        # Verify files were copied
        session_claude_dir = session_dir / ".claude"
        assert (session_claude_dir / "agents" / "deployers" / "aws-s3-static.md").exists()
        assert (session_claude_dir / "skills" / "aws" / "s3-upload.md").exists()
        assert result["agents_copied"] == 1
        assert result["skills_copied"] == 1

    def test_wildcard_matching(self, tmp_path):
        """Verify wildcard patterns copy all matching files in directory."""
        # Create rules file with wildcard pattern
        rules_path = tmp_path / "injection_rules.json"
        rules = {
            "rules": [
                {
                    "match": {"host_provider": "aws", "site_type": "dynamic"},
                    "inject": {
                        "agents": ["testers/*"],
                        "skills": ["testing/*"]
                    }
                }
            ]
        }
        rules_path.write_text(json.dumps(rules))

        # Create library directory with multiple files in wildcard directories
        library_dir = tmp_path / ".claude"
        testers_dir = library_dir / "agents" / "testers"
        testing_dir = library_dir / "skills" / "testing"
        testers_dir.mkdir(parents=True)
        testing_dir.mkdir(parents=True)

        # Create multiple agent files
        (testers_dir / "health-check.md").write_text("# Health Check Agent")
        (testers_dir / "screenshot.md").write_text("# Screenshot Agent")
        (testers_dir / "performance.md").write_text("# Performance Agent")

        # Create multiple skill files
        (testing_dir / "smoke-test.md").write_text("# Smoke Test Skill")
        (testing_dir / "integration-test.md").write_text("# Integration Test Skill")

        # Create session directory
        session_dir = tmp_path / "sessions" / "session-002"
        session_dir.mkdir(parents=True)

        engine = InjectionEngine(rules_path=str(rules_path), library_dir=str(library_dir))
        result = engine.inject("aws", "dynamic", str(session_dir))

        # Verify all files in wildcard directories were copied
        session_claude_dir = session_dir / ".claude"
        assert (session_claude_dir / "agents" / "testers" / "health-check.md").exists()
        assert (session_claude_dir / "agents" / "testers" / "screenshot.md").exists()
        assert (session_claude_dir / "agents" / "testers" / "performance.md").exists()
        assert (session_claude_dir / "skills" / "testing" / "smoke-test.md").exists()
        assert (session_claude_dir / "skills" / "testing" / "integration-test.md").exists()
        assert result["agents_copied"] == 3
        assert result["skills_copied"] == 2
