"""Back up and upgrade an existing SQLite database without replacing its rows."""

from pathlib import Path
import sqlite3

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from backend.models import Comment, Resume

SCHEMA_VERSION = 1


def backup_database(connection, backup_path):
    """Save the database to a new file; never overwrite an earlier backup."""
    with Path(backup_path).open("xb"):
        pass
    source = connection.connection.driver_connection
    backup = sqlite3.connect(backup_path)
    try:
        source.backup(backup)
    finally:
        backup.close()


def missing_indexes(connection):
    """Find model indexes that have not yet been added to this database."""
    inspector = inspect(connection)
    missing = []
    for table in (Resume.__table__, Comment.__table__):
        existing_names = [index["name"] for index in inspector.get_indexes(table.name)]
        for index in table.indexes:
            if index.name not in existing_names:
                missing.append(index)
    return missing


def upgrade_db(backup_path):
    """Back up once, then add missing context columns and indexes atomically."""
    if not Path(current_app.config["DATABASE"]).is_file():
        raise click.ClickException("Database does not exist. Use init-db for first setup.")
    engine = current_app.extensions["database_engine"]
    with engine.begin() as connection:
        version = connection.exec_driver_sql("PRAGMA user_version").scalar()
        if version > SCHEMA_VERSION:
            raise click.ClickException("Database is newer than this app. Use the matching app version.")
        inspector = inspect(connection)
        tables = inspector.get_table_names()
        if not all(table in tables for table in ("users", "resumes", "comments")):
            raise click.ClickException("Expected the existing users, resumes, and comments tables.")
        columns = [column["name"] for column in inspector.get_columns("resumes")]
        indexes = missing_indexes(connection)
        if ("target_field" in columns and "feedback_request" in columns and not indexes
                and version == SCHEMA_VERSION):
            return False

        backup_database(connection, backup_path)

        # create_all cannot add columns. Fixed ALTER statements preserve old rows.
        if "target_field" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE resumes ADD COLUMN target_field TEXT NOT NULL DEFAULT ''"
            )
        if "feedback_request" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE resumes ADD COLUMN feedback_request TEXT NOT NULL DEFAULT ''"
            )
        for index in indexes:
            index.create(connection)
        connection.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return True


@click.command("upgrade-db")
@click.option("--backup", required=True, type=click.Path(dir_okay=False, path_type=Path))
@with_appcontext
def upgrade_db_command(backup):
    """Upgrade an existing database after saving it to a new backup file."""
    try:
        changed = upgrade_db(backup)
    except (OSError, sqlite3.Error, SQLAlchemyError) as error:
        raise click.ClickException(
            "Upgrade failed; database changes were rolled back. Check the backup path and schema."
        ) from error
    if changed:
        click.echo(f"Database upgraded. Original data backed up to {backup}.")
    else:
        click.echo("Database is already up to date. Nothing was changed.")
