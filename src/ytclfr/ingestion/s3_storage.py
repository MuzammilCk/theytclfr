"""S3 object storage manager for distributed media transport.

Replaces local filesystem coupling between Celery workers (DR-18).
Videos are uploaded after ingestion and downloaded before extraction.
"""

from pathlib import Path

import boto3
from botocore.config import Config

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
        config = Config(
            connect_timeout=30,
            read_timeout=120,
            retries={
                "max_attempts": 5,
                "mode": "adaptive",
            },
            max_pool_connections=10,
        )
        self._client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
            config=config,
        )

    def upload_file(self, file_path: Path, object_key: str) -> str:
        """Upload a local file to S3 with adaptive transfer config.

        - Files under 25MB: single PUT (no multipart overhead)
        - Files over 25MB: multipart with 10MB chunks and 4x parallelism

        Args:
            file_path: Absolute path to the local file.
            object_key: S3 object key (e.g. "{job_id}/video.mp4").

        Returns:
            S3 URI string: "s3://{bucket}/{object_key}"

        Raises:
            S3StorageError: If the upload fails.
        """
        import os

        from boto3.s3.transfer import TransferConfig

        try:
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)

            # Adaptive multipart: skip multipart for small files,
            # use larger chunks + parallelism for large files.
            if file_size_mb < 25:
                # Single PUT — no multipart overhead, no part-ACK latency
                transfer_config = TransferConfig(
                    multipart_threshold=100 * 1024 * 1024,  # 100MB = effectively disabled
                    max_concurrency=1,
                    use_threads=False,
                )
            else:
                # Multipart with 10MB chunks and 4-way parallel upload
                transfer_config = TransferConfig(
                    multipart_threshold=25 * 1024 * 1024,
                    multipart_chunksize=10 * 1024 * 1024,
                    max_concurrency=4,
                    use_threads=True,
                )

            logger.info(
                "S3 upload starting: %s (%.1f MB, multipart=%s)",
                file_path.name,
                file_size_mb,
                "yes" if file_size_mb >= 25 else "no",
            )

            class ProgressPercentage:
                def __init__(self, filename: str, size: int) -> None:
                    self._filename = filename
                    self._size = size
                    self._seen_so_far = 0
                    self._last_logged_percentage = 0.0

                def __call__(self, bytes_amount: int) -> None:
                    self._seen_so_far += bytes_amount
                    if self._size > 0:
                        percentage = (self._seen_so_far / self._size) * 100
                        if percentage - self._last_logged_percentage >= 10:
                            logger.info(
                                "S3 Upload %s: %.1f%% complete",
                                self._filename,
                                percentage,
                            )
                            self._last_logged_percentage = percentage

            self._client.upload_file(
                str(file_path),
                self.bucket_name,
                object_key,
                Callback=ProgressPercentage(file_path.name, file_size),
                Config=transfer_config,
            )
            s3_uri = f"s3://{self.bucket_name}/{object_key}"
            logger.info(
                "Uploaded %s to %s (%.1f MB)",
                file_path.name,
                s3_uri,
                file_size_mb,
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
