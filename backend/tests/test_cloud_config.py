"""Tests for CloudConfig - resource naming conventions and tagging for AWS/Azure."""

import pytest
import re
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from cloud_config import CloudConfig


class TestCloudConfig:
    """Test cloud configuration for multi-user resource management."""

    # Sample test data
    SAMPLE_USER_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    SAMPLE_SESSION_ID = "session_001_build"

    def test_resource_name_format(self):
        """Resource names follow tmux-{guid_prefix}-{session_short} pattern."""
        name = CloudConfig.get_resource_name(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID
        )

        # Should start with 'tmux-'
        assert name.startswith("tmux-")

        # Should contain first 8 chars of GUID (before first hyphen)
        guid_prefix = self.SAMPLE_USER_ID.split("-")[0]  # 'a1b2c3d4'
        assert guid_prefix in name

        # Session ID should have underscores removed
        session_short = self.SAMPLE_SESSION_ID.replace("_", "")  # 'session001build'
        assert session_short in name

        # Full pattern check: tmux-{guid_prefix}-{session_short}
        expected_pattern = f"tmux-{guid_prefix}-{session_short}"
        assert name == expected_pattern

    def test_resource_name_truncation_s3(self):
        """S3 bucket names are truncated to <=63 chars and lowercase."""
        # Use a very long session ID to test truncation
        long_session = "very_long_session_name_that_exceeds_normal_limits_significantly"

        name = CloudConfig.get_resource_name(
            user_id=self.SAMPLE_USER_ID,
            session_id=long_session,
            resource_type="s3"
        )

        # Must be <= 63 characters
        assert len(name) <= 63

        # Must be lowercase
        assert name == name.lower()

        # Must still start with tmux-
        assert name.startswith("tmux-")

    def test_resource_name_truncation_azure_storage(self):
        """Azure storage names are <=24 chars, no hyphens, alphanumeric only."""
        name = CloudConfig.get_resource_name(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            resource_type="azure_storage"
        )

        # Must be <= 24 characters
        assert len(name) <= 24

        # Must have no hyphens
        assert "-" not in name

        # Must be alphanumeric only (lowercase)
        assert name.isalnum()
        assert name == name.lower()

    def test_get_tags_includes_required_fields(self):
        """All 9 mandatory tags are present in the returned dict."""
        tags = CloudConfig.get_tags(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            site_type="static"
        )

        # Check all 9 required fields
        required_fields = [
            "Project",
            "Environment",
            "UserGUID",
            "SessionID",
            "ExecutionID",
            "SiteType",
            "CreatedAt",
            "CreatedBy",
            "CostCenter"
        ]

        for field in required_fields:
            assert field in tags, f"Missing required tag: {field}"

        # Validate specific values
        assert tags["Project"] == "tmux-builder"
        assert tags["Environment"] == "production"  # default
        assert tags["UserGUID"] == self.SAMPLE_USER_ID
        assert tags["SessionID"] == self.SAMPLE_SESSION_ID
        assert tags["ExecutionID"] == f"{self.SAMPLE_USER_ID}_{self.SAMPLE_SESSION_ID}"
        assert tags["SiteType"] == "static"
        assert tags["CreatedBy"] == "tmux-builder-automation"
        assert tags["CostCenter"] == "user-sites"

        # CreatedAt should be ISO format timestamp
        created_at = tags["CreatedAt"]
        # Validate it can be parsed as ISO format
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))

    def test_aws_profile_is_sunwaretech(self):
        """AWS_PROFILE class attribute is set to 'sunwaretech'."""
        assert CloudConfig.AWS_PROFILE == "sunwaretech"

    def test_azure_profile_is_sunwaretech(self):
        """AZURE_PROFILE class attribute is set to 'sunwaretech'."""
        assert CloudConfig.AZURE_PROFILE == "sunwaretech"
