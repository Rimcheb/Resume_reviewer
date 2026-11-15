"""Disposable parser worker. Read a bounded document from stdin; emit bounded JSON."""

import json
import sys

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_PDF_PAGES = 10
MAX_DOCX_UNZIPPED = 10 * 1024 * 1024
MAX_PAGE_CONTENT = 1024 * 1024
RESUME_LIMIT = 20000


def apply_limits():
    """Bound CPU and memory before importing document parsers (POSIX hosts)."""
    import resource
    limits = [(resource.RLIMIT_CPU, 5)]
    # Darwin reports unlimited DATA/AS but rejects setting those limits. The
    # production Linux worker can enforce an address-space limit; Mac testing
    # retains the process, CPU, wall-clock, input and decompression boundaries.
    if sys.platform.startswith('linux'):
        limits.append((resource.RLIMIT_AS, 512 * 1024 * 1024))
    for kind, requested in limits:
        _, hard = resource.getrlimit(kind)
        cap = requested if hard == resource.RLIM_INFINITY else min(requested, hard)
        resource.setrlimit(kind, (cap, cap))


def file_text(upload):
    """Extract plain text inside a disposable, resource-limited process."""
    raw = upload.read(MAX_UPLOAD_BYTES + 1)
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        return None
    from io import BytesIO
    import zipfile
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from pypdf import PdfReader

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
            if len(text) > RESUME_LIMIT:
                break  # already too long; submission_error reports it
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
            text_length += sum(len(part) + 1 for part in parts[before:])
            if text_length > RESUME_LIMIT:
                break
        return "\n".join(parts).strip()
    return None


def main():
    """No database access, credentials, filesystem copies or raw exception output."""
    apply_limits()
    from io import BytesIO
    from types import SimpleNamespace
    raw = sys.stdin.buffer.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES or len(sys.argv) != 2 or sys.argv[1] not in ('.pdf', '.docx'):
        raise ValueError('Invalid parser input')
    stream = BytesIO(raw)
    text = file_text(SimpleNamespace(read=stream.read, filename='resume'+sys.argv[1]))
    if text is not None:
        text = text[:RESUME_LIMIT + 1]  # Preserve over-limit rejection without unbounded output.
    print(json.dumps(text))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        sys.exit(1)
