from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from database.db import Base

class Note(Base):
    __tablename__ = "notes"

    note_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    title = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
