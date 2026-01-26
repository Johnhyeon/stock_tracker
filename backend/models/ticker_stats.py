"""종목별 통계 모델."""
import uuid
from datetime import datetime, date

from sqlalchemy import Column, String, DateTime, Integer, Date, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class TickerMentionStats(Base):
    """종목별 일간 언급 통계."""
    __tablename__ = "ticker_mention_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 종목 정보
    stock_code = Column(String(10), nullable=False)  # 종목코드
    stock_name = Column(String(100), nullable=True)  # 종목명 (캐시)
    stat_date = Column(Date, nullable=False)  # 통계 날짜

    # YouTube 언급 통계
    youtube_mention_count = Column(Integer, default=0, nullable=False)
    youtube_total_views = Column(Integer, default=0, nullable=False)

    # DART 공시 통계
    disclosure_count = Column(Integer, default=0, nullable=False)
    high_importance_disclosure_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("stock_code", "stat_date", name="uq_ticker_stats_code_date"),
        Index("ix_ticker_stats_stock_code", "stock_code"),
        Index("ix_ticker_stats_stat_date", "stat_date"),
    )

    def __repr__(self):
        return f"<TickerMentionStats {self.stock_code} {self.stat_date}>"
