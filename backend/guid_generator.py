"""Generates deterministic GUIDs from user email and phone."""

import hashlib
import logging

logger = logging.getLogger(__name__)


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
