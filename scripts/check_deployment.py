"""Check public demo availability without creating accounts or changing data."""

import argparse
import json
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen


def check_deployment(base_url):
    """Verify the public entry point, web server, and database readiness."""
    for path, expected in [("/", None), ("/health", "ok"), ("/ready", "ready")]:
        with urlopen(base_url.rstrip("/") + path, timeout=30) as response:
            body = response.read()
            if expected is None:
                if urlsplit(response.url).path != "/login" or b"Resume Reviewer" not in body:
                    raise ValueError("The public entry point did not open the app login page")
            elif json.loads(body).get("status") != expected:
                raise ValueError(f"{path} did not report {expected}")
        print(f"PASS {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Public HTTPS address of the deployed app")
    args = parser.parse_args()
    if urlsplit(args.url).scheme != "https":
        parser.error("Provide an HTTPS address")
    try:
        check_deployment(args.url)
    except (URLError, OSError, ValueError) as error:
        parser.exit(1, f"Deployment check failed: {error}\n")
