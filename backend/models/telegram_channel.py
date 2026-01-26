"""텔레그램 채널 모니터링 모델."""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, BigInteger, Index
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class TelegramChannel(Base):
    """모니터링할 텔레그램 채널/그룹."""
    __tablename__ = "telegram_channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 채널 정보
    channel_id = Column(BigInteger, unique=True, nullable=False)  # 텔레그램 채널 ID
    channel_name = Column(String(200), nullable=False)  # 채널명 (표시용)
    channel_username = Column(String(100), nullable=True)  # @username (있는 경우)

    # 모니터링 설정
    is_enabled = Column(Boolean, default=True, nullable=False)  # 활성화 여부

    # 마지막 확인 메시지 ID (중복 방지)
    last_message_id = Column(BigInteger, default=0, nullable=False)

    __table_args__ = (
        Index("ix_telegram_channels_enabled", "is_enabled"),
        Index("ix_telegram_channels_channel_id", "channel_id"),
    )

    def __repr__(self):
        return f"<TelegramChannel {self.channel_name} ({self.channel_id})>"


class TelegramKeywordMatch(Base):
    """텔레그램 키워드 매칭 로그."""
    __tablename__ = "telegram_keyword_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 채널 정보
    channel_id = Column(BigInteger, nullable=False)
    channel_name = Column(String(200), nullable=False)

    # 메시지 정보
    message_id = Column(BigInteger, nullable=False)
    message_text = Column(String(1000), nullable=False)  # 메시지 내용 (일부)
    message_date = Column(DateTime, nullable=False)

    # 매칭 정보
    matched_keyword = Column(String(100), nullable=False)  # 매칭된 키워드 (종목명)
    stock_code = Column(String(10), nullable=True)  # 매칭된 종목코드
    idea_id = Column(UUID(as_uuid=True), nullable=True)  # 관련 아이디어 ID

    # 알림 발송 여부
    notification_sent = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_telegram_keyword_matches_created", "created_at"),
        Index("ix_telegram_keyword_matches_keyword", "matched_keyword"),
        Index("ix_telegram_keyword_matches_channel_msg", "channel_id", "message_id", unique=True),
    )

    def __repr__(self):
        return f"<TelegramKeywordMatch {self.matched_keyword} in {self.channel_name}>"
