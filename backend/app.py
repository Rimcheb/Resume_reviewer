"""Create the Flask application and initialize its configured storage."""

import os
from flask import Flask

from backend import database, sqlite_storage


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
    application.config["DATABASE"] = os.getenv(
        "DATABASE_PATH", os.path.join(application.instance_path, "resume_reviewer.sqlite")
    )
    application.config["STORAGE_BACKEND"] = sqlite_storage
    if config is not None:
        application.config.update(config)
    database.init_app(application)
    application.add_url_rule("/health", view_func=health)
    return application
