"""관심종목 그룹 모델."""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime

from core.database import Base


class WatchlistGroup(Base):
    __tablename__ = "watchlist_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    color = Column(String(20), nullable=True, default="#6366f1")
    order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
