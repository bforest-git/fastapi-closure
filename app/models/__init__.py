"""SQLAlchemy ORM models for the application."""
from sqlalchemy import (
    Column, Integer, String, BigInteger, DateTime, Boolean, UniqueConstraint, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base


class Closure(Base):  # pylint: disable=too-few-public-methods
    """ORM model representing a road closure report."""

    __tablename__ = "closures"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, index=True)
    message_id = Column(BigInteger)
    sent_at = Column(DateTime)
    author_id = Column(Integer, ForeignKey("authors.id"), nullable=True)
    issue_id = Column(String, ForeignKey("issues.tracker_key"), nullable=True, index=True)

    author = relationship("Author", back_populates="closures")
    issue = relationship("Issue", back_populates="closure", uselist=False)


class Author(Base):  # pylint: disable=too-few-public-methods
    """ORM model representing a message author."""

    __tablename__ = "authors"

    id = Column(Integer, primary_key=True)
    messenger = Column(String, nullable=False)
    chat_id = Column(BigInteger, nullable=False, index=True)
    is_banned = Column(Boolean, default=False, nullable=False)

    __table_args__ = (UniqueConstraint('messenger', 'chat_id'),)

    closures = relationship("Closure", back_populates="author")


class Issue(Base):  # pylint: disable=too-few-public-methods
    """ORM model representing a Yandex Tracker issue."""

    __tablename__ = "issues"

    tracker_key = Column(String, primary_key=True, index=True)
    status = Column(String)
    result = Column(String, nullable=True)
    tracker_text = Column(String, nullable=True)
    assignee = Column(String, nullable=True)
    resolved_by = Column(String, nullable=True)
    is_answered = Column(Boolean, default=False, nullable=False)

    closure = relationship("Closure", back_populates="issue", uselist=False)
