"""Azure VM Deployer - Deploy dynamic sites to Azure VMs.

Handles Node.js, Python, and other dynamic applications.
Uses the sunwaretech Azure profile for authentication.
"""

import logging
import os
import secrets
import string
from typing import Dict, List, Optional, Any

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient

from cloud_config import CloudConfig

logger = logging.getLogger(__name__)

# Default VM configuration
DEFAULT_VM_SIZE = 'Standard_B1s'
DEFAULT_IMAGE_PUBLISHER = 'Canonical'
DEFAULT_IMAGE_OFFER = '0001-com-ubuntu-server-jammy'
DEFAULT_IMAGE_SKU = '22_04-lts-gen2'
DEFAULT_IMAGE_VERSION = 'latest'
DEFAULT_ADMIN_USERNAME = 'azureuser'


def _generate_secure_password() -> str:
    """Generate a secure random password for VM admin.

    Returns:
        A 16-character password with mixed case, digits, and special characters.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(16))


class AzureVMDeployer:
    """Deploy dynamic sites to Azure VMs.

    Uses the sunwaretech Azure profile and CloudConfig for resource
    naming and tagging conventions. Supports Node.js and Python
    applications with Custom Script Extension for setup.
    """

    def __init__(
        self,
        user_id: str,
        session_id: str,
        subscription_id: Optional[str] = None,
        location: Optional[str] = None
    ):
        """Initialize the Azure VM deployer.

        Args:
            user_id: User GUID for resource naming and tagging
            session_id: Session identifier for resource naming and tagging
            subscription_id: Azure subscription ID (from env if not provided)
            location: Azure location (defaults to CloudConfig.AZURE_DEFAULT_LOCATION)
        """
        self.user_id = user_id
        self.session_id = session_id
        self.subscription_id = subscription_id or os.environ.get('AZURE_SUBSCRIPTION_ID')
        self.location = location or CloudConfig.AZURE_DEFAULT_LOCATION
        self.profile = CloudConfig.AZURE_PROFILE

        # Generate resource names using CloudConfig naming conventions
        guid_prefix = user_id.split("-")[0][:8]
        session_short = session_id.replace("_", "")

        # VM name: tmux-{guid}-{session}
        self.vm_name = CloudConfig.get_resource_name(
            user_id=user_id,
            session_id=session_id,
            resource_type="azure_vm"
        )

        # Resource group: tmux-{guid}-{session}-rg
        self.resource_group_name = f"tmux-{guid_prefix}-{session_short}-rg"

        # VNet name: tmux-{guid}-{session}-vnet
        self.vnet_name = f"tmux-{guid_prefix}-{session_short}-vnet"

        # Subnet name: tmux-{guid}-{session}-subnet
        self.subnet_name = f"tmux-{guid_prefix}-{session_short}-subnet"

        # Public IP name: tmux-{guid}-{session}-pip
        self.public_ip_name = f"tmux-{guid_prefix}-{session_short}-pip"

        # NIC name: tmux-{guid}-{session}-nic
        self.nic_name = f"tmux-{guid_prefix}-{session_short}-nic"

        # NSG name: tmux-{guid}-{session}-nsg
        self.nsg_name = f"tmux-{guid_prefix}-{session_short}-nsg"

        # Generate tags using CloudConfig for dynamic sites
        self.tags = CloudConfig.get_tags(
            user_id=user_id,
            session_id=session_id,
            site_type="dynamic"
        )

        # Lazy-loaded clients
        self._credential: Optional[DefaultAzureCredential] = None
        self._compute_client: Optional[ComputeManagementClient] = None
        self._network_client: Optional[NetworkManagementClient] = None
        self._resource_client: Optional[ResourceManagementClient] = None

        # Track public IP for URL
        self._public_ip_address: Optional[str] = None

    @property
    def credential(self) -> DefaultAzureCredential:
        """Lazy-loaded Azure DefaultAzureCredential."""
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        return self._credential

    @property
    def compute_client(self) -> ComputeManagementClient:
        """Lazy-loaded ComputeManagementClient with credential authentication."""
        if self._compute_client is None:
            self._compute_client = ComputeManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )
        return self._compute_client

    @property
    def network_client(self) -> NetworkManagementClient:
        """Lazy-loaded NetworkManagementClient with credential authentication."""
        if self._network_client is None:
            self._network_client = NetworkManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )
        return self._network_client

    @property
    def resource_client(self) -> ResourceManagementClient:
        """Lazy-loaded ResourceManagementClient with credential authentication."""
        if self._resource_client is None:
            self._resource_client = ResourceManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )
        return self._resource_client

    def deploy(self, source_path: str, site_type: str = 'node') -> Dict[str, Any]:
        """Deploy dynamic site to Azure VM.

        Creates resource group, network resources, VM, and deploys code.

        Args:
            source_path: Path to source code directory
            site_type: Type of application ('node' or 'python')

        Returns:
            Dictionary with deployment details:
            - url: HTTP URL to access the deployed application
            - vm_name: Azure VM name
            - public_ip: Public IP address
            - resource_group: Resource group name
            - provider: 'azure'
            - type: 'vm'

        Raises:
            Exception: If Azure API calls fail
        """
        logger.info(f"Deploying {site_type} app from {source_path} to Azure VM")

        try:
            # Step 1: Ensure resource group exists
            self._ensure_resource_group()

            # Step 2: Create network resources (VNet, Subnet, Public IP, NSG, NIC)
            nic_id, public_ip = self._create_network_resources()

            # Step 3: Create the VM
            self._create_vm(nic_id)

            # Step 4: Deploy application code using Custom Script Extension
            self._deploy_code(site_type)

            return {
                "url": f"http://{public_ip}",
                "vm_name": self.vm_name,
                "public_ip": public_ip,
                "resource_group": self.resource_group_name,
                "provider": "azure",
                "type": "vm"
            }
        except Exception as e:
            logger.error(f"Azure API error during deployment: {e}")
            raise

    def terminate(self) -> Dict[str, Any]:
        """Terminate the Azure VM and clean up resources.

        Deletes the VM and associated resources (NIC, Public IP, NSG).
        Does not delete the VNet or resource group.

        Returns:
            Dictionary with termination status
        """
        logger.info(f"Terminating VM {self.vm_name}")

        try:
            # Delete VM
            poller = self.compute_client.virtual_machines.begin_delete(
                resource_group_name=self.resource_group_name,
                vm_name=self.vm_name
            )
            poller.result()  # Wait for completion

            # Delete NIC
            poller = self.network_client.network_interfaces.begin_delete(
                resource_group_name=self.resource_group_name,
                network_interface_name=self.nic_name
            )
            poller.result()

            # Delete Public IP
            poller = self.network_client.public_ip_addresses.begin_delete(
                resource_group_name=self.resource_group_name,
                public_ip_address_name=self.public_ip_name
            )
            poller.result()

            logger.info(f"Successfully terminated VM {self.vm_name}")

            return {
                "terminated": True,
                "vm_name": self.vm_name,
                "resource_group": self.resource_group_name
            }
        except Exception as e:
            logger.error(f"Error terminating VM: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get status of the Azure VM.

        Returns:
            Dictionary with VM status details:
            - vm_name: VM name
            - state: Current power state
            - provisioning_state: Provisioning state
            - public_ip: Public IP address (if available)
        """
        logger.info(f"Getting status for VM {self.vm_name}")

        try:
            vm = self.compute_client.virtual_machines.get(
                resource_group_name=self.resource_group_name,
                vm_name=self.vm_name,
                expand='instanceView'
            )

            # Parse statuses to get power state
            power_state = 'unknown'
            provisioning_state = 'unknown'

            if vm.instance_view and vm.instance_view.statuses:
                for status in vm.instance_view.statuses:
                    if status.code.startswith('PowerState/'):
                        power_state = status.code.split('/')[-1]
                    elif status.code.startswith('ProvisioningState/'):
                        provisioning_state = status.code.split('/')[-1]

            # Get public IP if available
            public_ip = self._get_public_ip()

            return {
                "vm_name": self.vm_name,
                "state": power_state,
                "provisioning_state": provisioning_state,
                "public_ip": public_ip,
                "resource_group": self.resource_group_name
            }
        except Exception as e:
            logger.error(f"Error getting VM status: {e}")
            raise

    def _ensure_resource_group(self) -> str:
        """Create or update resource group.

        Returns:
            Resource group name
        """
        logger.info(f"Ensuring resource group: {self.resource_group_name}")

        azure_tags = CloudConfig.get_azure_tags(self.tags)

        self.resource_client.resource_groups.create_or_update(
            resource_group_name=self.resource_group_name,
            parameters={
                "location": self.location,
                "tags": azure_tags
            }
        )

        return self.resource_group_name

    def _create_network_resources(self) -> tuple:
        """Create all network resources: VNet, Subnet, NSG, Public IP, NIC.

        Returns:
            Tuple of (nic_id, public_ip_address)
        """
        azure_tags = CloudConfig.get_azure_tags(self.tags)

        # Create VNet
        logger.info(f"Creating VNet: {self.vnet_name}")
        poller = self.network_client.virtual_networks.begin_create_or_update(
            resource_group_name=self.resource_group_name,
            virtual_network_name=self.vnet_name,
            parameters={
                "location": self.location,
                "tags": azure_tags,
                "address_space": {
                    "address_prefixes": ["10.0.0.0/16"]
                }
            }
        )
        poller.result()

        # Create Subnet
        logger.info(f"Creating Subnet: {self.subnet_name}")
        poller = self.network_client.subnets.begin_create_or_update(
            resource_group_name=self.resource_group_name,
            virtual_network_name=self.vnet_name,
            subnet_name=self.subnet_name,
            subnet_parameters={
                "address_prefix": "10.0.0.0/24"
            }
        )
        subnet = poller.result()

        # Create NSG with rules for HTTP and SSH
        logger.info(f"Creating NSG: {self.nsg_name}")
        poller = self.network_client.network_security_groups.begin_create_or_update(
            resource_group_name=self.resource_group_name,
            network_security_group_name=self.nsg_name,
            parameters={
                "location": self.location,
                "tags": azure_tags,
                "security_rules": [
                    {
                        "name": "AllowSSH",
                        "priority": 100,
                        "direction": "Inbound",
                        "access": "Allow",
                        "protocol": "Tcp",
                        "source_port_range": "*",
                        "destination_port_range": "22",
                        "source_address_prefix": "*",
                        "destination_address_prefix": "*"
                    },
                    {
                        "name": "AllowHTTP",
                        "priority": 110,
                        "direction": "Inbound",
                        "access": "Allow",
                        "protocol": "Tcp",
                        "source_port_range": "*",
                        "destination_port_range": "80",
                        "source_address_prefix": "*",
                        "destination_address_prefix": "*"
                    },
                    {
                        "name": "AllowHTTPS",
                        "priority": 120,
                        "direction": "Inbound",
                        "access": "Allow",
                        "protocol": "Tcp",
                        "source_port_range": "*",
                        "destination_port_range": "443",
                        "source_address_prefix": "*",
                        "destination_address_prefix": "*"
                    },
                    {
                        "name": "AllowAppPort",
                        "priority": 130,
                        "direction": "Inbound",
                        "access": "Allow",
                        "protocol": "Tcp",
                        "source_port_range": "*",
                        "destination_port_range": "3000",
                        "source_address_prefix": "*",
                        "destination_address_prefix": "*"
                    }
                ]
            }
        )
        nsg = poller.result()

        # Create Public IP
        logger.info(f"Creating Public IP: {self.public_ip_name}")
        poller = self.network_client.public_ip_addresses.begin_create_or_update(
            resource_group_name=self.resource_group_name,
            public_ip_address_name=self.public_ip_name,
            parameters={
                "location": self.location,
                "tags": azure_tags,
                "sku": {"name": "Standard"},
                "public_ip_allocation_method": "Static",
                "public_ip_address_version": "IPv4"
            }
        )
        public_ip = poller.result()
        self._public_ip_address = public_ip.ip_address

        # Create NIC
        logger.info(f"Creating NIC: {self.nic_name}")
        poller = self.network_client.network_interfaces.begin_create_or_update(
            resource_group_name=self.resource_group_name,
            network_interface_name=self.nic_name,
            parameters={
                "location": self.location,
                "tags": azure_tags,
                "ip_configurations": [{
                    "name": "ipconfig1",
                    "subnet": {"id": subnet.id},
                    "public_ip_address": {"id": public_ip.id}
                }],
                "network_security_group": {"id": nsg.id}
            }
        )
        nic = poller.result()

        logger.info(f"Network resources created. Public IP: {self._public_ip_address}")

        return (nic.id, self._public_ip_address)

    def _create_vm(self, nic_id: str) -> str:
        """Create the Azure VM.

        Args:
            nic_id: Network Interface ID to attach to VM

        Returns:
            VM name
        """
        logger.info(f"Creating VM: {self.vm_name}")

        azure_tags = CloudConfig.get_azure_tags(self.tags)

        # Get password from environment or generate a secure random one
        admin_password = os.environ.get('AZURE_VM_ADMIN_PASSWORD') or _generate_secure_password()

        poller = self.compute_client.virtual_machines.begin_create_or_update(
            resource_group_name=self.resource_group_name,
            vm_name=self.vm_name,
            parameters={
                "location": self.location,
                "tags": azure_tags,
                "hardware_profile": {
                    "vm_size": DEFAULT_VM_SIZE
                },
                "storage_profile": {
                    "image_reference": {
                        "publisher": DEFAULT_IMAGE_PUBLISHER,
                        "offer": DEFAULT_IMAGE_OFFER,
                        "sku": DEFAULT_IMAGE_SKU,
                        "version": DEFAULT_IMAGE_VERSION
                    },
                    "os_disk": {
                        "name": f"{self.vm_name}-osdisk",
                        "caching": "ReadWrite",
                        "create_option": "FromImage",
                        "managed_disk": {
                            "storage_account_type": "Standard_LRS"
                        }
                    }
                },
                "os_profile": {
                    "computer_name": self.vm_name[:15],  # Max 15 chars for Linux
                    "admin_username": DEFAULT_ADMIN_USERNAME,
                    "admin_password": admin_password,
                    "linux_configuration": {
                        "disable_password_authentication": False
                    }
                },
                "network_profile": {
                    "network_interfaces": [{
                        "id": nic_id,
                        "primary": True
                    }]
                }
            }
        )

        vm = poller.result()
        logger.info(f"VM {self.vm_name} created successfully")

        return self.vm_name

    def _deploy_code(self, site_type: str) -> None:
        """Deploy application code using Custom Script Extension.

        Args:
            site_type: Application type ('node' or 'python')
        """
        logger.info(f"Deploying {site_type} application code to VM")

        setup_script = self._get_setup_script(site_type)

        # Use Custom Script Extension to run setup
        poller = self.compute_client.virtual_machine_extensions.begin_create_or_update(
            resource_group_name=self.resource_group_name,
            vm_name=self.vm_name,
            vm_extension_name="customScript",
            extension_parameters={
                "location": self.location,
                "publisher": "Microsoft.Azure.Extensions",
                "type_properties_type": "CustomScript",
                "type_handler_version": "2.1",
                "auto_upgrade_minor_version": True,
                "settings": {
                    "commandToExecute": f"bash -c '{setup_script}'"
                }
            }
        )

        poller.result()
        logger.info(f"Custom Script Extension completed for {site_type} app")

    def _get_setup_script(self, site_type: str) -> str:
        """Generate setup script based on site type.

        Args:
            site_type: Application type ('node' or 'python')

        Returns:
            Shell script content
        """
        base_script = """
sudo apt-get update -y
sudo apt-get install -y git
sudo mkdir -p /app
sudo chown -R $USER:$USER /app
cd /app
"""

        if site_type == 'node':
            return base_script + """
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
npm install
npm start &
"""
        elif site_type == 'python':
            return base_script + """
sudo apt-get install -y python3 python3-pip python3-venv
python3 -m venv /app/venv
source /app/venv/bin/activate
pip install -r requirements.txt
python app.py &
"""
        else:
            return base_script + f"""
echo "Unknown site type: {site_type}"
"""

    def _get_public_ip(self) -> str:
        """Get the public IP address of the VM.

        Returns:
            Public IP address string, or empty string if not available
        """
        if self._public_ip_address:
            return self._public_ip_address

        try:
            public_ip = self.network_client.public_ip_addresses.get(
                resource_group_name=self.resource_group_name,
                public_ip_address_name=self.public_ip_name
            )
            return public_ip.ip_address or ''
        except Exception:
            return ''
