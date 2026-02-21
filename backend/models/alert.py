"""알림 규칙 및 로그 모델."""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Text, Integer, DateTime, Enum, Boolean, JSON, Index
from sqlalchemy.dialects.postgresql import UUID

from core.database import Base


class AlertType(str, PyEnum):
    """알림 유형."""
    YOUTUBE_SURGE = "youtube_surge"  # YouTube 급증 감지
    DISCLOSURE_IMPORTANT = "disclosure_important"  # 중요 공시 발생
    FOMO_WARNING = "fomo_warning"  # FOMO 위험 경고
    TARGET_REACHED = "target_reached"  # 목표가 도달
    FUNDAMENTAL_DETERIORATION = "fundamental_deterioration"  # 펀더멘털 악화
    TIME_EXPIRED = "time_expired"  # 예상 기간 초과
    EXPERT_NEW_MENTION = "expert_new_mention"  # 전문가 신규 언급
    EXPERT_CROSS_CHECK = "expert_cross_check"  # 내 종목 전문가 언급
    TELEGRAM_KEYWORD = "telegram_keyword"  # 텔레그램 키워드 감지
    CUSTOM = "custom"  # 사용자 정의


class NotificationChannel(str, PyEnum):
    """알림 채널."""
    TELEGRAM = "telegram"
    EMAIL = "email"
    BOTH = "both"


class AlertRule(Base):
    """알림 규칙."""
    __tablename__ = "alert_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    alert_type = Column(Enum(AlertType), nullable=False)

    # 활성화 여부
    is_enabled = Column(Boolean, default=True, nullable=False)

    # 알림 채널
    channel = Column(Enum(NotificationChannel), default=NotificationChannel.TELEGRAM, nullable=False)

    # 조건 설정 (JSON)
    conditions = Column(JSON, default=dict, nullable=False)
    # 예: {"threshold": 5, "time_window_hours": 24, "stock_codes": ["005930"]}

    # 쿨다운 (분) - 동일 알림 재발송 방지
    cooldown_minutes = Column(Integer, default=60, nullable=False)

    # 마지막 발송 시간
    last_triggered_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_alert_rules_type", "alert_type"),
        Index("ix_alert_rules_enabled", "is_enabled"),
    )

    def __repr__(self):
        return f"<AlertRule {self.name} ({self.alert_type.value})>"


class NotificationLog(Base):
    """알림 발송 로그."""
    __tablename__ = "notification_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 알림 규칙 (nullable - 수동 발송도 가능)
    alert_rule_id = Column(UUID(as_uuid=True), nullable=True)

    alert_type = Column(Enum(AlertType), nullable=False)
    channel = Column(Enum(NotificationChannel), nullable=False)

    # 수신자 정보
    recipient = Column(String(200), nullable=True)  # 이메일 주소 또는 텔레그램 chat_id

    # 알림 내용
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)

    # 발송 결과
    is_success = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text, nullable=True)

    # 관련 엔티티
    related_entity_type = Column(String(50), nullable=True)  # idea, position, disclosure, youtube
    related_entity_id = Column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_notification_logs_created", "created_at"),
        Index("ix_notification_logs_type", "alert_type"),
    )

    def __repr__(self):
        return f"<NotificationLog {self.alert_type.value} - {'성공' if self.is_success else '실패'}>"
