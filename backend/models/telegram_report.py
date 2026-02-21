"""텔레그램 리포트 모델."""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, BigInteger, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.database import Base


class TelegramReport(Base):
    """텔레그램 채널에서 수집한 리포트."""
    __tablename__ = "telegram_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    channel_id = Column(BigInteger, nullable=False)
    channel_name = Column(String(200), nullable=False)

    message_id = Column(BigInteger, nullable=False)
    message_text = Column(Text, nullable=False)
    message_date = Column(DateTime, nullable=False)
    message_url = Column(String(500), nullable=True)

    extracted_links = Column(JSONB, nullable=True)
    extracted_stocks = Column(JSONB, nullable=True)
    extracted_themes = Column(JSONB, nullable=True)

    is_processed = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_telegram_reports_channel_msg", "channel_id", "message_id", unique=True),
        Index("ix_telegram_reports_message_date", "message_date"),
        Index("ix_telegram_reports_is_processed", "is_processed"),
    )

    def __repr__(self):
        return f"<TelegramReport {self.channel_name} msg={self.message_id}>"
