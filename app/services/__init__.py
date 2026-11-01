"""Builds the storage and database objects selected by the configuration."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Services:
    storage: object    # save_file / delete_file / get_download_target
    users: object      # create / get_by_email
    resources: object  # create / get / delete / search / list_by_uploader / list_subjects


def build_services(config):
    local_root = Path(config["LOCAL_DATA_DIR"])

    if config["STORAGE_BACKEND"] == "s3":
        from .storage_service import S3Storage
        storage = S3Storage(config["S3_BUCKET_NAME"], config["AWS_REGION"])
    else:
        from .storage_service import LocalStorage
        storage = LocalStorage(local_root / "files")

    if config["DB_BACKEND"] == "dynamodb":
        from .dynamodb_service import DynamoResourceRepository, DynamoUserRepository
        users = DynamoUserRepository(config["DYNAMODB_USERS_TABLE"], config["AWS_REGION"])
        resources = DynamoResourceRepository(config["DYNAMODB_RESOURCES_TABLE"], config["AWS_REGION"])
    else:
        from .local_db_service import LocalResourceRepository, LocalUserRepository
        users = LocalUserRepository(local_root / "users.json")
        resources = LocalResourceRepository(local_root / "resources.json")

    return Services(storage=storage, users=users, resources=resources)
