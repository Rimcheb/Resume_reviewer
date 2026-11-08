"""Define the tables and constraints used for new databases and ORM queries."""

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    """An account identified by its email address."""

    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(Text, nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    __table_args__ = (CheckConstraint(func.length(func.trim(email)) > 0),)


class Resume(Base):
    """Pasted resume text belonging to one user."""

    __tablename__ = "resumes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(Text, nullable=False, server_default=func.current_timestamp())
    target_field = Column(Text, nullable=False, server_default="")
    feedback_request = Column(Text, nullable=False, server_default="")
    __table_args__ = (
        CheckConstraint(func.length(func.trim(content)) > 0),
        Index("ix_resumes_created_at_id", "created_at", "id"),
        Index("ix_resumes_user_created_at_id", "user_id", "created_at", "id"),
    )


class Comment(Base):
    """Feedback or a follow-up written by a user on a resume."""

    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(Text, nullable=False, server_default=func.current_timestamp())
    __table_args__ = (
        CheckConstraint(func.length(func.trim(content)) > 0),
        Index("ix_comments_resume_author", "resume_id", "author_id"),
        Index("ix_comments_resume_created_id", "resume_id", "created_at", "id"),
        Index("ix_comments_author_id", "author_id", "id"),
    )


class ReviewCredit(Base):
    """A resume this member reviewed for someone else; earns them one resume post.

    resume_id has no foreign key on purpose: the credit stays when the owner later
    deletes the resume (and with it the review).
    """

    __tablename__ = "review_credits"
    id = Column(Integer, primary_key=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    resume_id = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint("reviewer_id", "resume_id"),)


class CommentRating(Base):
    """One owner's helpfulness decision about a peer's comment."""

    __tablename__ = "comment_ratings"
    id = Column(Integer, primary_key=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=False)
    rater_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    helpful = Column(Integer, nullable=False)
    __table_args__ = (
        CheckConstraint("helpful IN (0, 1)"),
        UniqueConstraint("comment_id", "rater_id"),
    )
