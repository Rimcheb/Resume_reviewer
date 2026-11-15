"""Run untrusted document extraction outside the web process with bounded lifetime."""

import json
from pathlib import Path
import subprocess
import sys
from threading import BoundedSemaphore

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_RESULT_BYTES = 160000
PARSE_TIMEOUT_SECONDS = 10
# Per web process; do not queue unlimited document parsers behind a busy server.
_PARSER_SLOTS = BoundedSemaphore(2)


class UploadError(ValueError):
    """A recoverable import error, safe to show without internal parser details."""
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def extract_upload(upload):
    """Bound input/output, isolate parser imports, and kill/reap timed-out workers."""
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in ('.pdf', '.docx'):
        return None
    raw = upload.read(MAX_UPLOAD_BYTES + 1)
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        return None
    if not _PARSER_SLOTS.acquire(blocking=False):
        raise UploadError('File import is busy. Try again shortly or paste your résumé text.', 503)
    try:
        try:
            process = subprocess.Popen(
                [sys.executable, '-m', 'backend.upload_parser', suffix],
                cwd=Path(__file__).resolve().parent.parent,
                env={'PYTHONIOENCODING': 'utf-8', 'LANG': 'C.UTF-8'},
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            raise UploadError('File import is unavailable. Try again later or paste your résumé text.', 503) from error
        try:
            output, _ = process.communicate(input=raw, timeout=PARSE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as error:
            process.kill()
            process.communicate()  # Reap the child and close its pipes.
            raise UploadError('This file took too long to read. Try a simpler PDF/DOCX or paste the text.') from error
        if process.returncode != 0 or len(output) > MAX_RESULT_BYTES:
            return None
        try:
            result = json.loads(output)
        except (ValueError, UnicodeDecodeError):
            return None
        return result if result is None or isinstance(result, str) else None
    finally:
        _PARSER_SLOTS.release()
