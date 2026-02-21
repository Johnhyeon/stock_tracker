"""전문가 언급 모델."""
from datetime import datetime, date
from uuid import uuid4

from sqlalchemy import Column, String, Integer, Float, Date, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class ExpertMention(Base):
    """전문가 종목 언급 기록.

    텔레그램 채널에서 수집된 전문가들의 종목 언급 데이터.
    """
    __tablename__ = "expert_mentions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 종목 정보
    stock_name = Column(String(100), nullable=False)  # 종목명
    stock_code = Column(String(10), nullable=True)    # 종목코드 (매칭 후 채워짐)

    # 언급 정보
    mention_date = Column(Date, nullable=False)       # 언급 날짜
    change_rate = Column(Float, nullable=True)        # 언급일 등락률

    # 출처 정보
    source_link = Column(Text, nullable=True)         # 텔레그램 링크
    chat_id = Column(String(50), nullable=True)       # 채팅 ID

    # 성과 추적
    mention_price = Column(Integer, nullable=True)    # 언급 시점 주가
    current_price = Column(Integer, nullable=True)    # 현재 주가
    performance = Column(Float, nullable=True)        # 성과 (%)

    __table_args__ = (
        Index('ix_expert_mentions_stock_name', 'stock_name'),
        Index('ix_expert_mentions_stock_code', 'stock_code'),
        Index('ix_expert_mentions_date', 'mention_date'),
        Index('ix_expert_mentions_stock_date', 'stock_code', 'mention_date'),
    )

    def __repr__(self):
        return f"<ExpertMention {self.stock_name} @ {self.mention_date}>"


class ExpertStats(Base):
    """전문가 종목별 통계.

    일간 집계 데이터.
    """
    __tablename__ = "expert_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 종목 정보
    stock_name = Column(String(100), nullable=False)
    stock_code = Column(String(10), nullable=True)
    stat_date = Column(Date, nullable=False)

    # 통계
    mention_count = Column(Integer, default=0)        # 언급 횟수

    # KIS API 데이터
    current_price = Column(Integer, nullable=True)
    price_change = Column(Integer, nullable=True)
    price_change_rate = Column(Float, nullable=True)
    volume = Column(Integer, nullable=True)

    # 첫 언급 이후 성과
    first_mention_date = Column(Date, nullable=True)
    first_mention_price = Column(Integer, nullable=True)
    total_performance = Column(Float, nullable=True)  # 첫 언급 대비 성과

    __table_args__ = (
        Index('ix_expert_stats_stock_date', 'stock_code', 'stat_date', unique=True),
        Index('ix_expert_stats_date', 'stat_date'),
    )

    def __repr__(self):
        return f"<ExpertStats {self.stock_name} @ {self.stat_date}>"
