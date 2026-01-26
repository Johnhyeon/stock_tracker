import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime, ForeignKey, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base


class Position(Base):
    __tablename__ = "positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idea_id = Column(UUID(as_uuid=True), ForeignKey("investment_ideas.id"), nullable=False)

    ticker = Column(String(20), nullable=False)
    entry_price = Column(Numeric(15, 2), nullable=False)
    entry_date = Column(Date, default=date.today, nullable=False)
    quantity = Column(Integer, nullable=False)

    exit_price = Column(Numeric(15, 2), nullable=True)
    exit_date = Column(Date, nullable=True)
    exit_reason = Column(String(50), nullable=True)

    strategy_params = Column(JSON, default=dict, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    idea = relationship("InvestmentIdea", back_populates="positions")

    @property
    def is_open(self) -> bool:
        return self.exit_date is None

    @property
    def days_held(self) -> int:
        end_date = self.exit_date or date.today()
        return (end_date - self.entry_date).days

    @property
    def realized_return_pct(self) -> float | None:
        if self.exit_price is None:
            return None
        return float((self.exit_price - self.entry_price) / self.entry_price * 100)

    def __repr__(self):
        return f"<Position {self.ticker} - {self.quantity}주>"
