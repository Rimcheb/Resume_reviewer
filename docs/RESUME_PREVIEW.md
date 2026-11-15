# Unpublished résumé preview (#108)

Submission and edit forms offer Preview résumé. The preview uses the same
resume_content renderer and shared document styles as the saved detail/history
pages. It shows a clear Preview only — not published notice, keeps the editable
form and its role/feedback/format values, and offers preview-again or final save.
Plain text stays escaped. When the separately gated Quill integration is enabled,
HTML is sanitized using the same allowlist as final submission.

POST /resumes/preview or /resumes/<id>/preview with the existing form fields and
CSRF token. Preview applies the same validation as save and checks ownership on
existing résumés. It never writes a résumé, comment or revision. A selected file
first goes through the import-review step; the user can then preview its text.
Only confirmed Submit/Save publishes and creates a revision. No server draft
store is introduced; navigating away is still the separate frontend draft task
#107. Quill remains disabled by default and still needs its frontend integration.

The shared .resume-text styles now also apply to preview/history pages, preserving
plain-text newlines and consistent document spacing instead of collapsing them.

## Dependencies and validation

Draft PR stacked on the combined backend integration (PR #120). No new migration
beyond schema 7. All 59 tests pass, including six new preview tests for preserved
state, plain/HTML rendering, final-render parity, owner permissions, feature flag,
validation/CSRF/authentication, file import and no-save/no-revision behavior.

Local browser verification exercised DOCX import through the isolated worker,
review, preview, correction, repeat preview and final save. Screenshots show the
unpublished preview and the saved corrected text. HTML/Quill round-trip tests are
still required once Amira connects the editor; this PR does not claim the full
rich-text editor is ready.
