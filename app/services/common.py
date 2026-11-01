"""Helpers shared by the local and DynamoDB database services.

Both backends build items with the same functions, so a record looks identical
whether it lives in a JSON file (local) or in DynamoDB (AWS).
"""
import uuid
from datetime import datetime, timezone

# Every resource carries this constant. The "all-uploaded-index" uses it as its
# partition key so we can list the whole library newest-first with a Query
# instead of a table Scan.
ALL_PARTITION_VALUE = "RESOURCE"


class DatabaseError(Exception):
    """Raised when the database layer cannot complete an operation."""


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def new_id():
    return uuid.uuid4().hex


def build_user_item(name, email, password_hash):
    return {
        "email": email.strip().lower(),
        "user_id": new_id(),
        "name": name.strip(),
        "password_hash": password_hash,
        "created_at": utc_now_iso(),
    }


def build_resource_item(*, title, description, subject, category, uploader_id,
                        uploader_name, s3_key, original_filename, file_type,
                        content_type, file_size):
    title = title.strip()
    subject = subject.strip()
    return {
        "resource_id": new_id(),
        "title": title,
        "title_lower": title.lower(),      # used for case-insensitive title search
        "description": description.strip(),
        "subject": subject,
        "subject_key": subject.lower(),    # partition key of the subject index
        "category": category,
        "uploader_id": uploader_id,
        "uploader_name": uploader_name,
        "s3_key": s3_key,                  # only the key is stored, never the file
        "original_filename": original_filename,
        "file_type": file_type,
        "content_type": content_type,
        "file_size": int(file_size),
        "uploaded_at": utc_now_iso(),      # ISO-8601 UTC, sorts correctly as text
        "gsi_all": ALL_PARTITION_VALUE,
    }


def title_matches(item, query):
    """True if every word of the query appears in the title (case-insensitive)."""
    if not query or not query.strip():
        return True
    title = item.get("title_lower") or item.get("title", "").lower()
    return all(term in title for term in query.lower().split())


def unique_subjects(items):
    """Distinct subjects (case-insensitive), sorted alphabetically.

    `items` must be newest-first. We walk it oldest-first so the spelling used
    by the first uploader ("DBMS") wins over later variants ("dbms").
    """
    seen = {}
    for item in reversed(items):
        seen.setdefault(item["subject_key"], item["subject"])
    return sorted(seen.values(), key=str.lower)
