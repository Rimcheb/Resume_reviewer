"""Handle account input, password hashing, and authentication routes."""

from email_validator import EmailNotValidError, validate_email
from functools import wraps
from urllib.parse import urlsplit

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from backend import database

bp = Blueprint("auth", __name__)


def normalize_email(value):
    """Check address syntax without contacting an email server."""
    address = validate_email(value.strip(), check_deliverability=False)
    return address.normalized.lower()


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Create an account after validating the email and password."""
    email = ""
    error = None
    status = 200
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        try:
            email = normalize_email(email)
        except EmailNotValidError:
            error = "Enter a valid email address."

        if not 8 <= len(password) <= 128 or not password.strip():
            error = "Use a password with 8 to 128 characters."

        if error is None:
            password_hash = generate_password_hash(password)
            user = database.create_user(email, password_hash)
            if user is None:
                error = "That email is already registered."
                status = 409
            else:
                flash("Your account is ready.")
                return redirect(url_for("auth.login"), code=303)
        if status == 200:
            status = 400
    return render_template("register.html", email=email, error=error), status


@bp.before_app_request
def load_user():
    """Read identity from the signed session, never from submitted form IDs."""
    g.user = None
    if request.endpoint in ("health", "ready", "static"):
        return
    user_id = session.get("user_id")
    if isinstance(user_id, int):
        g.user = database.get_user_by_id(user_id)
        if g.user is None:
            session.clear()


def login_required(view):
    """Protect a route while keeping its original function name."""
    @wraps(view)
    def protected_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return protected_view


def safe_next(value):
    """Accept only a local absolute path for the post-login redirect."""
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return url_for("auth.account")
    for character in value:
        if ord(character) < 32 or ord(character) == 127:
            return url_for("auth.account")
    try:
        parts = urlsplit(value)
    except ValueError:
        return url_for("auth.account")
    if parts.scheme or parts.netloc:
        return url_for("auth.account")
    return value


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Check credentials and start a fresh signed session."""
    email = ""
    error = None
    next_url = safe_next(request.args.get("next", ""))
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = None
        try:
            email = normalize_email(email)
        except EmailNotValidError:
            pass
        else:
            user = database.get_user_by_email(email)

        if user is not None and 8 <= len(password) <= 128:
            if check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                return redirect(next_url, code=303)
        error = "Email or password is incorrect."
    status = 401 if error else 200
    return render_template("login.html", email=email, error=error, next_url=next_url), status


@bp.post("/logout")
@login_required
def logout():
    """Clear the session so this browser loses account access."""
    session.clear()
    return redirect(url_for("auth.login"), code=303)


@bp.get("/account")
@login_required
def account():
    """Show the current user's account without exposing password data."""
    return render_template("account.html")


@bp.get("/")
def index():
    """Send users to the appropriate starting page."""
    if g.user is None:
        return redirect(url_for("auth.login"))
    return redirect(url_for("auth.account"))
