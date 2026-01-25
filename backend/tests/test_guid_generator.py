import pytest
from guid_generator import generate_guid

def test_guid_generation_is_deterministic():
    """Test that same email+phone always generates same GUID."""
    email = "test@example.com"
    phone = "+15551234567"

    guid1 = generate_guid(email, phone)
    guid2 = generate_guid(email, phone)

    assert guid1 == guid2

def test_guid_generation_different_inputs():
    """Test that different inputs generate different GUIDs."""
    guid1 = generate_guid("user1@example.com", "+15551111111")
    guid2 = generate_guid("user2@example.com", "+15552222222")

    assert guid1 != guid2

def test_guid_format():
    """Test GUID format (should be hex string)."""
    guid = generate_guid("test@example.com", "+15551234567")

    assert isinstance(guid, str)
    assert len(guid) == 64  # SHA256 produces 64 hex characters
    assert all(c in '0123456789abcdef' for c in guid)

def test_guid_case_insensitive_email():
    """Test that email case doesn't affect GUID."""
    guid1 = generate_guid("Test@Example.COM", "+15551234567")
    guid2 = generate_guid("test@example.com", "+15551234567")

    assert guid1 == guid2
