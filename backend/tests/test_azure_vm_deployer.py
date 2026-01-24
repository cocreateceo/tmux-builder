"""Tests for Azure VM deployer - dynamic site deployment to Azure VMs."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock Azure SDK modules before importing azure_vm_deployer
mock_identity = MagicMock()
mock_compute = MagicMock()
mock_network = MagicMock()
mock_resource = MagicMock()

sys.modules["azure.identity"] = mock_identity
sys.modules["azure.mgmt.compute"] = mock_compute
sys.modules["azure.mgmt.network"] = mock_network
sys.modules["azure.mgmt.resource"] = mock_resource

from cloud_config import CloudConfig


class TestAzureVMDeployer:
    """Test Azure VM deployer with mocked Azure SDK interactions."""

    # Sample test data
    SAMPLE_USER_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    SAMPLE_SESSION_ID = "session_001_build"
    SAMPLE_SUBSCRIPTION_ID = "12345678-1234-1234-1234-123456789012"

    def setup_method(self):
        """Reset mock state before each test."""
        mock_identity.reset_mock()
        mock_compute.reset_mock()
        mock_network.reset_mock()
        mock_resource.reset_mock()
        # Clear cached module to force reimport with fresh mocks
        if 'azure_vm_deployer' in sys.modules:
            del sys.modules['azure_vm_deployer']

    def test_azure_vm_deployer_init(self):
        """Test AzureVMDeployer initializes correctly."""
        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        assert deployer.user_id == self.SAMPLE_USER_ID
        assert deployer.session_id == self.SAMPLE_SESSION_ID
        assert deployer.subscription_id == self.SAMPLE_SUBSCRIPTION_ID

    def test_azure_vm_deployer_uses_sunwaretech_profile(self):
        """Deployer uses the 'sunwaretech' Azure profile from CloudConfig."""
        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        assert deployer.profile == "sunwaretech"
        assert deployer.profile == CloudConfig.AZURE_PROFILE

    def test_azure_vm_deployer_deploy_creates_vm(self):
        """Test deploy method creates Azure VM."""
        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        # Mock methods
        deployer._ensure_resource_group = MagicMock(return_value='tmux-rg')
        deployer._create_network_resources = MagicMock(return_value=('nic-id', '1.2.3.4'))
        deployer._create_vm = MagicMock(return_value='vm-12345')
        deployer._deploy_code = MagicMock()

        result = deployer.deploy('/path/to/source', 'node')

        assert result['url'] == 'http://1.2.3.4'
        assert result['provider'] == 'azure'
        assert result['type'] == 'vm'
        assert result['vm_name'] is not None

    def test_azure_vm_deployer_default_location(self):
        """Deployer uses default location from CloudConfig."""
        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        assert deployer.location == CloudConfig.AZURE_DEFAULT_LOCATION

    def test_azure_vm_deployer_custom_location(self):
        """Deployer accepts custom location parameter."""
        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID,
            location='westus2'
        )

        assert deployer.location == 'westus2'

    def test_azure_vm_deployer_tags_include_required_fields(self):
        """All required CloudConfig tags are present."""
        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
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
        assert tags["SiteType"] == "dynamic"
        assert tags["CreatedBy"] == "tmux-builder-automation"
        assert tags["CostCenter"] == "user-sites"

    def test_azure_vm_deployer_resource_group_name_format(self):
        """Resource group name follows naming convention with '-rg' suffix."""
        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
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

    def test_azure_vm_deployer_vm_name_follows_convention(self):
        """VM name follows CloudConfig naming convention."""
        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        vm_name = deployer.vm_name

        # Should use CloudConfig naming convention
        expected_name = CloudConfig.get_resource_name(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            resource_type="azure_vm"
        )
        assert vm_name == expected_name
        assert vm_name.startswith('tmux-')

    def test_azure_vm_deployer_lazy_loads_clients(self):
        """Clients are lazy-loaded when accessed."""
        # Setup mocks
        mock_credential = MagicMock()
        mock_identity.DefaultAzureCredential.return_value = mock_credential

        mock_compute_client = MagicMock()
        mock_compute.ComputeManagementClient.return_value = mock_compute_client

        mock_network_client = MagicMock()
        mock_network.NetworkManagementClient.return_value = mock_network_client

        mock_resource_client = MagicMock()
        mock_resource.ResourceManagementClient.return_value = mock_resource_client

        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        # Clients should not be created yet
        mock_identity.DefaultAzureCredential.assert_not_called()

        # Access credential property
        _ = deployer.credential
        mock_identity.DefaultAzureCredential.assert_called_once()

        # Access compute_client property
        _ = deployer.compute_client
        mock_compute.ComputeManagementClient.assert_called_once()

    def test_azure_vm_deployer_deploy_calls_methods_in_order(self):
        """Deploy method calls internal methods in correct order."""
        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        # Mock internal methods with tracking
        call_order = []

        def mock_ensure_rg():
            call_order.append('ensure_resource_group')
            return 'tmux-rg'

        def mock_create_network():
            call_order.append('create_network_resources')
            return ('nic-id', '1.2.3.4')

        def mock_create_vm(nic_id):
            call_order.append('create_vm')
            return 'vm-12345'

        def mock_deploy_code(site_type):
            call_order.append('deploy_code')

        deployer._ensure_resource_group = mock_ensure_rg
        deployer._create_network_resources = mock_create_network
        deployer._create_vm = mock_create_vm
        deployer._deploy_code = mock_deploy_code

        deployer.deploy('/path/to/source', 'node')

        assert call_order == [
            'ensure_resource_group',
            'create_network_resources',
            'create_vm',
            'deploy_code'
        ]

    def test_azure_vm_deployer_get_status(self):
        """Test get_status returns current VM state."""
        # Setup mocks
        mock_credential = MagicMock()
        mock_identity.DefaultAzureCredential.return_value = mock_credential

        mock_compute_client = MagicMock()
        mock_compute.ComputeManagementClient.return_value = mock_compute_client

        # Mock VM instance view response
        mock_vm = MagicMock()
        mock_vm.instance_view.statuses = [
            MagicMock(code='ProvisioningState/succeeded'),
            MagicMock(code='PowerState/running')
        ]
        mock_compute_client.virtual_machines.get.return_value = mock_vm

        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        result = deployer.get_status()

        assert 'vm_name' in result
        assert 'state' in result

    def test_azure_vm_deployer_terminate(self):
        """Test terminate method deletes VM and associated resources."""
        # Setup mocks
        mock_credential = MagicMock()
        mock_identity.DefaultAzureCredential.return_value = mock_credential

        mock_compute_client = MagicMock()
        mock_compute.ComputeManagementClient.return_value = mock_compute_client

        mock_network_client = MagicMock()
        mock_network.NetworkManagementClient.return_value = mock_network_client

        # Mock delete operations to return pollers
        mock_vm_delete_poller = MagicMock()
        mock_compute_client.virtual_machines.begin_delete.return_value = mock_vm_delete_poller

        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        result = deployer.terminate()

        assert result['terminated'] is True
        mock_compute_client.virtual_machines.begin_delete.assert_called_once()

    def test_azure_vm_deployer_node_setup_script(self):
        """Test that Node.js setup script is generated correctly."""
        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        script = deployer._get_setup_script('node')

        assert 'npm install' in script
        assert 'node' in script.lower() or 'nodejs' in script.lower()

    def test_azure_vm_deployer_python_setup_script(self):
        """Test that Python setup script is generated correctly."""
        from azure_vm_deployer import AzureVMDeployer
        deployer = AzureVMDeployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            subscription_id=self.SAMPLE_SUBSCRIPTION_ID
        )

        script = deployer._get_setup_script('python')

        assert 'pip install' in script
        assert 'python' in script.lower()
