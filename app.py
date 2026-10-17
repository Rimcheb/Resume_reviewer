"""Minimal Flask entry point for the Resume Reviewer backend."""

from flask import Flask

app = Flask(__name__)


@app.get("/health")
def health():
    """Confirm the web server is responding; does not check a database."""
    return {"status": "ok"}
