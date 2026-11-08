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


def line_count(resume):
    """Number of lines shown, matching the numbered list on the resume page."""
    return max(1, len(resume["content"].splitlines()))


def line_error(value, resume, required):
    """Parse the line number; return (number or None, error message or None)."""
    if not value.strip():
        return None, ("Choose the resume line your review is about." if required else None)
    count = line_count(resume)
    if not value.strip().isdigit() or not 1 <= int(value) <= count:
        return None, f"Choose a line number from 1 to {count}."
    return int(value), None


@bp.post("/resumes/<int:resume_id>/comments")
@login_required
def create(resume_id):
    """Save a comment under the session author, including owner follow-ups."""
    resume = database.get_resume_by_id(resume_id)
    if resume is None:
        abort(404)
    content = request.form.get("comment", "")
    is_owner = resume["user_id"] == g.user["id"]
    line_number, error = line_error(request.form.get("line", ""), resume, required=not is_owner)
    error = comment_error(content) or error
    if error is not None:
        return render_template("comment_form.html", resume=resume, content=content,
                               error=error, comment_limit=COMMENT_LIMIT, comment=None,
                               line=request.form.get("line", ""), line_count=line_count(resume),
                               line_required=not is_owner), 400
    comment = database.create_comment(resume_id, g.user["id"], content, line_number)
    return redirect(url_for("resumes.detail", resume_id=resume_id,
                            _anchor=f"comment-{comment['id']}"), code=303)


@bp.route("/comments/<int:comment_id>/edit", methods=["GET", "POST"])
@login_required
def edit(comment_id):
    """Let only the comment author edit the text, keeping its author and resume."""
    comment = database.get_comment_by_id(comment_id)
    if comment is None:
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
    if comment is None:
        abort(404)
    require_owner(comment["author_id"])
    if not database.delete_comment(comment_id):
        abort(404)
    flash("Comment deleted.")
    return redirect(url_for("resumes.detail", resume_id=comment["resume_id"]), code=303)
