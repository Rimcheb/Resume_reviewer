import re
import unittest
from urllib.parse import quote, urlsplit, parse_qs
from werkzeug.security import generate_password_hash
from backend.auth import safe_next
from backend import database
from test_identity import IdentityTests as Fixture


class NavigationTests(unittest.TestCase):
    setUp = Fixture.setUp
    login = Fixture.login

    def test_default_login_and_home_land_on_browse(self):
        with self.app.app_context():
            database.create_user('login@example.com', generate_password_hash('test-password'), 'Login')
        client = self.app.test_client()
        page = client.get('/login').get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        result = client.post('/login', data={'email': 'login@example.com', 'password': 'test-password', 'csrf_token': token})
        self.assertEqual(result.status_code, 303)
        self.assertEqual(result.location, '/resumes')
        self.assertEqual(client.get('/').location, '/resumes')

    def test_login_return_destinations_are_safe(self):
        with self.app.test_request_context():
            for value in ('https://evil.example', '//evil.example', '/\\evil', '/%2f%2fevil', '/%0d%0aLocation:evil', ''):
                with self.subTest(value=value):
                    self.assertEqual(safe_next(value), '/resumes')
            self.assertEqual(safe_next('/resumes?field=SWE&page=2'), '/resumes?field=SWE&page=2')
        anonymous = self.app.test_client()
        result = anonymous.get('/resumes?field=SWE&page=2')
        self.assertEqual(parse_qs(urlsplit(result.location).query)['next'], ['/resumes?field=SWE&page=2'])

    def test_back_links_keep_list_filter_and_page(self):
        destination = '/my-resumes?field=Software&page=1'
        page = self.client.get(f'/resumes/{self.resume["id"]}?return_to={quote(destination, safe="")}').get_data(as_text=True)
        self.assertIn('Back to My Résumés', page)
        self.assertIn('/my-resumes?page=1&amp;field=Software+engineering', page)
        for destination in ('//evil.example/resumes', '/account', '/resumes?page=-1', '/resumes?page=no'):
            page = self.client.get(f'/resumes/{self.resume["id"]}?return_to={quote(destination, safe="")}').get_data(as_text=True)
            self.assertIn('href="/resumes">Back to Browse', page)
        listing = self.client.get('/my-resumes?field=Software').get_data(as_text=True)
        self.assertIn('Manage your résumés and check feedback', listing)
        self.assertIn('return_to=', listing)
        self.assertIn('aria-current="page">My resumes', listing)

    def test_navbar_logout_is_csrf_protected_and_removes_access(self):
        page = self.client.get('/resumes').get_data(as_text=True)
        self.assertIn('action="/logout"', page)
        self.assertEqual(self.client.get('/logout').status_code, 405)
        self.assertEqual(self.client.post('/logout').status_code, 400)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        self.assertEqual(self.client.post('/logout', data={'csrf_token': token}).status_code, 303)
        self.assertEqual(self.client.get('/my-resumes').status_code, 302)

del Fixture


class DropdownNavigationTests(unittest.TestCase):
    setUp = NavigationTests.setUp
    login = NavigationTests.login
    def test_dropdown_and_back_keep_canonical_filter_and_page(self):
        with self.app.app_context():
            for number in range(11):
                database.create_resume(self.owner['id'], f'Legacy resume {number}', 'SWE', '')
        listing = self.client.get('/my-resumes?field=SWE&page=2')
        self.assertEqual(listing.status_code, 200)
        html = listing.get_data(as_text=True)
        self.assertIn('<select id="field" name="field">', html)
        self.assertIn('<option selected>Software engineering</option>', html)
        import html as html_module
        link = re.search(r'href="([^"]*return_to=[^"]*)"', html).group(1)
        detail = self.client.get(html_module.unescape(link)).get_data(as_text=True)
        self.assertIn('/my-resumes?page=2&amp;field=Software+engineering', detail)
        bad = self.client.get(f'/resumes/{self.resume["id"]}', query_string={'return_to': '/resumes?field=unknown'})
        self.assertIn('href="/resumes">Back to Browse', bad.get_data(as_text=True))
