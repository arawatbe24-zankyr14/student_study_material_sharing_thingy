"""Storage, local database and configuration checks (no Flask app needed)."""
import io
import time

import pytest

from app.config import ConfigError, validate_config
from app.services.common import build_resource_item, build_user_item, title_matches
from app.services.local_db_service import LocalResourceRepository, LocalUserRepository
from app.services.storage_service import LocalStorage, StorageError, generate_storage_key


def make_item(title="OS Unit 1", subject="OS", category="Lecture Notes", uploader="u1"):
    return build_resource_item(
        title=title, description="", subject=subject, category=category,
        uploader_id=uploader, uploader_name="Asha", s3_key="resources/u1/x.pdf",
        original_filename="x.pdf", file_type="pdf",
        content_type="application/pdf", file_size=10)


# ---------- storage ----------

def test_storage_keys_are_unique_and_well_formed():
    keys = {generate_storage_key("user1", "pdf") for _ in range(50)}
    assert len(keys) == 50
    assert all(k.startswith("resources/user1/") and k.endswith(".pdf") for k in keys)


def test_local_storage_save_download_delete(tmp_path):
    storage = LocalStorage(tmp_path)
    key = generate_storage_key("u1", "pdf")
    storage.save_file(io.BytesIO(b"hello"), key, "application/pdf")
    target = storage.get_download_target(key, "n.pdf", "application/pdf")
    assert open(target.path, "rb").read() == b"hello" and target.url is None
    storage.delete_file(key)
    storage.delete_file(key)                      # deleting twice is harmless
    with pytest.raises(StorageError):
        storage.get_download_target(key, "n.pdf", "application/pdf")


def test_local_storage_blocks_path_traversal(tmp_path):
    storage = LocalStorage(tmp_path / "files")
    with pytest.raises(StorageError):
        storage.save_file(io.BytesIO(b"x"), "../../evil.txt", "text/plain")


# ---------- items ----------

def test_resource_item_holds_metadata_not_file_content():
    item = make_item(title="  Spaced  ", subject="DBMS")
    assert item["title"] == "Spaced" and item["title_lower"] == "spaced"
    assert item["subject_key"] == "dbms" and item["s3_key"].startswith("resources/")
    assert item["gsi_all"] == "RESOURCE" and len(item["resource_id"]) == 32
    assert isinstance(item["file_size"], int) and item["uploaded_at"]


def test_title_matching_uses_every_word():
    item = make_item(title="Operating Systems Unit 1")
    assert title_matches(item, "unit operating")
    assert title_matches(item, "")
    assert not title_matches(item, "operating networks")


# ---------- local users ----------

def test_user_repository_rejects_duplicate_email(tmp_path):
    users = LocalUserRepository(tmp_path / "users.json")
    assert users.create(build_user_item("Asha", "Asha@x.com", "hash")) is True
    assert users.create(build_user_item("Other", "asha@X.com", "hash")) is False
    assert users.get_by_email("ASHA@x.com")["name"] == "Asha"
    assert users.get_by_email("nobody@x.com") is None


# ---------- local resources ----------

@pytest.fixture
def repo(tmp_path):
    repository = LocalResourceRepository(tmp_path / "resources.json")
    for title, subject, category, uploader in [
        ("Operating Systems Unit 1", "OS", "Lecture Notes", "u1"),
        ("DBMS ER Diagrams", "DBMS", "Lecture Notes", "u2"),
        ("OS Past Paper", "os", "Question Paper", "u1"),
    ]:
        repository.create(make_item(title, subject, category, uploader))
        time.sleep(0.002)                          # distinct timestamps
    return repository


def test_search_returns_newest_first(repo):
    assert [r["title"] for r in repo.search()][0] == "OS Past Paper"


def test_search_filters(repo):
    assert len(repo.search(subject="OS")) == 2                       # case-insensitive
    assert len(repo.search(category="Lecture Notes")) == 2
    assert len(repo.search(subject="os", category="Question Paper")) == 1
    assert [r["title"] for r in repo.search(query="DBMS")] == ["DBMS ER Diagrams"]
    assert repo.search(query="nothing like this") == []


def test_search_respects_limit(repo):
    assert len(repo.search(limit=2)) == 2


def test_subjects_and_uploader_listing(repo):
    assert repo.list_subjects() == ["DBMS", "OS"]                    # first spelling wins
    assert len(repo.list_by_uploader("u1")) == 2
    assert repo.list_by_uploader("nobody") == []


def test_get_and_delete(repo):
    resource_id = repo.search()[0]["resource_id"]
    assert repo.get(resource_id)["resource_id"] == resource_id
    repo.delete(resource_id)
    assert repo.get(resource_id) is None


# ---------- configuration safety ----------

PROD = {"APP_ENV": "production", "SECRET_KEY": "x" * 40, "STORAGE_BACKEND": "s3",
        "DB_BACKEND": "dynamodb", "S3_BUCKET_NAME": "my-bucket"}


def test_valid_production_config_passes():
    validate_config(dict(PROD))


@pytest.mark.parametrize("change", [
    {"SECRET_KEY": "short"},
    {"STORAGE_BACKEND": "local"},
    {"DB_BACKEND": "local"},
    {"S3_BUCKET_NAME": ""},
    {"STORAGE_BACKEND": "ftp"},
])
def test_unsafe_production_config_is_refused(change):
    with pytest.raises(ConfigError):
        validate_config(dict(PROD, **change))


def test_local_mode_gets_a_development_secret():
    cfg = {"APP_ENV": "local", "SECRET_KEY": "", "STORAGE_BACKEND": "local", "DB_BACKEND": "local"}
    validate_config(cfg)
    assert cfg["SECRET_KEY"]
