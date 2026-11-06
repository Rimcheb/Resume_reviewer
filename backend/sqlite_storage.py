"""Implement user storage and database setup using SQLite and SQLAlchemy."""

from pathlib import Path

import click
from flask import current_app, g
from flask.cli import with_appcontext
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from backend.models import Base, User


def configure_connection(connection, connection_record):
    """Let SQLAlchemy start transactions and enforce SQLite foreign keys."""
    connection.isolation_level = None
    connection.execute("PRAGMA foreign_keys = ON")


def begin_transaction(connection):
    """Start a real transaction, including for table creation and reads."""
    connection.exec_driver_sql("BEGIN")


def get_db():
    """Reuse one ORM session during this request."""
    if "db" not in g:
        g.db = Session(current_app.extensions["database_engine"])
    return g.db


def close_db(error=None):
    """Close the session and roll back any unfinished transaction."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the model tables atomically, only when no tables exist."""
    Path(current_app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    engine = current_app.extensions["database_engine"]
    with engine.begin() as connection:
        if inspect(connection).get_table_names():
            raise click.ClickException("Database already has tables. Nothing was changed.")
        Base.metadata.create_all(connection)


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Expose initial table creation as an explicit terminal command."""
    init_db()
    click.echo("Database initialized.")


def init_app(app):
    """Configure SQLite connections and register cleanup and initialization."""
    url = URL.create("sqlite", database=str(Path(app.config["DATABASE"]).resolve()))
    engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    event.listen(engine, "connect", configure_connection)
    event.listen(engine, "begin", begin_transaction)
    app.extensions["database_engine"] = engine
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)


def user_data(user):
    """Copy a database object into a record that works outside its session."""
    if user is None:
        return None
    return {"id": user.id, "email": user.email, "password_hash": user.password_hash}


def get_user_by_email(email):
    """Find one user using a parameterized query."""
    user = get_db().scalar(select(User).where(User.email == email))
    return user_data(user)


def get_user_by_id(user_id):
    """Find one user by primary key."""
    return user_data(get_db().get(User, user_id))


def create_user(email, password_hash):
    """Save one user atomically; return None if the email already exists."""
    db = get_db()
    user = User(email=email, password_hash=password_hash)
    db.add(user)
    try:
        db.flush()
        result = user_data(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        if get_user_by_email(email) is not None:
            return None
        raise
    except SQLAlchemyError:
        db.rollback()
        raise
    return result
