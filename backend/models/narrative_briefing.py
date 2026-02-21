"""내러티브 브리핑 DB 캐시 모델."""
import uuid
import hashlib
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.database import Base


class NarrativeBriefing(Base):
    """AI 생성 내러티브 브리핑 캐시."""
    __tablename__ = "narrative_briefings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_code = Column(String(20), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    one_liner = Column(String(500), nullable=True)
    why_moving = Column(Text, nullable=True)
    theme_context = Column(Text, nullable=True)
    expert_perspective = Column(Text, nullable=True)
    catalysts = Column(JSONB, default=list)
    risk_factors = Column(JSONB, default=list)
    narrative_strength = Column(String(20), default="weak")
    market_outlook = Column(String(20), nullable=True)
    financial_highlight = Column(Text, nullable=True)

    input_data_hash = Column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_narrative_briefings_stock_code", "stock_code"),
        Index("ix_narrative_briefings_expires", "expires_at"),
    )

    def __repr__(self):
        return f"<NarrativeBriefing {self.stock_code} ({self.generated_at})>"

    @staticmethod
    def compute_hash(data: dict) -> str:
        """입력 데이터 해시 계산 (캐시 무효화 판단용)."""
        import json
        raw = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
