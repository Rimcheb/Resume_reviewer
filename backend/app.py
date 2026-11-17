"""Create the Flask application before connecting individual backend features."""

import os
from flask import Flask


def health():
    """Confirm the web server is responding; does not check a database."""
    return {"status": "ok"}


def create_app(config=None):
    """Make an independent app while preserving the shared frontend locations."""
    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    application = Flask(
        __name__,
        template_folder=os.path.join(project_path, "templates"),
        static_folder=os.path.join(project_path, "static"),
        instance_path=os.path.join(project_path, "instance"),
    )
    if config is not None:
        application.config.update(config)
    application.add_url_rule("/health", view_func=health)
    return application
