"""
DynamoDB client for tracking AWS resources per user/project.

Stores deployment information including S3 buckets, CloudFront distributions,
and other AWS resources created for each project.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import boto3
from botocore.exceptions import ClientError

from config import AWS_ROOT_PROFILE, AWS_DEFAULT_REGION

logger = logging.getLogger(__name__)

# DynamoDB table name
DYNAMODB_TABLE_NAME = "tmux-deployments"


class DynamoDBClient:
    """Client for storing and retrieving project AWS resources in DynamoDB."""

    def __init__(
        self,
        table_name: str = DYNAMODB_TABLE_NAME,
        region: str = AWS_DEFAULT_REGION,
        profile: str = AWS_ROOT_PROFILE
    ):
        """
        Initialize DynamoDB client.

        Args:
            table_name: DynamoDB table name
            region: AWS region
            profile: AWS profile name
        """
        self.table_name = table_name
        self.region = region
        self.profile = profile
        self._dynamodb = None
        self._table = None

    @property
    def dynamodb(self):
        """Lazy-load DynamoDB resource."""
        if self._dynamodb is None:
            session = boto3.Session(
                profile_name=self.profile,
                region_name=self.region
            )
            self._dynamodb = session.resource('dynamodb')
        return self._dynamodb

    @property
    def table(self):
        """Lazy-load DynamoDB table."""
        if self._table is None:
            self._table = self.dynamodb.Table(self.table_name)
        return self._table

    def ensure_table_exists(self) -> bool:
        """
        Create the DynamoDB table if it doesn't exist.

        Returns:
            True if table exists or was created, False on error
        """
        try:
            # Check if table exists
            self.table.load()
            logger.info(f"DynamoDB table '{self.table_name}' exists")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                # Create the table
                logger.info(f"Creating DynamoDB table '{self.table_name}'...")
                try:
                    session = boto3.Session(
                        profile_name=self.profile,
                        region_name=self.region
                    )
                    client = session.client('dynamodb')
                    client.create_table(
                        TableName=self.table_name,
                        AttributeDefinitions=[
                            {'AttributeName': 'userId', 'AttributeType': 'S'},
                            {'AttributeName': 'projectId', 'AttributeType': 'S'}
                        ],
                        KeySchema=[
                            {'AttributeName': 'userId', 'KeyType': 'HASH'},
                            {'AttributeName': 'projectId', 'KeyType': 'RANGE'}
                        ],
                        BillingMode='PAY_PER_REQUEST',
                        Tags=[
                            {'Key': 'Project', 'Value': 'tmux-builder'},
                            {'Key': 'ManagedBy', 'Value': 'tmux-builder'}
                        ]
                    )
                    # Wait for table to be created
                    waiter = client.get_waiter('table_exists')
                    waiter.wait(TableName=self.table_name)
                    logger.info(f"DynamoDB table '{self.table_name}' created successfully")
                    # Reset table reference to pick up new table
                    self._table = None
                    return True
                except Exception as create_error:
                    logger.error(f"Failed to create DynamoDB table: {create_error}")
                    return False
            else:
                logger.error(f"Error checking DynamoDB table: {e}")
                return False

    def save_project_resources(
        self,
        user_id: str,
        project_id: str,
        project_name: str,
        aws_resources: Dict[str, Any],
        email: str = ""
    ) -> bool:
        """
        Save or update project AWS resources.

        Args:
            user_id: User identifier (email or ID)
            project_id: Project GUID
            project_name: Human-readable project name
            aws_resources: Dict of AWS resources (s3Bucket, cloudFrontId, etc.)
            email: User email

        Returns:
            True if successful, False otherwise
        """
        try:
            now = datetime.now(timezone.utc).isoformat()

            # Check if item exists
            existing = self.get_project_resources(user_id, project_id)

            item = {
                'userId': user_id,
                'projectId': project_id,
                'projectName': project_name,
                'email': email,
                'awsResources': aws_resources,
                'updatedAt': now
            }

            if existing:
                # Update - preserve createdAt
                item['createdAt'] = existing.get('createdAt', now)
                # Merge resources (keep old ones, add new ones)
                merged_resources = existing.get('awsResources', {})
                merged_resources.update(aws_resources)
                item['awsResources'] = merged_resources
            else:
                item['createdAt'] = now

            self.table.put_item(Item=item)
            logger.info(f"Saved resources for project {project_id}: {list(aws_resources.keys())}")
            return True

        except Exception as e:
            logger.error(f"DynamoDB error saving resources: {e}")
            return False

    def get_project_resources(self, user_id: str, project_id: str) -> Optional[Dict]:
        """
        Get resources for a specific project.

        Args:
            user_id: User identifier
            project_id: Project GUID

        Returns:
            Project data dict or None if not found
        """
        try:
            response = self.table.get_item(Key={
                'userId': user_id,
                'projectId': project_id
            })
            return response.get('Item')
        except Exception as e:
            logger.error(f"DynamoDB error getting resources: {e}")
            return None

    def get_user_projects(self, user_id: str) -> List[Dict]:
        """
        Get all projects for a user.

        Args:
            user_id: User identifier

        Returns:
            List of project data dicts
        """
        try:
            response = self.table.query(
                KeyConditionExpression='userId = :uid',
                ExpressionAttributeValues={':uid': user_id}
            )
            return response.get('Items', [])
        except Exception as e:
            logger.error(f"DynamoDB error getting user projects: {e}")
            return []

    def update_resources(
        self,
        user_id: str,
        project_id: str,
        aws_resources: Dict[str, Any]
    ) -> bool:
        """
        Update AWS resources for existing project (merge with existing).

        Args:
            user_id: User identifier
            project_id: Project GUID
            aws_resources: New AWS resources to merge

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get existing resources first
            existing = self.get_project_resources(user_id, project_id)
            if not existing:
                logger.warning(f"Project {project_id} not found for update")
                return False

            # Merge resources
            merged = existing.get('awsResources', {})
            merged.update(aws_resources)

            self.table.update_item(
                Key={
                    'userId': user_id,
                    'projectId': project_id
                },
                UpdateExpression='SET awsResources = :res, updatedAt = :upd',
                ExpressionAttributeValues={
                    ':res': merged,
                    ':upd': datetime.now(timezone.utc).isoformat()
                }
            )
            logger.info(f"Updated resources for project {project_id}")
            return True

        except Exception as e:
            logger.error(f"DynamoDB error updating resources: {e}")
            return False

    def delete_project(self, user_id: str, project_id: str) -> bool:
        """
        Delete a project record.

        Args:
            user_id: User identifier
            project_id: Project GUID

        Returns:
            True if successful, False otherwise
        """
        try:
            self.table.delete_item(Key={
                'userId': user_id,
                'projectId': project_id
            })
            logger.info(f"Deleted project {project_id} from DynamoDB")
            return True
        except Exception as e:
            logger.error(f"DynamoDB error deleting project: {e}")
            return False

    def get_all_resources_by_guid(self, project_id: str) -> Optional[Dict]:
        """
        Get project resources by GUID only (scans table).
        Use sparingly - prefer user_id + project_id lookup.

        Args:
            project_id: Project GUID

        Returns:
            Project data dict or None
        """
        try:
            response = self.table.scan(
                FilterExpression='projectId = :pid',
                ExpressionAttributeValues={':pid': project_id}
            )
            items = response.get('Items', [])
            return items[0] if items else None
        except Exception as e:
            logger.error(f"DynamoDB error scanning for project: {e}")
            return None


# Global instance (lazy-loaded)
_dynamo_client: Optional[DynamoDBClient] = None


def get_dynamo_client() -> DynamoDBClient:
    """Get or create the global DynamoDB client."""
    global _dynamo_client
    if _dynamo_client is None:
        _dynamo_client = DynamoDBClient()
    return _dynamo_client
