# Quill backend contract (#106)

This is backend groundwork. It does not install the Quill toolbar. Keep
RICH_TEXT_ENABLED=False until the frontend is connected and end-to-end checks pass.
The current textarea is not a rich-text editing experience. Never enable HTML
submissions in a deployed app before replacing it with the editor.

## Submission and editing

POST the existing form fields (resume, target_field, feedback_request, csrf_token)
plus content_format=html. Send HTML for resume; do not send Delta JSON. Plain-text
clients can omit content_format or send plain. Existing records explicitly default
to plain; HTML-looking text is never automatically interpreted as markup.

The HTML allowlist supports p/br, h1/h2/h3, strong/b, em/i, u, ul/ol/li, and span
with only ql-size-small, ql-size-large or ql-size-huge classes. Arbitrary CSS,
attributes, links, images, embeds, scripts and event handlers are not supported.
The frontend must use these same formats and preserve list structure. Validate
actual Quill output against this contract before enabling submissions. Unsupported
formatting is removed server-side; it must not be offered by the toolbar.

Limits: 20,000 text characters and 100,000 HTML characters. Blank, nonbreaking-space,
zero-width-only, embed-only and formatting-only submissions are rejected. Server
sanitization is mandatory regardless of what the client sends. The detail page
sanitizes HTML again before rendering; plain text remains escaped.

On edit, the textarea contains escaped HTML and a hidden content_format value.
The Quill integration must replace the textarea, initialize it using the stored
format, preserve existing plain-text content as text, and update the form payload.
The backend flag may be enabled through application config only after integration.

## Database deployment

Schema version 4 adds resumes.content_format with default plain. Before upgrade,
stop writes and run the existing upgrade-db command with a new backup path. The
migration supports earlier schemas, preserves content verbatim and is repeatable.
For rollback, restore the backup with the matching earlier application version;
newer writes after the backup require separate recovery.

## Validation

Run `python -m unittest discover -s tests -v`. Tests exercise the enabled
contract explicitly and verify that HTML submission is disabled by default.
Frontend follow-up: real Quill paste/save/edit/reload tests, mobile/keyboard toolbar
checks, and confirmation that sizes/lists survive sanitization. #106 remains open.

Sanitizer reference: https://nh3.readthedocs.io/en/latest/
