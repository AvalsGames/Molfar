from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from database.db import Base

class FileRecord(Base):
    __tablename__ = "files"

    file_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    original_filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # 'document', 'photo', 'audio', 'video'
    file_tg_id = Column(String, nullable=False) # Telegram file unique id
    channel_message_id = Column(Integer, nullable=True) # Message ID in the private channel
    category = Column(String, default="Загальне")
    tags = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=func.now())
