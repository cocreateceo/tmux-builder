"""Azure Static Deployer for Blob Storage + CDN static website deployment.

Deploys static websites to Azure Blob Storage with CDN distribution,
using the sunwaretech Azure profile for authentication.
"""

import mimetypes
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from azure.identity import DefaultAzureCredential
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.cdn import CdnManagementClient
from azure.storage.blob import BlobServiceClient, ContentSettings

from cloud_config import CloudConfig


class AzureStaticDeployer:
    """Deploy static websites to Azure Blob Storage with CDN.

    Uses the sunwaretech Azure profile and CloudConfig for resource
    naming and tagging conventions.
    """

    def __init__(
        self,
        user_id: str,
        session_id: str,
        location: Optional[str] = None,
        subscription_id: Optional[str] = None
    ):
        """Initialize the Azure static deployer.

        Args:
            user_id: User GUID for resource naming and tagging
            session_id: Session identifier for resource naming and tagging
            location: Azure location (defaults to CloudConfig.AZURE_DEFAULT_LOCATION)
            subscription_id: Azure subscription ID (required for resource management)
        """
        self.user_id = user_id
        self.session_id = session_id
        self.location = location or CloudConfig.AZURE_DEFAULT_LOCATION
        self.subscription_id = subscription_id
        self.profile = CloudConfig.AZURE_PROFILE

        # Generate resource names using CloudConfig naming conventions
        # Storage account: alphanumeric only, no hyphens, <=24 chars
        self.storage_account_name = CloudConfig.get_resource_name(
            user_id=user_id,
            session_id=session_id,
            resource_type="azure_storage"
        )

        # Extract GUID prefix and session short for other resource names
        guid_prefix = user_id.split("-")[0][:8]
        session_short = session_id.replace("_", "")

        # Resource group: tmux-{guid}-{session}-rg
        self.resource_group_name = f"tmux-{guid_prefix}-{session_short}-rg"

        # CDN profile: tmux-{guid}-{session}-cdn
        self.cdn_profile_name = f"tmux-{guid_prefix}-{session_short}-cdn"

        # CDN endpoint: tmux-{guid}-{session}-ep
        self.cdn_endpoint_name = f"tmux-{guid_prefix}-{session_short}-ep"

        # Generate tags using CloudConfig
        self.tags = CloudConfig.get_tags(
            user_id=user_id,
            session_id=session_id,
            site_type="static"
        )

        # Lazy-loaded clients
        self._credential: Optional[DefaultAzureCredential] = None
        self._storage_client: Optional[StorageManagementClient] = None
        self._cdn_client: Optional[CdnManagementClient] = None
        self._blob_service_client: Optional[BlobServiceClient] = None

    @property
    def credential(self) -> DefaultAzureCredential:
        """Lazy-loaded Azure DefaultAzureCredential."""
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        return self._credential

    @property
    def storage_client(self) -> StorageManagementClient:
        """Lazy-loaded StorageManagementClient with credential authentication."""
        if self._storage_client is None:
            self._storage_client = StorageManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )
        return self._storage_client

    @property
    def cdn_client(self) -> CdnManagementClient:
        """Lazy-loaded CdnManagementClient with credential authentication."""
        if self._cdn_client is None:
            self._cdn_client = CdnManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )
        return self._cdn_client

    def deploy(self, source_dir: str) -> Dict[str, str]:
        """Deploy a static website to Azure Blob Storage with CDN.

        Creates a resource group, storage account with static website hosting,
        uploads all files, and creates a CDN profile and endpoint.

        Args:
            source_dir: Path to directory containing static website files

        Returns:
            Dictionary with deployment details:
            - url: CDN URL for the deployed site
            - storage_url: Direct Blob Storage URL
            - storage_account: Storage account name
            - cdn_endpoint: CDN endpoint name
            - resource_group: Resource group name
        """
        # Create the resource group
        self._create_resource_group()

        # Create the storage account with static website hosting
        storage_url = self._create_storage_account()

        # Upload all files to the $web container
        self._upload_files(source_dir)

        # Create CDN profile and endpoint
        cdn_url = self._create_cdn()

        return {
            "url": cdn_url,
            "storage_url": storage_url,
            "storage_account": self.storage_account_name,
            "cdn_endpoint": self.cdn_endpoint_name,
            "resource_group": self.resource_group_name
        }

    def redeploy(self, source_dir: str) -> Dict[str, str]:
        """Update an existing deployment with new files.

        Re-uploads all files and purges the CDN cache.

        Args:
            source_dir: Path to directory containing static website files

        Returns:
            Dictionary with:
            - url: CDN URL
            - purge_status: CDN cache purge status
        """
        # Upload updated files
        self._upload_files(source_dir)

        # Purge the CDN cache
        self.purge_cdn()

        # Get the CDN endpoint URL
        cdn_url = f"https://{self.cdn_endpoint_name}.azureedge.net"

        return {
            "url": cdn_url,
            "purge_status": "initiated"
        }

    def purge_cdn(self, paths: Optional[List[str]] = None) -> Dict[str, str]:
        """Purge CDN cache for specified paths.

        Args:
            paths: List of paths to purge (defaults to ["/*"])

        Returns:
            Dictionary with purge status
        """
        if paths is None:
            paths = ["/*"]

        # Create CDN purge request
        self.cdn_client.endpoints.begin_purge_content(
            resource_group_name=self.resource_group_name,
            profile_name=self.cdn_profile_name,
            endpoint_name=self.cdn_endpoint_name,
            content_file_paths={"content_paths": paths}
        )

        return {
            "status": "purge_initiated",
            "paths": paths
        }

    def _create_resource_group(self) -> None:
        """Create Azure resource group with tags.

        Creates a resource group in the specified location with
        CloudConfig tags applied.
        """
        from azure.mgmt.resource import ResourceManagementClient

        resource_client = ResourceManagementClient(
            credential=self.credential,
            subscription_id=self.subscription_id
        )

        # Convert tags to Azure format (string values)
        azure_tags = CloudConfig.get_azure_tags(self.tags)

        resource_client.resource_groups.create_or_update(
            resource_group_name=self.resource_group_name,
            parameters={
                "location": self.location,
                "tags": azure_tags
            }
        )

    def _create_storage_account(self) -> str:
        """Create storage account and enable static website hosting.

        Creates the storage account, enables static website hosting,
        and returns the static website URL.

        Returns:
            Static website primary endpoint URL
        """
        # Convert tags to Azure format
        azure_tags = CloudConfig.get_azure_tags(self.tags)

        # Create the storage account
        poller = self.storage_client.storage_accounts.begin_create(
            resource_group_name=self.resource_group_name,
            account_name=self.storage_account_name,
            parameters={
                "location": self.location,
                "sku": {"name": "Standard_LRS"},
                "kind": "StorageV2",
                "tags": azure_tags,
                "properties": {
                    "access_tier": "Hot",
                    "allow_blob_public_access": True,
                    "minimum_tls_version": "TLS1_2"
                }
            }
        )

        # Wait for storage account creation to complete
        storage_account = poller.result()

        # Enable static website hosting
        self.storage_client.blob_services.set_service_properties(
            resource_group_name=self.resource_group_name,
            account_name=self.storage_account_name,
            parameters={
                "static_website": {
                    "enabled": True,
                    "index_document": "index.html",
                    "error_document_404_path": "error.html"
                }
            }
        )

        # Get the static website URL
        # Format: https://{storage_account}.z13.web.core.windows.net/
        storage_url = f"https://{self.storage_account_name}.z13.web.core.windows.net"

        return storage_url

    def _upload_files(self, source_dir: str) -> List[str]:
        """Upload all files from source directory to $web container.

        Recursively uploads all files, preserving directory structure
        and setting appropriate content-types.

        Args:
            source_dir: Path to source directory

        Returns:
            List of uploaded blob names
        """
        # Get storage account keys
        keys = self.storage_client.storage_accounts.list_keys(
            resource_group_name=self.resource_group_name,
            account_name=self.storage_account_name
        )
        storage_key = keys.keys[0].value

        # Create BlobServiceClient
        connection_string = (
            f"DefaultEndpointsProtocol=https;"
            f"AccountName={self.storage_account_name};"
            f"AccountKey={storage_key};"
            f"EndpointSuffix=core.windows.net"
        )

        blob_service_client = BlobServiceClient.from_connection_string(connection_string)

        # Get the $web container client
        container_client = blob_service_client.get_container_client("$web")

        source_path = Path(source_dir)
        uploaded_blobs = []

        for file_path in source_path.rglob("*"):
            if file_path.is_file():
                # Calculate relative path for blob name
                relative_path = file_path.relative_to(source_path)
                blob_name = str(relative_path).replace("\\", "/")  # Handle Windows paths

                # Determine content type
                content_type, _ = mimetypes.guess_type(str(file_path))
                if content_type is None:
                    content_type = "application/octet-stream"

                # Read file content
                with open(file_path, "rb") as f:
                    file_content = f.read()

                # Upload to $web container with content type
                blob_client = container_client.get_blob_client(blob_name)
                blob_client.upload_blob(
                    data=file_content,
                    content_settings=ContentSettings(content_type=content_type),
                    overwrite=True
                )

                uploaded_blobs.append(blob_name)

        return uploaded_blobs

    def _create_cdn(self) -> str:
        """Create CDN profile and endpoint.

        Creates a CDN profile and endpoint pointing to the storage
        account's static website, returns the CDN URL.

        Returns:
            CDN endpoint URL
        """
        # Convert tags to Azure format
        azure_tags = CloudConfig.get_azure_tags(self.tags)

        # Create CDN profile
        self.cdn_client.profiles.begin_create(
            resource_group_name=self.resource_group_name,
            profile_name=self.cdn_profile_name,
            profile={
                "location": "global",
                "sku": {"name": "Standard_Microsoft"},
                "tags": azure_tags
            }
        ).result()

        # Create CDN endpoint pointing to the static website
        origin_hostname = f"{self.storage_account_name}.z13.web.core.windows.net"

        self.cdn_client.endpoints.begin_create(
            resource_group_name=self.resource_group_name,
            profile_name=self.cdn_profile_name,
            endpoint_name=self.cdn_endpoint_name,
            endpoint={
                "location": "global",
                "tags": azure_tags,
                "origins": [
                    {
                        "name": f"{self.storage_account_name}-origin",
                        "host_name": origin_hostname,
                        "https_port": 443,
                        "origin_host_header": origin_hostname
                    }
                ],
                "is_https_allowed": True,
                "is_http_allowed": False,
                "query_string_caching_behavior": "IgnoreQueryString"
            }
        ).result()

        # CDN endpoint URL
        cdn_url = f"https://{self.cdn_endpoint_name}.azureedge.net"

        return cdn_url
