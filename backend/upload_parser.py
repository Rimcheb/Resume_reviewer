"""Disposable parser worker. Read a bounded document from stdin; emit bounded JSON."""

import json
import sys

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_PDF_PAGES = 10
MAX_DOCX_UNZIPPED = 10 * 1024 * 1024
MAX_PAGE_CONTENT = 1024 * 1024
RESUME_LIMIT = 20000
CPU_SECONDS = 5
MEMORY_BYTES = 512 * 1024 * 1024


def apply_limits():
    """Set the worker's resource limits before loading the document libraries."""
    if sys.platform == "win32":
        import win32api
        import win32job

        job = win32job.CreateJobObject(None, "")
        kind = win32job.JobObjectExtendedLimitInformation
        limits = win32job.QueryInformationJobObject(job, kind)
        basic = limits["BasicLimitInformation"]
        basic["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_PROCESS_TIME | win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
        basic["PerProcessUserTimeLimit"] = CPU_SECONDS * 10_000_000  # Windows uses 100 ns units.
        limits["ProcessMemoryLimit"] = MEMORY_BYTES
        win32job.SetInformationJobObject(job, kind, limits)
        win32job.AssignProcessToJobObject(job, win32api.GetCurrentProcess())
        return

    import resource
    limits = [(resource.RLIMIT_CPU, CPU_SECONDS)]
    # Darwin reports unlimited DATA/AS but rejects setting those limits. The
    # production Linux worker can enforce an address-space limit; Mac testing
    # retains the process, CPU, wall-clock, input and decompression boundaries.
    if sys.platform.startswith('linux'):
        limits.append((resource.RLIMIT_AS, MEMORY_BYTES))
    for kind, requested in limits:
        _, hard = resource.getrlimit(kind)
        cap = requested if hard == resource.RLIM_INFINITY else min(requested, hard)
        resource.setrlimit(kind, (cap, cap))


def file_text(raw, suffix):
    """Extract plain text inside a disposable, resource-limited process."""
    if not raw:
        return None
    from io import BytesIO

    data = BytesIO(raw)
    if suffix == ".pdf":
        if not raw.startswith(b"%PDF-"):
            return None
        from pypdf import PdfReader

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
    if suffix == ".docx":
        import zipfile
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph

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


def main():
    """No database access, credentials, filesystem copies or raw exception output."""
    apply_limits()
    raw = sys.stdin.buffer.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES or len(sys.argv) != 2 or sys.argv[1] not in ('.pdf', '.docx'):
        raise ValueError('Invalid parser input')
    text = file_text(raw, sys.argv[1])
    if text is not None:
        text = text[:RESUME_LIMIT + 1]  # Preserve over-limit rejection without unbounded output.
    print(json.dumps(text, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        sys.exit(1)
