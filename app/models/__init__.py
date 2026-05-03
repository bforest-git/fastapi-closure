from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Boolean
from app.database import Base

class Closure(Base):
    __tablename__ = "closures"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, index=True)
    messenger = Column(String, index=True)
    chat_id = Column(BigInteger)
    message_id = Column(BigInteger)
    sent_at = Column(DateTime)
    tracker_key = Column(String, nullable=True)
    status = Column(String, nullable=True)
    result = Column(String, nullable=True)
    tracker_text = Column(String, nullable=True)
    is_answered = Column(Boolean, default=False, nullable=False)