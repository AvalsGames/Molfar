from sqlalchemy import Column, Integer, String, DateTime, func
from database.db import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    username = Column(String, nullable=True)
    timezone = Column(String, default='Europe/Kyiv')
    created_at = Column(DateTime, default=func.now())
