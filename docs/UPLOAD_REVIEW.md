# Import résumé files for review (#76)

This is an extension of PR #77, based on feature/feedback-file-upload. It does not
duplicate the original upload implementation or depend on the separate identity,
navigation, Quill or revision PR stack.

## User flow

Choose a PDF/DOCX file and press Import file for review. The server extracts text
into the existing form without creating or updating a résumé. Review/correct it,
remove private details, then submit. Choosing a file and pressing the final Submit
button also routes through import/review, rather than publishing unchecked text.
The next form has no selected file, so edited text is what gets saved.

For existing résumés, only the owner can import a replacement. The database stays
unchanged until Save changes. Parsing errors preserve the previously entered text,
role and feedback request. There is no app-managed persistent original-file store;
normal request handling may spool temporary upload data before request cleanup.

## Parsing and limits

PDF: require the PDF signature, reject encrypted documents, cap at ten pages and
the original PR’s per-page decoded-content limit. Image-only/scanned PDFs require
OCR and receive a readable-text error; OCR is not implemented here.

DOCX: validate its ZIP/document structure and ten-MiB declared uncompressed size
before opening it. Extract body paragraphs and top-level tables in document order,
including cell text and without duplicate horizontally merged cells. Headers,
footers, nested-table layout and exact formatting are not preserved. Files and
extracted text are limited to two MiB and 20,000 characters respectively. The
request body permits a small multipart overhead above the file limit.

## Remaining review/deployment concerns

Browser verification confirmed DOCX import (including table cells), review before
saving, correction of extracted text, and final submission. Parsing still runs in
the web request, inherited from PR #77. File/page/
expansion limits reduce risk but do not guarantee a strict CPU/memory budget.
Before public deployment, review subprocess/time-budget isolation and parser
library versions. No database migration is introduced. When integrating with the
Quill/revision stack, imported text must use explicit plain format, and confirmed
Save changes—not import—must create the revision snapshot.

## Validation

`python -m unittest discover -s tests -v`: seven focused tests exercise real PDF
and DOCX files, table extraction order, review before publishing, corrected-text
saving, encrypted/blank/corrupt/unsupported files, file/text/ZIP-expansion limits,
owner permissions, CSRF and preserved existing content. Browser import/review/save flow was also verified with a fictional DOCX résumé.
The draft still awaits parser resource-isolation and dependency review.
