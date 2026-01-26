"""알림 관련 스키마."""
from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field

from models.alert import AlertType, NotificationChannel


# ============ Alert Rule Schemas ============

class AlertRuleBase(BaseModel):
    """알림 규칙 기본 스키마."""
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    alert_type: AlertType
    channel: NotificationChannel = NotificationChannel.TELEGRAM
    is_enabled: bool = True
    conditions: dict[str, Any] = Field(default_factory=dict)
    cooldown_minutes: int = Field(default=60, ge=1)


class AlertRuleCreate(AlertRuleBase):
    """알림 규칙 생성 스키마."""
    pass


class AlertRuleUpdate(BaseModel):
    """알림 규칙 수정 스키마."""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    channel: Optional[NotificationChannel] = None
    is_enabled: Optional[bool] = None
    conditions: Optional[dict[str, Any]] = None
    cooldown_minutes: Optional[int] = Field(None, ge=1)


class AlertRuleResponse(AlertRuleBase):
    """알림 규칙 응답 스키마."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    last_triggered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ Notification Log Schemas ============

class NotificationLogResponse(BaseModel):
    """알림 로그 응답 스키마."""
    id: UUID
    created_at: datetime
    alert_rule_id: Optional[UUID] = None
    alert_type: AlertType
    channel: NotificationChannel
    recipient: Optional[str] = None
    title: str
    message: str
    is_success: bool
    error_message: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None

    class Config:
        from_attributes = True


# ============ Test Notification Schema ============

class TestNotificationRequest(BaseModel):
    """테스트 알림 요청 스키마."""
    channel: NotificationChannel = NotificationChannel.TELEGRAM
    recipient: Optional[str] = None  # 없으면 기본값 사용
    title: str = "테스트 알림"
    message: str = "Investment Tracker 알림 시스템이 정상적으로 작동합니다."


class TestNotificationResponse(BaseModel):
    """테스트 알림 응답 스키마."""
    success: bool
    channel: NotificationChannel
    message: str
    error: Optional[str] = None


# ============ Alert Settings Schema ============

class AlertSettingsResponse(BaseModel):
    """알림 설정 현황 응답 스키마."""
    telegram_configured: bool
    telegram_bot_username: Optional[str] = None
    email_configured: bool
    smtp_host: Optional[str] = None
    total_rules: int
    enabled_rules: int


# ============ Manual Alert Schema ============

class ManualAlertRequest(BaseModel):
    """수동 알림 발송 요청."""
    channel: NotificationChannel = NotificationChannel.TELEGRAM
    recipient: Optional[str] = None
    title: str
    message: str
    alert_type: AlertType = AlertType.CUSTOM
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
