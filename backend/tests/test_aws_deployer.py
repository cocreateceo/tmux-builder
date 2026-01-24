"""Tests for AWSStaticDeployer - S3 + CloudFront deployment for static websites."""

import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path
import sys
import os
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock boto3 before importing aws_deployer
mock_boto3 = MagicMock()
sys.modules["boto3"] = mock_boto3

from cloud_config import CloudConfig
from aws_deployer import AWSStaticDeployer


class TestAWSStaticDeployer:
    """Test AWS static deployer with mocked boto3 interactions."""

    # Sample test data
    SAMPLE_USER_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    SAMPLE_SESSION_ID = "session_001_build"

    def setup_method(self):
        """Reset mock state before each test."""
        mock_boto3.reset_mock()

    def test_deployer_uses_sunwaretech_profile(self):
        """Deployer uses the 'sunwaretech' AWS profile from CloudConfig."""
        # Set up mock session
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = MagicMock()

        deployer = AWSStaticDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID
        )

        # Access the s3_client to trigger lazy initialization
        _ = deployer.s3_client

        # Verify Session was created with sunwaretech profile
        mock_boto3.Session.assert_called_with(profile_name="sunwaretech")
        assert deployer.profile == "sunwaretech"

    def test_bucket_name_generated_correctly(self):
        """Bucket name uses CloudConfig naming and is <= 63 characters."""
        deployer = AWSStaticDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID
        )

        # Bucket name should follow CloudConfig naming convention
        expected_name = CloudConfig.get_resource_name(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            resource_type="s3"
        )

        assert deployer.bucket_name == expected_name
        assert len(deployer.bucket_name) <= 63
        assert deployer.bucket_name.startswith("tmux-")

    def test_deploy_creates_bucket_with_tags(self):
        """Deploy creates S3 bucket with required CloudConfig tags."""
        # Set up mock session and clients
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_s3_client = MagicMock()
        mock_cf_client = MagicMock()
        mock_sts_client = MagicMock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}

        def client_factory(service_name):
            if service_name == "s3":
                return mock_s3_client
            elif service_name == "cloudfront":
                return mock_cf_client
            elif service_name == "sts":
                return mock_sts_client
            return MagicMock()

        mock_session.client.side_effect = client_factory

        # Mock CloudFront distribution creation response
        mock_cf_client.create_distribution.return_value = {
            "Distribution": {
                "Id": "E1234567890ABC",
                "DomainName": "d1234567890.cloudfront.net"
            }
        }

        deployer = AWSStaticDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID
        )

        # Create a temporary source directory with a test file
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "index.html"
            test_file.write_text("<html><body>Test</body></html>")

            # Deploy
            result = deployer.deploy(temp_dir)

        # Verify bucket was created
        mock_s3_client.create_bucket.assert_called_once()

        # Verify tags were applied to the bucket
        mock_s3_client.put_bucket_tagging.assert_called_once()
        tagging_call = mock_s3_client.put_bucket_tagging.call_args

        # Extract tags from the call
        tag_set = tagging_call[1]["Tagging"]["TagSet"]
        tag_dict = {t["Key"]: t["Value"] for t in tag_set}

        # Verify required tags
        assert tag_dict["Project"] == "tmux-builder"
        assert tag_dict["UserGUID"] == self.SAMPLE_USER_ID
        assert tag_dict["SessionID"] == self.SAMPLE_SESSION_ID
        assert tag_dict["SiteType"] == "static"
        assert "CreatedAt" in tag_dict

    def test_deploy_uploads_files(self):
        """Deploy uploads all source files to S3 bucket."""
        # Set up mock session and clients
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_s3_client = MagicMock()
        mock_cf_client = MagicMock()
        mock_sts_client = MagicMock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}

        def client_factory(service_name):
            if service_name == "s3":
                return mock_s3_client
            elif service_name == "cloudfront":
                return mock_cf_client
            elif service_name == "sts":
                return mock_sts_client
            return MagicMock()

        mock_session.client.side_effect = client_factory

        # Mock CloudFront distribution creation response
        mock_cf_client.create_distribution.return_value = {
            "Distribution": {
                "Id": "E1234567890ABC",
                "DomainName": "d1234567890.cloudfront.net"
            }
        }

        deployer = AWSStaticDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID
        )

        # Create a temporary source directory with multiple files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            (Path(temp_dir) / "index.html").write_text("<html>Index</html>")
            (Path(temp_dir) / "style.css").write_text("body { color: red; }")
            (Path(temp_dir) / "script.js").write_text("console.log('test');")

            # Create subdirectory with file
            subdir = Path(temp_dir) / "assets"
            subdir.mkdir()
            (subdir / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")

            # Deploy
            result = deployer.deploy(temp_dir)

        # Verify all files were uploaded
        upload_calls = mock_s3_client.put_object.call_args_list
        uploaded_keys = [call[1]["Key"] for call in upload_calls]

        assert "index.html" in uploaded_keys
        assert "style.css" in uploaded_keys
        assert "script.js" in uploaded_keys
        assert "assets/image.png" in uploaded_keys

    def test_deploy_returns_cloudfront_url(self):
        """Deploy returns CloudFront URL and distribution_id."""
        # Set up mock session and clients
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_s3_client = MagicMock()
        mock_cf_client = MagicMock()
        mock_sts_client = MagicMock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}

        def client_factory(service_name):
            if service_name == "s3":
                return mock_s3_client
            elif service_name == "cloudfront":
                return mock_cf_client
            elif service_name == "sts":
                return mock_sts_client
            return MagicMock()

        mock_session.client.side_effect = client_factory

        # Mock CloudFront distribution creation response
        expected_distribution_id = "E1234567890ABC"
        expected_domain = "d1234567890.cloudfront.net"
        mock_cf_client.create_distribution.return_value = {
            "Distribution": {
                "Id": expected_distribution_id,
                "DomainName": expected_domain
            }
        }

        deployer = AWSStaticDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID
        )

        # Create a temporary source directory with a test file
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "index.html"
            test_file.write_text("<html><body>Test</body></html>")

            # Deploy
            result = deployer.deploy(temp_dir)

        # Verify result contains expected fields
        assert "url" in result
        assert "bucket" in result
        assert "distribution_id" in result
        assert "region" in result

        # Verify CloudFront URL format
        assert result["url"] == f"https://{expected_domain}"
        assert result["distribution_id"] == expected_distribution_id
        assert result["bucket"] == deployer.bucket_name
        assert result["region"] == deployer.region
