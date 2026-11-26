import re
import tempfile
import unittest
from pathlib import Path
from werkzeug.security import check_password_hash
from backend.app import create_app
from backend import database

class AuthTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.app=create_app({'TESTING':True,'SECRET_KEY':'test-only','DATABASE':str(Path(temp.name)/'test.sqlite'),'SESSION_COOKIE_SECURE':False})
        self.addCleanup(self.app.extensions['database_engine'].dispose)
        self.app.test_cli_runner().invoke(args=['init-db'])
        self.client=self.app.test_client()
    def post(self,path,data):
        page=self.client.get(path).get_data(as_text=True)
        token=re.search(r'name="csrf_token" value="([^"]+)"',page).group(1)
        return self.client.post(path,data={**data,'csrf_token':token})
    def test_registration_login_logout_and_session_isolation(self):
        payload={'email':'alex@example.com','password':'a-long-password','display_name':'Alex'}
        self.assertEqual(self.post('/register',payload).status_code,303)
        with self.app.app_context():
            user=database.get_user_by_email(payload['email'])
            self.assertNotEqual(user['password_hash'],payload['password'])
            self.assertTrue(check_password_hash(user['password_hash'],payload['password']))
        self.assertEqual(self.post('/register',payload).status_code,409)
        self.assertEqual(self.post('/login?next=//evil.example',payload).location,'/resumes')
        page=self.client.get('/account').get_data(as_text=True)
        self.assertNotIn(user['password_hash'],page)
        self.assertEqual(self.app.test_client().get('/account').status_code,302)
        token=re.search(r'name="csrf_token" value="([^"]+)"',page).group(1)
        self.assertEqual(self.client.post('/logout',data={'csrf_token':token}).status_code,303)
        self.assertEqual(self.client.get('/account').status_code,302)
    def test_invalid_credentials_and_csrf(self):
        result=self.post('/register',{'email':'invalid','password':'long-password'})
        self.assertEqual(result.status_code,400)
        self.assertIn('class="message-error"',result.get_data(as_text=True))
        self.assertEqual(self.post('/login',{'email':'missing@example.com','password':'long-password'}).status_code,401)
        self.assertEqual(self.client.post('/register',data={'email':'x@example.com','password':'long-password'}).status_code,400)
