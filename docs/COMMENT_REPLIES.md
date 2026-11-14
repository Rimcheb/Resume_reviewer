# Direct feedback replies (#109)

Authenticated members can reply to an available original comment using its Reply
link. The reply form quotes that comment. Replies appear directly beneath the
original comment, ordered by creation time and ID, with a link back to it. This
first implementation supports one reply level; replies to replies are rejected.

The server derives the author from the signed session and the reviewed revision
from the parent comment. Submitted author/revision values cannot override these.
A parent must belong to the same résumé, be an original comment, and not be deleted.
All existing CSRF, text validation, authorship and résumé access rules still apply.
Future private-sharing changes must protect the reply route along with detail and
revision routes. Reply edits cannot change parent, author or reviewed revision.

## Deletion

Deleting a comment with replies replaces its content with “Comment deleted.” and
removes its ratings, retaining the replies and their context. Deleted comments
cannot be edited, rated or receive further replies. Deleted comments do not count
as peer feedback or reputation. Comments without replies are deleted normally.
Deleting a reply leaves its parent intact. A placeholder may remain if its last
reply is later deleted. Deleting a résumé removes its full discussion and history
in one transaction. There is no recovery UI for deleted comment text.

## Migration and dependencies

Schema version 6 adds nullable comments.parent_id and is_deleted (default 0).
Existing comments become original comments. The upgrade-db command backs up the
old database to a new path and supports repeatable upgrades. Stop writes during
deployment. Rollback requires restoring that backup and matching earlier code;
newer writes after backup require separate recovery.

This PR is stacked on draft PR #116, with its earlier dependencies. It does not
enable Quill, merge the stack, or deploy anything. Other storage backends need the
optional parent_id create_comment argument and equivalent grouping/deletion rules.

## Validation

`python -m unittest discover -s tests -v`: 28 tests pass, including six new reply
tests covering session identity, inherited revision, parent validation, one-level
threads, authorship, CSRF, validation retry, deletion/rating behavior, full résumé
deletion and a repeatable version-5 migration. Local browser verification exercised
the reply form and posted a fictional reply in its thread.
