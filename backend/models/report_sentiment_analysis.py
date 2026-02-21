"""리포트 감정분석 모델."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, Text, ForeignKey, Enum, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.database import Base


class SentimentType(str, enum.Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"


class InvestmentSignal(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    WATCH = "WATCH"


class ReportSentimentAnalysis(Base):
    """텔레그램 리포트 감정분석 결과."""
    __tablename__ = "report_sentiment_analysis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    telegram_report_id = Column(UUID(as_uuid=True), ForeignKey("telegram_reports.id"), nullable=False)

    stock_code = Column(String(10), nullable=False)
    stock_name = Column(String(100), nullable=False)

    sentiment = Column(Enum(SentimentType, name="sentimenttype", create_type=False), nullable=False)
    sentiment_score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)

    summary = Column(Text, nullable=True)
    key_points = Column(JSONB, nullable=True)

    investment_signal = Column(Enum(InvestmentSignal, name="investmentsignal", create_type=False), nullable=True)

    __table_args__ = (
        Index("ix_report_sentiment_stock_code", "stock_code"),
        Index("ix_report_sentiment_report_id", "telegram_report_id"),
    )

    def __repr__(self):
        return f"<ReportSentimentAnalysis {self.stock_code} {self.sentiment}>"
