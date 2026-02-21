"""텔레그램 리포트 수집 및 감정 분석 작업."""
import logging

from core.database import async_session_maker
from services.telegram_report_service import TelegramReportService
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


@track_job_execution("telegram_report_collect")
async def collect_telegram_reports():
    """텔레그램 리포트 수집."""
    logger.info("Starting telegram report collection...")
    try:
        async with async_session_maker() as db:
            service = TelegramReportService(db)
            if not service.is_telethon_configured:
                logger.warning("Telethon not configured, skipping report collection")
                return
            result = await service.collect_messages(limit=100)
            logger.info(f"Telegram report collection completed: {result}")
            return result
    except Exception as e:
        logger.error(f"Telegram report collection failed: {e}")
        raise


@track_job_execution("sentiment_analyze")
async def analyze_telegram_sentiments():
    """텔레그램 리포트 감정 분석."""
    logger.info("Starting telegram sentiment analysis...")
    try:
        async with async_session_maker() as db:
            service = TelegramReportService(db)
            if not service.is_gemini_configured:
                logger.warning("Gemini not configured, skipping sentiment analysis")
                return
            result = await service.analyze_sentiment_batch(limit=10)
            logger.info(f"Telegram sentiment analysis completed: {result}")
            return result
    except Exception as e:
        logger.error(f"Telegram sentiment analysis failed: {e}")
        raise
