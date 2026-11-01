"""Small display helpers used by templates and the JSON API."""
from datetime import datetime


def format_file_size(num_bytes):
    """1536 -> '1.5 KB'"""
    size = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def format_date(iso_string):
    """'2026-10-28T09:30:00+00:00' -> '28 Oct 2026'"""
    try:
        return datetime.fromisoformat(iso_string).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return ""


def resource_to_public(item, current_user_id, download_url):
    """The fields the browser is allowed to see (never the S3 key)."""
    return {
        "resource_id": item["resource_id"],
        "title": item["title"],
        "description": item.get("description", ""),
        "subject": item["subject"],
        "category": item["category"],
        "uploader_name": item["uploader_name"],
        "file_type": item["file_type"],
        "file_size": format_file_size(item["file_size"]),
        "uploaded_at": format_date(item["uploaded_at"]),
        "can_delete": item["uploader_id"] == current_user_id,
        "download_url": download_url,
    }
