"""Implement storage operations using SQLite and SQLAlchemy."""
from pathlib import Path
import click
from flask import current_app, g
from flask.cli import with_appcontext
from sqlalchemy import create_engine, event, inspect, select, func, delete
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from backend.models import Base, Comment, Resume, User
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from backend.models import CommentRating
from backend.sqlite_upgrade import SCHEMA_VERSION, upgrade_db_command
from backend.sqlite_upgrade import backup_db_command


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
    engine = current_app.extensions["database_engine"]
    if engine.dialect.name == "sqlite":
        Path(current_app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with engine.begin() as connection:
        if inspect(connection).get_table_names():
            raise click.ClickException("Database already has tables. Nothing was changed.")
        Base.metadata.create_all(connection)
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql(f"PRAGMA user_version = {SCHEMA_VERSION}")


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Expose initial table creation as an explicit terminal command."""
    init_db()
    click.echo("Database initialized.")


def init_app(app):
    """Use Postgres when configured, otherwise keep the local SQLite setup."""
    if app.config["DATABASE_URL"]:
        url = make_url(app.config["DATABASE_URL"])
        if url.get_backend_name() not in {"postgres", "postgresql"}:
            raise RuntimeError("DATABASE_URL must point to Postgres.")
        url = url.set(drivername="postgresql+psycopg")
        engine = create_engine(url, poolclass=NullPool, hide_parameters=True,
                               connect_args={"prepare_threshold": None})
    else:
        url = URL.create("sqlite", database=str(Path(app.config["DATABASE"]).resolve()))
        engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
        event.listen(engine, "connect", configure_connection)
        event.listen(engine, "begin", begin_transaction)
        app.cli.add_command(upgrade_db_command)
        app.cli.add_command(backup_db_command)
    app.extensions["database_engine"] = engine
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)


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
        if get_db().get_bind().dialect.name == "postgresql":
            match = func.strpos(func.lower(Resume.target_field), func.lower(target_field))
        else:
            match = func.instr(func.lowercase(Resume.target_field), target_field.lower())
        query = query.where(match > 0)
    query = query.order_by(Resume.created_at.desc(), Resume.id.desc())
    rows = get_db().execute(query.limit(limit).offset(offset)).all()
    records = []
    for resume, has_peer_feedback in rows:
        records.append(resume_data(resume, has_peer_feedback))
    return records


def comment_data(comment):
    """Copy a comment without exposing account details or an ORM object."""
    if comment is None:
        return None
    return {
        "id": comment.id, "resume_id": comment.resume_id, "author_id": comment.author_id,
        "content": comment.content, "created_at": comment.created_at,
    }


def create_comment(resume_id, author_id, content):
    """Save a comment atomically; foreign keys require an existing resume and author."""
    db = get_db()
    comment = Comment(resume_id=resume_id, author_id=author_id, content=content)
    db.add(comment)
    try:
        db.flush()
        result = comment_data(comment)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return result


def list_comments(resume_id):
    """Read only this resume's comments in a stable discussion order."""
    query = select(Comment).where(Comment.resume_id == resume_id)
    query = query.order_by(Comment.created_at, Comment.id)
    records = []
    for comment in get_db().scalars(query):
        records.append(comment_data(comment))
    return records


def get_comment_by_id(comment_id):
    """Find a comment by primary key and return a plain record."""
    return comment_data(get_db().get(Comment, comment_id))


def update_resume(resume_id, content, target_field, feedback_request):
    """Change only the editable fields, keeping ownership, creation time, and comments."""
    db = get_db()
    resume = db.get(Resume, resume_id)
    if resume is None:
        return False
    resume.content = content
    resume.target_field = target_field
    resume.feedback_request = feedback_request
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return True


def delete_resume(resume_id):
    """Delete children before their parent in one transaction, preserving foreign keys."""
    db = get_db()
    resume = db.get(Resume, resume_id)
    if resume is None:
        return False
    try:
        comment_ids = select(Comment.id).where(Comment.resume_id == resume_id)
        db.execute(delete(CommentRating).where(CommentRating.comment_id.in_(comment_ids)))
        db.execute(delete(Comment).where(Comment.resume_id == resume_id))
        db.delete(resume)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return True


def update_comment(comment_id, content):
    """Change only comment text, retaining its author, resume, and creation time."""
    db = get_db()
    comment = db.get(Comment, comment_id)
    if comment is None:
        return False
    comment.content = content
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return True


def delete_comment(comment_id):
    """Delete a single comment and roll back a failed write."""
    db = get_db()
    comment = db.get(Comment, comment_id)
    if comment is None:
        return False
    try:
        db.execute(delete(CommentRating).where(CommentRating.comment_id == comment_id))
        db.delete(comment)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return True


def save_rating(comment_id, rater_id, helpful):
    """Use the unique key to insert or update one rating in a single statement."""
    db = get_db()
    insert = postgres_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(CommentRating).values(
        comment_id=comment_id, rater_id=rater_id, helpful=helpful
    )
    statement = statement.on_conflict_do_update(
        index_elements=["comment_id", "rater_id"], set_={"helpful": helpful}
    )
    try:
        db.execute(statement)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def delete_rating(comment_id, rater_id):
    """Delete only the authorized owner's rating, in one transaction."""
    db = get_db()
    try:
        db.execute(delete(CommentRating).where(
            CommentRating.comment_id == comment_id, CommentRating.rater_id == rater_id
        ))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def eligible_ratings():
    """Exclude ratings by non-owners and ratings on self-comments."""
    return select(CommentRating).join(Comment).join(Resume).where(
        CommentRating.rater_id == Resume.user_id,
        Comment.author_id != Resume.user_id,
    )


def list_ratings(resume_id):
    """Read valid ratings for this discussion without loading account details."""
    query = eligible_ratings().where(Resume.id == resume_id)
    ratings = {}
    for rating in get_db().scalars(query):
        ratings[rating.comment_id] = rating.helpful
    return ratings


def get_reputation(user_id):
    """Derive counts in SQL so changes and deletions cannot leave stale totals."""
    query = eligible_ratings().where(Comment.author_id == user_id)
    query = query.with_only_columns(func.sum(CommentRating.helpful), func.count(CommentRating.id))
    helpful, total = get_db().execute(query).one()
    helpful = helpful or 0
    percentage = None
    if total:
        percentage = round(100 * helpful / total)
    return {"helpful": helpful, "total": total, "percentage": percentage}


def is_ready():
    """Check the database file, schema version and mapped columns without writing."""
    engine = current_app.extensions["database_engine"]
    sqlite = engine.dialect.name == "sqlite"
    if sqlite and not Path(current_app.config["DATABASE"]).is_file():
        return False
    try:
        with engine.connect() as connection:
            if sqlite and connection.exec_driver_sql("PRAGMA user_version").scalar() != SCHEMA_VERSION:
                return False
            for table in Base.metadata.sorted_tables:
                connection.execute(select(table).limit(0))
    except SQLAlchemyError:
        return False
    return True
