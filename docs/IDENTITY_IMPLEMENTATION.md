# Display names and résumé ownership (#66, #68)

Users can choose a required public name during registration and change it on
Your account. Comments and reviewer profiles display that name; existing users
without one display as Reviewer until they set it. Names are not unique account
identifiers or verified identities. Comments and profiles also show a stable reviewer
number so people with the same name can be distinguished. Existing accounts keep
their names and may update them on Your account. Authentication continues to use email and the
signed session. Email addresses are never used as public-name fallbacks.

Browse and My Résumés mark the signed-in user's submissions as Your résumé.
Public names are bounded to 80 characters, reject @ and Unicode control/format
characters, and are escaped by Jinja. Account updates retain CSRF protection and
use the session's identity, ignoring submitted user IDs.

## Dependencies and review

This branch integrates the existing backend stack through
feature/release-reputation (PR #55). main does not yet contain that stack. Review
this identity change relative to the integration commit 68cc336; do not treat the
inherited backend as new identity work. The current main README/project plan were
preserved during integration. This implements the identity portion of #66 and
ownership badge portion of #68; date formatting and broader card styling remain.

## Existing database deployment

Stop writes and use the existing upgrade command with a new backup path:

    SECRET_KEY=... .venv/bin/flask --app app upgrade-db --backup /path/to/new-backup.sqlite

Schema version 3 adds users.display_name with an empty default. Existing rows and
IDs are preserved; the backup contains the pre-upgrade database. Repeating the
upgrade is a no-op. Never run init-db on an existing database. To roll back, stop
the app and restore the backup together with the matching previous app version;
changes made after the backup would need separate recovery.

## Validation

    .venv/bin/python -m unittest discover -s tests -v

Tests cover registration, public name rendering and escaping, private-email
non-disclosure, owner badges, authenticated name changes, forged user IDs, invalid
names, CSRF, anonymous access, and a repeatable backed-up version-2 migration.

## Review updates

Registration requires a valid display name and preserves the first email/password
validation error. Duplicate names remain allowed; public reviewer numbers distinguish
profiles without exposing email. Ownership uses the shared accent badge. Integrated
#75, #81 and #96 from the updated base, preserving the dropdown, score threshold,
exaggeration flags and the shared backed-up model-column migration. The migration
also detects a missing display_name column when the existing database is already
version 3 from #96; readiness checks the actual mapped columns.
