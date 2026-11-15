# Feedback backend integration

This branch combines PR #119's profile/field-preference/alias/revision/reply stack
with PR #118's upload-review extension. It is a review integration branch, not a
merge to main or deployment. Integration commit 142ed47 resolves upload-form and
content-format conflicts. Imported text is explicitly plain; failed imports retain
the current draft's format. Only confirmed saves create résumé revision snapshots.

## Parser resource boundaries

Document extraction runs in a fresh subprocess. Input arrives through stdin and
only a bounded JSON text result comes back. The process receives neither the app's
credential environment nor the user's original filename. It cannot access the app
through a passed database/session handle. This is resource containment, not an OS
security sandbox: the child still runs under the service account.

Each web process permits two active parser children and rejects extra imports
with a retryable busy response. A child has a ten-second wall-clock deadline and
a five-second CPU limit. Timed-out children are killed and reaped. Linux also caps
address space at 512 MiB. Darwin rejects DATA/AS limit changes, so macOS development
uses CPU/time/input/page/decompression limits without a hard memory cap. Validate
actual Linux-host limits and aggregate worker counts before deployment.

The existing two-MiB file limit, ten-page PDF limit, per-page decoded stream bound,
ten-MiB DOCX expansion limit and 20,000-character text limit remain. Parser output
is bounded. The parent handles unavailable workers, malformed results and parser
crashes without publishing or losing the existing draft. pypdf is updated to 7.1.0
and python-docx to 1.2.0; the real-file tests run against those pinned versions.

## Validation

`python -m unittest discover -s tests -v`: 53 tests pass. This includes every test
from the integrated branches plus worker timeout/cleanup/capacity/protocol checks,
platform-limit checks, a complete backed-up schema-v2-to-v7 upgrade preserving
ratings and unknown old comment history, and HTML-to-imported-plain replacement
with a snapshot created only on confirmed save. No extra schema migration beyond
version 7 is introduced by this integration.

## Remaining frontend and release work

- Connect and end-to-end test Amira's Quill toolbar; HTML submission stays disabled
  by default. Use docs/RICH_TEXT_CONTRACT.md.
- Draft protection (#107) can initially be frontend-only. Cross-device drafts need
  a separate agreed persistence scope; no server draft store is introduced here.
- Preview (#108) is the next small PR, reusing the current safe renderer.
- Review and merge dependency PRs in order; reconcile the parallel upload branch
  before retargeting this integration. Keep issues open until their requirements
  are merged and verified.
- Verify Linux deployment resource limits, database backup/upgrade/rollback, and
  public-site behavior in the release review. No production state was changed.
