"""Check the public health endpoint without starting a network server."""

import unittest

from app import app


class HealthEndpointTest(unittest.TestCase):
    def test_health_returns_ok(self):
        with app.test_client() as client:
            response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)
        self.assertEqual(response.get_json(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
