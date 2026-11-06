"""Forward storage operations through the selected backend."""
from flask import current_app


def init_app(app):
    """Initialize the chosen backend once and keep it on this app."""
    backend = app.config["STORAGE_BACKEND"]
    backend.init_app(app)
    app.extensions["storage"] = backend


def get_user_by_email(email):
    """Find a user by their already-normalized email, or return None."""
    return current_app.extensions["storage"].get_user_by_email(email)


def get_user_by_id(user_id):
    """Find a user by their integer ID, or return None."""
    return current_app.extensions["storage"].get_user_by_id(user_id)


def create_user(email, password_hash):
    """Save a normalized email and password hash, or return None if duplicate."""
    return current_app.extensions["storage"].create_user(email, password_hash)


def create_resume(user_id, content, target_field, feedback_request):
    """Save validated submission fields and return a plain resume record."""
    return current_app.extensions["storage"].create_resume(
        user_id, content, target_field, feedback_request
    )


def get_resume_by_id(resume_id):
    """Return a resume record, or None when it does not exist."""
    return current_app.extensions["storage"].get_resume_by_id(resume_id)


def list_resumes(user_id=None, target_field="", limit=10, offset=0):
    """Return newest first; match literal field substrings after Python lower()."""
    return current_app.extensions["storage"].list_resumes(user_id, target_field, limit, offset)
