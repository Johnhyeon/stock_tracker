"""알림 체크 스케줄러 작업."""
import logging

from core.database import async_session_maker
from services.alert_service import AlertService

logger = logging.getLogger(__name__)


async def check_alerts():
    """
    활성화된 모든 알림 규칙을 확인하고 조건 충족 시 알림 발송.
    """
    logger.info("알림 체크 작업 시작")

    async with async_session_maker() as session:
        try:
            service = AlertService(session)
            triggered_count = await service.check_and_trigger_alerts()
            logger.info(f"알림 체크 완료: {triggered_count}건 발송")
        except Exception as e:
            logger.error(f"알림 체크 작업 오류: {e}")
            raise
