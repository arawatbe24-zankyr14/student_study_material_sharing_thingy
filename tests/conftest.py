"""Shared test helpers. Tests use the LOCAL backends only: no AWS, no network."""
import io
import zipfile
from pathlib import Path

import pytest

from app import create_app

PDF_BYTES = b"%PDF-1.4\n% test document\n"


def make_pptx_bytes():
    """The smallest ZIP that looks like a .pptx to our validator."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("ppt/presentation.xml", "<presentation/>")
    return buffer.getvalue()


def stored_files(app):
    """Every file currently in the (fake) storage folder."""
    root = Path(app.config["LOCAL_DATA_DIR"]) / "files"
    return [p for p in root.rglob("*") if p.is_file()]


@pytest.fixture
def make_app(tmp_path):
    def factory(**overrides):
        config = {
            "TESTING": True,
            "APP_ENV": "local",
            "SECRET_KEY": "test-secret-key",
            "STORAGE_BACKEND": "local",
            "DB_BACKEND": "local",
            "LOCAL_DATA_DIR": str(tmp_path / "data"),
            "MAX_UPLOAD_MB": 1,
            "MAX_CONTENT_LENGTH": 2 * 1024 * 1024,
            "MIN_PASSWORD_LENGTH": 8,
            "ALLOWED_EMAIL_DOMAIN": "",
        }
        config.update(overrides)
        return create_app(config)
    return factory


@pytest.fixture
def app(make_app):
    return make_app()


@pytest.fixture
def services(app):
    return app.extensions["services"]


class Browser:
    """A test browser that looks after cookies and CSRF tokens for us."""

    def __init__(self, app):
        self.client = app.test_client()

    def token(self):
        response = self.client.get("/login")
        if response.status_code == 302:      # already logged in
            self.client.get("/dashboard")
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def register(self, email, name="Test Student", password="password123", confirm=None):
        return self.client.post("/register", data={
            "csrf_token": self.token(), "name": name, "email": email,
            "password": password,
            "confirm_password": password if confirm is None else confirm})

    def login(self, email, password="password123", next_url=None):
        url = "/login" + (f"?next={next_url}" if next_url else "")
        return self.client.post(url, data={
            "csrf_token": self.token(), "email": email, "password": password})

    def sign_in(self, email, name="Test Student"):
        assert self.register(email, name=name).status_code == 302
        assert self.login(email).status_code == 302
        return self

    def logout(self, with_token=True):
        data = {"csrf_token": self.token()} if with_token else {}
        return self.client.post("/logout", data=data)

    def user_id(self):
        with self.client.session_transaction() as session:
            return session["user_id"]

    def upload(self, title="Operating Systems Unit 1", subject="Operating Systems",
               category="Lecture Notes", description="", content=PDF_BYTES,
               filename="notes.pdf", with_token=True):
        data = {"title": title, "subject": subject, "category": category,
                "description": description}
        if with_token:
            data["csrf_token"] = self.token()
        if content is not None:
            data["file"] = (io.BytesIO(content), filename)
        return self.client.post("/upload", data=data, content_type="multipart/form-data")

    def library(self, **params):
        response = self.client.get("/api/resources", query_string=params)
        return response.get_json()

    def delete(self, resource_id, with_token=True):
        headers = {"X-CSRF-Token": self.token()} if with_token else {}
        return self.client.delete(f"/api/resources/{resource_id}", headers=headers)

    def download(self, resource_id):
        return self.client.get(f"/resources/{resource_id}/download")


@pytest.fixture
def browser(app):
    return Browser(app)


@pytest.fixture
def other_browser(app):
    return Browser(app)
