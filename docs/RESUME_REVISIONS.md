# Reviewed résumé versions (#110)

New résumés receive an immutable snapshot. Changing content, its format, the target
field, or requested feedback creates another snapshot in the same transaction.
Saving unchanged values does not create a duplicate. Snapshot IDs are identifiers,
not per-résumé version counters.

The discussion form includes the revision shown when the page loaded. A stale
page can therefore submit feedback against the text actually reviewed. The server
validates that the revision belongs to the same résumé. A missing revision from
an older client is recorded as unknown rather than guessed. Comment edits retain
the original association; validation errors retain the submitted revision.

Comments link to the reviewed snapshot and indicate when a later edit exists.
Historical pages apply the current authenticated-member access policy, validate
the résumé/revision pairing, and sanitize rich text using the existing renderer.
Deleting a résumé removes its comments, ratings and snapshots atomically. Future
private-sharing changes must apply the same access helper to historical routes.

## Migration and deployment

Schema version 5 creates resume_revisions and nullable comments.revision_id. The
existing upgrade-db command first backs up to a new path. It captures each
existing résumé's current state, but leaves old comments unassociated: the earlier
text was never stored. No historical version is fabricated. Repeating the upgrade
is a no-op. Stop writes during deployment. Rollback requires restoring the backup
with the matching prior application version; later writes need separate recovery.

This branch depends on draft PR #115 and inherits the disabled-by-default Quill
HTML flag. It does not enable or implement the editor. Other storage backends must
implement equivalent snapshot/lookup semantics and the optional create_comment
revision argument when integrated.

## Validation

Run `python -m unittest discover -s tests -v`: 22 tests pass. Seven new tests cover
stale-page feedback, immutable content/context, no-op edits, revision access and
cross-résumé rejection, validation retries, comment edits, deletion, transaction
rollback, and a backed-up repeatable v4 migration. Local browser screenshots show
the outdated-feedback indicator and its original-text page.
