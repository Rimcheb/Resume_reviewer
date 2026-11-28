import re
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from backend import database, sqlite_storage
from backend.models import ResumeRevision
from backend.sqlite_upgrade import upgrade_db
from test_identity import IdentityTests as Fixture


class RevisionTests(unittest.TestCase):
    setUp = Fixture.setUp
    login = Fixture.login

    def post_comment(self, content, revision_id):
        page = self.client.get(f'/resumes/{self.resume["id"]}').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        return self.client.post(f'/resumes/{self.resume["id"]}/comments', data={
            'comment': content, 'revision_id': revision_id, 'csrf_token': token})

    def test_stale_open_page_comment_keeps_reviewed_revision(self):
        page = self.client.get(f'/resumes/{self.resume["id"]}').get_data(as_text=True)
        viewed = int(re.search(r'name="revision_id" value="(\d+)"', page).group(1))
        with self.app.app_context():
            database.update_resume(self.resume['id'], 'Changed résumé', 'Data science', 'New request')
            latest = database.get_current_revision(self.resume['id'])
            self.assertNotEqual(latest['id'], viewed)
        self.assertEqual(self.post_comment('About the original', viewed).status_code, 303)
        with self.app.app_context():
            comment = database.list_comments(self.resume['id'])[-1]
            self.assertEqual(comment['revision_id'], viewed)
        page = self.client.get(f'/resumes/{self.resume["id"]}').get_data(as_text=True)
        self.assertIn('This feedback refers to an earlier version.', page)
        old = self.client.get(f'/resumes/{self.resume["id"]}/revisions/{viewed}').get_data(as_text=True)
        self.assertIn('Resume text', old)
        self.assertNotIn('Changed résumé', old)
        self.assertNotIn('Post comment', old)

    def test_noop_edits_do_not_create_versions_and_context_changes_do(self):
        with self.app.app_context():
            original = database.get_current_revision(self.resume['id'])
            database.update_resume(self.resume['id'], 'Resume text', 'Software', '')
            self.assertEqual(database.get_current_revision(self.resume['id'])['id'], original['id'])
            database.update_resume(self.resume['id'], 'Resume text', 'Software', 'New feedback request')
            self.assertNotEqual(database.get_current_revision(self.resume['id'])['id'], original['id'])
            self.assertEqual(database.get_revision(self.resume['id'], original['id'])['feedback_request'], '')

    def test_cross_resume_or_invalid_revision_rejected(self):
        with self.app.app_context():
            other = database.create_resume(self.peer['id'], 'Other résumé', 'Finance', '')
            foreign = database.get_current_revision(other['id'])['id']
        for revision in (foreign, 999999, 'not-an-id'):
            self.assertEqual(self.post_comment('Invalid context', revision).status_code, 400)
        self.assertEqual(self.client.get(f'/resumes/{self.resume["id"]}/revisions/{foreign}').status_code, 404)
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get(f'/resumes/{other["id"]}/revisions/{foreign}').status_code, 302)

    def test_validation_retry_preserves_revision_and_comment_edit_does_not_move_it(self):
        with self.app.app_context():
            viewed = database.get_current_revision(self.resume['id'])['id']
        retry = self.post_comment('', viewed).get_data(as_text=True)
        self.assertIn(f'name="revision_id" value="{viewed}"', retry)
        self.post_comment('Original comment', viewed)
        with self.app.app_context():
            comment = database.list_comments(self.resume['id'])[-1]
            database.update_resume(self.resume['id'], 'Changed', 'Software', '')
            database.update_comment(comment['id'], 'Edited comment')
            self.assertEqual(database.get_comment_by_id(comment['id'])['revision_id'], viewed)

    def test_deletion_removes_versions_and_comment_associations(self):
        with self.app.app_context():
            viewed = database.get_current_revision(self.resume['id'])['id']
            database.create_comment(self.resume['id'], self.peer['id'], 'Feedback', viewed)
            self.assertTrue(database.delete_resume(self.resume['id']))
            self.assertIsNone(database.get_revision(self.resume['id'], viewed))
            self.assertEqual(database.list_comments(self.resume['id']), [])
        self.assertEqual(self.client.get(f'/resumes/{self.resume["id"]}/revisions/{viewed}').status_code, 404)

    def test_v4_migration_keeps_old_comment_versions_unknown(self):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("""CREATE TABLE comments_v4 (
                id INTEGER PRIMARY KEY, resume_id INTEGER NOT NULL REFERENCES resumes(id),
                author_id INTEGER NOT NULL REFERENCES users(id), content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            conn.execute('INSERT INTO comments_v4 SELECT id, resume_id, author_id, content, created_at FROM comments')
            conn.execute('DROP TABLE comments')
            conn.execute('ALTER TABLE comments_v4 RENAME TO comments')
            conn.execute('DROP TABLE resume_revisions')
            conn.execute('PRAGMA user_version = 4')
            conn.commit()
        backup = Path(self.temp.name) / 'v4.sqlite'
        with self.app.app_context():
            self.assertTrue(upgrade_db(backup))
            self.assertEqual(database.get_current_revision(self.resume['id'])['content'], 'Resume text')
            self.assertIsNone(database.list_comments(self.resume['id'])[0]['revision_id'])
            self.assertFalse(upgrade_db(Path(self.temp.name) / 'unused.sqlite'))
            self.assertEqual(sqlite_storage.get_db().scalar(select(func.count()).select_from(ResumeRevision)), 1)
        with closing(sqlite3.connect(self.path)) as conn:
            references = [(row[3], row[2], row[4]) for row in conn.execute('PRAGMA foreign_key_list(comments)')]
            self.assertIn(('revision_id', 'resume_revisions', 'id'), references)
        with closing(sqlite3.connect(backup)) as conn:
            self.assertNotIn('resume_revisions', [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")])

    def test_failed_snapshot_rolls_back_resume_edit(self):
        with self.app.app_context():
            before = database.get_current_revision(self.resume['id'])
            with patch('backend.sqlite_storage.snapshot', side_effect=SQLAlchemyError('test failure')):
                with self.assertRaises(SQLAlchemyError):
                    database.update_resume(self.resume['id'], 'Must roll back', 'Software', '')
            self.assertEqual(database.get_resume_by_id(self.resume['id'])['content'], 'Resume text')
            self.assertEqual(database.get_current_revision(self.resume['id'])['id'], before['id'])


del Fixture
