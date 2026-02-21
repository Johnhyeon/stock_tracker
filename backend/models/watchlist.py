"""관심종목 모델."""
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey

from core.database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), unique=True, nullable=False, index=True)
    stock_name = Column(String(100), nullable=True)
    memo = Column(String(500), nullable=True)
    group_id = Column(Integer, ForeignKey("watchlist_groups.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
