import re
from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.app import create_app
from backend import database, sqlite_storage
from backend.sqlite_upgrade import upgrade_db


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / 'test.sqlite')
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test-key',
                               'DATABASE': self.path, 'SESSION_COOKIE_SECURE': False})
        self.addCleanup(self.app.extensions['database_engine'].dispose)
        with self.app.app_context():
            sqlite_storage.init_db()
            self.owner = database.create_user('private-owner@example.com', 'unused', 'Alex')
            self.peer = database.create_user('private-peer@example.com', 'unused', 'Sam')
            self.resume = database.create_resume(self.owner['id'], 'Resume text', 'Software', '')
            database.create_comment(self.resume['id'], self.peer['id'], 'Add project details')
        self.client = self.app.test_client()
        self.login(self.owner['id'])

    def login(self, user_id):
        with self.client.session_transaction() as session:
            session['user_id'] = user_id

    def post_account(self, data):
        page = self.client.get('/account').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        return self.client.post('/account', data={**data, 'csrf_token': token})

    def test_names_and_ownership_visible_without_private_email(self):
        detail = self.client.get(f'/resumes/{self.resume["id"]}').get_data(as_text=True)
        self.assertIn('Sam</a>', detail)
        self.assertNotIn('private-peer@example.com', detail)
        profile = self.client.get(f'/reviewers/{self.peer["id"]}').get_data(as_text=True)
        self.assertIn('Sam feedback', profile)
        self.assertNotIn('private-peer@example.com', profile)
        self.assertIn('Your résumé', self.client.get('/resumes').get_data(as_text=True))
        self.login(self.peer['id'])
        self.assertNotIn('Your résumé', self.client.get('/resumes').get_data(as_text=True))

    def test_name_update_uses_session_identity_and_escapes_html(self):
        response = self.post_account({'display_name': '<b>Alex</b>', 'user_id': self.peer['id']})
        self.assertEqual(response.status_code, 303)
        with self.app.app_context():
            self.assertEqual(database.get_user_by_id(self.peer['id'])['display_name'], 'Sam')
        page = self.client.get(f'/reviewers/{self.owner["id"]}').get_data(as_text=True)
        self.assertIn('&lt;b&gt;Alex&lt;/b&gt;', page)
        self.assertNotIn('<b>Alex</b>', page)

    def test_invalid_names_and_csrf_rejected(self):
        for name in (' ', 'x' * 81, 'email@example.com', 'hidden\x00name'):
            with self.subTest(name=name):
                self.assertEqual(self.post_account({'display_name': name}).status_code, 400)
        self.assertEqual(self.client.post('/account', data={'display_name': 'Forged'}).status_code, 400)
        with self.app.app_context():
            self.assertEqual(database.get_user_by_id(self.owner['id'])['display_name'], 'Alex')

    def test_existing_account_migration_preserves_data_and_is_repeatable(self):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute('ALTER TABLE users DROP COLUMN display_name')
            conn.execute('PRAGMA user_version = 2')
            conn.commit()
        backup = Path(self.temp.name) / 'before.sqlite'
        with self.app.app_context():
            self.assertTrue(upgrade_db(backup))
            self.assertEqual(database.get_user_by_id(self.owner['id'])['display_name'], 'Reviewer')
            self.assertEqual(database.get_resume_by_id(self.resume['id'])['content'], 'Resume text')
            self.assertFalse(upgrade_db(Path(self.temp.name) / 'unused.sqlite'))
        with closing(sqlite3.connect(backup)) as conn:
            self.assertNotIn('display_name', [row[1] for row in conn.execute('PRAGMA table_info(users)')])
        self.assertFalse((Path(self.temp.name) / 'unused.sqlite').exists())

    def test_registration_saves_public_name(self):
        client = self.app.test_client()
        page = client.get('/register').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        response = client.post('/register', data={
            'email': 'new@example.com', 'password': 'long-test-password',
            'display_name': '  Taylor  ', 'csrf_token': token,
        })
        self.assertEqual(response.status_code, 303)
        with self.app.app_context():
            self.assertEqual(database.get_user_by_email('new@example.com')['display_name'], 'Taylor')

    def test_anonymous_account_updates_redirect(self):
        self.client = self.app.test_client()
        page = self.client.get('/login').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        self.assertEqual(self.client.post('/account', data={'display_name': 'No', 'csrf_token': token}).status_code, 302)
