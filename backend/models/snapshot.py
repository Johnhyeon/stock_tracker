import uuid
from datetime import datetime, date
from sqlalchemy import Column, Integer, Numeric, Date, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base


class TrackingSnapshot(Base):
    __tablename__ = "tracking_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idea_id = Column(UUID(as_uuid=True), ForeignKey("investment_ideas.id"), nullable=False)
    snapshot_date = Column(Date, default=date.today, nullable=False)

    price_data = Column(JSON, default=dict, nullable=True)
    days_held = Column(Integer, nullable=True)
    unrealized_return_pct = Column(Numeric(10, 2), nullable=True)

    news_sentiment = Column(JSON, default=dict, nullable=True)
    chart_signals = Column(JSON, default=dict, nullable=True)
    plugin_data = Column(JSON, default=dict, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    idea = relationship("InvestmentIdea", back_populates="snapshots")

    def __repr__(self):
        return f"<TrackingSnapshot {self.idea_id} - {self.snapshot_date}>"
