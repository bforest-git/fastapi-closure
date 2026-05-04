"""Pydantic schemas for request/response validation."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ClosureCreate(BaseModel):
    """Schema for creating a new closure."""

    text: str
    message_id: int
    sent_at: datetime
    author_id: int


class ClosureRead(BaseModel):
    """Schema for reading a closure."""

    id: int
    text: str
    message_id: int
    sent_at: datetime
    author_id: Optional[int] = None
    issue_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class IssueRead(BaseModel):
    """Schema for reading an issue."""

    tracker_key: str
    status: str
    result: Optional[str] = None
    tracker_text: Optional[str] = None
    assignee: Optional[str] = None
    resolved_by: Optional[str] = None
    is_answered: bool = False

    model_config = ConfigDict(from_attributes=True)

    closure: Optional[ClosureRead] = None


class IssueUpdate(BaseModel):
    """Schema for updating an issue."""

    status: Optional[str] = None
    result: Optional[str] = None
    tracker_text: Optional[str] = None
    assignee: Optional[str] = None
    resolved_by: Optional[str] = None
    is_answered: Optional[bool] = None


class ClosureUpdate(BaseModel):
    """Schema for updating a closure."""

    text: Optional[str] = None
    message_id: Optional[int] = None
    sent_at: Optional[datetime] = None
    issue_id: Optional[str] = None


class AuthorRead(BaseModel):
    """Schema for reading an author."""

    id: int
    messenger: str
    chat_id: int
    is_banned: bool

    model_config = ConfigDict(from_attributes=True)


class AuthorBanRequest(BaseModel):
    """Schema for banning an author."""

    user_id: int


class AuthorCreate(BaseModel):
    """Schema for creating a new author."""

    messenger: str
    chat_id: int
