"""Validate and save feedback from authenticated members."""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from backend import database
from backend.auth import login_required

bp = Blueprint("comments", __name__)
COMMENT_LIMIT = 5000


def comment_error(content):
    """Return an input problem, or None for valid feedback or a follow-up."""
    if not content.strip() or len(content) > COMMENT_LIMIT:
        return f"Enter a comment with 1 to {COMMENT_LIMIT:,} characters."
    return None


@bp.post("/resumes/<int:resume_id>/comments")
@login_required
def create(resume_id):
    """Save a comment under the session author, including owner follow-ups."""
    resume = database.get_resume_by_id(resume_id)
    if resume is None:
        abort(404)
    content = request.form.get("comment", "")
    error = comment_error(content)
    if error is not None:
        return render_template("comment_form.html", resume=resume, content=content,
                               error=error, comment_limit=COMMENT_LIMIT, comment=None), 400
    comment = database.create_comment(resume_id, g.user["id"], content)
    return redirect(url_for("resumes.detail", resume_id=resume_id,
                            _anchor=f"comment-{comment['id']}"), code=303)
