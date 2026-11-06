"""Keep ownership checks separate from login and database operations."""

from flask import abort, g


def require_owner(owner_id):
    """After login_required, reject access unless this user owns the record."""
    if g.user["id"] != owner_id:
        abort(403)
