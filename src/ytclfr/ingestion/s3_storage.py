"""S3 object storage manager for distributed media transport.

Replaces local filesystem coupling between Celery workers (DR-18).
Videos are uploaded after ingestion and downloaded before extraction.
"""

from pathlib import Path

import boto3

from ytclfr.core.config import Settings
from ytclfr.core.logging import get_logger

logger = get_logger(__name__)


class S3StorageError(Exception):
    """Raised when an S3 operation fails."""


class S3StorageManager:
    """Manages S3 uploads and downloads for video media files."""

    def __init__(self, settings: Settings) -> None:
        if not settings.s3_bucket_name:
            raise S3StorageError(
                "S3_BUCKET_NAME is not configured. "
                "Cannot use S3 storage without a bucket."
            )
        self.bucket_name = settings.s3_bucket_name
        self._client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    def upload_file(self, file_path: Path, object_key: str) -> str:
        """Upload a local file to S3.

        Args:
            file_path: Absolute path to the local file.
            object_key: S3 object key (e.g. "{job_id}/video.mp4").

        Returns:
            S3 URI string: "s3://{bucket}/{object_key}"

        Raises:
            S3StorageError: If the upload fails.
        """
        try:
            self._client.upload_file(
                str(file_path),
                self.bucket_name,
                object_key,
            )
            s3_uri = f"s3://{self.bucket_name}/{object_key}"
            logger.info(
                "Uploaded %s to %s",
                file_path.name,
                s3_uri,
            )
            return s3_uri
        except Exception as exc:
            raise S3StorageError(
                f"Failed to upload {file_path} to "
                f"s3://{self.bucket_name}/{object_key}: {exc}"
            ) from exc

    def download_file(self, object_key: str, download_path: Path) -> None:
        """Download a file from S3 to a local path.

        Args:
            object_key: S3 object key to download.
            download_path: Local path to write the file to.

        Raises:
            S3StorageError: If the download fails.
        """
        try:
            download_path.parent.mkdir(parents=True, exist_ok=True)
            self._client.download_file(
                self.bucket_name,
                object_key,
                str(download_path),
            )
            logger.info(
                "Downloaded s3://%s/%s to %s",
                self.bucket_name,
                object_key,
                download_path,
            )
        except Exception as exc:
            raise S3StorageError(
                f"Failed to download s3://{self.bucket_name}/{object_key}: {exc}"
            ) from exc

    def delete_directory(self, prefix: str) -> None:
        """Deletes all objects with a specific prefix (simulates directory deletion)."""
        try:
            paginator = self._client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            delete_us = dict(Objects=[])
            
            for item in pages.search('Contents'):
                if item:
                    delete_us['Objects'].append({'Key': item['Key']})
                    # S3 allows deleting max 1000 objects per request
                    if len(delete_us['Objects']) >= 1000:
                        self._client.delete_objects(Bucket=self.bucket_name, Delete=delete_us)
                        delete_us = dict(Objects=[])
                        
            if len(delete_us['Objects']):
                self._client.delete_objects(Bucket=self.bucket_name, Delete=delete_us)
                
            logger.info("Successfully cleaned up S3 prefix: %s", prefix)
        except Exception as e:
            logger.error("Failed to clean up S3 prefix %s: %s", prefix, e)
            raise S3StorageError(f"Cleanup failed: {e}")
