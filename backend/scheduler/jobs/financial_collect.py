"""재무제표 수집 스케줄러 작업."""
import logging
from datetime import timedelta

from sqlalchemy import select, func, and_

from core.database import async_session_maker
from core.timezone import now_kst
from models.stock_ohlcv import StockOHLCV
from models.financial_statement import FinancialStatement
from services.financial_statement_service import FinancialStatementService
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


def _is_earnings_season() -> bool:
    """분기 보고서 발표 시즌인지 확인.

    3월(연간), 5월(1분기), 8월(반기), 11월(3분기) 보고서가 집중 발표됨.
    해당 월에는 갱신 주기를 7일로 단축.
    """
    return now_kst().month in (3, 5, 8, 11)


@track_job_execution("financial_collect")
async def collect_financial_statements_job():
    """추적 중인 종목의 재무제표 수집.

    - 분기 보고서 시즌(3/5/8/11월): 7일 이상 미갱신 종목 대상
    - 그 외: 30일 이상 미갱신 종목 대상
    """
    earnings_season = _is_earnings_season()
    refresh_days = 7 if earnings_season else 30
    logger.info(f"Starting financial collection (earnings_season={earnings_season}, refresh_days={refresh_days})")

    async with async_session_maker() as db:
        # OHLCV 데이터가 있는 종목 = 추적 중인 종목
        stock_stmt = (
            select(StockOHLCV.stock_code)
            .distinct()
        )
        stock_result = await db.execute(stock_stmt)
        all_stocks = [r[0] for r in stock_result]

        if not all_stocks:
            logger.info("No tracked stocks found")
            return

        # refresh_days 이내에 수집된 종목 제외
        threshold = now_kst().replace(tzinfo=None) - timedelta(days=refresh_days)
        recent_stmt = (
            select(FinancialStatement.stock_code)
            .where(FinancialStatement.collected_at >= threshold)
            .distinct()
        )
        recent_result = await db.execute(recent_stmt)
        recent_stocks = {r[0] for r in recent_result}

        targets = [s for s in all_stocks if s not in recent_stocks]
        logger.info(f"Financial collect targets: {len(targets)} / {len(all_stocks)} total")

        service = FinancialStatementService(db)
        collected = 0
        failed = 0

        for stock_code in targets:
            try:
                result = await service.collect_financial_statements(stock_code, years=3)
                if result["collected_count"] > 0:
                    collected += 1
                    logger.info(f"Collected {result['collected_count']} items for {stock_code}")
            except Exception as e:
                failed += 1
                logger.error(f"Failed to collect financial data for {stock_code}: {e}")
                try:
                    await db.rollback()
                except Exception:
                    pass

        logger.info(f"Financial collection done: {collected} success, {failed} failed")


@track_job_execution("dart_corp_sync")
async def sync_dart_corp_codes_job():
    """DART 고유번호 매핑 동기화."""
    logger.info("Starting DART corp codes sync")

    async with async_session_maker() as db:
        service = FinancialStatementService(db)
        try:
            count = await service.sync_corp_codes()
            logger.info(f"Synced {count} corp codes")
        except Exception as e:
            logger.error(f"Failed to sync corp codes: {e}")
