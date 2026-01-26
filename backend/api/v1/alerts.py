"""알림 API 엔드포인트."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from models.alert import AlertType, NotificationChannel
from schemas.alert import (
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleResponse,
    NotificationLogResponse,
    TestNotificationRequest,
    TestNotificationResponse,
    AlertSettingsResponse,
    ManualAlertRequest,
)
from services.alert_service import AlertService
from integrations.telegram.client import get_telegram_client
from integrations.email.client import get_email_client

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ============ Alert Rules ============

@router.get("/rules", response_model=list[AlertRuleResponse])
async def get_alert_rules(
    enabled_only: bool = False,
    alert_type: Optional[AlertType] = None,
    db: AsyncSession = Depends(get_async_db),
):
    """알림 규칙 목록 조회."""
    service = AlertService(db)
    rules = await service.get_rules(enabled_only=enabled_only, alert_type=alert_type)
    return rules


@router.post("/rules", response_model=AlertRuleResponse, status_code=201)
async def create_alert_rule(
    data: AlertRuleCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """알림 규칙 생성."""
    service = AlertService(db)
    rule = await service.create_rule(data.model_dump())
    return rule


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """알림 규칙 상세 조회."""
    service = AlertService(db)
    rule = await service.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="알림 규칙을 찾을 수 없습니다.")
    return rule


@router.patch("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: UUID,
    data: AlertRuleUpdate,
    db: AsyncSession = Depends(get_async_db),
):
    """알림 규칙 수정."""
    service = AlertService(db)
    rule = await service.update_rule(rule_id, data.model_dump(exclude_unset=True))
    if not rule:
        raise HTTPException(status_code=404, detail="알림 규칙을 찾을 수 없습니다.")
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_alert_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """알림 규칙 삭제."""
    service = AlertService(db)
    deleted = await service.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="알림 규칙을 찾을 수 없습니다.")


@router.post("/rules/{rule_id}/toggle", response_model=AlertRuleResponse)
async def toggle_alert_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """알림 규칙 활성화/비활성화 토글."""
    service = AlertService(db)
    rule = await service.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="알림 규칙을 찾을 수 없습니다.")

    updated = await service.update_rule(rule_id, {"is_enabled": not rule.is_enabled})
    return updated


# ============ Notification Logs ============

@router.get("/logs", response_model=list[NotificationLogResponse])
async def get_notification_logs(
    limit: int = 50,
    alert_type: Optional[AlertType] = None,
    success_only: bool = False,
    db: AsyncSession = Depends(get_async_db),
):
    """알림 발송 로그 조회."""
    service = AlertService(db)
    logs = await service.get_logs(
        limit=limit,
        alert_type=alert_type,
        success_only=success_only,
    )
    return logs


# ============ Test & Manual Notifications ============

@router.post("/test", response_model=TestNotificationResponse)
async def send_test_notification(
    data: TestNotificationRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """테스트 알림 발송."""
    service = AlertService(db)

    try:
        success = await service.send_notification(
            channel=data.channel,
            title=data.title,
            message=data.message,
            recipient=data.recipient,
            alert_type=AlertType.CUSTOM,
        )

        return TestNotificationResponse(
            success=success,
            channel=data.channel,
            message="테스트 알림이 발송되었습니다." if success else "알림 발송에 실패했습니다.",
        )

    except Exception as e:
        return TestNotificationResponse(
            success=False,
            channel=data.channel,
            message="알림 발송 중 오류가 발생했습니다.",
            error=str(e),
        )


@router.post("/send", response_model=TestNotificationResponse)
async def send_manual_notification(
    data: ManualAlertRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """수동 알림 발송."""
    service = AlertService(db)

    try:
        success = await service.send_notification(
            channel=data.channel,
            title=data.title,
            message=data.message,
            recipient=data.recipient,
            alert_type=data.alert_type,
            related_entity_type=data.related_entity_type,
            related_entity_id=data.related_entity_id,
        )

        return TestNotificationResponse(
            success=success,
            channel=data.channel,
            message="알림이 발송되었습니다." if success else "알림 발송에 실패했습니다.",
        )

    except Exception as e:
        return TestNotificationResponse(
            success=False,
            channel=data.channel,
            message="알림 발송 중 오류가 발생했습니다.",
            error=str(e),
        )


# ============ Settings ============

@router.get("/settings", response_model=AlertSettingsResponse)
async def get_alert_settings(
    db: AsyncSession = Depends(get_async_db),
):
    """알림 설정 현황 조회."""
    service = AlertService(db)
    return await service.get_settings_status()


# ============ Manual Trigger ============

@router.post("/check")
async def trigger_alert_check(
    db: AsyncSession = Depends(get_async_db),
):
    """알림 규칙 수동 체크 (스케줄러 작업 수동 실행)."""
    service = AlertService(db)
    triggered_count = await service.check_and_trigger_alerts()
    return {
        "message": f"알림 체크 완료",
        "triggered_count": triggered_count,
    }
