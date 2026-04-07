from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from database.db import Base

class Reminder(Base):
    __tablename__ = "reminders"

    reminder_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    text = Column(String, nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    is_recurring = Column(Boolean, default=False)
    recurrence_type = Column(String, nullable=True)  # 'daily', 'weekly', 'monthly'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
