"""Application factory."""
import logging

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from .auth import SessionAuthProvider, current_user, get_csrf_token, verify_csrf
from .auth import bp as auth_bp
from .config import Config, validate_config
from .routes import bp as main_bp
from .services import build_services
from .services.common import DatabaseError
from .services.storage_service import StorageError
from .services.validation import CATEGORIES
from .utils import format_date, format_file_size


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    validate_config(app.config)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    services = build_services(app.config)
    app.extensions["services"] = services
    app.extensions["auth_provider"] = SessionAuthProvider(
        services.users, app.config["MIN_PASSWORD_LENGTH"], app.config["ALLOWED_EMAIL_DOMAIN"])

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.before_request(verify_csrf)

    app.jinja_env.filters["filesize"] = format_file_size
    app.jinja_env.filters["datefmt"] = format_date

    @app.context_processor
    def inject_globals():
        return {
            "current_user": current_user(),
            "csrf_token": get_csrf_token,
            "categories": CATEGORIES,
            "max_upload_mb": app.config["MAX_UPLOAD_MB"],
        }

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        # Only our own CSS/JS may run: templates must not use inline <script> or style="".
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; frame-ancestors 'none'; form-action 'self'")
        return response

    def respond_with_error(code, message):
        if request.path.startswith("/api/"):
            return jsonify(error=message), code
        return render_template("error.html", code=code, message=message), code

    @app.errorhandler(400)
    def bad_request(error):
        return respond_with_error(400, error.description)

    @app.errorhandler(404)
    def not_found(error):
        return respond_with_error(404, "The page you asked for does not exist.")

    @app.errorhandler(413)
    def too_large(error):
        message = f"The upload is too large. Maximum file size is {app.config['MAX_UPLOAD_MB']} MB."
        if request.path == "/upload":
            flash(message, "error")
            return redirect(url_for("main.upload"))
        return respond_with_error(413, message)

    @app.errorhandler(StorageError)
    @app.errorhandler(DatabaseError)
    def cloud_error(error):
        app.logger.error("Cloud service error: %s", error)
        return respond_with_error(502, str(error))

    @app.errorhandler(500)
    def server_error(error):
        return respond_with_error(500, "Something went wrong on our side. Please try again.")

    return app
