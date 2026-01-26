import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from core.database import Base


class IdeaType(str, PyEnum):
    RESEARCH = "research"
    CHART = "chart"


class IdeaStatus(str, PyEnum):
    ACTIVE = "active"
    EXITED = "exited"
    WATCHING = "watching"


class FundamentalHealth(str, PyEnum):
    HEALTHY = "healthy"
    DETERIORATING = "deteriorating"
    BROKEN = "broken"


class InvestmentIdea(Base):
    __tablename__ = "investment_ideas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    type = Column(Enum(IdeaType), nullable=False)
    sector = Column(String(100), nullable=True)
    tickers = Column(JSON, default=list, nullable=False)
    thesis = Column(Text, nullable=False)

    expected_timeframe_days = Column(Integer, nullable=False)
    target_return_pct = Column(Numeric(10, 2), nullable=False)

    status = Column(Enum(IdeaStatus), default=IdeaStatus.WATCHING, nullable=False)
    fundamental_health = Column(Enum(FundamentalHealth), default=FundamentalHealth.HEALTHY, nullable=False)

    metadata_ = Column("metadata", JSON, default=dict, nullable=True)
    tags = Column(ARRAY(String), default=list, nullable=True)
    version = Column(Integer, default=1, nullable=False)

    positions = relationship("Position", back_populates="idea", cascade="all, delete-orphan")
    snapshots = relationship("TrackingSnapshot", back_populates="idea", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<InvestmentIdea {self.id} - {self.type.value}>"
