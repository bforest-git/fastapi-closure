from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ClosureCreate(BaseModel):
    text: str
    messenger: str
    chat_id: int
    message_id: int
    sent_at: datetime
    is_answered: bool = False

class ClosureRead(BaseModel):
    id: int
    text: str
    messenger: str
    chat_id: int
    message_id: int
    sent_at: datetime
    tracker_key: str | None = None
    status: str | None = None
    result: str | None = None
    tracker_text: str | None = None
    is_answered: bool = False

    model_config = ConfigDict(from_attributes=True)

class ClosureStatusUpdate(BaseModel):
    status: str