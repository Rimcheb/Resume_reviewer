import re
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from backend import database
from backend.sqlite_upgrade import upgrade_db
from test_identity import IdentityTests as Fixture


class ProfileTests(unittest.TestCase):
    setUp = Fixture.setUp
    login = Fixture.login

    def post(self, path, data):
        page = self.client.get('/account').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        return self.client.post(path, data={**data, 'csrf_token': token})

    def test_public_profile_has_name_fields_bio_without_private_account_data(self):
        self.assertEqual(self.post('/account/fields', {'review_fields': ['Data science', 'Software engineering', 'invalid']}).status_code, 303)
        self.assertEqual(self.post('/account/bio', {'expertise_bio': 'Built Python projects and reviewed internship résumés.'}).status_code, 303)
        page = self.client.get(f'/reviewers/{self.owner["id"]}').get_data(as_text=True)
        for text in ('Alex feedback', 'Software engineering', 'Data science', 'Built Python projects', 'self-reported', 'Edit your expertise'):
            self.assertIn(text, page)
        self.assertNotIn('private-owner@example.com', page)
        self.assertNotIn('unused', page)
        self.assertNotIn('<li>invalid</li>', page)
        self.login(self.peer['id'])
        self.assertNotIn('Edit your expertise', self.client.get(f'/reviewers/{self.owner["id"]}').get_data(as_text=True))

    def test_bio_updates_use_session_identity_and_escape_markup(self):
        self.post('/account/bio', {'expertise_bio': '<script>alert(1)</script>', 'user_id': self.peer['id']})
        with self.app.app_context():
            self.assertEqual(database.get_user_by_id(self.peer['id'])['expertise_bio'], '')
        page = self.client.get(f'/reviewers/{self.owner["id"]}').get_data(as_text=True)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
        self.assertNotIn('<script>alert(1)</script>', page)

    def test_empty_bio_can_be_cleared_and_limits_reject_invalid_updates(self):
        self.post('/account/bio', {'expertise_bio': 'Experience'})
        for bio in ('x'*501, 'Bad\x00bio'):
            self.assertEqual(self.post('/account/bio', {'expertise_bio': bio}).status_code, 400)
        with self.app.app_context():
            self.assertEqual(database.get_user_by_id(self.owner['id'])['expertise_bio'], 'Experience')
        self.assertEqual(self.post('/account/bio', {'expertise_bio': '  '}).status_code, 303)
        page = self.client.get(f'/reviewers/{self.owner["id"]}').get_data(as_text=True)
        self.assertIn('No expertise bio shared yet.', page)
        self.assertIn('No review fields shared yet.', page)
        self.assertEqual(self.client.post('/account/bio', data={'expertise_bio': 'No token'}).status_code, 400)

    def test_preferences_prioritize_known_aliases_without_hiding_other_fields(self):
        self.post('/account/fields', {'review_fields': ['Software engineering']})
        with self.app.app_context():
            database.create_resume(self.peer['id'], 'Finance example', 'Finance', '')
            database.create_resume(self.peer['id'], 'SWE example', 'SWE', '')
            records = database.list_resumes(preferred_fields=['Software engineering'])
            self.assertEqual(records[0]['target_field'], 'SWE')
        page = self.client.get('/resumes').get_data(as_text=True)
        self.assertIn('Résumés in your review fields appear first', page)
        self.assertLess(page.index('SWE #'), page.index('Finance #'))
        self.assertIn('Finance #', page)

    def test_profiles_and_updates_require_login(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get(f'/reviewers/{self.owner["id"]}').status_code, 302)
        page = anonymous.get('/login').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        self.assertEqual(anonymous.post('/account/bio', data={'expertise_bio': 'No', 'csrf_token': token}).status_code, 302)
        self.assertEqual(self.client.get('/reviewers/999999').status_code, 404)

    def test_v6_upgrade_keeps_accounts_and_data_and_can_repeat(self):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute('ALTER TABLE users DROP COLUMN review_fields')
            conn.execute('ALTER TABLE users DROP COLUMN expertise_bio')
            conn.execute('PRAGMA user_version = 6')
            conn.commit()
        backup = Path(self.temp.name) / 'v6.sqlite'
        with self.app.app_context():
            self.assertTrue(upgrade_db(backup))
            user = database.get_user_by_id(self.owner['id'])
            self.assertEqual(user['display_name'], 'Alex')
            self.assertEqual(user['review_fields'], [])
            self.assertEqual(user['expertise_bio'], '')
            self.assertEqual(database.get_resume_by_id(self.resume['id'])['content'], 'Resume text')
            self.assertFalse(upgrade_db(Path(self.temp.name) / 'unused.sqlite'))
        with closing(sqlite3.connect(backup)) as conn:
            self.assertNotIn('expertise_bio', [r[1] for r in conn.execute('PRAGMA table_info(users)')])


del Fixture
