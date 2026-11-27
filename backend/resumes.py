"""Validate resume submissions and serve pages for authenticated members."""

from io import BytesIO
import zipfile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from pypdf import PdfReader

from backend import database
from backend.auth import login_required
from backend.comments import COMMENT_LIMIT
from backend.models import FIELDS
from backend.permissions import require_owner

bp = Blueprint("resumes", __name__)

RESUME_LIMIT = 20000
FEEDBACK_LIMIT = 1000
PAGE_SIZE = 10
MAX_PAGE = 1000000


def submission_error(content, target_field, feedback_request):
    """Return the first input problem, or None when the submission is valid."""
    if not content.strip() or len(content) > RESUME_LIMIT:
        return f"Enter resume text with 1 to {RESUME_LIMIT:,} characters."
    if target_field not in FIELDS:
        return "Choose a target field from the list."
    if len(feedback_request) > FEEDBACK_LIMIT:
        return f"Keep your feedback request within {FEEDBACK_LIMIT:,} characters."
    return None


MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_PDF_PAGES = 10
MAX_DOCX_UNZIPPED = 10 * 1024 * 1024
MAX_PAGE_CONTENT = 1024 * 1024  # a text-heavy resume page is well under 100 KB


def file_text(upload):
    """Extract plain text, checking page and unpacked-size limits before parsing."""
    raw = upload.read(MAX_UPLOAD_BYTES + 1)
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        return None
    data = BytesIO(raw)
    name = upload.filename.lower()
    if name.endswith(".pdf"):
        if not raw.startswith(b"%PDF-"):
            return None
        reader = PdfReader(data)
        if reader.is_encrypted:
            return None
        if len(reader.pages) > MAX_PDF_PAGES:
            return None
        text = ""
        for page in reader.pages:
            contents = page.get_contents()
            if contents is not None and len(contents.get_data()) > MAX_PAGE_CONTENT:
                return None
            text += (page.extract_text() or "") + "\n"
            if len(text.strip()) > RESUME_LIMIT:
                break  # The import form reports the length error.
        return text.strip()
    if name.endswith(".docx"):
        with zipfile.ZipFile(data) as archive:
            if sum(entry.file_size for entry in archive.infolist()) > MAX_DOCX_UNZIPPED:
                return None
            if "word/document.xml" not in archive.namelist():
                return None
        data.seek(0)
        parts = []
        text_length = 0
        for block in Document(data).iter_inner_content():
            before = len(parts)
            if isinstance(block, Paragraph):
                parts.append(block.text)
            elif isinstance(block, Table):
                for row in block.rows:
                    seen = set()
                    cells = []
                    for cell in row.cells:
                        if cell._tc not in seen:
                            seen.add(cell._tc)
                            cells.append(cell.text)
                    parts.append("\t".join(cells))
            # Stop early only if the text exceeds the limit even without separators.
            text_length += sum(len(part.strip()) for part in parts[before:])
            if text_length > RESUME_LIMIT:
                break
        return "\n".join(parts).strip()
    return None


UNREADABLE_FILE = "Upload a readable .pdf or .docx file, or paste your resume as text."


def submission_form(content="", target_field="", feedback_request="", error=None, resume=None):
    """Keep form values and limits together for initial display and errors."""
    return render_template(
        "submit_resume.html", content=content, target_field=target_field,
        feedback_request=feedback_request, error=error, resume=resume,
        resume_limit=RESUME_LIMIT, fields=FIELDS, feedback_limit=FEEDBACK_LIMIT,
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
    comments = database.list_comments(resume_id)
    return render_template("view_resume.html", resume=resume, comments=comments,
                           ratings=database.list_ratings(resume_id),
                           comment_limit=COMMENT_LIMIT)


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
        target_field = request.form.get("target_field", "")
        feedback_request = request.form.get("feedback_request", "")
        error = submission_error(content, target_field, feedback_request)
        if error is not None:
            return submission_form(content, target_field, feedback_request, error, resume), 400
        changed = database.update_resume(resume_id, content, target_field.strip(), feedback_request)
        if not changed:
            abort(404)
        flash("Resume updated. Existing comments were kept.")
        return redirect(url_for("resumes.detail", resume_id=resume_id), code=303)
    return submission_form(resume["content"], resume["target_field"],
                           resume["feedback_request"], resume=resume)


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
    if target_field and target_field not in FIELDS:
        abort(400)
    # ponytail: storage still matches by substring, so résumés saved before the
    # dropdown existed (free text like "Software Engineering intern") still show up.
    # One extra row tells us whether a next page exists without counting all rows.
    records = database.list_resumes(user_id, target_field, PAGE_SIZE + 1, (page - 1) * PAGE_SIZE)
    if page > 1 and not records:
        abort(404)
    return render_template(
        "resume_list.html", resumes=records[:PAGE_SIZE], has_next=len(records) > PAGE_SIZE,
        page=page, target_field=target_field, is_mine=user_id is not None,
        endpoint=request.endpoint, fields=FIELDS,
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
    """Fill the editable form with imported text, or keep the draft on error."""
    pasted = request.form.get("resume", "")
    target = request.form.get("target_field", "")
    feedback = request.form.get("feedback_request", "")
    if upload is None or not upload.filename:
        return submission_form(pasted, target, feedback, "Choose a PDF or DOCX file to import.", resume), 400
    try:
        content = file_text(upload)
    except Exception:  # Both parsers raise several kinds of errors for unreadable files.
        content = None
    if content is None:
        return submission_form(pasted, target, feedback, UNREADABLE_FILE, resume), 400
    if not content.strip():
        return submission_form(pasted, target, feedback,
            "No readable text was found. Scanned PDFs need text recognition; paste the text or use a text-based PDF/DOCX.", resume), 400
    if len(content) > RESUME_LIMIT:
        return submission_form(pasted, target, feedback,
            "The extracted résumé exceeds 20,000 characters. Use a shorter document or paste the relevant text.", resume), 400
    flash("File imported. Review the extracted text below, remove private details, and submit when ready. Nothing has been saved yet.")
    return submission_form(content, target, feedback, resume=resume)
