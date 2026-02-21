"""지수 OHLCV 수집 스케줄러 작업."""
import logging
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)


def _parse_date(date_str: str) -> date:
    """YYYYMMDD 문자열을 date 객체로 변환."""
    return datetime.strptime(date_str, "%Y%m%d").date()


async def _upsert_index_records(db, index_code: str, records: list[dict]):
    """지수 OHLCV 레코드 upsert."""
    from models.market_index_ohlcv import MarketIndexOHLCV
    from sqlalchemy.dialects.postgresql import insert
    from core.timezone import now_kst

    index_name = "코스피" if index_code == "0001" else "코스닥"
    for rec in records:
        stmt = insert(MarketIndexOHLCV).values(
            index_code=index_code,
            trade_date=_parse_date(rec["date"]),
            index_name=index_name,
            open_value=rec.get("open", 0),
            high_value=rec.get("high", 0),
            low_value=rec.get("low", 0),
            close_value=rec.get("close", 0),
            volume=rec.get("volume", 0),
            trading_value=rec.get("trading_value", 0),
            created_at=now_kst().replace(tzinfo=None),
        ).on_conflict_do_update(
            index_elements=["index_code", "trade_date"],
            set_={
                "open_value": rec.get("open", 0),
                "high_value": rec.get("high", 0),
                "low_value": rec.get("low", 0),
                "close_value": rec.get("close", 0),
                "volume": rec.get("volume", 0),
                "trading_value": rec.get("trading_value", 0),
            },
        )
        await db.execute(stmt)


async def collect_index_ohlcv():
    """KOSPI/KOSDAQ 지수 OHLCV 일별 수집 (최근 30일)."""
    from integrations.kis.client import get_kis_client
    from core.database import async_session_maker
    from core.timezone import now_kst

    kis = get_kis_client()

    async with async_session_maker() as db:
        for index_code in ["0001", "1001"]:
            try:
                end_date = now_kst().strftime("%Y%m%d")
                start_date = (now_kst() - timedelta(days=30)).strftime("%Y%m%d")
                records = await kis.get_index_daily_ohlcv(index_code, start_date, end_date)

                if not records:
                    logger.warning(f"지수 OHLCV 데이터 없음: {index_code}")
                    continue

                await _upsert_index_records(db, index_code, records)
                await db.commit()
                logger.info(f"지수 OHLCV 수집 완료: {index_code}, {len(records)}건")
            except Exception as e:
                logger.error(f"지수 OHLCV 수집 실패 ({index_code}): {e}")


async def backfill_index_ohlcv(start_date_str: str = "20220102"):
    """지수 OHLCV 과거 데이터 백필.

    DB에 없는 구간을 start_date부터 현재까지 채움.
    """
    from integrations.kis.client import get_kis_client
    from core.database import async_session_maker
    from models.market_index_ohlcv import MarketIndexOHLCV
    from sqlalchemy import select, func
    from core.timezone import now_kst

    kis = get_kis_client()
    today_str = now_kst().strftime("%Y%m%d")

    async with async_session_maker() as db:
        for index_code in ["0001", "1001"]:
            name = "KOSPI" if index_code == "0001" else "KOSDAQ"
            try:
                # DB에서 가장 이른 날짜 조회
                stmt = select(func.min(MarketIndexOHLCV.trade_date)).where(
                    MarketIndexOHLCV.index_code == index_code
                )
                result = await db.execute(stmt)
                earliest = result.scalar()

                if earliest and earliest <= _parse_date(start_date_str):
                    logger.info(f"{name}: 이미 {earliest}부터 데이터 존재, 스킵")
                    continue

                # 백필 범위: start_date ~ (earliest - 1) 또는 today
                end = (earliest - timedelta(days=1)).strftime("%Y%m%d") if earliest else today_str
                logger.info(f"{name}: {start_date_str} ~ {end} 백필 시작")

                records = await kis.get_index_daily_ohlcv(index_code, start_date_str, end)
                if not records:
                    logger.warning(f"{name}: 백필 데이터 없음")
                    continue

                await _upsert_index_records(db, index_code, records)
                await db.commit()
                logger.info(f"{name}: 백필 완료, {len(records)}건 저장")
            except Exception as e:
                logger.error(f"{name}: 백필 실패: {e}")
