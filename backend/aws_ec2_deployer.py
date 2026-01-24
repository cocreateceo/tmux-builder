"""
AWS EC2 Deployer - Deploy dynamic sites to EC2 instances.

Handles Node.js, Python, and other dynamic applications.
Uses the sunwaretech AWS profile for authentication.
"""

import time
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Dict, List, Optional, Any

from cloud_config import CloudConfig

logger = logging.getLogger(__name__)

# Default EC2 configuration
DEFAULT_AMI = 'ami-0c02fb55956c7d316'  # Amazon Linux 2023 (us-east-1)
DEFAULT_INSTANCE_TYPE = 't3.micro'
DEFAULT_KEY_NAME = 'tmux-builder-key'
DEFAULT_IAM_ROLE = 'tmux-builder-ec2-role'
SSM_AGENT_STARTUP_DELAY = 30  # Seconds to wait for SSM agent to start


class AWSEC2Deployer:
    """Deploy dynamic sites to AWS EC2.

    Uses the sunwaretech AWS profile and CloudConfig for resource
    naming and tagging conventions. Supports Node.js and Python
    applications with SSM-based remote command execution.
    """

    def __init__(
        self,
        user_id: str,
        session_id: str,
        region: Optional[str] = None
    ):
        """Initialize the AWS EC2 deployer.

        Args:
            user_id: User GUID for resource naming and tagging
            session_id: Session identifier for resource naming and tagging
            region: AWS region (defaults to CloudConfig.AWS_DEFAULT_REGION)
        """
        self.user_id = user_id
        self.session_id = session_id
        self.region = region or CloudConfig.AWS_DEFAULT_REGION
        self.profile = CloudConfig.AWS_PROFILE

        # Lazy-loaded clients
        self._session: Optional[boto3.Session] = None
        self._ec2: Optional[boto3.client] = None
        self._ssm: Optional[boto3.client] = None

    @property
    def ec2(self):
        """Lazy-load EC2 client with profile authentication."""
        if self._ec2 is None:
            if self._session is None:
                self._session = boto3.Session(profile_name=self.profile)
            self._ec2 = self._session.client('ec2', region_name=self.region)
        return self._ec2

    @property
    def ssm(self):
        """Lazy-load SSM client with profile authentication."""
        if self._ssm is None:
            if self._session is None:
                self._session = boto3.Session(profile_name=self.profile)
            self._ssm = self._session.client('ssm', region_name=self.region)
        return self._ssm

    def deploy(self, source_path: str, site_type: str = 'node') -> Dict[str, Any]:
        """Deploy dynamic site to EC2.

        Creates or reuses an EC2 instance, uploads application code,
        and runs setup commands based on the site type.

        Args:
            source_path: Path to source code directory
            site_type: Type of application ('node' or 'python')

        Returns:
            Dictionary with deployment details:
            - url: HTTP URL to access the deployed application
            - instance_id: EC2 instance ID
            - provider: 'aws'
            - type: 'ec2'

        Raises:
            ClientError: If AWS API calls fail
        """
        logger.info(f"Deploying {site_type} app from {source_path}")

        try:
            # Launch or get existing instance
            instance_id = self._get_or_create_instance()

            # Wait for instance to be ready
            self._wait_for_instance(instance_id)

            # Upload application code
            self._upload_code(instance_id, source_path)

            # Run setup and start commands
            self._run_setup_commands(instance_id, site_type)

            # Get public IP for URL
            public_ip = self._get_public_ip(instance_id)

            return {
                "url": f"http://{public_ip}",
                "instance_id": instance_id,
                "provider": "aws",
                "type": "ec2"
            }
        except ClientError as e:
            logger.error(f"AWS API error during deployment: {e}")
            raise

    def terminate(self, instance_id: str) -> Dict[str, Any]:
        """Terminate an EC2 instance.

        Args:
            instance_id: EC2 instance ID to terminate

        Returns:
            Dictionary with termination status
        """
        logger.info(f"Terminating instance {instance_id}")

        self.ec2.terminate_instances(InstanceIds=[instance_id])

        return {
            "terminated": True,
            "instance_id": instance_id
        }

    def get_status(self, instance_id: str) -> Dict[str, Any]:
        """Get status of an EC2 instance.

        Args:
            instance_id: EC2 instance ID

        Returns:
            Dictionary with instance status details
        """
        response = self.ec2.describe_instances(InstanceIds=[instance_id])

        instance = response['Reservations'][0]['Instances'][0]

        return {
            "instance_id": instance_id,
            "state": instance['State']['Name'],
            "public_ip": instance.get('PublicIpAddress', '')
        }

    def _get_or_create_instance(self) -> str:
        """Launch new EC2 instance with proper tags.

        Creates an instance with the CloudConfig naming convention
        and all required tags for cost tracking.

        Returns:
            Instance ID of the launched instance
        """
        # Generate instance name using CloudConfig
        instance_name = CloudConfig.get_resource_name(
            user_id=self.user_id,
            session_id=self.session_id,
            resource_type="ec2"
        )

        # Get tags for cost tracking
        tags = CloudConfig.get_tags(
            user_id=self.user_id,
            session_id=self.session_id,
            site_type="dynamic"
        )
        aws_tags = CloudConfig.get_aws_tags_list(tags)

        # Add Name tag
        aws_tags.append({'Key': 'Name', 'Value': instance_name})

        logger.info(f"Launching EC2 instance: {instance_name}")

        response = self.ec2.run_instances(
            ImageId=DEFAULT_AMI,
            InstanceType=DEFAULT_INSTANCE_TYPE,
            MinCount=1,
            MaxCount=1,
            KeyName=DEFAULT_KEY_NAME,
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': aws_tags
            }],
            UserData=self._get_user_data_script(),
            IamInstanceProfile={'Name': DEFAULT_IAM_ROLE}
        )

        instance_id = response['Instances'][0]['InstanceId']
        logger.info(f"Launched instance: {instance_id}")

        return instance_id

    def _wait_for_instance(self, instance_id: str, timeout: int = 300) -> None:
        """Wait for instance to be running and reachable.

        Uses EC2 waiter to wait for running state, then adds
        additional delay for services to start.

        Args:
            instance_id: EC2 instance ID
            timeout: Maximum wait time in seconds
        """
        logger.info(f"Waiting for instance {instance_id} to be ready")

        waiter = self.ec2.get_waiter('instance_running')
        waiter.wait(
            InstanceIds=[instance_id],
            WaiterConfig={
                'Delay': 10,
                'MaxAttempts': timeout // 10
            }
        )

        # Additional wait for SSM agent and services to start
        time.sleep(SSM_AGENT_STARTUP_DELAY)
        logger.info(f"Instance {instance_id} is running")

    def _upload_code(self, instance_id: str, source_path: str) -> None:
        """Upload source code to instance via S3 and SSM.

        Uses S3 as an intermediary to transfer files to the instance.

        Args:
            instance_id: EC2 instance ID
            source_path: Path to source code directory
        """
        logger.info(f"Uploading code to {instance_id} from {source_path}")
        # Would use S3 as intermediary in production:
        # zip source -> upload to S3 -> SSM command to download
        raise NotImplementedError("Code upload via S3 not yet implemented")

    def _run_setup_commands(self, instance_id: str, site_type: str) -> None:
        """Run setup commands on instance via SSM.

        Executes appropriate installation and startup commands
        based on the application type.

        Args:
            instance_id: EC2 instance ID
            site_type: Application type ('node' or 'python')
        """
        logger.info(f"Running {site_type} setup commands on {instance_id}")

        if site_type == 'node':
            commands = [
                'cd /app',
                'npm install',
                'npm start &'
            ]
        elif site_type == 'python':
            commands = [
                'cd /app',
                'pip install -r requirements.txt',
                'python app.py &'
            ]
        else:
            commands = ['echo "Unknown site type"']

        self.ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={'commands': commands}
        )

        logger.info(f"Setup commands sent to {instance_id}")

    def _get_public_ip(self, instance_id: str) -> str:
        """Get public IP address of instance.

        Args:
            instance_id: EC2 instance ID

        Returns:
            Public IP address string, or empty string if not assigned
        """
        response = self.ec2.describe_instances(InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        return instance.get('PublicIpAddress', '')

    def _get_user_data_script(self) -> str:
        """Return user data script for instance initialization.

        Installs required software and creates application directory.

        Returns:
            Shell script for EC2 user data
        """
        return '''#!/bin/bash
yum update -y
yum install -y nodejs npm python3 python3-pip git
mkdir -p /app
chown ec2-user:ec2-user /app
'''
