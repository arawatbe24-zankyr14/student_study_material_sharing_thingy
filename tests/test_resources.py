"""Upload, metadata, library search, download, delete and permissions."""
from pathlib import Path

from app.services.common import DatabaseError
from app.services.storage_service import StorageError
from tests.conftest import PDF_BYTES, make_pptx_bytes, stored_files


# ---------- upload ----------

def test_upload_requires_login(browser, app, services):
    response = browser.upload()
    assert response.status_code == 302 and "/login" in response.location
    assert stored_files(app) == [] and services.resources.search() == []


def test_upload_stores_file_and_metadata(browser, app, services):
    browser.sign_in("asha@x.com", name="Asha")
    response = browser.upload(title="OS Unit 1", subject="Operating Systems",
                              category="Lecture Notes", description="Scheduling")
    assert response.status_code == 302 and response.location.endswith("/library")

    item = services.resources.search()[0]
    assert item["title"] == "OS Unit 1" and item["subject"] == "Operating Systems"
    assert item["category"] == "Lecture Notes" and item["description"] == "Scheduling"
    assert item["uploader_id"] == browser.user_id() and item["uploader_name"] == "Asha"
    assert item["file_type"] == "pdf" and item["file_size"] == len(PDF_BYTES)
    assert item["s3_key"].startswith(f"resources/{browser.user_id()}/") and item["s3_key"].endswith(".pdf")
    assert item["uploaded_at"]
    target = services.storage.get_download_target(item["s3_key"], "x.pdf", "application/pdf")
    assert Path(target.path).read_bytes() == PDF_BYTES


def test_same_filename_twice_gets_different_keys(browser, services):
    browser.sign_in("asha@x.com")
    browser.upload(title="First copy")
    browser.upload(title="Second copy")
    keys = {item["s3_key"] for item in services.resources.search()}
    assert len(keys) == 2


def test_pptx_upload_accepted(browser, services):
    browser.sign_in("asha@x.com")
    response = browser.upload(content=make_pptx_bytes(), filename="slides.pptx")
    assert response.status_code == 302
    assert services.resources.search()[0]["file_type"] == "pptx"


def test_invalid_uploads_store_nothing(browser, app, services):
    browser.sign_in("asha@x.com")
    cases = [
        dict(content=b"MZ junk", filename="virus.exe"),
        dict(content=b"not a pdf", filename="fake.pdf"),
        dict(content=b"", filename="empty.pdf"),
        dict(content=None),                                   # no file at all
        dict(title="x"),                                      # title too short
        dict(category="Hacking"),                             # unknown category
        dict(content=PDF_BYTES + b"x" * (1024 * 1024 + 10)),  # over the 1 MB test limit
    ]
    for case in cases:
        assert browser.upload(**case).status_code == 400, case
    assert stored_files(app) == [] and services.resources.search() == []


def test_form_values_survive_a_rejected_upload(browser):
    browser.sign_in("asha@x.com")
    html = browser.upload(title="Keep this title", content=b"junk").get_data(as_text=True)
    assert 'value="Keep this title"' in html


def test_oversized_request_is_rejected_with_message(browser, app):
    browser.sign_in("asha@x.com")
    response = browser.upload(content=PDF_BYTES + b"x" * (3 * 1024 * 1024))
    assert response.status_code == 302 and response.location.endswith("/upload")
    assert "too large" in browser.client.get("/upload").get_data(as_text=True)
    assert stored_files(app) == []


def test_upload_without_csrf_token_is_rejected(browser, app):
    browser.sign_in("asha@x.com")
    assert browser.upload(with_token=False).status_code == 400
    assert stored_files(app) == []


def test_file_is_removed_if_metadata_save_fails(browser, app, services, monkeypatch):
    browser.sign_in("asha@x.com")

    def database_down(item):
        raise DatabaseError("Could not save the resource details.")
    monkeypatch.setattr(services.resources, "create", database_down)

    assert browser.upload().status_code == 502
    assert stored_files(app) == []                  # nothing orphaned in storage


def test_storage_failure_creates_no_record(browser, services, monkeypatch):
    browser.sign_in("asha@x.com")

    def storage_down(fileobj, key, content_type):
        raise StorageError("Could not upload the file to cloud storage.")
    monkeypatch.setattr(services.storage, "save_file", storage_down)

    assert browser.upload().status_code == 502
    assert services.resources.search() == []


# ---------- library and search ----------

def seed(browser):
    browser.upload(title="Operating Systems Unit 1", subject="Operating Systems", category="Lecture Notes")
    browser.upload(title="DBMS ER Diagrams", subject="DBMS", category="Assignment")
    browser.upload(title="OS Past Paper 2024", subject="operating systems", category="Question Paper")


def test_library_lists_newest_first_with_safe_fields(browser):
    browser.sign_in("asha@x.com")
    seed(browser)
    data = browser.library()
    assert data["count"] == 3 and data["resources"][0]["title"] == "OS Past Paper 2024"
    first = data["resources"][0]
    assert {"title", "subject", "category", "uploader_name", "uploaded_at",
            "file_type", "file_size", "download_url", "can_delete"} <= set(first)
    assert "s3_key" not in first and "uploader_id" not in first


def test_search_and_filters(browser):
    browser.sign_in("asha@x.com")
    seed(browser)
    assert browser.library(q="dbms")["count"] == 1
    assert browser.library(q="unit operating")["count"] == 1
    assert browser.library(q="nothing like this")["count"] == 0
    assert browser.library(subject="Operating Systems")["count"] == 2
    assert browser.library(category="Assignment")["count"] == 1
    assert browser.library(subject="operating systems", category="Question Paper")["count"] == 1


def test_unknown_category_filter_is_rejected(browser):
    browser.sign_in("asha@x.com")
    assert browser.client.get("/api/resources?category=Bogus").status_code == 400


def test_empty_library_returns_empty_list(browser):
    browser.sign_in("asha@x.com")
    assert browser.library() == {"count": 0, "resources": []}


def test_library_page_lists_subjects(browser):
    browser.sign_in("asha@x.com")
    seed(browser)
    html = browser.client.get("/library").get_data(as_text=True)
    assert "DBMS" in html and "Operating Systems" in html


def test_hostile_title_is_escaped_in_html(browser):
    browser.sign_in("asha@x.com")
    browser.upload(title="<script>alert(1)</script>")
    html = browser.client.get("/dashboard").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


# ---------- download ----------

def test_download_returns_the_file(browser):
    browser.sign_in("asha@x.com")
    browser.upload(title="Operating Systems Unit 1")
    resource = browser.library()["resources"][0]
    response = browser.client.get(resource["download_url"])
    assert response.status_code == 200 and response.data == PDF_BYTES
    assert "attachment" in response.headers["Content-Disposition"]
    assert ".pdf" in response.headers["Content-Disposition"]


def test_other_logged_in_students_can_download(browser, other_browser):
    browser.sign_in("asha@x.com")
    browser.upload()
    other_browser.sign_in("bob@x.com", name="Bob")
    resource = other_browser.library()["resources"][0]
    assert other_browser.client.get(resource["download_url"]).data == PDF_BYTES


def test_download_requires_login(browser, other_browser):
    browser.sign_in("asha@x.com")
    browser.upload()
    url = browser.library()["resources"][0]["download_url"]
    response = other_browser.client.get(url)             # never logged in
    assert response.status_code == 302 and "/login" in response.location


def test_download_unknown_or_malformed_id_is_404(browser):
    browser.sign_in("asha@x.com")
    assert browser.download("0" * 32).status_code == 404
    assert browser.download("not-a-valid-id").status_code == 404


# ---------- delete and permissions ----------

def test_owner_can_delete_file_and_record(browser, app, services):
    browser.sign_in("asha@x.com")
    browser.upload()
    resource_id = browser.library()["resources"][0]["resource_id"]
    assert browser.library()["resources"][0]["can_delete"] is True

    assert browser.delete(resource_id).status_code == 200
    assert services.resources.get(resource_id) is None and stored_files(app) == []
    assert browser.delete(resource_id).status_code == 404          # already gone


def test_other_student_cannot_delete(browser, other_browser, app, services):
    browser.sign_in("asha@x.com")
    browser.upload()
    resource_id = browser.library()["resources"][0]["resource_id"]

    other_browser.sign_in("bob@x.com", name="Bob")
    assert other_browser.library()["resources"][0]["can_delete"] is False
    assert other_browser.delete(resource_id).status_code == 403
    assert services.resources.get(resource_id) is not None and len(stored_files(app)) == 1


def test_delete_requires_csrf_token(browser, services):
    browser.sign_in("asha@x.com")
    browser.upload()
    resource_id = browser.library()["resources"][0]["resource_id"]
    assert browser.delete(resource_id, with_token=False).status_code == 400
    assert services.resources.get(resource_id) is not None


def test_dashboard_shows_only_own_uploads_in_my_list(browser, other_browser):
    browser.sign_in("asha@x.com", name="Asha")
    browser.upload(title="Asha notes")
    other_browser.sign_in("bob@x.com", name="Bob")
    html = other_browser.client.get("/dashboard").get_data(as_text=True)
    assert "Nothing uploaded yet" in html          # Bob has no uploads
    assert "Asha notes" in html                    # but sees it under "Latest in the library"
    assert 'data-delete-id' not in html            # and gets no Delete button for it
