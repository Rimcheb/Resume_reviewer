"""Expose user storage operations through the application's chosen backend.

User records contain id, email and password_hash. Missing lookups return None.
create_user returns None only for a duplicate email; other failures raise.
"""

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
