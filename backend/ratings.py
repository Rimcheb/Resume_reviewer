"""Handle owner helpfulness decisions and a member-only reviewer summary."""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from backend import database
from backend.auth import login_required
from backend.permissions import require_owner

bp = Blueprint("ratings", __name__)


def ratable_comment(comment_id):
    """Only a resume owner may rate a comment written by someone else."""
    comment = database.get_comment_by_id(comment_id)
    if comment is None:
        abort(404)
    resume = database.get_resume_by_id(comment["resume_id"])
    if resume is None:
        abort(404)
    require_owner(resume["user_id"])
    if comment["author_id"] == g.user["id"]:
        abort(403)
    return comment


@bp.post("/comments/<int:comment_id>/rating")
@login_required
def save(comment_id):
    """Validate the form and save a decision under the signed-in owner's ID."""
    comment = ratable_comment(comment_id)
    helpful = request.form.get("helpful")
    if helpful not in ("0", "1"):
        return render_template("error.html", message="Choose helpful or not helpful."), 400
    database.save_rating(comment_id, g.user["id"], int(helpful))
    flash("Feedback rating saved.")
    return redirect(url_for("resumes.detail", resume_id=comment["resume_id"],
                            _anchor=f"comment-{comment_id}"), code=303)


@bp.post("/comments/<int:comment_id>/applied")
@login_required
def applied(comment_id):
    """Let the resume owner mark advice they used, which the reviewer then sees."""
    comment = ratable_comment(comment_id)
    value = request.form.get("applied")
    if value not in ("0", "1"):
        return render_template("error.html", message="Choose applied or not applied."), 400
    database.mark_applied(comment_id, int(value))
    flash("Marked as applied." if value == "1" else "Applied mark removed.")
    return redirect(url_for("resumes.detail", resume_id=comment["resume_id"],
                            _anchor=f"comment-{comment_id}"), code=303)


@bp.post("/comments/<int:comment_id>/rating/delete")
@login_required
def delete(comment_id):
    """Remove a decision without deleting the comment it refers to."""
    comment = ratable_comment(comment_id)
    database.delete_rating(comment_id, g.user["id"])
    flash("Feedback rating removed.")
    return redirect(url_for("resumes.detail", resume_id=comment["resume_id"],
                            _anchor=f"comment-{comment_id}"), code=303)


@bp.get("/reviewers/<int:user_id>")
@login_required
def reviewer(user_id):
    """Show only the member ID and derived helpfulness, never their email or hash."""
    if database.get_user_by_id(user_id) is None:
        abort(404)
    return render_template("reviewer.html", user_id=user_id,
                           reputation=database.get_reputation(user_id))
