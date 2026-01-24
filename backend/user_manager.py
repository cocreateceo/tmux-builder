"""User Manager - handles multi-user GUID generation and registry management."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Default users directory (can be patched in tests)
USERS_DIR = Path(__file__).parent.parent / "users"


class UserManager:
    """Manages user creation, lookup, and registry operations."""

    def __init__(self):
        """Initialize UserManager with users directory."""
        # Import dynamically to support patching in tests
        import user_manager
        self._users_dir = user_manager.USERS_DIR
        self._ensure_users_dir()

    def _ensure_users_dir(self) -> None:
        """Ensure the users directory exists."""
        self._users_dir.mkdir(parents=True, exist_ok=True)

    def _get_registry_path(self) -> Path:
        """Get path to registry.json file."""
        return self._users_dir / "registry.json"

    def _load_registry(self) -> dict:
        """Load registry from file, creating empty one if not exists."""
        registry_path = self._get_registry_path()
        if registry_path.exists():
            return json.loads(registry_path.read_text())
        return {}

    def _save_registry(self, registry: dict) -> None:
        """Save registry to file."""
        registry_path = self._get_registry_path()
        registry_path.write_text(json.dumps(registry, indent=2))

    def _make_registry_key(self, email: str, phone: str) -> str:
        """Create registry key from email and phone."""
        return f"{email.lower()}|{phone}"

    def generate_guid(self, email: str, phone: str) -> str:
        """
        Generate deterministic UUID5 from email+phone combination.

        Args:
            email: User's email address (will be lowercased)
            phone: User's phone number

        Returns:
            Deterministic UUID5 string based on email+phone
        """
        # Combine email (lowercased) and phone for deterministic hashing
        combined = f"{email.lower()}|{phone}"
        # Use URL namespace for UUID5
        return str(uuid.uuid5(uuid.NAMESPACE_URL, combined))

    def create_user(
        self,
        email: str,
        phone: str,
        host_provider: str,
        site_type: str
    ) -> dict:
        """
        Create a new user or return existing user.

        Args:
            email: User's email address
            phone: User's phone number
            host_provider: Cloud provider ('aws' or 'azure')
            site_type: Type of site ('static' or 'dynamic')

        Returns:
            Dict with user_id and is_new flag
        """
        # Check if user already exists
        existing = self.get_user_by_email_phone(email, phone)
        if existing:
            return {"user_id": existing["user_id"], "is_new": False}

        # Generate new GUID
        user_id = self.generate_guid(email, phone)

        # Create user folder structure
        user_path = self._users_dir / user_id
        user_path.mkdir(parents=True, exist_ok=True)
        (user_path / "sessions").mkdir(exist_ok=True)

        # Create user.json
        user_data = {
            "user_id": user_id,
            "email": email,
            "phone": phone,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "host_provider": host_provider,
            "site_type": site_type
        }
        (user_path / "user.json").write_text(json.dumps(user_data, indent=2))

        # Update registry
        registry = self._load_registry()
        registry_key = self._make_registry_key(email, phone)
        registry[registry_key] = user_id
        self._save_registry(registry)

        return {"user_id": user_id, "is_new": True}

    def get_user_by_email_phone(self, email: str, phone: str) -> Optional[dict]:
        """
        Look up existing user by email+phone combination.

        Args:
            email: User's email address
            phone: User's phone number

        Returns:
            User info dict if found, None otherwise
        """
        registry = self._load_registry()
        registry_key = self._make_registry_key(email, phone)

        if registry_key in registry:
            user_id = registry[registry_key]
            return self.get_user_info(user_id)
        return None

    def get_user_info(self, user_id: str) -> Optional[dict]:
        """
        Get user info by GUID.

        Args:
            user_id: User's GUID

        Returns:
            User info dict if found, None otherwise
        """
        user_json_path = self._users_dir / user_id / "user.json"
        if user_json_path.exists():
            return json.loads(user_json_path.read_text())
        return None

    def list_users(self) -> list:
        """
        List all user GUIDs.

        Returns:
            List of user GUID strings
        """
        registry = self._load_registry()
        return list(set(registry.values()))
