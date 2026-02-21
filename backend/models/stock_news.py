"""종목별 뉴스 모델."""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Boolean, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class StockNews(Base):
    """종목별 뉴스."""
    __tablename__ = "stock_news"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_code = Column(String(10), nullable=False, index=True)
    stock_name = Column(String(100), nullable=True)

    title = Column(String(500), nullable=False)
    url = Column(String(1000), unique=True, nullable=False)
    source = Column(String(100), nullable=True)
    published_at = Column(DateTime, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Gemini 분류 (수집 후 배치)
    catalyst_type = Column(String(30), nullable=True)  # policy/earnings/contract/theme/management/product/other
    importance = Column(String(10), nullable=True)  # high/medium/low
    is_quality = Column(Boolean, default=False, nullable=False)

    collection_source = Column(String(50), nullable=True)  # naver_api, rss
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_stock_news_code_published", "stock_code", "published_at"),
        Index("ix_stock_news_catalyst_type", "catalyst_type"),
    )

    def __repr__(self):
        return f"<StockNews {self.stock_code} - {self.title[:30]}>"
