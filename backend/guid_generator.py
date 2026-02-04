"""Generates deterministic GUIDs from user email and phone."""

import hashlib
import logging
import re

logger = logging.getLogger(__name__)

# Valid GUID pattern: 64 hexadecimal characters
GUID_PATTERN = re.compile(r'^[a-f0-9]{64}$')


def is_valid_guid(guid: str) -> bool:
    """
    Validate GUID format to prevent path traversal attacks.

    Args:
        guid: String to validate

    Returns:
        True if valid 64-character hex string, False otherwise
    """
    if not guid or not isinstance(guid, str):
        return False
    return bool(GUID_PATTERN.match(guid))


def generate_guid(email: str, phone: str) -> str:
    """
    Generate deterministic GUID from email and phone.

    Uses SHA256 hash of normalized email:phone string.
    Same email+phone always produces same GUID.

    Args:
        email: User email address
        phone: User phone number

    Returns:
        64-character hexadecimal GUID string
    """
    # Normalize inputs
    email_normalized = email.lower().strip()
    phone_normalized = phone.strip()

    # Create combined string
    combined = f"{email_normalized}:{phone_normalized}"

    # Generate SHA256 hash
    guid = hashlib.sha256(combined.encode('utf-8')).hexdigest()

    logger.debug(f"Generated GUID for {email_normalized}: {guid[:16]}...")

    return guid
