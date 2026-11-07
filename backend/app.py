"""Create the web app and connect its small components."""

import os
from flask import Flask, render_template, request
from flask_wtf.csrf import CSRFError, CSRFProtect

from backend import auth, comments, database, resumes, ratings, sqlite_storage


def csrf_error(error):
    """Ask the user to reload an expired or invalid form."""
    return render_template("error.html", message="Please reload the form and try again."), 400


UPLOAD_LIMIT = 2 * 1024 * 1024
UPLOAD_ENDPOINTS = ("resumes.create", "resumes.edit")


def allow_uploads():
    """Give only the resume form the larger body limit; every other route keeps 256 KB.

    Registered before CSRFProtect, whose own hook reads the form before any view runs.
    """
    if request.endpoint in UPLOAD_ENDPOINTS:
        request.max_content_length = UPLOAD_LIMIT


def too_large(error):
    """Explain a request over the body limit instead of showing a bare 413."""
    if request.endpoint in UPLOAD_ENDPOINTS:
        message = "That file is too large. Upload a PDF or Word file under 2 MB, or paste the text."
    else:
        message = "That request is too large."
    return render_template("error.html", message=message), 413


def health():
    """Confirm the web server is responding; does not check a database."""
    return {"status": "ok"}


def ready():
    """Tell the host whether storage is ready without revealing connection details."""
    if database.is_ready():
        return {"status": "ready"}
    return {"status": "unavailable"}, 503


def create_app(config=None):
    """Make an app with optional settings, including the storage choice."""
    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    application = Flask(
        __name__,
        template_folder=os.path.join(project_path, "templates"),
        static_folder=os.path.join(project_path, "static"),
        instance_path=os.path.join(project_path, "instance"),
    )
    application.config["DATABASE"] = os.getenv(
        "DATABASE_PATH", os.path.join(application.instance_path, "resume_reviewer.sqlite")
    )
    application.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        STORAGE_BACKEND=sqlite_storage,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "true") != "false",
        MAX_CONTENT_LENGTH=256 * 1024,
    )
    if config is not None:
        application.config.update(config)

    if not application.config["SECRET_KEY"]:
        raise RuntimeError("Set SECRET_KEY before starting the app.")

    database.init_app(application)
    application.before_request(allow_uploads)
    CSRFProtect(application)
    application.register_error_handler(CSRFError, csrf_error)
    application.register_error_handler(413, too_large)
    application.register_blueprint(auth.bp)
    application.register_blueprint(resumes.bp)
    application.register_blueprint(comments.bp)
    application.register_blueprint(ratings.bp)
    application.add_url_rule("/health", view_func=health)
    application.add_url_rule("/ready", view_func=ready)
    return application
