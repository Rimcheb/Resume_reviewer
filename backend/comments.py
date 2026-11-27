"""Validate and save feedback from authenticated members."""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from backend import database
from backend.auth import login_required
from backend.permissions import require_owner

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
    raw_parent = request.form.get("parent_id", "")
    try:
        parent_id = int(raw_parent) if raw_parent else None
    except ValueError:
        abort(400)
    parent = database.get_comment_by_id(parent_id) if parent_id is not None else None
    if parent_id is not None and (parent is None or parent["resume_id"] != resume_id or parent["is_deleted"] or parent["parent_id"] is not None):
        abort(400)
    content = request.form.get("comment", "")
    error = comment_error(content)
    if error is not None:
        return render_template("comment_form.html", resume=resume, content=content,
                               error=error, comment_limit=COMMENT_LIMIT, comment=None,
                               revision_id=parent["revision_id"] if parent else request.form.get("revision_id", ""),
                               parent_id=parent_id, parent=parent), 400
    raw_revision = request.form.get("revision_id", "")
    try:
        revision_id = parent["revision_id"] if parent else (int(raw_revision) if raw_revision else None)
        comment = database.create_comment(resume_id, g.user["id"], content, revision_id, parent_id)
    except ValueError:
        abort(400)
    return redirect(url_for("resumes.detail", resume_id=resume_id,
                            _anchor=f"comment-{comment['id']}"), code=303)


@bp.route("/comments/<int:comment_id>/edit", methods=["GET", "POST"])
@login_required
def edit(comment_id):
    """Let only the comment author edit the text, keeping its author and resume."""
    comment = database.get_comment_by_id(comment_id)
    if comment is None or comment["is_deleted"]:
        abort(404)
    require_owner(comment["author_id"])
    resume = database.get_resume_by_id(comment["resume_id"])
    if resume is None:
        abort(404)
    content = comment["content"]
    error = None
    status = 200
    if request.method == "POST":
        content = request.form.get("comment", "")
        error = comment_error(content)
        if error is None:
            if not database.update_comment(comment_id, content):
                abort(404)
            flash("Comment updated.")
            return redirect(url_for("resumes.detail", resume_id=resume["id"],
                                    _anchor=f"comment-{comment_id}"), code=303)
        status = 400
    return render_template("comment_form.html", resume=resume, comment=comment,
                           content=content, error=error, comment_limit=COMMENT_LIMIT), status


@bp.post("/comments/<int:comment_id>/delete")
@login_required
def delete(comment_id):
    """Let only the comment author delete it; the resume itself remains."""
    comment = database.get_comment_by_id(comment_id)
    if comment is None or comment["is_deleted"]:
        abort(404)
    require_owner(comment["author_id"])
    if not database.delete_comment(comment_id):
        abort(404)
    flash("Comment deleted.")
    return redirect(url_for("resumes.detail", resume_id=comment["resume_id"]), code=303)


@bp.get("/comments/<int:comment_id>/reply")
@login_required
def reply(comment_id):
    """Open a direct reply while applying the résumé’s current access policy."""
    parent = database.get_comment_by_id(comment_id)
    if parent is None or parent["is_deleted"] or parent["parent_id"] is not None:
        abort(404)
    resume = database.get_resume_by_id(parent["resume_id"])
    if resume is None:
        abort(404)
    return render_template("comment_form.html", resume=resume, comment=None,
        content="", error=None, comment_limit=COMMENT_LIMIT, parent=parent,
        parent_id=parent["id"], revision_id=parent["revision_id"])
