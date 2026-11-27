"""Implement storage operations using SQLite and SQLAlchemy."""
from pathlib import Path
import click
from flask import current_app, g
from flask.cli import with_appcontext
from sqlalchemy import create_engine, event, inspect, select, func, delete
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from backend.fields import normalize_field
from backend.models import Base, Comment, CommentRating, Resume, ResumeRevision, User
from backend.sqlite_upgrade import SCHEMA_VERSION, backup_db_command, upgrade_db_command


def configure_connection(connection, connection_record):
    """Let SQLAlchemy start transactions and enforce SQLite foreign keys."""
    connection.isolation_level = None
    connection.execute("PRAGMA foreign_keys = ON")
    # Use the same lowercase rules as other storage implementations.
    connection.create_function("lowercase", 1, str.lower)
    connection.create_function("canonical_field", 1, normalize_field, deterministic=True)


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
    app.cli.add_command(backup_db_command)


def user_data(user):
    """Copy a database object into a plain record that works outside a session."""
    if user is None:
        return None
    return {"id": user.id, "email": user.email, "password_hash": user.password_hash,
            "display_name": user.display_name or "Reviewer"}


def get_user_by_email(email):
    """Find one user using a parameterized query."""
    user = get_db().scalar(select(User).where(User.email == email))
    return user_data(user)


def get_user_by_id(user_id):
    """Find one user by primary key."""
    return user_data(get_db().get(User, user_id))


def create_user(email, password_hash, display_name=""):
    """Save one user atomically; return None if the email already exists."""
    db = get_db()
    user = User(email=email, password_hash=password_hash, display_name=display_name)
    try:
        db.add(user)
        db.flush()  # Get the new ID before committing and expiring the ORM object.
        result = user_data(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        if get_user_by_email(email) is not None:
            return None
        raise
    except Exception:
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
        "content_format": resume.content_format,
        "created_at": resume.created_at,
        "target_field": resume.target_field,
        "feedback_request": resume.feedback_request,
        "has_peer_feedback": has_peer_feedback,
    }


def create_resume(user_id, content, target_field, feedback_request, content_format="plain"):
    """Save one resume and roll back if any database operation fails."""
    db = get_db()
    resume = Resume(user_id=user_id, content=content, target_field=target_field,
                    feedback_request=feedback_request, content_format=content_format)
    try:
        db.add(resume)
        db.flush()
        db.add(snapshot(resume))
        result = resume_data(resume)
        db.commit()
    except Exception:
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
        category = normalize_field(target_field)
        if category is None:
            return []
        query = query.where(func.canonical_field(Resume.target_field) == category)
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
        "pushes_exaggeration": comment.pushes_exaggeration,
        "revision_id": comment.revision_id,
    }


def create_comment(resume_id, author_id, content, revision_id=None):
    """Save feedback with the version the reviewer saw, if known."""
    db = get_db()
    try:
        if revision_id is not None:
            revision = db.get(ResumeRevision, revision_id)
            if revision is None or revision.resume_id != resume_id:
                raise ValueError("Revision does not belong to this résumé.")
        comment = Comment(resume_id=resume_id, author_id=author_id, content=content,
                          revision_id=revision_id)
        db.add(comment)
        db.flush()
        result = comment_data(comment)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result


def list_comments(resume_id):
    """Read only this resume's comments in a stable discussion order."""
    query = select(Comment, User.display_name).join(User, User.id == Comment.author_id).where(Comment.resume_id == resume_id)
    query = query.order_by(Comment.created_at, Comment.id)
    records = []
    for comment, display_name in get_db().execute(query):
        record = comment_data(comment)
        record["author_display_name"] = display_name or "Reviewer"
        records.append(record)
    return records


def get_comment_by_id(comment_id):
    """Find a comment by primary key and return a plain record."""
    return comment_data(get_db().get(Comment, comment_id))


def update_resume(resume_id, content, target_field, feedback_request, content_format="plain"):
    """Change only the editable fields, keeping ownership, creation time, and comments."""
    db = get_db()
    try:
        resume = db.get(Resume, resume_id)
        if resume is None:
            return False
        resume.content = content
        resume.content_format = content_format
        resume.target_field = target_field
        resume.feedback_request = feedback_request
        if db.is_modified(resume):
            db.add(snapshot(resume))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def delete_resume(resume_id):
    """Delete children before their parent in one transaction, preserving foreign keys."""
    db = get_db()
    try:
        resume = db.get(Resume, resume_id)
        if resume is None:
            return False
        comment_ids = select(Comment.id).where(Comment.resume_id == resume_id)
        db.execute(delete(CommentRating).where(CommentRating.comment_id.in_(comment_ids)))
        db.execute(delete(Comment).where(Comment.resume_id == resume_id))
        db.execute(delete(ResumeRevision).where(ResumeRevision.resume_id == resume_id))
        db.delete(resume)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def update_comment(comment_id, content):
    """Change only comment text, retaining its author, resume, and creation time."""
    db = get_db()
    try:
        comment = db.get(Comment, comment_id)
        if comment is None:
            return False
        comment.content = content
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def flag_exaggeration(comment_id, flagged):
    """Set or clear the owner's 'pushes me to exaggerate' flag on one comment."""
    db = get_db()
    try:
        comment = db.get(Comment, comment_id)
        if comment is None:
            return False
        comment.pushes_exaggeration = flagged
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def delete_comment(comment_id):
    """Delete a single comment and roll back a failed write."""
    db = get_db()
    try:
        comment = db.get(Comment, comment_id)
        if comment is None:
            return False
        db.execute(delete(CommentRating).where(CommentRating.comment_id == comment_id))
        db.delete(comment)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def save_rating(comment_id, rater_id, helpful):
    """Use the unique key to insert or update one rating in a single statement."""
    db = get_db()
    statement = insert(CommentRating).values(
        comment_id=comment_id, rater_id=rater_id, helpful=helpful
    )
    statement = statement.on_conflict_do_update(
        index_elements=["comment_id", "rater_id"], set_={"helpful": helpful}
    )
    try:
        db.execute(statement)
        db.commit()
    except Exception:
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
    except Exception:
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
    if not Path(current_app.config["DATABASE"]).is_file():
        return False
    try:
        with current_app.extensions["database_engine"].connect() as connection:
            if connection.exec_driver_sql("PRAGMA user_version").scalar() != SCHEMA_VERSION:
                return False
            for table in Base.metadata.sorted_tables:
                connection.execute(select(table).limit(0))
    except SQLAlchemyError:
        return False
    return True


def update_display_name(user_id, display_name):
    """Save an account name atomically."""
    db = get_db()
    try:
        user = db.get(User, user_id)
        if user is None:
            return False
        user.display_name = display_name
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def snapshot(resume):
    """Copy the résumé and its feedback request as they appear now."""
    return ResumeRevision(
        resume_id=resume.id, content=resume.content, content_format=resume.content_format,
        target_field=resume.target_field, feedback_request=resume.feedback_request,
    )


def revision_data(revision):
    """Copy a stored snapshot into a plain record."""
    if revision is None:
        return None
    return {
        "id": revision.id, "resume_id": revision.resume_id,
        "content": revision.content, "content_format": revision.content_format,
        "target_field": revision.target_field, "feedback_request": revision.feedback_request,
        "created_at": revision.created_at,
    }


def get_current_revision(resume_id):
    """Return the latest saved snapshot for this résumé."""
    query = select(ResumeRevision).where(ResumeRevision.resume_id == resume_id)
    query = query.order_by(ResumeRevision.id.desc()).limit(1)
    return revision_data(get_db().scalar(query))


def get_revision(resume_id, revision_id):
    """Look up a snapshot only within the specified résumé."""
    query = select(ResumeRevision).where(
        ResumeRevision.id == revision_id, ResumeRevision.resume_id == resume_id,
    )
    return revision_data(get_db().scalar(query))
