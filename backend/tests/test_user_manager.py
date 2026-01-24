"""Tests for UserManager - multi-user GUID generation and registry management."""

import pytest
import json
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from user_manager import UserManager


class TestUserManager:
    """Test user management functionality."""

    def test_generate_guid_is_unique(self, tmp_path):
        """Different email+phone combinations produce different GUIDs."""
        with patch('user_manager.USERS_DIR', tmp_path):
            manager = UserManager()

            guid1 = manager.generate_guid("user1@example.com", "+1234567890")
            guid2 = manager.generate_guid("user2@example.com", "+1234567890")
            guid3 = manager.generate_guid("user1@example.com", "+0987654321")

            # All GUIDs should be different
            assert guid1 != guid2
            assert guid1 != guid3
            assert guid2 != guid3

            # Same inputs should produce same GUID (deterministic)
            guid1_again = manager.generate_guid("user1@example.com", "+1234567890")
            assert guid1 == guid1_again

            # Email case should not matter (lowercased before hashing)
            guid1_upper = manager.generate_guid("USER1@EXAMPLE.COM", "+1234567890")
            assert guid1 == guid1_upper

    def test_create_user_creates_folder_structure(self, tmp_path):
        """Creating a user creates the expected folder structure and files."""
        with patch('user_manager.USERS_DIR', tmp_path):
            manager = UserManager()

            result = manager.create_user(
                email="newuser@example.com",
                phone="+1112223333",
                host_provider="aws",
                site_type="static"
            )

            user_id = result["user_id"]
            user_path = tmp_path / user_id

            # Folder structure should exist
            assert user_path.exists()
            assert (user_path / "sessions").is_dir()
            assert (user_path / "user.json").is_file()

            # user.json should have correct structure
            user_data = json.loads((user_path / "user.json").read_text())
            assert user_data["user_id"] == user_id
            assert user_data["email"] == "newuser@example.com"
            assert user_data["phone"] == "+1112223333"
            assert user_data["host_provider"] == "aws"
            assert user_data["site_type"] == "static"
            assert "created_at" in user_data

    def test_registry_updated_on_create(self, tmp_path):
        """Creating a user updates the registry.json with email+phone mapping."""
        with patch('user_manager.USERS_DIR', tmp_path):
            manager = UserManager()

            result = manager.create_user(
                email="registered@example.com",
                phone="+5556667777",
                host_provider="azure",
                site_type="dynamic"
            )

            user_id = result["user_id"]

            # Registry should exist and contain mapping
            registry_path = tmp_path / "registry.json"
            assert registry_path.is_file()

            registry = json.loads(registry_path.read_text())
            registry_key = "registered@example.com|+5556667777"
            assert registry_key in registry
            assert registry[registry_key] == user_id

    def test_existing_user_returns_same_guid(self, tmp_path):
        """Creating a user with existing email+phone returns existing user with is_new=False."""
        with patch('user_manager.USERS_DIR', tmp_path):
            manager = UserManager()

            # First creation
            result1 = manager.create_user(
                email="existing@example.com",
                phone="+9998887777",
                host_provider="aws",
                site_type="static"
            )

            assert result1["is_new"] == True

            # Second creation with same email+phone
            result2 = manager.create_user(
                email="existing@example.com",
                phone="+9998887777",
                host_provider="azure",  # Different provider should be ignored
                site_type="dynamic"     # Different type should be ignored
            )

            assert result2["is_new"] == False
            assert result2["user_id"] == result1["user_id"]

            # Verify no duplicate folders created
            user_folders = [d for d in tmp_path.iterdir() if d.is_dir()]
            assert len(user_folders) == 1
