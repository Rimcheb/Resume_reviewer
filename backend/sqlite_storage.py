"""Implement storage operations using SQLite and SQLAlchemy."""
from pathlib import Path
import click
from flask import current_app, g
from flask.cli import with_appcontext
from sqlalchemy import create_engine, event, inspect, select, func
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from backend.models import Base, Comment, Resume, User
from backend.sqlite_upgrade import SCHEMA_VERSION, upgrade_db_command


def configure_connection(connection, connection_record):
    """Let SQLAlchemy start transactions and enforce SQLite foreign keys."""
    connection.isolation_level = None
    connection.execute("PRAGMA foreign_keys = ON")
    # Use the same lowercase rules as other storage implementations.
    connection.create_function("lowercase", 1, str.lower)


def begin_transaction(connection):
    """Start a real transaction, including for table creation and reads."""
    connection.exec_driver_sql("BEGIN")


def get_db():
    """Reuse one ORM session during this request."""
    if "db" not in g:
        g.db = Session(current_app.extensions["database_engine"])
    return g.db


def close_db(error=None):
    """Close the session; close also rolls back any unfinished transaction."""
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
        connection.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Expose initial table creation as an explicit terminal command."""
    init_db()
    click.echo("Database initialized.")


def init_app(app):
    """Configure SQLite connections and register cleanup and setup."""
    url = URL.create("sqlite", database=str(Path(app.config["DATABASE"]).resolve()))
    engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    event.listen(engine, "connect", configure_connection)
    event.listen(engine, "begin", begin_transaction)
    app.extensions["database_engine"] = engine
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(upgrade_db_command)


def user_data(user):
    """Copy a database object into a plain record that works outside a session."""
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
        db.flush()  # Get the new ID before committing and expiring the ORM object.
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


def resume_data(resume, has_peer_feedback=False):
    """Copy a resume without exposing account details or an ORM object."""
    if resume is None:
        return None
    return {
        "id": resume.id,
        "user_id": resume.user_id,
        "content": resume.content,
        "created_at": resume.created_at,
        "target_field": resume.target_field,
        "feedback_request": resume.feedback_request,
        "has_peer_feedback": has_peer_feedback,
    }


def create_resume(user_id, content, target_field, feedback_request):
    """Save one resume and roll back if any database operation fails."""
    db = get_db()
    resume = Resume(user_id=user_id, content=content, target_field=target_field,
                    feedback_request=feedback_request)
    db.add(resume)
    try:
        db.flush()
        result = resume_data(resume)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return result


def resume_query():
    """Select resumes and whether someone other than the owner has commented."""
    peer_feedback = select(Comment.id).where(
        Comment.resume_id == Resume.id,
        Comment.author_id != Resume.user_id,
    ).exists()
    return select(Resume, peer_feedback)


def get_resume_by_id(resume_id):
    """Find one resume and its peer-feedback status by primary key."""
    row = get_db().execute(resume_query().where(Resume.id == resume_id)).first()
    if row is None:
        return None
    resume, has_peer_feedback = row
    return resume_data(resume, has_peer_feedback)


def list_resumes(user_id=None, target_field="", limit=10, offset=0):
    """Filter, order, and limit rows in SQL before copying the returned records."""
    query = resume_query()
    if user_id is not None:
        query = query.where(Resume.user_id == user_id)
    if target_field:
        field = func.lowercase(Resume.target_field)
        # instr finds literal text, including % and _, and returns 0 if absent.
        query = query.where(func.instr(field, target_field.lower()) > 0)
    query = query.order_by(Resume.created_at.desc(), Resume.id.desc())
    rows = get_db().execute(query.limit(limit).offset(offset)).all()
    records = []
    for resume, has_peer_feedback in rows:
        records.append(resume_data(resume, has_peer_feedback))
    return records
