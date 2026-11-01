"""Input validation for forms and uploaded files (pure Python, no AWS)."""
import os
import re
import zipfile

from werkzeug.utils import secure_filename

ALLOWED_TYPES = {
    "pdf": "application/pdf",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

CATEGORIES = [
    "Lecture Notes",
    "Assignment",
    "Question Paper",
    "Lab Manual",
    "Presentation",
    "Reference Material",
    "Other",
]

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")  # legacy .ppt (OLE2 container)


class ValidationError(Exception):
    """A user-facing validation message."""


def validate_registration(form, min_password_length=8, allowed_domain=""):
    name = (form.get("name") or "").strip()
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""
    confirm = form.get("confirm_password") or ""

    if not 2 <= len(name) <= 60:
        raise ValidationError("Name must be between 2 and 60 characters.")
    if not EMAIL_RE.match(email) or len(email) > 120:
        raise ValidationError("Please enter a valid email address.")
    if allowed_domain and not email.endswith("@" + allowed_domain):
        raise ValidationError(f"Registration is limited to @{allowed_domain} email addresses.")
    if len(password) < min_password_length:
        raise ValidationError(f"Password must be at least {min_password_length} characters long.")
    if len(password) > 128:
        raise ValidationError("Password is too long (maximum 128 characters).")
    if password != confirm:
        raise ValidationError("Passwords do not match.")
    return {"name": name, "email": email, "password": password}


def validate_resource_form(form):
    title = (form.get("title") or "").strip()
    subject = (form.get("subject") or "").strip()
    category = (form.get("category") or "").strip()
    description = (form.get("description") or "").strip()

    if not 3 <= len(title) <= 120:
        raise ValidationError("Title must be between 3 and 120 characters.")
    if not 2 <= len(subject) <= 60:
        raise ValidationError("Subject must be between 2 and 60 characters.")
    if category not in CATEGORIES:
        raise ValidationError("Please choose a valid category.")
    if len(description) > 500:
        raise ValidationError("Description must be 500 characters or fewer.")
    return {"title": title, "subject": subject, "category": category, "description": description}


def _looks_like_pptx(stream):
    """A .pptx is a ZIP that contains [Content_Types].xml and a ppt/ folder."""
    try:
        with zipfile.ZipFile(stream) as archive:
            names = archive.namelist()
        return "[Content_Types].xml" in names and any(n.startswith("ppt/") for n in names)
    except zipfile.BadZipFile:
        return False
    finally:
        stream.seek(0)


def validate_upload_file(file_storage, max_bytes):
    """Check extension, size and file signature.

    Returns (extension, content_type, size_in_bytes, safe_original_filename).
    The stream is rewound so it can be uploaded afterwards.
    """
    if file_storage is None or not file_storage.filename:
        raise ValidationError("Please choose a file to upload.")

    original = file_storage.filename
    extension = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if extension not in ALLOWED_TYPES:
        raise ValidationError("Only PDF, PPT and PPTX files are allowed.")

    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)

    if size == 0:
        raise ValidationError("The uploaded file is empty.")
    if size > max_bytes:
        raise ValidationError(f"File is too large. Maximum size is {max_bytes // (1024 * 1024)} MB.")

    header = stream.read(8)
    stream.seek(0)

    if extension == "pdf":
        valid = header.startswith(b"%PDF-")
    elif extension == "ppt":
        valid = header.startswith(OLE_MAGIC)
    else:
        valid = header.startswith(b"PK\x03\x04") and _looks_like_pptx(stream)

    if not valid:
        raise ValidationError("The file content does not match its extension. Upload a genuine PDF, PPT or PPTX.")

    safe_name = secure_filename(original) or f"resource.{extension}"
    return extension, ALLOWED_TYPES[extension], size, safe_name
