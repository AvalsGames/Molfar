from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from database.db import Base

class ListItem(Base):
    __tablename__ = "list_items"

    item_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    category = Column(String, nullable=False)  # '🎬 Фільми', '📺 Аніме', '🎮 Ігри', '📚 Книги', '🎵 Музика'
    title = Column(String, nullable=False)
    status = Column(String, default='до_перегляду')  # 'до_перегляду', 'переглядаю', 'переглянув'
    added_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
