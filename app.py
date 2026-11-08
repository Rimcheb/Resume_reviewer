"""Expose the Flask factory to the command line."""

import os

from backend.app import create_app

if os.getenv("VERCEL"):
    app = create_app()
