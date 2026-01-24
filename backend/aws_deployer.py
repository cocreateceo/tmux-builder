"""AWS Static Deployer for S3 + CloudFront static website deployment.

Deploys static websites to S3 with CloudFront CDN distribution,
using the sunwaretech AWS profile for authentication.
"""

import boto3
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

from cloud_config import CloudConfig


class AWSStaticDeployer:
    """Deploy static websites to AWS S3 with CloudFront CDN.

    Uses the sunwaretech AWS profile and CloudConfig for resource
    naming and tagging conventions.
    """

    def __init__(
        self,
        user_id: str,
        session_id: str,
        region: Optional[str] = None
    ):
        """Initialize the AWS static deployer.

        Args:
            user_id: User GUID for resource naming and tagging
            session_id: Session identifier for resource naming and tagging
            region: AWS region (defaults to CloudConfig.AWS_DEFAULT_REGION)
        """
        self.user_id = user_id
        self.session_id = session_id
        self.region = region or CloudConfig.AWS_DEFAULT_REGION
        self.profile = CloudConfig.AWS_PROFILE

        # Generate bucket name using CloudConfig naming convention
        self.bucket_name = CloudConfig.get_resource_name(
            user_id=user_id,
            session_id=session_id,
            resource_type="s3"
        )

        # Lazy-loaded clients
        self._session: Optional[boto3.Session] = None
        self._s3_client = None
        self._cf_client = None

    @property
    def s3_client(self):
        """Lazy-loaded S3 client with profile authentication."""
        if self._s3_client is None:
            if self._session is None:
                self._session = boto3.Session(profile_name=self.profile)
            self._s3_client = self._session.client("s3")
        return self._s3_client

    @property
    def cf_client(self):
        """Lazy-loaded CloudFront client with profile authentication."""
        if self._cf_client is None:
            if self._session is None:
                self._session = boto3.Session(profile_name=self.profile)
            self._cf_client = self._session.client("cloudfront")
        return self._cf_client

    def deploy(self, source_dir: str) -> Dict[str, str]:
        """Deploy a static website to S3 with CloudFront.

        Creates an S3 bucket, uploads all files, configures static
        website hosting, and creates a CloudFront distribution.

        Args:
            source_dir: Path to directory containing static website files

        Returns:
            Dictionary with deployment details:
            - url: CloudFront URL for the deployed site
            - bucket: S3 bucket name
            - distribution_id: CloudFront distribution ID
            - region: AWS region
        """
        # Create the S3 bucket
        self._create_bucket()

        # Upload all files from source directory
        self._upload_files(source_dir)

        # Create CloudFront distribution
        cf_result = self._create_cloudfront_distribution()

        return {
            "url": cf_result["url"],
            "bucket": self.bucket_name,
            "distribution_id": cf_result["distribution_id"],
            "region": self.region
        }

    def redeploy(
        self,
        source_dir: str,
        distribution_id: str
    ) -> Dict[str, str]:
        """Update an existing deployment with new files.

        Re-uploads all files and invalidates the CloudFront cache.

        Args:
            source_dir: Path to directory containing static website files
            distribution_id: Existing CloudFront distribution ID

        Returns:
            Dictionary with:
            - url: CloudFront URL
            - invalidation_id: CloudFront cache invalidation ID
        """
        # Upload updated files
        self._upload_files(source_dir)

        # Invalidate the CloudFront cache
        invalidation_result = self.invalidate_cache(distribution_id)

        # Get the distribution domain name
        distribution = self.cf_client.get_distribution(Id=distribution_id)
        domain_name = distribution["Distribution"]["DomainName"]

        return {
            "url": f"https://{domain_name}",
            "invalidation_id": invalidation_result["invalidation_id"]
        }

    def invalidate_cache(
        self,
        distribution_id: str,
        paths: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Invalidate CloudFront cache for specified paths.

        Args:
            distribution_id: CloudFront distribution ID
            paths: List of paths to invalidate (defaults to ["/*"])

        Returns:
            Dictionary with invalidation_id
        """
        if paths is None:
            paths = ["/*"]

        # Create a unique caller reference for the invalidation
        caller_reference = f"invalidation-{uuid.uuid4()}"

        response = self.cf_client.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                "Paths": {
                    "Quantity": len(paths),
                    "Items": paths
                },
                "CallerReference": caller_reference
            }
        )

        return {
            "invalidation_id": response["Invalidation"]["Id"]
        }

    def _create_bucket(self) -> None:
        """Create S3 bucket with static website hosting enabled.

        Creates the bucket, enables static website hosting,
        sets public access policy, and applies tags.
        """
        # Create the bucket
        # Note: us-east-1 doesn't require LocationConstraint
        if self.region == "us-east-1":
            self.s3_client.create_bucket(Bucket=self.bucket_name)
        else:
            self.s3_client.create_bucket(
                Bucket=self.bucket_name,
                CreateBucketConfiguration={
                    "LocationConstraint": self.region
                }
            )

        # Enable static website hosting
        self.s3_client.put_bucket_website(
            Bucket=self.bucket_name,
            WebsiteConfiguration={
                "IndexDocument": {"Suffix": "index.html"},
                "ErrorDocument": {"Key": "error.html"}
            }
        )

        # Disable block public access for static website
        self.s3_client.put_public_access_block(
            Bucket=self.bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False
            }
        )

        # Set bucket policy for public read access
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{self.bucket_name}/*"
                }
            ]
        }

        import json
        self.s3_client.put_bucket_policy(
            Bucket=self.bucket_name,
            Policy=json.dumps(bucket_policy)
        )

        # Apply tags using CloudConfig
        tags = CloudConfig.get_tags(
            user_id=self.user_id,
            session_id=self.session_id,
            site_type="static"
        )
        aws_tags = CloudConfig.get_aws_tags_list(tags)

        self.s3_client.put_bucket_tagging(
            Bucket=self.bucket_name,
            Tagging={"TagSet": aws_tags}
        )

    def _upload_files(self, source_dir: str) -> List[str]:
        """Upload all files from source directory to S3 bucket.

        Recursively uploads all files, preserving directory structure
        and setting appropriate content-types.

        Args:
            source_dir: Path to source directory

        Returns:
            List of uploaded file keys
        """
        source_path = Path(source_dir)
        uploaded_keys = []

        for file_path in source_path.rglob("*"):
            if file_path.is_file():
                # Calculate relative path for S3 key
                relative_path = file_path.relative_to(source_path)
                s3_key = str(relative_path).replace("\\", "/")  # Handle Windows paths

                # Determine content type
                content_type, _ = mimetypes.guess_type(str(file_path))
                if content_type is None:
                    content_type = "application/octet-stream"

                # Read file content
                with open(file_path, "rb") as f:
                    file_content = f.read()

                # Upload to S3
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=file_content,
                    ContentType=content_type
                )

                uploaded_keys.append(s3_key)

        return uploaded_keys

    def _create_cloudfront_distribution(self) -> Dict[str, str]:
        """Create CloudFront distribution for the S3 bucket.

        Creates a distribution with the S3 bucket as origin,
        applies tags, and returns distribution details.

        Returns:
            Dictionary with:
            - distribution_id: CloudFront distribution ID
            - url: HTTPS URL of the distribution
        """
        # S3 website endpoint as origin
        s3_origin_domain = f"{self.bucket_name}.s3-website-{self.region}.amazonaws.com"

        # Generate unique caller reference
        caller_reference = f"tmux-{self.user_id[:8]}-{self.session_id}-{uuid.uuid4()}"

        # Get tags for the distribution
        tags = CloudConfig.get_tags(
            user_id=self.user_id,
            session_id=self.session_id,
            site_type="static"
        )
        aws_tags = CloudConfig.get_aws_tags_list(tags)

        # Create the CloudFront distribution
        response = self.cf_client.create_distribution(
            DistributionConfig={
                "CallerReference": caller_reference,
                "Comment": f"tmux-builder distribution for {self.session_id}",
                "Enabled": True,
                "Origins": {
                    "Quantity": 1,
                    "Items": [
                        {
                            "Id": f"S3-{self.bucket_name}",
                            "DomainName": s3_origin_domain,
                            "CustomOriginConfig": {
                                "HTTPPort": 80,
                                "HTTPSPort": 443,
                                "OriginProtocolPolicy": "http-only",
                                "OriginSslProtocols": {
                                    "Quantity": 1,
                                    "Items": ["TLSv1.2"]
                                }
                            }
                        }
                    ]
                },
                "DefaultCacheBehavior": {
                    "TargetOriginId": f"S3-{self.bucket_name}",
                    "ViewerProtocolPolicy": "redirect-to-https",
                    "AllowedMethods": {
                        "Quantity": 2,
                        "Items": ["GET", "HEAD"],
                        "CachedMethods": {
                            "Quantity": 2,
                            "Items": ["GET", "HEAD"]
                        }
                    },
                    "ForwardedValues": {
                        "QueryString": False,
                        "Cookies": {"Forward": "none"}
                    },
                    "TrustedSigners": {
                        "Enabled": False,
                        "Quantity": 0
                    },
                    "MinTTL": 0,
                    "DefaultTTL": 86400,
                    "MaxTTL": 31536000
                },
                "DefaultRootObject": "index.html",
                "PriceClass": "PriceClass_100"
            }
        )

        distribution_id = response["Distribution"]["Id"]
        domain_name = response["Distribution"]["DomainName"]

        # Apply tags to the distribution
        self.cf_client.tag_resource(
            Resource=f"arn:aws:cloudfront::{self._get_account_id()}:distribution/{distribution_id}",
            Tags={"Items": aws_tags}
        )

        return {
            "distribution_id": distribution_id,
            "url": f"https://{domain_name}"
        }

    def _get_account_id(self) -> str:
        """Get the AWS account ID for the current profile.

        Returns:
            AWS account ID string
        """
        sts_client = self._session.client("sts")
        return sts_client.get_caller_identity()["Account"]
