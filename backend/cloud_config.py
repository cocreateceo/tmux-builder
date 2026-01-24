"""Cloud configuration for multi-user resource naming and tagging.

Provides resource naming conventions with truncation for AWS and Azure,
mandatory tags for cost tracking, and cloud profile configuration.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import re


class CloudConfig:
    """Cloud configuration for resource naming, tagging, and profile management."""

    # Cloud profile configuration
    AWS_PROFILE = "sunwaretech"
    AZURE_PROFILE = "sunwaretech"
    AWS_DEFAULT_REGION = "us-east-1"
    AZURE_DEFAULT_LOCATION = "eastus"

    # Resource name length limits by type
    LIMITS = {
        "s3": 63,
        "cloudfront": 128,
        "ec2": 255,
        "azure_storage": 24,
        "azure_cdn": 50,
        "azure_vm": 64,
        "default": 63
    }

    @classmethod
    def get_resource_name(
        cls,
        user_id: str,
        session_id: str,
        resource_type: str = "default",
        suffix: Optional[str] = None
    ) -> str:
        """Generate a resource name following the naming convention.

        Pattern: tmux-{guid_prefix}-{session_short}[-suffix]
        - guid_prefix: first 8 chars of GUID (before first hyphen)
        - session_short: session_id with underscores removed
        - Truncated based on resource_type limits

        For azure_storage: removes hyphens, lowercase only, alphanumeric.

        Args:
            user_id: User GUID (e.g., 'a1b2c3d4-e5f6-7890-abcd-ef1234567890')
            session_id: Session identifier (e.g., 'session_001_build')
            resource_type: Type of resource (s3, azure_storage, etc.)
            suffix: Optional suffix to append

        Returns:
            Formatted resource name, truncated to appropriate limit.
        """
        # Extract first 8 chars of GUID (before first hyphen)
        guid_prefix = user_id.split("-")[0][:8]

        # Remove underscores from session_id
        session_short = session_id.replace("_", "")

        # Build base name
        if suffix:
            name = f"tmux-{guid_prefix}-{session_short}-{suffix}"
        else:
            name = f"tmux-{guid_prefix}-{session_short}"

        # Get limit for resource type
        limit = cls.LIMITS.get(resource_type, cls.LIMITS["default"])

        # Special handling for azure_storage: no hyphens, alphanumeric only
        if resource_type == "azure_storage":
            # Remove hyphens and make lowercase
            name = name.replace("-", "").lower()
            # Keep only alphanumeric characters
            name = re.sub(r'[^a-z0-9]', '', name)
            # Truncate to limit
            name = name[:limit]
        else:
            # Lowercase and truncate
            name = name.lower()[:limit]

        return name

    @classmethod
    def get_tags(
        cls,
        user_id: str,
        session_id: str,
        site_type: str,
        environment: str = "production",
        extra_tags: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Generate mandatory tags for cost tracking and resource management.

        Args:
            user_id: User GUID
            session_id: Session identifier
            site_type: Type of site (static, dynamic, etc.)
            environment: Deployment environment (default: 'production')
            extra_tags: Additional tags to merge

        Returns:
            Dictionary with all mandatory tags plus any extra tags.
        """
        # Generate ISO timestamp
        created_at = datetime.now(timezone.utc).isoformat()

        tags = {
            "Project": "tmux-builder",
            "Environment": environment,
            "UserGUID": user_id,
            "SessionID": session_id,
            "ExecutionID": f"{user_id}_{session_id}",
            "SiteType": site_type,
            "CreatedAt": created_at,
            "CreatedBy": "tmux-builder-automation",
            "CostCenter": "user-sites"
        }

        # Merge extra tags if provided
        if extra_tags:
            tags.update(extra_tags)

        return tags

    @classmethod
    def get_aws_tags_list(cls, tags: Dict[str, str]) -> List[Dict[str, str]]:
        """Convert tags dict to AWS format.

        AWS uses [{"Key": k, "Value": v}, ...] format.

        Args:
            tags: Dictionary of tag key-value pairs

        Returns:
            List of dicts with 'Key' and 'Value' keys.
        """
        return [{"Key": k, "Value": str(v)} for k, v in tags.items()]

    @classmethod
    def get_azure_tags(cls, tags: Dict[str, Any]) -> Dict[str, str]:
        """Convert tags dict to Azure format.

        Azure uses a flat dict with string values.

        Args:
            tags: Dictionary of tag key-value pairs

        Returns:
            Dictionary with all values converted to strings.
        """
        return {k: str(v) for k, v in tags.items()}
