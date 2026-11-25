"""Validate resume submissions and serve pages for authenticated members."""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from backend import database
from backend.auth import login_required

bp = Blueprint("resumes", __name__)

RESUME_LIMIT = 20000
FIELD_LIMIT = 100
FEEDBACK_LIMIT = 1000
PAGE_SIZE = 10
MAX_PAGE = 1000000


def submission_error(content, target_field, feedback_request):
    """Return the first input problem, or None when the submission is valid."""
    if not content.strip() or len(content) > RESUME_LIMIT:
        return f"Enter resume text with 1 to {RESUME_LIMIT:,} characters."
    if not target_field.strip() or len(target_field) > FIELD_LIMIT:
        return f"Enter a target role or field with 1 to {FIELD_LIMIT} characters."
    if len(feedback_request) > FEEDBACK_LIMIT:
        return f"Keep your feedback request within {FEEDBACK_LIMIT:,} characters."
    return None


def submission_form(content="", target_field="", feedback_request="", error=None, resume=None):
    """Keep form values and limits together for initial display and errors."""
    return render_template(
        "submit_resume.html", content=content, target_field=target_field,
        feedback_request=feedback_request, error=error, resume=resume,
        resume_limit=RESUME_LIMIT, field_limit=FIELD_LIMIT, feedback_limit=FEEDBACK_LIMIT,
    )


@bp.get("/resumes/new")
@login_required
def new():
    """Show the existing submission form with a privacy explanation."""
    return submission_form()


@bp.post("/resumes")
@login_required
def create():
    """Save text under the signed-in user's ID and open its detail page."""
    content = request.form.get("resume", "")
    target_field = request.form.get("target_field", "")
    feedback_request = request.form.get("feedback_request", "")
    error = submission_error(content, target_field, feedback_request)
    if error is not None:
        return submission_form(content, target_field, feedback_request, error), 400
    resume = database.create_resume(
        g.user["id"], content, target_field.strip(), feedback_request
    )
    return redirect(url_for("resumes.detail", resume_id=resume["id"]), code=303)


@bp.get("/resumes/<int:resume_id>")
@login_required
def detail(resume_id):
    """Allow authenticated members to read a resume without account details."""
    resume = database.get_resume_by_id(resume_id)
    if resume is None:
        abort(404)
    comments = []
    return render_template("view_resume.html", resume=resume, comments=comments,
                           ratings={},
                           comment_limit=0)
