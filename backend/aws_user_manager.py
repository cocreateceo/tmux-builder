"""
AWS IAM User Manager for per-session isolated deployments.

Creates temporary IAM users with GUID-scoped permissions so each session
can only access resources prefixed with their own GUID.
"""

import json
import logging
import boto3
from botocore.config import Config
from pathlib import Path
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

from config import PROJECT_ROOT

# AWS API timeout configuration (seconds)
AWS_CONNECT_TIMEOUT = 10
AWS_READ_TIMEOUT = 30

logger = logging.getLogger(__name__)

# Policy template path
POLICY_TEMPLATE_PATH = PROJECT_ROOT / "backend" / "scripts" / "user_policy_template.json"


class AWSUserManager:
    """Manages per-session IAM users with GUID-scoped permissions."""

    def __init__(self, root_profile: str = "cocreate", region: str = "us-east-1"):
        """
        Initialize AWS User Manager.

        Args:
            root_profile: AWS profile name with IAM management permissions
            region: AWS region for resources
        """
        self.root_profile = root_profile
        self.region = region
        self._session = None
        self._iam_client = None

    @property
    def session(self):
        """Lazy-load boto3 session with root profile."""
        if self._session is None:
            self._session = boto3.Session(
                profile_name=self.root_profile,
                region_name=self.region
            )
        return self._session

    @property
    def iam_client(self):
        """Lazy-load IAM client with timeout configuration."""
        if self._iam_client is None:
            config = Config(
                connect_timeout=AWS_CONNECT_TIMEOUT,
                read_timeout=AWS_READ_TIMEOUT,
                retries={'max_attempts': 3}
            )
            self._iam_client = self.session.client('iam', config=config)
        return self._iam_client

    def _get_user_name(self, guid: str) -> str:
        """Generate IAM user name from GUID (first 12 chars)."""
        return f"tmux-user-{guid[:12]}"

    def _get_policy_name(self, guid: str) -> str:
        """Generate policy name from GUID."""
        return f"tmux-policy-{guid[:12]}"

    def _load_policy_template(self) -> dict:
        """Load the IAM policy template."""
        if not POLICY_TEMPLATE_PATH.exists():
            raise FileNotFoundError(f"Policy template not found: {POLICY_TEMPLATE_PATH}")

        return json.loads(POLICY_TEMPLATE_PATH.read_text())

    def _render_policy(self, guid: str) -> str:
        """
        Render policy template with GUID substitution.

        Args:
            guid: Session GUID to scope resources

        Returns:
            JSON string of rendered policy
        """
        template = self._load_policy_template()

        # Convert to string, replace ${guid} placeholders, convert back
        policy_str = json.dumps(template)
        policy_str = policy_str.replace("${guid}", guid[:12])

        return policy_str

    async def create_user_for_session(self, guid: str) -> Dict[str, Any]:
        """
        Create IAM user with limited permissions for this session.

        Args:
            guid: Session GUID

        Returns:
            Dictionary with access_key_id, secret_access_key, user_name
        """
        user_name = self._get_user_name(guid)
        policy_name = self._get_policy_name(guid)

        try:
            # Step 1: Create IAM user
            logger.info(f"Creating IAM user: {user_name}")
            try:
                self.iam_client.create_user(
                    UserName=user_name,
                    Tags=[
                        {'Key': 'guid', 'Value': guid},
                        {'Key': 'created-by', 'Value': 'tmux-builder'},
                        {'Key': 'Project', 'Value': 'tmux-builder'}
                    ]
                )
            except ClientError as e:
                if e.response['Error']['Code'] == 'EntityAlreadyExists':
                    logger.info(f"User {user_name} already exists, will reuse")
                else:
                    raise

            # Step 2: Create and attach inline policy
            logger.info(f"Attaching policy: {policy_name}")
            policy_document = self._render_policy(guid)

            try:
                self.iam_client.put_user_policy(
                    UserName=user_name,
                    PolicyName=policy_name,
                    PolicyDocument=policy_document
                )
            except ClientError as e:
                logger.error(f"Failed to attach policy: {e}")
                raise

            # Step 3: Create access keys
            logger.info(f"Creating access keys for {user_name}")

            # First, delete any existing keys (limit is 2 per user)
            try:
                existing_keys = self.iam_client.list_access_keys(UserName=user_name)
                for key in existing_keys.get('AccessKeyMetadata', []):
                    self.iam_client.delete_access_key(
                        UserName=user_name,
                        AccessKeyId=key['AccessKeyId']
                    )
            except ClientError:
                pass  # Ignore errors deleting old keys

            # Create new access key
            response = self.iam_client.create_access_key(UserName=user_name)
            access_key = response['AccessKey']

            credentials = {
                'user_name': user_name,
                'access_key_id': access_key['AccessKeyId'],
                'secret_access_key': access_key['SecretAccessKey'],
                'region': self.region,
                'guid': guid
            }

            logger.info(f"Successfully created IAM user and credentials for session {guid}")
            return credentials

        except Exception as e:
            logger.error(f"Failed to create IAM user for session {guid}: {e}")
            raise

    async def get_or_create_credentials(self, guid: str, session_path: Path) -> Dict[str, Any]:
        """
        Get existing credentials or create new user.

        Args:
            guid: Session GUID
            session_path: Path to session directory

        Returns:
            Dictionary with AWS credentials
        """
        creds_file = session_path / ".aws_credentials"

        # Check if credentials already exist
        if creds_file.exists():
            try:
                existing_creds = json.loads(creds_file.read_text())
                if existing_creds.get('guid') == guid:
                    logger.info(f"Using existing AWS credentials for session {guid}")
                    return existing_creds
            except (json.JSONDecodeError, IOError):
                pass  # Will create new credentials

        # Create new user and credentials
        credentials = await self.create_user_for_session(guid)

        # Store credentials in session folder
        creds_file.write_text(json.dumps(credentials, indent=2))
        logger.info(f"Stored AWS credentials at {creds_file}")

        return credentials

    def get_credentials_from_session(self, session_path: Path) -> Optional[Dict[str, Any]]:
        """
        Read existing credentials from session folder (synchronous).

        Args:
            session_path: Path to session directory

        Returns:
            Credentials dict or None if not found
        """
        creds_file = session_path / ".aws_credentials"

        if not creds_file.exists():
            return None

        try:
            return json.loads(creds_file.read_text())
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read credentials: {e}")
            return None

    def delete_user(self, guid: str) -> bool:
        """
        Delete IAM user and all associated resources.

        Args:
            guid: Session GUID

        Returns:
            True if successful, False otherwise
        """
        user_name = self._get_user_name(guid)
        policy_name = self._get_policy_name(guid)

        try:
            # Delete inline policies
            try:
                self.iam_client.delete_user_policy(
                    UserName=user_name,
                    PolicyName=policy_name
                )
            except ClientError:
                pass  # Policy might not exist

            # Delete access keys
            try:
                keys = self.iam_client.list_access_keys(UserName=user_name)
                for key in keys.get('AccessKeyMetadata', []):
                    self.iam_client.delete_access_key(
                        UserName=user_name,
                        AccessKeyId=key['AccessKeyId']
                    )
            except ClientError:
                pass

            # Delete user
            self.iam_client.delete_user(UserName=user_name)
            logger.info(f"Deleted IAM user: {user_name}")
            return True

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                logger.info(f"User {user_name} does not exist")
                return True
            logger.error(f"Failed to delete IAM user {user_name}: {e}")
            return False

    def user_exists(self, guid: str) -> bool:
        """Check if IAM user exists for this GUID."""
        user_name = self._get_user_name(guid)
        try:
            self.iam_client.get_user(UserName=user_name)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                return False
            raise
