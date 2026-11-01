"""Form and file validation (pure Python: no Flask app needed)."""
import io

import pytest
from werkzeug.datastructures import FileStorage

from app.services.validation import (OLE_MAGIC, ValidationError, validate_registration,
                                     validate_resource_form, validate_upload_file)
from tests.conftest import PDF_BYTES, make_pptx_bytes

MB = 1024 * 1024


def upload(name, data):
    return FileStorage(stream=io.BytesIO(data), filename=name)


# ---------- uploaded files ----------

def test_accepts_pdf():
    ext, content_type, size, safe_name = validate_upload_file(upload("My Notes.pdf", PDF_BYTES), MB)
    assert (ext, content_type, size) == ("pdf", "application/pdf", len(PDF_BYTES))
    assert safe_name == "My_Notes.pdf"


def test_accepts_pptx():
    assert validate_upload_file(upload("deck.pptx", make_pptx_bytes()), MB)[0] == "pptx"


def test_accepts_legacy_ppt():
    assert validate_upload_file(upload("old.ppt", OLE_MAGIC + b"\x00" * 64), MB)[0] == "ppt"


def test_extension_is_case_insensitive():
    assert validate_upload_file(upload("NOTES.PDF", PDF_BYTES), MB)[0] == "pdf"


def test_stream_is_rewound_after_validation():
    file = upload("a.pdf", PDF_BYTES)
    validate_upload_file(file, MB)
    assert file.stream.read(5) == b"%PDF-"


@pytest.mark.parametrize("filename,content", [
    ("virus.exe", b"MZ\x90\x00"),                 # wrong extension
    ("notes.pdf.exe", PDF_BYTES),                 # double extension
    ("notes", PDF_BYTES),                         # no extension
    ("notes.pdf", b"this is not a pdf"),          # right extension, wrong content
    ("deck.pptx", b"PK\x03\x04 not really"),      # ZIP header but not a presentation
    ("deck.pptx", PDF_BYTES),                     # PDF renamed to .pptx
    ("deck.ppt", PDF_BYTES),                      # PDF renamed to .ppt
])
def test_rejects_bad_files(filename, content):
    with pytest.raises(ValidationError):
        validate_upload_file(upload(filename, content), MB)


def test_rejects_empty_file():
    with pytest.raises(ValidationError):
        validate_upload_file(upload("a.pdf", b""), MB)


def test_rejects_oversized_file():
    with pytest.raises(ValidationError):
        validate_upload_file(upload("a.pdf", PDF_BYTES + b"x" * 100), 50)


def test_rejects_missing_file():
    with pytest.raises(ValidationError):
        validate_upload_file(None, MB)
    with pytest.raises(ValidationError):
        validate_upload_file(upload("", PDF_BYTES), MB)


# ---------- resource form ----------

GOOD_FORM = {"title": "  OS Unit 1  ", "subject": "Operating Systems",
             "category": "Lecture Notes", "description": "Process scheduling"}


def test_resource_form_ok_and_trimmed():
    assert validate_resource_form(GOOD_FORM)["title"] == "OS Unit 1"


@pytest.mark.parametrize("field,value", [
    ("title", "ab"), ("title", "x" * 121), ("subject", "x"),
    ("category", "Hacking"), ("category", ""), ("description", "x" * 501),
])
def test_resource_form_rejects_bad_values(field, value):
    form = dict(GOOD_FORM, **{field: value})
    with pytest.raises(ValidationError):
        validate_resource_form(form)


def test_description_is_optional():
    assert validate_resource_form(dict(GOOD_FORM, description=""))["description"] == ""


# ---------- registration form ----------

GOOD_REG = {"name": "Asha", "email": "Asha@Example.com",
            "password": "password123", "confirm_password": "password123"}


def test_registration_ok_and_email_lowercased():
    assert validate_registration(GOOD_REG)["email"] == "asha@example.com"


@pytest.mark.parametrize("field,value", [
    ("name", "A"), ("email", "not-an-email"), ("email", "a@b"),
    ("password", "short"), ("confirm_password", "different123"),
])
def test_registration_rejects_bad_values(field, value):
    with pytest.raises(ValidationError):
        validate_registration(dict(GOOD_REG, **{field: value}))


def test_registration_domain_restriction():
    with pytest.raises(ValidationError):
        validate_registration(GOOD_REG, allowed_domain="college.edu")
    ok = dict(GOOD_REG, email="asha@college.edu")
    assert validate_registration(ok, allowed_domain="college.edu")["email"] == "asha@college.edu"
