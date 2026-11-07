"""Validate and save feedback from authenticated members."""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from backend import database
from backend.auth import login_required
from backend.permissions import require_owner

bp = Blueprint("comments", __name__)
COMMENT_LIMIT = 5000
SECTION_LIMIT = 1200  # four sections plus labels stay under COMMENT_LIMIT

# The review template from the survey: (form name, label, hint).
SECTIONS = (
    ("clarity", "Clarity & grammar", "Typos, unclear sentences, wording that could be tighter."),
    ("formatting", "Formatting", "Layout, length, consistency, how easy it is to skim."),
    ("role_fit", "Fit for the target role", "What a recruiter in this field would look for and miss."),
    ("top_changes", "Top 3 changes, and why", "Number them 1 to 3. Say where each change goes and why it matters."),
)


def comment_error(content):
    """Return an input problem, or None for valid feedback or a follow-up."""
    if not content.strip() or len(content) > COMMENT_LIMIT:
        return f"Enter a comment with 1 to {COMMENT_LIMIT:,} characters."
    return None


def review_content(form):
    """Join the template sections into one comment; return an error message if one is missing.

    Saving the sections as labelled text keeps the database unchanged.
    """
    parts = [(label, form.get(key, "").strip()) for key, label, _ in SECTIONS]
    if not all(text for _, text in parts):
        return None, "Fill in every section of the review."
    if any(len(text) > SECTION_LIMIT for _, text in parts):
        return None, f"Keep each section within {SECTION_LIMIT:,} characters."
    return "\n\n".join(f"{label}:\n{text}" for label, text in parts), None


@bp.post("/resumes/<int:resume_id>/comments")
@login_required
def create(resume_id):
    """Save a review from the template, or a free-text follow-up from the resume owner."""
    resume = database.get_resume_by_id(resume_id)
    if resume is None:
        abort(404)
    is_owner = resume["user_id"] == g.user["id"]
    if is_owner:
        content = request.form.get("comment", "")
        error = comment_error(content)
    else:
        content, error = review_content(request.form)
    if error is not None:
        return render_template("comment_form.html", resume=resume, content=content or "",
                               error=error, comment_limit=COMMENT_LIMIT, comment=None,
                               sections=None if is_owner else SECTIONS,
                               section_limit=SECTION_LIMIT, values=request.form), 400
    comment = database.create_comment(resume_id, g.user["id"], content)
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
