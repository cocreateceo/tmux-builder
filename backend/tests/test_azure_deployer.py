"""Tests for AzureStaticDeployer - Azure Blob Storage + CDN deployment for static websites."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock Azure SDK modules before importing azure_deployer
mock_identity = MagicMock()
mock_storage_management = MagicMock()
mock_cdn_management = MagicMock()
mock_blob_service = MagicMock()

sys.modules["azure.identity"] = mock_identity
sys.modules["azure.mgmt.storage"] = mock_storage_management
sys.modules["azure.mgmt.cdn"] = mock_cdn_management
sys.modules["azure.storage.blob"] = mock_blob_service

from cloud_config import CloudConfig
from azure_deployer import AzureStaticDeployer


class TestAzureStaticDeployer:
    """Test Azure static deployer with mocked Azure SDK interactions."""

    # Sample test data
    SAMPLE_USER_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    SAMPLE_SESSION_ID = "session_001_build"
    SAMPLE_SUBSCRIPTION_ID = "12345678-1234-1234-1234-123456789012"

    def setup_method(self):
        """Reset mock state before each test."""
        mock_identity.reset_mock()
        mock_storage_management.reset_mock()
        mock_cdn_management.reset_mock()
        mock_blob_service.reset_mock()

    def test_deployer_uses_sunwaretech_profile(self):
        """Deployer uses the 'sunwaretech' Azure profile from CloudConfig."""
        deployer = AzureStaticDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        # Verify profile matches CloudConfig.AZURE_PROFILE
        assert deployer.profile == "sunwaretech"
        assert deployer.profile == CloudConfig.AZURE_PROFILE

    def test_storage_account_name_valid(self):
        """Storage account name is <=24 chars, no hyphens, lowercase, alphanumeric."""
        deployer = AzureStaticDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        storage_name = deployer.storage_account_name

        # Must be <= 24 characters
        assert len(storage_name) <= 24, f"Storage account name '{storage_name}' exceeds 24 chars"

        # Must have no hyphens
        assert "-" not in storage_name, f"Storage account name '{storage_name}' contains hyphens"

        # Must be lowercase
        assert storage_name == storage_name.lower(), f"Storage account name '{storage_name}' is not lowercase"

        # Must be alphanumeric only
        assert storage_name.isalnum(), f"Storage account name '{storage_name}' is not alphanumeric"

        # Should use CloudConfig naming convention
        expected_name = CloudConfig.get_resource_name(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            resource_type="azure_storage"
        )
        assert storage_name == expected_name

    def test_tags_include_required_fields(self):
        """All required CloudConfig tags are present."""
        deployer = AzureStaticDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        tags = deployer.tags

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
        assert tags["UserGUID"] == self.SAMPLE_USER_ID
        assert tags["SessionID"] == self.SAMPLE_SESSION_ID
        assert tags["SiteType"] == "static"
        assert tags["CreatedBy"] == "tmux-builder-automation"
        assert tags["CostCenter"] == "user-sites"

    def test_resource_group_name_format(self):
        """Resource group name follows naming convention with '-rg' suffix."""
        deployer = AzureStaticDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        rg_name = deployer.resource_group_name

        # Should start with 'tmux-'
        assert rg_name.startswith("tmux-"), f"Resource group name '{rg_name}' does not start with 'tmux-'"

        # Should end with '-rg'
        assert rg_name.endswith("-rg"), f"Resource group name '{rg_name}' does not end with '-rg'"

        # Should contain first 8 chars of GUID
        guid_prefix = self.SAMPLE_USER_ID.split("-")[0]  # 'a1b2c3d4'
        assert guid_prefix in rg_name, f"Resource group name '{rg_name}' does not contain GUID prefix '{guid_prefix}'"

        # Should contain session_id (with underscores removed)
        session_short = self.SAMPLE_SESSION_ID.replace("_", "")  # 'session001build'
        assert session_short in rg_name, f"Resource group name '{rg_name}' does not contain session short '{session_short}'"

        # Full pattern check: tmux-{guid_prefix}-{session_short}-rg
        expected_pattern = f"tmux-{guid_prefix}-{session_short}-rg"
        assert rg_name == expected_pattern, f"Resource group name '{rg_name}' does not match expected pattern '{expected_pattern}'"
