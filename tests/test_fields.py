import re
import tempfile
import unittest
from pathlib import Path
from backend.app import create_app
from backend import database, sqlite_storage
from backend.fields import normalize_field


class FieldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'DATABASE': str(Path(self.temp.name) / 'db.sqlite'), 'SESSION_COOKIE_SECURE': False})
        self.addCleanup(self.app.extensions['database_engine'].dispose)
        with self.app.app_context():
            sqlite_storage.init_db()
            self.user = database.create_user('test@example.com', 'unused')
            for label in ('SWE', 'Software Engineering intern', 'Finance', 'Unlisted role'):
                database.create_resume(self.user['id'], 'Example résumé', label, '')
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = self.user['id']

    def test_aliases_and_unknown_inputs(self):
        for value in ('SWE', 'software engineer', ' SOFTWARE   ENGINEERING ', 'Software Engineering intern'):
            self.assertEqual(normalize_field(value), 'Software engineering')
        for value in ('', 'SWE-not-real', 'Unlisted role', '%', '_'):
            self.assertIsNone(normalize_field(value))

    def test_filter_matches_legacy_and_canonical_roles(self):
        for value in ('SWE', 'software engineer', 'Software engineering'):
            response = self.client.get('/resumes', query_string={'field': value})
            self.assertEqual(response.status_code, 200)
            page = response.get_data(as_text=True)
            self.assertIn('SWE #', page)
            self.assertIn('Software Engineering intern #', page)
            self.assertNotIn('Finance #', page)
            self.assertNotIn('Unlisted role #', page)
        self.assertEqual(self.client.get('/resumes?field=unknown').status_code, 400)
        with self.app.app_context():
            self.assertEqual(len(database.list_resumes(target_field='Software engineering', limit=1)), 1)
            self.assertEqual(len(database.list_resumes(target_field='Software engineering', offset=1)), 1)
            self.assertEqual(database.get_resume_by_id(1)['target_field'], 'SWE')

    def test_submission_normalizes_alias_and_rejects_unknown(self):
        page = self.client.get('/resumes/new').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        payload = {'csrf_token': token, 'resume': 'A new résumé', 'target_field': 'swe'}
        self.assertEqual(self.client.post('/resumes', data=payload).status_code, 303)
        with self.app.app_context():
            self.assertEqual(database.list_resumes()[0]['target_field'], 'Software engineering')
        payload['target_field'] = 'Unknown'
        self.assertEqual(self.client.post('/resumes', data=payload).status_code, 400)

    def test_legacy_edit_selects_category_and_preserves_unknown_label(self):
        known = self.client.get('/resumes/1/edit').get_data(as_text=True)
        self.assertIn('<option selected>Software engineering</option>', known)
        unknown = self.client.get('/resumes/4/edit').get_data(as_text=True)
        self.assertIn('Unlisted role', unknown)
        self.assertIn('Choose the closest field', unknown)
