"""Validate resume submissions and serve pages for authenticated members."""

from urllib.parse import urlsplit, parse_qs

from flask import current_app, Blueprint, abort, flash, g, redirect, render_template, request, url_for

from backend import database
from backend.auth import login_required
from backend.comments import COMMENT_LIMIT
from backend.models import FIELDS
from backend.fields import normalize_field
from backend.permissions import require_owner
from backend.rich_text import HTML_LIMIT, TEXT_LIMIT, prepare_content
from backend.uploads import extract_upload, UploadError

bp = Blueprint("resumes", __name__)

RESUME_LIMIT = TEXT_LIMIT
FEEDBACK_LIMIT = 1000
PAGE_SIZE = 10
MAX_PAGE = 1000000


def submission_error(content, target_field, feedback_request, content_format="plain"):
    """Return the first input problem, or None when the submission is valid."""
    if content_format == "plain" and (not content.strip() or len(content) > RESUME_LIMIT):
        return f"Enter resume text with 1 to {RESUME_LIMIT:,} characters."
    if target_field not in FIELDS:
        return "Choose a target field from the list."
    if len(feedback_request) > FEEDBACK_LIMIT:
        return f"Keep your feedback request within {FEEDBACK_LIMIT:,} characters."
    return None


def submission_form(content="", target_field="", feedback_request="", error=None, resume=None, content_format="plain", preview=False):
    """Keep form values and limits together for initial display and errors."""
    return render_template(
        "submit_resume.html", content=content, target_field=normalize_field(target_field) or target_field,
        feedback_request=feedback_request, error=error, resume=resume, content_format=content_format,
        resume_limit=RESUME_LIMIT, fields=FIELDS, feedback_limit=FEEDBACK_LIMIT,
        html_limit=HTML_LIMIT, preview=preview,
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
    upload = request.files.get("resume_file")
    if upload is not None and upload.filename:
        return review_upload(upload)
    content = request.form.get("resume", "")
    target_field = normalize_field(request.form.get("target_field", "")) or ""
    feedback_request = request.form.get("feedback_request", "")
    content_format = request.form.get("content_format", "plain")
    try:
        content = submitted_content(content, content_format)
    except ValueError as problem:
        return submission_form(content, target_field, feedback_request, str(problem), content_format=content_format), 400
    error = submission_error(content, target_field, feedback_request, content_format)
    if error is not None:
        return submission_form(content, target_field, feedback_request, error, content_format=content_format), 400
    resume = database.create_resume(
        g.user["id"], content, target_field.strip(), feedback_request, content_format
    )
    return redirect(url_for("resumes.detail", resume_id=resume["id"]), code=303)


@bp.get("/resumes/<int:resume_id>")
@login_required
def detail(resume_id):
    """Allow authenticated members to read a resume without account details."""
    resume = database.get_resume_by_id(resume_id)
    if resume is None:
        abort(404)
    comments = database.list_comments(resume_id)
    return render_template("view_resume.html", resume=resume, comments=comments,
                           ratings=database.list_ratings(resume_id),
                           comment_limit=COMMENT_LIMIT, current_revision=database.get_current_revision(resume_id),
                           **list_return_context())


@bp.route("/resumes/<int:resume_id>/edit", methods=["GET", "POST"])
@login_required
def edit(resume_id):
    """Let the owner change resume text and context while keeping comments."""
    resume = database.get_resume_by_id(resume_id)
    if resume is None:
        abort(404)
    require_owner(resume["user_id"])
    if request.method == "POST":
        upload = request.files.get("resume_file")
        if upload is not None and upload.filename:
            return review_upload(upload, resume)
        content = request.form.get("resume", "")
        target_field = normalize_field(request.form.get("target_field", "")) or ""
        feedback_request = request.form.get("feedback_request", "")
        content_format = request.form.get("content_format", "plain")
        try:
            content = submitted_content(content, content_format)
        except ValueError as problem:
            return submission_form(content, target_field, feedback_request, str(problem), resume, content_format), 400
        error = submission_error(content, target_field, feedback_request, content_format)
        if error is not None:
            return submission_form(content, target_field, feedback_request, error, resume, content_format), 400
        changed = database.update_resume(resume_id, content, target_field.strip(), feedback_request, content_format)
        if not changed:
            abort(404)
        flash("Resume updated. Existing comments were kept.")
        return redirect(url_for("resumes.detail", resume_id=resume_id), code=303)
    return submission_form(resume["content"], resume["target_field"],
                           resume["feedback_request"], resume=resume, content_format=resume["content_format"])


@bp.post("/resumes/<int:resume_id>/delete")
@login_required
def delete(resume_id):
    """Let the owner remove a resume and all its comments together."""
    resume = database.get_resume_by_id(resume_id)
    if resume is None:
        abort(404)
    require_owner(resume["user_id"])
    if not database.delete_resume(resume_id):
        abort(404)
    flash("Resume and its comments deleted.")
    return redirect(url_for("resumes.mine"), code=303)


def resume_list(user_id=None):
    """Build either feed using a bounded page and an optional field filter from FIELDS."""
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        abort(400)
    if page < 1 or page > MAX_PAGE:
        abort(400)
    target_field = request.args.get("field", "").strip()
    if target_field:
        target_field = normalize_field(target_field)
        if target_field is None:
            abort(400)
    # Use preferences only when browsing the unfiltered community feed.
    preferred = g.user["review_fields"] if user_id is None and not target_field else []
    # One extra row tells us whether a next page exists without counting all rows.
    records = database.list_resumes(user_id, target_field, PAGE_SIZE + 1, (page - 1) * PAGE_SIZE,
                                    preferred)
    if page > 1 and not records:
        abort(404)
    return render_template(
        "resume_list.html", resumes=records[:PAGE_SIZE], has_next=len(records) > PAGE_SIZE,
        page=page, target_field=target_field, is_mine=user_id is not None,
        endpoint=request.endpoint, fields=FIELDS, preferred=preferred,
    )


@bp.get("/resumes")
@login_required
def feed():
    """Show community submissions to signed-in members."""
    return resume_list()


@bp.get("/my-resumes")
@login_required
def mine():
    """Show only submissions owned by the signed-in user."""
    return resume_list(g.user["id"])


def list_return_context():
    """Rebuild Back destinations from known list routes and bounded parameters."""
    fallback = {"back_url": url_for("resumes.feed"), "back_label": "Back to Browse"}
    value = request.args.get("return_to", "")
    try:
        parts = urlsplit(value)
        if parts.scheme or parts.netloc or parts.fragment or parts.path not in ("/resumes", "/my-resumes"):
            return fallback
        query = parse_qs(parts.query)
        page = int(query.get("page", ["1"])[0])
        field = query.get("field", [""])[0]
        if not 1 <= page <= MAX_PAGE:
            return fallback
        if field:
            field = normalize_field(field)
            if field is None:
                return fallback
    except ValueError:
        return fallback
    endpoint = "resumes.mine" if parts.path == "/my-resumes" else "resumes.feed"
    return {"back_url": url_for(endpoint, page=page, field=field),
            "back_label": "Back to My Résumés" if endpoint == "resumes.mine" else "Back to Browse"}


def submitted_content(content, content_format):
    """Keep HTML submission disabled until the Quill integration is ready."""
    if content_format == "html" and not current_app.config["RICH_TEXT_ENABLED"]:
        raise ValueError("Formatted editing is not available yet.")
    return prepare_content(content, content_format)


@bp.get("/resumes/<int:resume_id>/revisions/<int:revision_id>")
@login_required
def revision(resume_id, revision_id):
    """Apply current résumé access rules before showing immutable history."""
    resume = database.get_resume_by_id(resume_id)
    if resume is None:
        abort(404)
    record = database.get_revision(resume_id, revision_id)
    if record is None:
        abort(404)
    return render_template("resume_revision.html", resume=resume, revision=record)


UNREADABLE_FILE = "Upload a readable .pdf or .docx file, or paste your resume as text."


@bp.post("/resumes/import")
@bp.post("/resumes/<int:resume_id>/import")
@login_required
def import_file(resume_id=None):
    """Extract into an editable form without saving a résumé or retaining the file."""
    resume = None
    if resume_id is not None:
        resume = database.get_resume_by_id(resume_id)
        if resume is None:
            abort(404)
        require_owner(resume["user_id"])
    return review_upload(request.files.get("resume_file"), resume)


def review_upload(upload, resume=None):
    """Fill the editable form with imported plain text, or keep the draft on error."""
    pasted = request.form.get("resume", "")
    original_format = request.form.get("content_format", "plain")
    target = request.form.get("target_field", "")
    feedback = request.form.get("feedback_request", "")
    if upload is None or not upload.filename:
        return submission_form(pasted, target, feedback, "Choose a PDF or DOCX file to import.", resume, original_format), 400
    try:
        content = extract_upload(upload)
    except UploadError as error:
        return submission_form(pasted, target, feedback, str(error), resume, original_format), error.status
    if content is None:
        return submission_form(pasted, target, feedback, UNREADABLE_FILE, resume, original_format), 400
    if not content.strip():
        return submission_form(pasted, target, feedback,
            "No readable text was found. Scanned PDFs need text recognition; paste the text or use a text-based PDF/DOCX.", resume, original_format), 400
    if len(content) > RESUME_LIMIT:
        return submission_form(pasted, target, feedback,
            "The extracted résumé exceeds 20,000 characters. Use a shorter document or paste the relevant text.", resume, original_format), 400
    flash("File imported. Review the extracted text below, remove private details, and submit when ready. Nothing has been saved yet.")
    return submission_form(content, target, feedback, resume=resume)


@bp.post("/resumes/preview")
@bp.post("/resumes/<int:resume_id>/preview")
@login_required
def preview(resume_id=None):
    """Render the same safe content as detail, preserving form state without writes."""
    resume = None
    if resume_id is not None:
        resume = database.get_resume_by_id(resume_id)
        if resume is None:
            abort(404)
        require_owner(resume["user_id"])
    upload = request.files.get("resume_file")
    if upload is not None and upload.filename:
        return review_upload(upload, resume)
    content = request.form.get("resume", "")
    content_format = request.form.get("content_format", "plain")
    target = normalize_field(request.form.get("target_field", "")) or ""
    feedback = request.form.get("feedback_request", "")
    try:
        clean_content = submitted_content(content, content_format)
    except ValueError as error:
        return submission_form(content, target, feedback, str(error), resume, content_format), 400
    error = submission_error(clean_content, target, feedback, content_format)
    if error is not None:
        return submission_form(content, target, feedback, error, resume, content_format), 400
    return submission_form(clean_content, target, feedback, resume=resume,
                           content_format=content_format, preview=True)
