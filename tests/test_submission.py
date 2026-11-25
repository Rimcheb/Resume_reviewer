import re
import unittest
from backend import database
from test_auth import AuthTests

class SubmissionTests(unittest.TestCase):
    setUp = AuthTests.setUp
    def sign_in(self):
        with self.app.app_context():
            self.owner=database.create_user('owner@example.com','unused')
            self.peer=database.create_user('peer@example.com','unused')
        with self.client.session_transaction() as session:session['user_id']=self.owner['id']
        page=self.client.get('/resumes/new').get_data(as_text=True)
        self.token=re.search(r'name="csrf_token" value="([^"]+)"',page).group(1)
    def submit(self,**overrides):
        data={'resume':'First line\n<script>example</script>','target_field':'Software','feedback_request':'Check clarity','csrf_token':self.token,'user_id':self.peer['id']}
        data.update(overrides)
        return self.client.post('/resumes',data=data)
    def test_save_display_escape_session_owner_and_access(self):
        self.sign_in();response=self.submit();self.assertEqual(response.status_code,303)
        page=self.client.get(response.location).get_data(as_text=True)
        self.assertIn('&lt;script&gt;example&lt;/script&gt;',page)
        self.assertNotIn('<script>example</script>',page)
        self.assertIn('Check clarity',page)
        with self.app.app_context():
            row=database.get_resume_by_id(int(response.location.rsplit('/',1)[1]))
            self.assertEqual(row['user_id'],self.owner['id'])
            self.assertEqual(row['content'],'First line\n<script>example</script>')
        self.assertEqual(self.app.test_client().get(response.location).status_code,302)
        self.assertEqual(self.client.get('/resumes/9999').status_code,404)
    def test_validation_keeps_draft_and_csrf_prevents_write(self):
        self.sign_in()
        for payload in ({'target_field':''},{'resume':' '},{'resume':'x'*20001},{'target_field':'x'*101},{'feedback_request':'x'*1001}):
            with self.subTest(payload=list(payload)):
                response=self.submit(**payload);self.assertEqual(response.status_code,400)
        response=self.submit(target_field='')
        self.assertIn('Check clarity',response.get_data(as_text=True))
        self.assertIn('class="message-error"',response.get_data(as_text=True))
        self.assertEqual(self.submit(csrf_token='invalid').status_code,400)
    def test_readable_date_preserves_exact_timestamp_in_title(self):
        from backend.app import readable_date
        self.assertEqual(readable_date('2026-11-05 14:03:22'),'Nov 5, 2026')
        self.assertEqual(readable_date('unknown'),'unknown')
        self.sign_in();response=self.submit()
        self.assertIn('<time title=',self.client.get(response.location).get_data(as_text=True))

    def test_upgrade_preserves_legacy_text_and_creates_backup(self):
        from backend.sqlite_upgrade import upgrade_db
        import sqlite3
        from contextlib import closing
        from pathlib import Path
        self.sign_in()
        with self.app.app_context():
            resume=database.create_resume(self.owner['id'],'Legacy resume','Software','Original request')
        path=self.app.config['DATABASE']
        with closing(sqlite3.connect(path)) as connection:
            connection.execute('ALTER TABLE resumes DROP COLUMN target_field')
            connection.execute('ALTER TABLE resumes DROP COLUMN feedback_request')
            connection.execute('PRAGMA user_version=0')
            connection.commit()
        backup=Path(path).with_name('backup.sqlite')
        with self.app.app_context():
            self.assertTrue(upgrade_db(backup))
            row=database.get_resume_by_id(resume['id'])
            self.assertEqual(row['content'],'Legacy resume')
            self.assertEqual(row['target_field'],'')
            self.assertFalse(upgrade_db(Path(path).with_name('unused.sqlite')))
        with closing(sqlite3.connect(backup)) as connection:
            self.assertNotIn('target_field',[row[1] for row in connection.execute('PRAGMA table_info(resumes)')])

del AuthTests
