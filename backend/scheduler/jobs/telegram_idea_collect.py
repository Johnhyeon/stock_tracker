"""텔레그램 아이디어 수집 작업."""
import logging

from core.database import async_session_maker
from services.telegram_idea_service import TelegramIdeaService
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


@track_job_execution("telegram_idea_collect")
async def collect_telegram_ideas():
    """텔레그램 아이디어 수집."""
    logger.info("Starting telegram idea collection...")
    try:
        async with async_session_maker() as db:
            service = TelegramIdeaService(db)
            result = await service.collect_ideas(limit=100)
            logger.info(f"Telegram idea collection completed: {result}")
            return result
    except Exception as e:
        logger.error(f"Telegram idea collection failed: {e}")
        raise
