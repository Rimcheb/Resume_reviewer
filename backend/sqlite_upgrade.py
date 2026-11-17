"""Back up and upgrade an existing SQLite database without replacing its rows."""

from pathlib import Path
import sqlite3

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CreateColumn

from backend.models import Base

SCHEMA_VERSION = 3


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


def existing_tables(connection):
    """Pair each model table that already exists with the inspector that found it."""
    inspector = inspect(connection)
    names = inspector.get_table_names()
    return inspector, [table for table in Base.metadata.sorted_tables if table.name in names]


def missing_indexes(connection):
    """Find model indexes on existing tables that the database does not have yet."""
    inspector, tables = existing_tables(connection)
    missing = []
    for table in tables:
        existing_names = [index["name"] for index in inspector.get_indexes(table.name)]
        for index in table.indexes:
            if index.name not in existing_names:
                missing.append(index)
    return missing


def missing_columns(connection):
    """Find model columns that existing tables do not have yet."""
    inspector, tables = existing_tables(connection)
    missing = []
    for table in tables:
        existing_names = [column["name"] for column in inspector.get_columns(table.name)]
        for column in table.columns:
            if column.name not in existing_names:
                missing.append(column)
    return missing


def upgrade_db(backup_path):
    """Back up once, then add missing tables, columns and indexes atomically."""
    if not Path(current_app.config["DATABASE"]).is_file():
        raise click.ClickException("Database does not exist. Use init-db for first setup.")
    engine = current_app.extensions["database_engine"]
    with engine.begin() as connection:
        version = connection.exec_driver_sql("PRAGMA user_version").scalar()
        if version > SCHEMA_VERSION:
            raise click.ClickException("Database is newer than this app. Use the matching app version.")
        tables = inspect(connection).get_table_names()
        if not all(table in tables for table in ("users", "resumes", "comments")):
            raise click.ClickException("Expected the existing users, resumes, and comments tables.")
        columns = missing_columns(connection)
        indexes = missing_indexes(connection)
        new_tables = [table for table in Base.metadata.sorted_tables if table.name not in tables]
        if not columns and not indexes and not new_tables and version == SCHEMA_VERSION:
            return False

        backup_database(connection, backup_path)

        # create_all cannot add columns to existing tables, so ALTER adds each one from
        # its model definition. A new NOT NULL column therefore needs a server_default.
        for column in columns:
            definition = CreateColumn(column).compile(dialect=connection.dialect)
            connection.exec_driver_sql(f"ALTER TABLE {column.table.name} ADD COLUMN {definition}")
        Base.metadata.create_all(connection)  # new tables, with their indexes
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


@click.command("backup-db")
@click.option("--backup", required=True, type=click.Path(dir_okay=False, path_type=Path))
@with_appcontext
def backup_db_command(backup):
    """Make a consistent SQLite snapshot in a new file without changing the source."""
    if not Path(current_app.config["DATABASE"]).is_file():
        raise click.ClickException("Database does not exist.")
    try:
        with current_app.extensions["database_engine"].connect() as connection:
            backup_database(connection, backup)
    except (OSError, sqlite3.Error, SQLAlchemyError) as error:
        raise click.ClickException("Backup failed. Use a new path in an existing writable folder.") from error
    click.echo(f"Database backed up to {backup}.")
