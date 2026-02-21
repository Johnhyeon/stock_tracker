"""OHLCV 일별 수집 작업."""
import logging
import asyncio

from sqlalchemy import select, distinct

from core.database import async_session_maker
from core.timezone import today_kst
from models import StockOHLCV, InvestmentIdea
from services.ohlcv_service import OHLCVService, is_trading_day
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


@track_job_execution("ohlcv_daily_collect")
async def collect_ohlcv_daily():
    """저장된 모든 종목의 OHLCV 일별 업데이트.

    매일 장 마감 후 실행되어 당일 데이터를 수집합니다.
    """
    today = today_kst()
    if not is_trading_day(today):
        logger.info(f"OHLCV 일별 수집 스킵: 비거래일 ({today})")
        return

    logger.info("OHLCV 일별 수집 시작")

    async with async_session_maker() as session:
        # 저장된 종목 목록 조회
        stmt = select(distinct(StockOHLCV.stock_code))
        result = await session.execute(stmt)
        codes = [row[0] for row in result.all()]

        if not codes:
            logger.info("저장된 OHLCV 종목 없음")
            return

        logger.info(f"업데이트 대상: {len(codes)}개 종목")

        service = OHLCVService(session)
        success = 0
        failed = 0

        for code in codes:
            try:
                if await service.collect_daily_update(code):
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                logger.warning(f"{code} 업데이트 실패: {e}")
                failed += 1

            # API 속도 제한 (초당 2회 이하)
            await asyncio.sleep(0.5)

        logger.info(f"OHLCV 일별 수집 완료: 성공 {success}, 실패 {failed}")


@track_job_execution("ohlcv_new_ideas_collect")
async def collect_ohlcv_for_new_ideas():
    """신규 아이디어 종목의 OHLCV 초기 수집.

    아직 OHLCV 데이터가 없는 아이디어 종목을 찾아 240일치 수집합니다.
    """
    import re

    logger.info("신규 아이디어 종목 OHLCV 수집 시작")

    async with async_session_maker() as session:
        # 아이디어 종목 코드 추출
        stmt = select(InvestmentIdea.tickers)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        idea_codes = set()
        for tickers in rows:
            if tickers:
                for ticker in tickers:
                    match = re.search(r'\(([A-Za-z0-9]{6})\)', ticker)
                    if match:
                        idea_codes.add(match.group(1))

        if not idea_codes:
            logger.info("아이디어에 등록된 종목 없음")
            return

        # 이미 OHLCV가 있는 종목
        stmt = select(distinct(StockOHLCV.stock_code))
        result = await session.execute(stmt)
        existing_codes = {row[0] for row in result.all()}

        # 신규 종목
        new_codes = idea_codes - existing_codes

        if not new_codes:
            logger.info("신규 수집 대상 종목 없음")
            return

        logger.info(f"신규 종목 {len(new_codes)}개 OHLCV 수집")

        service = OHLCVService(session)
        for code in new_codes:
            try:
                count = await service.collect_ohlcv(code, days=240)
                logger.info(f"{code}: {count}일 수집")
            except Exception as e:
                logger.warning(f"{code} 수집 실패: {e}")

            await asyncio.sleep(0.5)

        logger.info("신규 종목 OHLCV 수집 완료")
