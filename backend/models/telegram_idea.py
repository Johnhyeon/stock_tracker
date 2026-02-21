"""텔레그램 아이디어 모델."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, BigInteger, Float, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.database import Base


class IdeaSourceType(str, enum.Enum):
    MY = "my"
    OTHERS = "others"


class TelegramIdea(Base):
    """텔레그램 채널에서 수집한 투자 아이디어."""
    __tablename__ = "telegram_ideas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    channel_id = Column(BigInteger, nullable=False)
    channel_name = Column(String(200), nullable=False)
    source_type = Column(String(20), nullable=False)

    message_id = Column(BigInteger, nullable=False)
    message_text = Column(Text, nullable=False)
    original_date = Column(DateTime, nullable=False)

    is_forwarded = Column(Boolean, nullable=False, default=False)
    forward_from_name = Column(String(200), nullable=True)

    stock_code = Column(String(10), nullable=True)
    stock_name = Column(String(100), nullable=True)

    sentiment = Column(String(20), nullable=True)
    sentiment_score = Column(Float, nullable=True)

    raw_hashtags = Column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_telegram_ideas_stock_code", "stock_code"),
        Index("ix_telegram_ideas_original_date", "original_date"),
        Index("ix_telegram_ideas_channel_msg", "channel_id", "message_id"),
        Index("ix_telegram_ideas_source_type", "source_type"),
    )

    def __repr__(self):
        return f"<TelegramIdea {self.stock_code} from {self.channel_name}>"
