"""File storage. S3Storage is used on AWS, LocalStorage on a laptop.

Both classes expose the same three methods, so the rest of the app never needs
to know which one it is talking to:
    save_file(fileobj, key, content_type)
    delete_file(key)
    get_download_target(key, download_name, content_type, expires_in)
"""
import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Raised when the storage layer cannot complete an operation."""


@dataclass
class DownloadTarget:
    """Either a presigned URL (S3) or a local file path (development)."""
    url: Optional[str] = None
    path: Optional[str] = None


def generate_storage_key(user_id, extension):
    """Unique key such as resources/<user_id>/<random-hex>.pdf (no filename collisions)."""
    return f"resources/{user_id}/{uuid.uuid4().hex}.{extension}"


def _header_filename(name):
    """Make a filename safe to place inside a Content-Disposition header."""
    cleaned = name.replace('"', "").replace("\\", "").replace("\r", "").replace("\n", "")
    return cleaned.encode("ascii", "ignore").decode() or "download"


class LocalStorage:
    """Development-only storage that writes into a local folder."""

    def __init__(self, root_dir):
        self.root = Path(root_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key):
        path = (self.root / key).resolve()
        if self.root not in path.parents:  # blocks keys like ../../etc/passwd
            raise StorageError("Invalid storage key.")
        return path

    def save_file(self, fileobj, key, content_type):
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "wb") as out:
                shutil.copyfileobj(fileobj, out)
        except OSError as exc:
            logger.exception("Local save failed")
            raise StorageError("Could not save the file.") from exc

    def delete_file(self, key):
        try:
            self._resolve(key).unlink(missing_ok=True)
        except OSError as exc:
            logger.exception("Local delete failed")
            raise StorageError("Could not delete the file.") from exc

    def get_download_target(self, key, download_name, content_type, expires_in=300):
        path = self._resolve(key)
        if not path.is_file():
            raise StorageError("The file could not be found in storage.")
        return DownloadTarget(path=str(path))


class S3Storage:
    """Private S3 bucket. Credentials come from the EC2 IAM role (no keys in code)."""

    def __init__(self, bucket, region):
        if not bucket:
            raise StorageError("S3_BUCKET_NAME is not configured.")
        import boto3
        from botocore.config import Config as BotoConfig

        self.bucket = bucket
        self.client = boto3.client("s3", region_name=region,
                                   config=BotoConfig(signature_version="s3v4"))

    def save_file(self, fileobj, key, content_type):
        from botocore.exceptions import BotoCoreError, ClientError
        try:
            self.client.upload_fileobj(
                fileobj, self.bucket, key,
                ExtraArgs={"ContentType": content_type, "ServerSideEncryption": "AES256"},
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("S3 upload failed")
            raise StorageError("Could not upload the file to cloud storage.") from exc

    def delete_file(self, key):
        from botocore.exceptions import BotoCoreError, ClientError
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)  # idempotent
        except (BotoCoreError, ClientError) as exc:
            logger.exception("S3 delete failed")
            raise StorageError("Could not delete the file from cloud storage.") from exc

    def get_download_target(self, key, download_name, content_type, expires_in=300):
        """Short-lived presigned GET URL. The bucket itself stays private."""
        from botocore.exceptions import BotoCoreError, ClientError
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self.bucket,
                    "Key": key,
                    "ResponseContentType": content_type,
                    "ResponseContentDisposition":
                        f'attachment; filename="{_header_filename(download_name)}"',
                },
                ExpiresIn=expires_in,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Presigned URL generation failed")
            raise StorageError("Could not create a download link.") from exc
        return DownloadTarget(url=url)
