"""Main application routes: dashboard, upload, library, download, delete."""
import logging
import re

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, send_file, url_for)
from werkzeug.utils import secure_filename

from .auth import current_user, login_required
from .services.common import DatabaseError, build_resource_item
from .services.storage_service import StorageError, generate_storage_key
from .services.validation import (CATEGORIES, ValidationError,
                                  validate_resource_form, validate_upload_file)
from .utils import resource_to_public

logger = logging.getLogger(__name__)
bp = Blueprint("main", __name__)

RESOURCE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def services():
    return current_app.extensions["services"]


def _find_resource_or_none(resource_id):
    if not RESOURCE_ID_RE.match(resource_id):
        return None
    return services().resources.get(resource_id)


@bp.route("/")
def index():
    if current_user():
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@bp.route("/health")
def health():
    """Simple check used to confirm the server is running."""
    return jsonify(status="ok")


@bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    my_resources = services().resources.list_by_uploader(user["user_id"], limit=50)
    recent = services().resources.search(limit=6)
    return render_template("dashboard.html", my_resources=my_resources, recent=recent)


@bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "GET":
        return render_template("upload.html", form={})

    user = current_user()
    svc = services()
    try:
        meta = validate_resource_form(request.form)
        max_bytes = current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024
        upload_file = request.files.get("file")
        extension, content_type, size, safe_name = validate_upload_file(upload_file, max_bytes)
    except ValidationError as exc:
        flash(str(exc), "error")
        return render_template("upload.html", form=request.form), 400

    # Step 1: put the file in S3 under a unique key.
    key = generate_storage_key(user["user_id"], extension)
    try:
        svc.storage.save_file(upload_file.stream, key, content_type)
    except StorageError as exc:
        flash(str(exc), "error")
        return render_template("upload.html", form=request.form), 502

    # Step 2: save the metadata. If this fails, remove the file so nothing is orphaned.
    item = build_resource_item(
        title=meta["title"], description=meta["description"], subject=meta["subject"],
        category=meta["category"], uploader_id=user["user_id"], uploader_name=user["name"],
        s3_key=key, original_filename=safe_name, file_type=extension,
        content_type=content_type, file_size=size)
    try:
        svc.resources.create(item)
    except DatabaseError as exc:
        try:
            svc.storage.delete_file(key)
        except StorageError:
            logger.error("Orphaned storage object after failed DB write: %s", key)
        flash(str(exc), "error")
        return render_template("upload.html", form=request.form), 502

    flash(f"“{meta['title']}” was uploaded successfully.", "success")
    return redirect(url_for("main.library"))


@bp.route("/library")
@login_required
def library():
    subjects = services().resources.list_subjects()
    return render_template("library.html", subjects=subjects)


@bp.route("/api/resources")
@login_required
def api_resources():
    query = request.args.get("q", "").strip()[:100]
    subject = request.args.get("subject", "").strip()[:60]
    category = request.args.get("category", "").strip()
    if category and category not in CATEGORIES:
        return jsonify(error="Unknown category."), 400

    items = services().resources.search(query=query, subject=subject or None,
                                        category=category or None, limit=100)
    user_id = current_user()["user_id"]
    resources = [
        resource_to_public(i, user_id, url_for("main.download", resource_id=i["resource_id"]))
        for i in items
    ]
    return jsonify(resources=resources, count=len(resources))


@bp.route("/resources/<resource_id>/download")
@login_required
def download(resource_id):
    item = _find_resource_or_none(resource_id)
    if item is None:
        return render_template("error.html", code=404, message="That resource does not exist."), 404

    name = f"{secure_filename(item['title']) or 'resource'}.{item['file_type']}"
    target = services().storage.get_download_target(
        item["s3_key"], name, item["content_type"],
        current_app.config["PRESIGNED_URL_EXPIRY_SECONDS"])

    if target.url:  # S3: browser is sent to a short-lived presigned URL
        return redirect(target.url)
    return send_file(target.path, as_attachment=True, download_name=name,
                     mimetype=item["content_type"])  # local development


@bp.route("/api/resources/<resource_id>", methods=["DELETE"])
@login_required
def delete_resource(resource_id):
    item = _find_resource_or_none(resource_id)
    if item is None:
        return jsonify(error="Resource not found."), 404
    if item["uploader_id"] != current_user()["user_id"]:
        return jsonify(error="You can only delete your own uploads."), 403

    # Delete the file first (S3 delete is idempotent), then the record.
    # If the second step fails, retrying the delete is safe.
    services().storage.delete_file(item["s3_key"])
    services().resources.delete(resource_id)
    return jsonify(message="Resource deleted.")
