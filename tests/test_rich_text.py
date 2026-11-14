import re
import unittest
from contextlib import closing
from pathlib import Path
import sqlite3
from backend import database
from backend.rich_text import prepare_content, render_content
from backend.sqlite_upgrade import upgrade_db
from test_identity import IdentityTests as Fixture


class RichTextTests(unittest.TestCase):
    setUp = Fixture.setUp
    login = Fixture.login

    def submit(self, content, content_format='html', path='/resumes'):
        page = self.client.get('/resumes/new').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        return self.client.post(path, data={'csrf_token': token, 'resume': content,
                    'content_format': content_format, 'target_field': 'Software', 'feedback_request': ''})

    def test_html_disabled_until_editor_integration(self):
        self.assertEqual(self.submit('<p>Example</p>').status_code, 400)
        self.assertEqual(self.submit('Plain example', 'plain').status_code, 303)

    def test_formatting_sanitized_saved_rendered_and_reopened(self):
        self.app.config['RICH_TEXT_ENABLED'] = True
        response = self.submit('<h2 onclick="bad()">Education</h2><p><strong>School</strong><em>Degree</em><span class="ql-size-large evil">Large</span></p><ul><li>Project</li></ul><script>bad()</script><img src=x onerror=bad()>')
        self.assertEqual(response.status_code, 303)
        page = self.client.get(response.location).get_data(as_text=True)
        self.assertIn('<h2>Education</h2>', page)
        self.assertIn('<strong>School</strong>', page)
        self.assertIn('class="ql-size-large"', page)
        self.assertNotIn('bad()', page)
        self.assertNotIn('evil', page)
        self.assertNotIn('<img', page)
        with self.app.app_context():
            stored = database.list_resumes()[0]
            self.assertEqual(stored['content_format'], 'html')
            self.assertEqual(prepare_content(stored['content'], 'html'), stored['content'])
        edit_page = self.client.get(response.location + '/edit').get_data(as_text=True)
        self.assertIn('name="content_format" value="html"', edit_page)
        self.assertIn('&lt;h2&gt;Education&lt;/h2&gt;', edit_page)
        updated = self.submit('<p><u>Updated</u></p>', path=response.location + '/edit')
        self.assertEqual(updated.status_code, 303)
        self.assertIn('<u>Updated</u>', self.client.get(response.location).get_data(as_text=True))

    def test_empty_invalid_and_oversize_submissions_rejected(self):
        self.app.config['RICH_TEXT_ENABLED'] = True
        for content in ('<p><br></p>', '<p>&nbsp;\u200b</p>', '<script>only script</script>', '<img src=x>', '<p>'+'x'*20001+'</p>', '<p>'+' '*100001+'</p>'):
            with self.subTest(content=content[:40]):
                self.assertEqual(self.submit(content).status_code, 400)
        self.assertEqual(self.submit('Example', 'unknown').status_code, 400)
        self.assertEqual(self.submit('<p>Example</p>', path=f'/resumes/{self.resume["id"]}/edit').status_code, 303)
        self.login(self.peer['id'])
        self.assertEqual(self.submit('<p>Forbidden</p>', path=f'/resumes/{self.resume["id"]}/edit').status_code, 403)

    def test_plain_text_is_never_inferred_as_html(self):
        result = self.submit('<strong>literal</strong>', 'plain')
        page = self.client.get(result.location).get_data(as_text=True)
        self.assertIn('&lt;strong&gt;literal&lt;/strong&gt;', page)
        self.assertEqual(str(render_content('<script>bad()</script><p>Safe</p>', 'html')), '<p>Safe</p>')

    def test_version_three_upgrade_marks_existing_resumes_plain(self):
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute('ALTER TABLE resumes DROP COLUMN content_format')
            conn.execute('PRAGMA user_version = 3')
            conn.commit()
        with self.app.app_context():
            self.assertTrue(upgrade_db(Path(self.temp.name) / 'v3.sqlite'))
            record = database.get_resume_by_id(self.resume['id'])
            self.assertEqual(record['content_format'], 'plain')
            self.assertEqual(record['content'], 'Resume text')
            self.assertFalse(upgrade_db(Path(self.temp.name) / 'unused.sqlite'))


del Fixture
