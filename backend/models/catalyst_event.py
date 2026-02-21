"""Catalyst Event 모델 - 종목별 재료 추적."""
import uuid
from datetime import datetime, date

from sqlalchemy import Column, String, Text, Integer, BigInteger, Float, Boolean, DateTime, Date, Index
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class CatalystEvent(Base):
    """종목별 카탈리스트(재료) 이벤트."""
    __tablename__ = "catalyst_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_code = Column(String(10), nullable=False, index=True)
    stock_name = Column(String(100), nullable=True)

    # 이벤트 정보
    event_date = Column(Date, nullable=False)
    catalyst_type = Column(String(30), nullable=True)  # policy/earnings/contract/theme/management/product/other
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # 발생 시점 데이터 스냅샷
    price_at_event = Column(Integer, nullable=True)
    volume_at_event = Column(BigInteger, nullable=True)
    price_change_pct = Column(Float, nullable=True)

    # 추적 데이터 (매일 업데이트)
    return_t1 = Column(Float, nullable=True)
    return_t5 = Column(Float, nullable=True)
    return_t10 = Column(Float, nullable=True)
    return_t20 = Column(Float, nullable=True)
    current_return = Column(Float, nullable=True)
    max_return = Column(Float, nullable=True)
    max_return_day = Column(Integer, nullable=True)

    # 수급 동반 여부
    flow_confirmed = Column(Boolean, default=False, nullable=False)
    flow_score_5d = Column(Float, nullable=True)

    # 후속 뉴스
    followup_news_count = Column(Integer, default=0, nullable=False)
    latest_news_date = Column(Date, nullable=True)

    # 라이프사이클
    status = Column(String(20), default="active", nullable=False)  # active / weakening / expired
    days_alive = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_catalyst_events_event_date", "event_date"),
        Index("ix_catalyst_events_status", "status"),
        Index("ix_catalyst_events_catalyst_type", "catalyst_type"),
        Index("ix_catalyst_events_code_date", "stock_code", "event_date"),
    )

    def __repr__(self):
        return f"<CatalystEvent {self.stock_code} - {self.title[:30]} ({self.status})>"
