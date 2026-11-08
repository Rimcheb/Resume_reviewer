"""Validate and save feedback from authenticated members."""

import math
import time

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from backend import database
from backend.auth import login_required
from backend.permissions import require_owner

bp = Blueprint("comments", __name__)
COMMENT_LIMIT = 5000

# Survey: most people expect about 15 minutes per review; 5 filters out drive-by reviews.
MIN_REVIEW_SECONDS = 5 * 60
TARGET_REVIEW_SECONDS = 15 * 60
DEEP_REVIEW_SECONDS = 30 * 60


def review_started(resume_id):
    """Record (once) when the signed-in reviewer opened this resume, and return it."""
    return database.start_review(resume_id, g.user["id"], int(time.time()))


def review_seconds(resume_id):
    """Seconds since the signed-in reviewer opened the resume, or None if they never did."""
    started = database.get_review_start(resume_id, g.user["id"])
    return None if started is None else int(time.time()) - started


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
    spent = None
    if error is None and resume["user_id"] != g.user["id"]:
        spent = review_seconds(resume_id)
        if spent is None:
            error = "Open the resume page and read it before posting a review."
        elif spent < MIN_REVIEW_SECONDS:
            minutes = math.ceil((MIN_REVIEW_SECONDS - spent) / 60)
            error = (f"Reviews need at least {MIN_REVIEW_SECONDS // 60} minutes. "
                     f"Take about {minutes} more minute{'s' if minutes > 1 else ''}, then post again.")
    if error is not None:
        return render_template("comment_form.html", resume=resume, content=content,
                               error=error, comment_limit=COMMENT_LIMIT, comment=None), 400
    comment = database.create_comment(resume_id, g.user["id"], content, spent)
    if spent is not None:
        database.finish_review(resume_id, g.user["id"])
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
