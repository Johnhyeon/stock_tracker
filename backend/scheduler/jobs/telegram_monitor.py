"""텔레그램 채널 모니터링 스케줄러 작업."""
import logging

from core.database import async_session_maker
from services.telegram_monitor_service import TelegramMonitorService

logger = logging.getLogger(__name__)


async def monitor_telegram_channels():
    """텔레그램 채널 모니터링 및 키워드 알림 발송.

    등록된 텔레그램 채널의 새 메시지를 확인하고,
    활성 아이디어 종목명이 언급되면 알림을 발송합니다.
    """
    async with async_session_maker() as db:
        service = TelegramMonitorService(db)

        if not service.is_configured:
            logger.debug("텔레그램 API가 설정되지 않아 모니터링 스킵")
            return

        try:
            result = await service.run_monitor_cycle()
            if result.get("matches_found", 0) > 0:
                logger.info(
                    f"텔레그램 모니터링: {result['matches_found']}개 매칭, "
                    f"{result['notifications_sent']}개 알림 발송"
                )
        except Exception as e:
            logger.error(f"텔레그램 모니터링 실패: {e}")
        finally:
            # 연결 정리
            await service.disconnect()
