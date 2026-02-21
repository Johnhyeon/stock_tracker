"""매매 기록 모델."""
import uuid
from datetime import datetime, date
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database import Base


class TradeType(str, PyEnum):
    BUY = "BUY"
    ADD_BUY = "ADD_BUY"
    SELL = "SELL"
    PARTIAL_SELL = "PARTIAL_SELL"


class Trade(Base):
    __tablename__ = "trades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    position_id = Column(UUID(as_uuid=True), ForeignKey("positions.id"), nullable=False)

    trade_type = Column(Enum(TradeType), nullable=False)
    trade_date = Column(Date, default=date.today, nullable=False)
    price = Column(Numeric(15, 2), nullable=False)
    quantity = Column(Integer, nullable=False)

    # 매도 시 실현손익
    realized_profit = Column(Numeric(15, 2), nullable=True)
    realized_return_pct = Column(Numeric(10, 2), nullable=True)

    # 거래 후 포지션 상태
    avg_price_after = Column(Numeric(15, 2), nullable=True)
    quantity_after = Column(Integer, nullable=True)

    reason = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)

    # 종목 정보 (조회 편의용)
    stock_code = Column(String(20), nullable=True)
    stock_name = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    position = relationship("Position", backref="trades")
