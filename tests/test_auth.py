"""Registration, login, logout, sessions and CSRF protection."""
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("path", ["/dashboard", "/library", "/upload"])
def test_protected_pages_redirect_to_login(browser, path):
    response = browser.client.get(path)
    assert response.status_code == 302 and "/login" in response.location


def test_api_and_download_require_login(browser):
    assert browser.client.get("/api/resources").status_code == 401
    assert browser.client.delete("/api/resources/" + "a" * 32).status_code in (400, 401)
    response = browser.client.get("/resources/" + "a" * 32 + "/download")
    assert response.status_code == 302 and "/login" in response.location


def test_health_check_is_public(browser):
    assert browser.client.get("/health").get_json() == {"status": "ok"}


def test_post_without_csrf_token_is_rejected(browser):
    response = browser.client.post("/login", data={"email": "a@x.com", "password": "password123"})
    assert response.status_code == 400


def test_registration_and_login(browser):
    assert browser.register("asha@x.com").status_code == 302
    response = browser.login("asha@x.com")
    assert response.status_code == 302 and response.location.endswith("/dashboard")
    assert browser.client.get("/dashboard").status_code == 200


def test_password_is_stored_hashed(browser, app):
    browser.register("asha@x.com", password="password123")
    stored = (Path(app.config["LOCAL_DATA_DIR"]) / "users.json").read_text()
    assert "password123" not in stored
    assert json.loads(stored)["asha@x.com"]["password_hash"].startswith(("scrypt:", "pbkdf2:"))


def test_duplicate_email_rejected_case_insensitively(browser):
    browser.register("asha@x.com")
    response = browser.register("ASHA@x.com")
    assert response.status_code == 400 and "already exists" in response.get_data(as_text=True)


@pytest.mark.parametrize("kwargs", [
    {"email": "bad-email"},
    {"email": "a@x.com", "password": "short"},
    {"email": "a@x.com", "confirm": "different123"},
    {"email": "a@x.com", "name": "A"},
])
def test_invalid_registration_is_rejected(browser, kwargs):
    assert browser.register(**kwargs).status_code == 400


def test_wrong_password_and_unknown_email_give_same_message(browser):
    browser.register("asha@x.com")
    wrong = browser.login("asha@x.com", password="wrong-password")
    unknown = browser.login("nobody@x.com")
    assert wrong.status_code == unknown.status_code == 401
    for response in (wrong, unknown):
        assert "Invalid email or password" in response.get_data(as_text=True)


def test_logged_in_user_skips_login_page(browser):
    browser.sign_in("asha@x.com")
    assert browser.client.get("/login").status_code == 302


def test_logout_requires_csrf_and_ends_session(browser):
    browser.sign_in("asha@x.com")
    assert browser.logout(with_token=False).status_code == 400
    assert browser.client.get("/dashboard").status_code == 200       # still logged in
    assert browser.logout().status_code == 302
    assert browser.client.get("/dashboard").status_code == 302       # now blocked


def test_login_redirect_only_to_local_paths(browser):
    browser.register("asha@x.com")
    assert browser.login("asha@x.com", next_url="//evil.example").location.endswith("/dashboard")
    browser.logout()
    assert browser.login("asha@x.com", next_url="/library").location.endswith("/library")


def test_email_domain_restriction(make_app):
    from tests.conftest import Browser
    restricted = Browser(make_app(ALLOWED_EMAIL_DOMAIN="college.edu"))
    assert restricted.register("a@gmail.com").status_code == 400
    assert restricted.register("a@college.edu").status_code == 302


def test_security_headers_present(browser):
    headers = browser.client.get("/login").headers
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'self'" in headers["Content-Security-Policy"]
