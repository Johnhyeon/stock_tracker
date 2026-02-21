"""내러티브 브리핑 자동 생성 잡.

장 마감 후 상위 스코어 종목에 대해 AI 내러티브 브리핑을 사전 생성.
"""
import logging

from core.database import async_session_maker
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


@track_job_execution("narrative_generate")
async def generate_narratives():
    """Smart Scanner 상위 종목 내러티브 브리핑 생성."""
    async with async_session_maker() as db:
        from services.smart_scanner_service import SmartScannerService
        from services.narrative_service import NarrativeService

        scanner = SmartScannerService(db)
        stocks = await scanner.scan_all(min_score=40, limit=30, sort_by="composite")

        if not stocks:
            logger.info("내러티브 생성 대상 없음")
            return

        codes = [s.stock_code for s in stocks]
        logger.info(f"내러티브 생성 시작: {len(codes)}개 종목")

        narrative_svc = NarrativeService(db)
        generated = await narrative_svc.batch_generate(codes)

        logger.info(f"내러티브 생성 완료: {generated}/{len(codes)}개")
