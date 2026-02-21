"""카탈리스트 감지 및 추적 작업."""
import logging

from core.database import async_session_maker
from services.catalyst_service import CatalystService
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


@track_job_execution("catalyst_detect")
async def detect_catalysts():
    """카탈리스트 감지.

    매일 17:00 실행 (장 마감 후, OHLCV 수집 이후).
    당일 3% 이상 변동 + 뉴스/공시 있는 종목에 CatalystEvent 생성.
    """
    async with async_session_maker() as db:
        service = CatalystService(db)
        created = await service.detect_new_catalysts()
        logger.info(f"카탈리스트 감지 완료: {created}건")


@track_job_execution("catalyst_update")
async def update_catalyst_tracking():
    """카탈리스트 추적 업데이트.

    매일 17:15 실행 (detect 이후).
    active 상태 이벤트의 수익률/수급/후속뉴스 업데이트 및 상태 판정.
    """
    async with async_session_maker() as db:
        service = CatalystService(db)
        updated = await service.update_tracking()
        logger.info(f"카탈리스트 추적 업데이트 완료: {updated}건")
