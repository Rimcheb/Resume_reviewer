"""Define the tables and constraints used for new databases and ORM queries."""

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, Text, func
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
    )
