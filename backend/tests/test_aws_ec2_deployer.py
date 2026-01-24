"""Tests for AWS EC2 deployer - dynamic site deployment to EC2 instances."""

import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock boto3 and botocore before importing aws_ec2_deployer
mock_boto3 = MagicMock()
sys.modules["boto3"] = mock_boto3

# Mock botocore.exceptions with a real exception class for testing
mock_botocore = MagicMock()
mock_botocore_exceptions = MagicMock()

class MockClientError(Exception):
    """Mock ClientError for testing."""
    pass

mock_botocore_exceptions.ClientError = MockClientError
mock_botocore.exceptions = mock_botocore_exceptions
sys.modules["botocore"] = mock_botocore
sys.modules["botocore.exceptions"] = mock_botocore_exceptions

from cloud_config import CloudConfig


class TestAWSEC2Deployer:
    """Test AWS EC2 deployer with mocked boto3 interactions."""

    # Sample test data
    SAMPLE_USER_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    SAMPLE_SESSION_ID = "session_001_build"

    def setup_method(self):
        """Reset mock state before each test."""
        mock_boto3.reset_mock()
        # Clear any cached module to force reimport with fresh mocks
        if 'aws_ec2_deployer' in sys.modules:
            del sys.modules['aws_ec2_deployer']

    def test_ec2_deployer_init_creates_clients(self):
        """Test AWSEC2Deployer initializes boto3 clients."""
        # Set up mock session
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = MagicMock()

        from aws_ec2_deployer import AWSEC2Deployer
        deployer = AWSEC2Deployer(self.SAMPLE_USER_ID, self.SAMPLE_SESSION_ID)

        # Access ec2 property to trigger lazy load
        _ = deployer.ec2

        # Verify Session was created with sunwaretech profile
        mock_boto3.Session.assert_called_with(profile_name="sunwaretech")
        mock_session.client.assert_called()

    def test_ec2_deployer_uses_sunwaretech_profile(self):
        """Deployer uses the 'sunwaretech' AWS profile from CloudConfig."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = MagicMock()

        from aws_ec2_deployer import AWSEC2Deployer
        deployer = AWSEC2Deployer(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID
        )

        # Access the ec2 client to trigger lazy initialization
        _ = deployer.ec2

        # Verify Session was created with sunwaretech profile
        mock_boto3.Session.assert_called_with(profile_name="sunwaretech")
        assert deployer.profile == "sunwaretech"

    def test_ec2_deployer_deploy_launches_instance(self):
        """Test deploy method launches EC2 instance."""
        # Set up mock session and clients
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_ec2 = MagicMock()
        mock_ssm = MagicMock()

        def client_factory(service_name, **kwargs):
            if service_name == "ec2":
                return mock_ec2
            elif service_name == "ssm":
                return mock_ssm
            return MagicMock()

        mock_session.client.side_effect = client_factory

        # Mock EC2 responses
        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-12345'}]
        }
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-12345',
                    'State': {'Name': 'running'},
                    'PublicIpAddress': '1.2.3.4'
                }]
            }]
        }

        # Mock waiter
        mock_waiter = MagicMock()
        mock_ec2.get_waiter.return_value = mock_waiter

        from aws_ec2_deployer import AWSEC2Deployer
        deployer = AWSEC2Deployer(self.SAMPLE_USER_ID, self.SAMPLE_SESSION_ID)

        # Mock the internal methods that do actual work
        deployer._wait_for_instance = MagicMock()
        deployer._upload_code = MagicMock()
        deployer._run_setup_commands = MagicMock()

        result = deployer.deploy('/path/to/source', 'node')

        assert result['instance_id'] == 'i-12345'
        assert result['url'] == 'http://1.2.3.4'
        assert result['provider'] == 'aws'
        assert result['type'] == 'ec2'

    def test_ec2_deployer_creates_instance_with_tags(self):
        """Deploy creates EC2 instance with required CloudConfig tags."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_ec2 = MagicMock()
        mock_ssm = MagicMock()

        def client_factory(service_name, **kwargs):
            if service_name == "ec2":
                return mock_ec2
            elif service_name == "ssm":
                return mock_ssm
            return MagicMock()

        mock_session.client.side_effect = client_factory

        # Mock EC2 responses
        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-12345'}]
        }
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-12345',
                    'State': {'Name': 'running'},
                    'PublicIpAddress': '1.2.3.4'
                }]
            }]
        }

        mock_waiter = MagicMock()
        mock_ec2.get_waiter.return_value = mock_waiter

        from aws_ec2_deployer import AWSEC2Deployer
        deployer = AWSEC2Deployer(self.SAMPLE_USER_ID, self.SAMPLE_SESSION_ID)

        # Mock internal methods
        deployer._wait_for_instance = MagicMock()
        deployer._upload_code = MagicMock()
        deployer._run_setup_commands = MagicMock()

        deployer.deploy('/path/to/source', 'node')

        # Verify run_instances was called
        mock_ec2.run_instances.assert_called_once()

        # Extract tags from the call
        call_kwargs = mock_ec2.run_instances.call_args[1]
        tag_specs = call_kwargs['TagSpecifications']

        # Find instance tags
        instance_tags = None
        for spec in tag_specs:
            if spec['ResourceType'] == 'instance':
                instance_tags = {t['Key']: t['Value'] for t in spec['Tags']}
                break

        assert instance_tags is not None
        assert instance_tags['Project'] == 'tmux-builder'
        assert instance_tags['UserGUID'] == self.SAMPLE_USER_ID
        assert instance_tags['SessionID'] == self.SAMPLE_SESSION_ID
        assert instance_tags['SiteType'] == 'dynamic'

    def test_ec2_deployer_runs_node_setup_commands(self):
        """Test that Node.js setup commands are run for node site type."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_ec2 = MagicMock()
        mock_ssm = MagicMock()

        def client_factory(service_name, **kwargs):
            if service_name == "ec2":
                return mock_ec2
            elif service_name == "ssm":
                return mock_ssm
            return MagicMock()

        mock_session.client.side_effect = client_factory

        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-12345'}]
        }
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-12345',
                    'State': {'Name': 'running'},
                    'PublicIpAddress': '1.2.3.4'
                }]
            }]
        }

        mock_waiter = MagicMock()
        mock_ec2.get_waiter.return_value = mock_waiter

        from aws_ec2_deployer import AWSEC2Deployer
        deployer = AWSEC2Deployer(self.SAMPLE_USER_ID, self.SAMPLE_SESSION_ID)

        # Only mock _wait_for_instance and _upload_code, let _run_setup_commands run
        deployer._wait_for_instance = MagicMock()
        deployer._upload_code = MagicMock()

        deployer.deploy('/path/to/source', 'node')

        # Verify SSM send_command was called
        mock_ssm.send_command.assert_called_once()
        call_kwargs = mock_ssm.send_command.call_args[1]

        assert call_kwargs['DocumentName'] == 'AWS-RunShellScript'
        assert 'npm install' in call_kwargs['Parameters']['commands']
        assert 'npm start' in ' '.join(call_kwargs['Parameters']['commands'])

    def test_ec2_deployer_runs_python_setup_commands(self):
        """Test that Python setup commands are run for python site type."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_ec2 = MagicMock()
        mock_ssm = MagicMock()

        def client_factory(service_name, **kwargs):
            if service_name == "ec2":
                return mock_ec2
            elif service_name == "ssm":
                return mock_ssm
            return MagicMock()

        mock_session.client.side_effect = client_factory

        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-12345'}]
        }
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-12345',
                    'State': {'Name': 'running'},
                    'PublicIpAddress': '1.2.3.4'
                }]
            }]
        }

        mock_waiter = MagicMock()
        mock_ec2.get_waiter.return_value = mock_waiter

        from aws_ec2_deployer import AWSEC2Deployer
        deployer = AWSEC2Deployer(self.SAMPLE_USER_ID, self.SAMPLE_SESSION_ID)

        deployer._wait_for_instance = MagicMock()
        deployer._upload_code = MagicMock()

        deployer.deploy('/path/to/source', 'python')

        # Verify SSM send_command was called with Python commands
        mock_ssm.send_command.assert_called_once()
        call_kwargs = mock_ssm.send_command.call_args[1]

        assert 'pip install -r requirements.txt' in call_kwargs['Parameters']['commands']
        assert 'python app.py' in ' '.join(call_kwargs['Parameters']['commands'])

    def test_ec2_deployer_instance_name_follows_convention(self):
        """Instance name follows CloudConfig naming convention."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_ec2 = MagicMock()
        mock_ssm = MagicMock()

        def client_factory(service_name, **kwargs):
            if service_name == "ec2":
                return mock_ec2
            elif service_name == "ssm":
                return mock_ssm
            return MagicMock()

        mock_session.client.side_effect = client_factory

        mock_ec2.run_instances.return_value = {
            'Instances': [{'InstanceId': 'i-12345'}]
        }
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-12345',
                    'State': {'Name': 'running'},
                    'PublicIpAddress': '1.2.3.4'
                }]
            }]
        }

        mock_waiter = MagicMock()
        mock_ec2.get_waiter.return_value = mock_waiter

        from aws_ec2_deployer import AWSEC2Deployer
        deployer = AWSEC2Deployer(self.SAMPLE_USER_ID, self.SAMPLE_SESSION_ID)

        deployer._wait_for_instance = MagicMock()
        deployer._upload_code = MagicMock()
        deployer._run_setup_commands = MagicMock()

        deployer.deploy('/path/to/source', 'node')

        # Extract the Name tag from the call
        call_kwargs = mock_ec2.run_instances.call_args[1]
        tag_specs = call_kwargs['TagSpecifications']

        instance_tags = None
        for spec in tag_specs:
            if spec['ResourceType'] == 'instance':
                instance_tags = {t['Key']: t['Value'] for t in spec['Tags']}
                break

        # Verify name follows convention
        expected_name = CloudConfig.get_resource_name(
            user_id=self.SAMPLE_USER_ID,
            session_id=self.SAMPLE_SESSION_ID,
            resource_type="ec2"
        )
        assert instance_tags['Name'] == expected_name
        assert instance_tags['Name'].startswith('tmux-')

    def test_ec2_deployer_default_region(self):
        """Deployer uses default region from CloudConfig."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = MagicMock()

        from aws_ec2_deployer import AWSEC2Deployer
        deployer = AWSEC2Deployer(self.SAMPLE_USER_ID, self.SAMPLE_SESSION_ID)

        assert deployer.region == CloudConfig.AWS_DEFAULT_REGION

    def test_ec2_deployer_custom_region(self):
        """Deployer accepts custom region parameter."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = MagicMock()

        from aws_ec2_deployer import AWSEC2Deployer
        deployer = AWSEC2Deployer(
            self.SAMPLE_USER_ID,
            self.SAMPLE_SESSION_ID,
            region='us-west-2'
        )

        assert deployer.region == 'us-west-2'

    def test_ec2_deployer_terminate_instance(self):
        """Test terminate method stops and terminates EC2 instance."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_ec2 = MagicMock()

        def client_factory(service_name, **kwargs):
            if service_name == "ec2":
                return mock_ec2
            return MagicMock()

        mock_session.client.side_effect = client_factory

        from aws_ec2_deployer import AWSEC2Deployer
        deployer = AWSEC2Deployer(self.SAMPLE_USER_ID, self.SAMPLE_SESSION_ID)

        result = deployer.terminate('i-12345')

        mock_ec2.terminate_instances.assert_called_once_with(
            InstanceIds=['i-12345']
        )
        assert result['terminated'] is True
        assert result['instance_id'] == 'i-12345'

    def test_ec2_deployer_get_status(self):
        """Test get_status returns current instance state."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_ec2 = MagicMock()
        mock_ec2.describe_instances.return_value = {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': 'i-12345',
                    'State': {'Name': 'running'},
                    'PublicIpAddress': '1.2.3.4'
                }]
            }]
        }

        def client_factory(service_name, **kwargs):
            if service_name == "ec2":
                return mock_ec2
            return MagicMock()

        mock_session.client.side_effect = client_factory

        from aws_ec2_deployer import AWSEC2Deployer
        deployer = AWSEC2Deployer(self.SAMPLE_USER_ID, self.SAMPLE_SESSION_ID)

        result = deployer.get_status('i-12345')

        assert result['instance_id'] == 'i-12345'
        assert result['state'] == 'running'
        assert result['public_ip'] == '1.2.3.4'
