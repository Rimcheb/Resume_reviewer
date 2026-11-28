import re
import unittest
from backend import database
import test_uploads as fixtures
from test_identity import IdentityTests as Fixture


class PreviewTests(unittest.TestCase):
    setUp = Fixture.setUp
    login = Fixture.login

    def post(self, path='/resumes/preview', **overrides):
        page = self.client.get('/resumes/new').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        data = {'csrf_token': token, 'resume': 'Unsaved <b>literal</b> résumé', 'content_format': 'plain',
                'target_field': 'SWE', 'feedback_request': 'Review my projects'}
        data.update(overrides)
        return self.client.post(path, data=data)

    def test_preview_preserves_plain_form_state_without_saving(self):
        result = self.post()
        self.assertEqual(result.status_code, 200)
        page = result.get_data(as_text=True)
        self.assertIn('Preview only — not published', page)
        self.assertIn('Unsaved &lt;b&gt;literal&lt;/b&gt; résumé', page)
        self.assertIn('<option selected>Software engineering</option>', page)
        self.assertIn('Review my projects', page)
        self.assertIn('action="/resumes"', page)
        with self.app.app_context():
            self.assertEqual(len(database.list_resumes()), 1)

    def test_formatted_preview_matches_saved_safe_rendering(self):
        self.app.config['RICH_TEXT_ENABLED'] = True
        content = '<h2>Education</h2><p><strong>School</strong></p><script>bad()</script>'
        preview = self.post(resume=content, content_format='html')
        self.assertEqual(preview.status_code, 200)
        self.assertIn('<h2>Education</h2><p><strong>School</strong></p>', preview.get_data(as_text=True))
        self.assertNotIn('bad()', preview.get_data(as_text=True))
        saved = self.post('/resumes', resume=content, content_format='html')
        detail = self.client.get(saved.location).get_data(as_text=True)
        self.assertIn('<h2>Education</h2><p><strong>School</strong></p>', detail)
        self.assertNotIn('bad()', detail)

    def test_edit_preview_requires_owner_and_creates_no_revision(self):
        with self.app.app_context():
            original = database.get_current_revision(self.resume['id'])
        self.assertEqual(self.post(f'/resumes/{self.resume["id"]}/preview', resume='Edited but unsaved').status_code, 200)
        with self.app.app_context():
            self.assertEqual(database.get_current_revision(self.resume['id'])['id'], original['id'])
            self.assertEqual(database.get_resume_by_id(self.resume['id'])['content'], 'Resume text')
        self.login(self.peer['id'])
        self.assertEqual(self.post(f'/resumes/{self.resume["id"]}/preview').status_code, 403)
        self.assertEqual(self.post('/resumes/999999/preview').status_code, 404)

    def test_preview_uses_same_validation_and_feature_flag(self):
        for overrides in ({'resume': ''}, {'target_field': 'unknown'}, {'feedback_request': 'x'*1001},
                          {'resume': 'x'*20001}, {'content_format': 'unknown'}, {'content_format': 'html', 'resume': '<p>Example</p>'}):
            self.assertEqual(self.post(**overrides).status_code, 400)
        self.assertEqual(self.client.post('/resumes/preview', data={'resume': 'No CSRF'}).status_code, 400)

    def test_preview_of_selected_file_imports_without_publishing(self):
        from io import BytesIO
        result = self.post(resume_file=(BytesIO(fixtures.docx_bytes()), 'resume.docx'))
        self.assertEqual(result.status_code, 200)
        page = result.get_data(as_text=True)
        self.assertIn('Nothing has been saved yet', page)
        self.assertIn('Calculator project', page)
        self.assertIn('name="content_format" value="plain"', page)
        with self.app.app_context():
            self.assertEqual(len(database.list_resumes()), 1)

    def test_preview_requires_authentication(self):
        anonymous = self.app.test_client()
        page = anonymous.get('/login').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        result = anonymous.post('/resumes/preview', data={'csrf_token': token, 'resume': 'Example'})
        self.assertEqual(result.status_code, 302)


del Fixture
