"""Central configuration. Every value comes from environment variables (.env)."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class ConfigError(Exception):
    """Raised when the configuration is unsafe or incomplete."""


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _local_dir(value):
    path = Path(value)
    return str(path if path.is_absolute() else BASE_DIR / path)


class Config:
    APP_ENV = os.getenv("APP_ENV", "local").strip().lower()
    _prod = APP_ENV == "production"

    SECRET_KEY = os.getenv("SECRET_KEY", "")

    # Backends: "local" for laptop development, "s3"/"dynamodb" for AWS.
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "s3" if _prod else "local").strip().lower()
    DB_BACKEND = os.getenv("DB_BACKEND", "dynamodb" if _prod else "local").strip().lower()
    LOCAL_DATA_DIR = _local_dir(os.getenv("LOCAL_DATA_DIR", "local_data"))

    # AWS settings
    AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
    DYNAMODB_USERS_TABLE = os.getenv("DYNAMODB_USERS_TABLE", "notes_platform_users")
    DYNAMODB_RESOURCES_TABLE = os.getenv("DYNAMODB_RESOURCES_TABLE", "notes_platform_resources")

    # Uploads
    MAX_UPLOAD_MB = _env_int("MAX_UPLOAD_MB", 20)
    # Flask rejects bigger requests with HTTP 413 (+1 MB allowance for form fields)
    MAX_CONTENT_LENGTH = (MAX_UPLOAD_MB + 1) * 1024 * 1024
    PRESIGNED_URL_EXPIRY_SECONDS = _env_int("PRESIGNED_URL_EXPIRY_SECONDS", 300)

    # Authentication
    AUTH_PROVIDER = "session"  # a future "cognito" provider would plug in here
    MIN_PASSWORD_LENGTH = _env_int("MIN_PASSWORD_LENGTH", 8)
    ALLOWED_EMAIL_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "").strip().lower().lstrip("@")
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=_env_int("SESSION_LIFETIME_HOURS", 8))


DEV_SECRET_KEY = "dev-only-secret-key-never-use-in-production"


def validate_config(cfg):
    """Check a Flask config mapping. Raises ConfigError on unsafe settings."""
    production = cfg.get("APP_ENV") == "production"

    if cfg.get("STORAGE_BACKEND") not in {"local", "s3"}:
        raise ConfigError("STORAGE_BACKEND must be 'local' or 's3'.")
    if cfg.get("DB_BACKEND") not in {"local", "dynamodb"}:
        raise ConfigError("DB_BACKEND must be 'local' or 'dynamodb'.")

    if production:
        if len(cfg.get("SECRET_KEY", "")) < 32:
            raise ConfigError("Production needs SECRET_KEY of at least 32 characters.")
        if cfg["STORAGE_BACKEND"] != "s3" or cfg["DB_BACKEND"] != "dynamodb":
            raise ConfigError("Production must use STORAGE_BACKEND=s3 and DB_BACKEND=dynamodb.")
    elif not cfg.get("SECRET_KEY"):
        cfg["SECRET_KEY"] = DEV_SECRET_KEY  # convenience for laptops only

    if cfg["STORAGE_BACKEND"] == "s3" and not cfg.get("S3_BUCKET_NAME"):
        raise ConfigError("S3_BUCKET_NAME is required when STORAGE_BACKEND=s3.")
