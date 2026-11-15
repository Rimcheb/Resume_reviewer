"""Handle account input, password hashing, and authentication routes."""

import unicodedata

from email_validator import EmailNotValidError, validate_email
from functools import wraps
from urllib.parse import urlsplit, unquote

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from backend import database
from backend.models import FIELDS

bp = Blueprint("auth", __name__)


def normalize_email(value):
    """Check address syntax without contacting an email server."""
    address = validate_email(value.strip(), check_deliverability=False)
    return address.normalized.lower()


def chosen_fields(form):
    """Keep only known fields from the checkboxes, in list order."""
    picked = set(form.getlist("review_fields"))
    return [field for field in FIELDS if field in picked]


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Create an account after validating the email and password."""
    email = ""
    display_name = ""
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

        display_name = request.form.get("display_name", "").strip()
        if display_name and not valid_display_name(display_name):
            error = "Use a display name with 1 to 80 characters, without @ or control characters."

        if error is None:
            password_hash = generate_password_hash(password)
            user = database.create_user(email, password_hash, display_name, review_fields=chosen_fields(request.form))
            if user is None:
                error = "That email is already registered."
                status = 409
            else:
                flash("Your account is ready.")
                return redirect(url_for("auth.login"), code=303)
        if status == 200:
            status = 400
    return render_template("register.html", email=email, display_name=display_name, error=error, fields=FIELDS, chosen=chosen_fields(request.form)), status


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
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return protected_view


def safe_next(value):
    """Accept only a local absolute path for the post-login redirect."""
    decoded = value
    for _ in range(3):
        decoded = unquote(decoded)
    if decoded.startswith("//") or "\\" in decoded or any(ord(c) < 32 or ord(c) == 127 for c in decoded):
        return url_for("resumes.feed")
    if not value.startswith("/") or value.startswith("//") or "\\" in value:
        return url_for("resumes.feed")
    for character in value:
        if ord(character) < 32 or ord(character) == 127:
            return url_for("resumes.feed")
    try:
        parts = urlsplit(value)
    except ValueError:
        return url_for("resumes.feed")
    if parts.scheme or parts.netloc:
        return url_for("resumes.feed")
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


def valid_display_name(value):
    """Accept a bounded public name without email addresses or control characters."""
    return 1 <= len(value) <= 80 and "@" not in value and all(
        not unicodedata.category(c).startswith("C") for c in value
    )


@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """Show the current user's account without exposing password data."""
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        if not valid_display_name(display_name):
            return render_template("account.html", error="Use a display name with 1 to 80 characters, without @ or control characters.", fields=FIELDS, chosen=g.user["review_fields"]), 400
        database.update_display_name(g.user["id"], display_name)
        flash("Display name updated.")
        return redirect(url_for("auth.account"), code=303)
    return render_template("account.html", fields=FIELDS, chosen=g.user["review_fields"])


@bp.get("/")
def index():
    """Send users to the appropriate starting page."""
    if g.user is None:
        return redirect(url_for("auth.login"))
    return redirect(url_for("resumes.feed"))


@bp.post("/account/fields")
@login_required
def review_fields():
    """Save the existing field preferences for the authenticated member."""
    database.update_review_fields(g.user["id"], chosen_fields(request.form))
    flash("Your review fields were saved.")
    return redirect(url_for("auth.account"), code=303)


@bp.post("/account/bio")
@login_required
def expertise_bio():
    """Allow members to change only their own optional public expertise bio."""
    bio = request.form.get("expertise_bio", "").strip()
    if len(bio) > 500 or any(unicodedata.category(c).startswith("C") and c not in "\n\t\r" for c in bio):
        return render_template("account.html", fields=FIELDS, chosen=g.user["review_fields"],
            bio_value=bio, error="Keep your expertise bio within 500 characters and remove unsupported control characters."), 400
    database.update_expertise_bio(g.user["id"], bio)
    flash("Your expertise bio was saved.")
    return redirect(url_for("auth.account", _anchor="expertise"), code=303)
