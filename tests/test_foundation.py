"""Exercise the app factory and stable public health/static contracts."""

import tempfile
import unittest
from pathlib import Path

from backend.app import create_app


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = self.make_app('first')
        self.client = self.app.test_client()

    def make_app(self, label):
        app = create_app({'TESTING': True, 'SECRET_KEY': 'test-only-'+label,
                          'DATABASE': str(Path(self.temp.name) / (label+'.sqlite'))})
        engine = app.extensions.get('database_engine')
        if engine is not None:
            self.addCleanup(engine.dispose)
        return app

    def test_health_get_returns_json_and_head_has_no_body(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'status': 'ok'})
        self.assertEqual(response.mimetype, 'application/json')
        head = self.client.head('/health')
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.data, b'')

    def test_health_is_read_only(self):
        self.assertEqual(self.client.post('/health').status_code, 405)
        self.assertEqual(self.client.get('/health').json, {'status': 'ok'})

    def test_factory_keeps_configuration_independent(self):
        other = self.make_app('second')
        self.app.config['FEATURE_FLAG'] = 'first-only'
        self.assertNotIn('FEATURE_FLAG', other.config)
        self.assertNotEqual(self.app.config['SECRET_KEY'], other.config['SECRET_KEY'])
        self.assertEqual(other.test_client().get('/health').json, {'status': 'ok'})

    def test_shared_stylesheet_is_served(self):
        response = self.client.get('/static/style.css')
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'text/css')
        self.assertIn(b'.container', response.data)


if __name__ == '__main__':
    unittest.main()
