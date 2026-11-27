import re
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from backend import database
from backend.sqlite_upgrade import upgrade_db
from test_identity import IdentityTests as Fixture


class ReplyTests(unittest.TestCase):
    login = Fixture.login
    setup_fixture = Fixture.setUp

    def setUp(self):
        self.setup_fixture()
        with self.app.app_context():
            self.revision = database.get_current_revision(self.resume['id'])['id']
            self.parent = database.create_comment(self.resume['id'], self.peer['id'], 'Original advice', self.revision)

    def post(self, path, data):
        page = self.client.get('/account').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        return self.client.post(path, data={**data, 'csrf_token': token})

    def reply(self, **overrides):
        data = {'comment': 'Thanks for the advice', 'parent_id': self.parent['id']}
        data.update(overrides)
        return self.post(f'/resumes/{self.resume["id"]}/comments', data)

    def test_reply_uses_session_author_and_parent_revision(self):
        with self.app.app_context():
            database.update_resume(self.resume['id'], 'Updated text', 'Software', '')
        response = self.reply(author_id=self.peer['id'], revision_id=999999)
        self.assertEqual(response.status_code, 303)
        with self.app.app_context():
            records = database.list_comments(self.resume['id'])
            child = records[-1]
            self.assertEqual(child['author_id'], self.owner['id'])
            self.assertEqual(child['parent_id'], self.parent['id'])
            self.assertEqual(child['revision_id'], self.revision)
        page = self.client.get(response.location).get_data(as_text=True)
        self.assertIn('class="comment-reply"', page)
        self.assertIn('Thanks for the advice', page)
        for comment in (self.parent, child):
            article = re.search(rf'<article id="comment-{comment["id"]}">(.*?)</article>', page, re.S)
            self.assertIsNotNone(article)
            link = re.search(r'<a href="([^"]+)">View reviewed version</a>', article.group(1))
            self.assertIsNotNone(link)
            self.assertEqual(link.group(1), f'/resumes/{self.resume["id"]}/revisions/{self.revision}')
            history = self.client.get(link.group(1))
            self.assertEqual(history.status_code, 200)
            self.assertIn('Resume text', history.get_data(as_text=True))
            self.assertNotIn('Updated text', history.get_data(as_text=True))
        form = self.client.get(f'/comments/{self.parent["id"]}/reply').get_data(as_text=True)
        self.assertIn('Original advice', form)
        self.assertIn(f'name="parent_id" value="{self.parent["id"]}"', form)

    def test_invalid_cross_resume_and_nested_parents_rejected(self):
        self.reply()
        with self.app.app_context():
            child = database.list_comments(self.resume['id'])[-1]
            other = database.create_resume(self.owner['id'], 'Other résumé', 'Finance', '')
            foreign = database.create_comment(other['id'], self.peer['id'], 'Foreign advice')
        for parent in ('bad', 999999, child['id'], foreign['id']):
            self.assertEqual(self.reply(parent_id=parent).status_code, 400)
        self.assertEqual(self.client.get(f'/comments/{child["id"]}/reply').status_code, 404)
        self.assertEqual(self.app.test_client().get(f'/comments/{self.parent["id"]}/reply').status_code, 302)

    def test_parent_delete_preserves_replies_and_removes_rating(self):
        self.reply()
        self.post(f'/comments/{self.parent["id"]}/rating', {'helpful': '1'})
        self.login(self.peer['id'])
        self.assertEqual(self.post(f'/comments/{self.parent["id"]}/delete', {}).status_code, 303)
        with self.app.app_context():
            parent = database.get_comment_by_id(self.parent['id'])
            self.assertTrue(parent['is_deleted'])
            self.assertEqual(parent['content'], 'Comment deleted.')
            self.assertEqual(database.get_reputation(self.peer['id'])['total'], 0)
            self.assertEqual(database.list_comments(self.resume['id'])[-1]['content'], 'Thanks for the advice')
        self.assertEqual(self.reply().status_code, 400)
        self.assertEqual(self.client.get(f'/comments/{self.parent["id"]}/edit').status_code, 404)
        self.assertEqual(self.post(f'/comments/{self.parent["id"]}/rating', {'helpful': '1'}).status_code, 404)

    def test_reply_edit_delete_permissions_and_parent_survival(self):
        self.reply()
        with self.app.app_context():
            child = database.list_comments(self.resume['id'])[-1]
        self.login(self.peer['id'])
        self.assertEqual(self.post(f'/comments/{child["id"]}/edit', {'comment': 'Forbidden'}).status_code, 403)
        self.assertEqual(self.post(f'/comments/{child["id"]}/delete', {}).status_code, 403)
        self.login(self.owner['id'])
        self.assertEqual(self.post(f'/comments/{child["id"]}/edit', {'comment': 'Updated reply', 'parent_id': 999}).status_code, 303)
        with self.app.app_context():
            self.assertEqual(database.get_comment_by_id(child['id'])['parent_id'], self.parent['id'])
        self.assertEqual(self.post(f'/comments/{child["id"]}/delete', {}).status_code, 303)
        with self.app.app_context():
            self.assertIsNone(database.get_comment_by_id(child['id']))
            self.assertFalse(database.get_comment_by_id(self.parent['id'])['is_deleted'])

    def test_validation_retry_keeps_parent_and_whole_resume_delete_works(self):
        response = self.reply(comment='')
        self.assertEqual(response.status_code, 400)
        self.assertIn(f'name="parent_id" value="{self.parent["id"]}"', response.get_data(as_text=True))
        self.assertEqual(self.client.post(f'/resumes/{self.resume["id"]}/comments', data={'comment': 'No token', 'parent_id': self.parent['id']}).status_code, 400)
        self.reply()
        with self.app.app_context():
            self.assertTrue(database.delete_resume(self.resume['id']))
            self.assertEqual(database.list_comments(self.resume['id']), [])

    def test_v5_migration_keeps_existing_comments_as_roots(self):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("""CREATE TABLE comments_v5 (
                id INTEGER PRIMARY KEY, resume_id INTEGER NOT NULL REFERENCES resumes(id),
                author_id INTEGER NOT NULL REFERENCES users(id), content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                revision_id INTEGER REFERENCES resume_revisions(id))""")
            conn.execute('INSERT INTO comments_v5 SELECT id, resume_id, author_id, content, created_at, revision_id FROM comments')
            conn.execute('DROP TABLE comments')
            conn.execute('ALTER TABLE comments_v5 RENAME TO comments')
            conn.execute('PRAGMA user_version = 5')
            conn.commit()
        with self.app.app_context():
            self.assertTrue(upgrade_db(Path(self.temp.name) / 'v5.sqlite'))
            for comment in database.list_comments(self.resume['id']):
                self.assertIsNone(comment['parent_id'])
                self.assertFalse(comment['is_deleted'])
            self.assertFalse(upgrade_db(Path(self.temp.name) / 'unused.sqlite'))
        with closing(sqlite3.connect(self.path)) as conn:
            references = [(r[3], r[2], r[4]) for r in conn.execute('PRAGMA foreign_key_list(comments)')]
            self.assertIn(('parent_id', 'comments', 'id'), references)
            self.assertIn(('revision_id', 'resume_revisions', 'id'), references)


del Fixture
