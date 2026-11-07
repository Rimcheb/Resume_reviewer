"""Keep ownership checks separate from login and database operations."""

from flask import abort, g, session

# ponytail: share links opened in this browser live in the signed session, capped so the
# cookie stays small; reopening the link restores access to older ones.
KEPT_SHARE_TOKENS = 20


def require_owner(owner_id):
    """After login_required, reject access unless this user owns the record."""
    if g.user["id"] != owner_id:
        abort(403)


def grant_shared_view(share_token):
    """Remember that this browser opened a private resume's share link."""
    tokens = [token for token in session.get("share_tokens", []) if token != share_token]
    session["share_tokens"] = (tokens + [share_token])[-KEPT_SHARE_TOKENS:]


def require_viewer(resume):
    """Allow public resumes, the owner, and holders of the current share link; else 404.

    Access is tied to the token, so making a resume private again with a new link
    shuts out people who only had the old one.
    """
    if resume["share_token"] is None or g.user["id"] == resume["user_id"]:
        return
    if resume["share_token"] not in session.get("share_tokens", []):
        abort(404)
