"""Authentication, sessions and CSRF protection.

All password/user logic lives in SessionAuthProvider. The routes only call
`register()` and `authenticate()`, so replacing this class with an Amazon
Cognito provider later would not require changing the routes or templates.
"""
import logging
import secrets
from functools import wraps

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from .services.common import build_user_item
from .services.validation import ValidationError, validate_registration

logger = logging.getLogger(__name__)
bp = Blueprint("auth", __name__)

# Used so that "unknown email" and "wrong password" take similar time.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


class AuthError(Exception):
    """A user-facing authentication problem."""


class SessionAuthProvider:
    """Email + password accounts stored in the users table (hashed passwords)."""

    def __init__(self, users, min_password_length=8, allowed_domain=""):
        self.users = users
        self.min_password_length = min_password_length
        self.allowed_domain = allowed_domain

    def register(self, form):
        data = validate_registration(form, self.min_password_length, self.allowed_domain)
        user = build_user_item(data["name"], data["email"],
                               generate_password_hash(data["password"]))
        if not self.users.create(user):
            raise AuthError("An account with this email already exists.")
        return user

    def authenticate(self, email, password):
        user = self.users.get_by_email(email or "")
        stored_hash = user["password_hash"] if user else _DUMMY_HASH
        password_ok = check_password_hash(stored_hash, password or "")
        if not user or not password_ok:
            raise AuthError("Invalid email or password.")  # same message for both cases
        return user


def get_auth_provider():
    return current_app.extensions["auth_provider"]


# ---------- session helpers ----------

def login_user(user):
    session.clear()  # new session on login prevents session fixation
    session["user_id"] = user["user_id"]
    session["name"] = user["name"]
    session["email"] = user["email"]
    session.permanent = True


def logout_user():
    session.clear()


def current_user():
    if "user_id" not in session:
        return None
    return {"user_id": session["user_id"], "name": session["name"], "email": session["email"]}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            if request.path.startswith("/api/"):
                return jsonify(error="Please log in to continue."), 401
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped


def _safe_next(target):
    """Only allow redirects to paths on this site (blocks open-redirect attacks)."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return None


# ---------- CSRF protection ----------

def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def verify_csrf():
    """Runs before every request. State-changing requests must carry the token."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(sent.encode(), expected.encode()):
        abort(400, description="Your security token is missing or expired. Please reload the page and try again.")


# ---------- routes ----------

@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        try:
            get_auth_provider().register(request.form)
        except (ValidationError, AuthError) as exc:
            flash(str(exc), "error")
            return render_template("register.html", form=request.form), 400
        flash("Account created. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        try:
            user = get_auth_provider().authenticate(
                request.form.get("email", "").strip().lower(),
                request.form.get("password", ""))
        except AuthError as exc:
            flash(str(exc), "error")
            return render_template("login.html", form=request.form), 401
        login_user(user)
        flash(f"Welcome back, {user['name']}!", "success")
        return redirect(_safe_next(request.args.get("next")) or url_for("main.dashboard"))
    return render_template("login.html", form={})


@bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
