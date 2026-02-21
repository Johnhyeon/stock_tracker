"""종목별 뉴스 수집 작업."""
import logging
from datetime import datetime

from core.database import async_session_maker, SessionLocal
from services.stock_news_service import StockNewsService
from services.theme_map_service import get_theme_map_service
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


def _get_watchlist_codes_and_names() -> dict[str, str]:
    """관심종목 코드+이름 반환 (동기)."""
    from models.watchlist import WatchlistItem
    db = SessionLocal()
    try:
        items = db.query(WatchlistItem).all()
        return {item.stock_code: (item.stock_name or "") for item in items}
    finally:
        db.close()


async def _get_scanner_top_stocks(limit: int = 50) -> dict[str, str]:
    """Smart Scanner 상위 종목 코드+이름 반환."""
    from services.smart_scanner_service import SmartScannerService
    async with async_session_maker() as db:
        try:
            svc = SmartScannerService(db)
            results = await svc.scan_all(min_score=0, limit=limit)
            return {r.stock_code: r.stock_name for r in results}
        except Exception as e:
            logger.error(f"Scanner 상위 종목 조회 실패: {e}")
            return {}


@track_job_execution("stock_news_collect_hot")
async def collect_hot_stock_news():
    """Tier 1: Smart Scanner 상위 + 워치리스트 종목 뉴스 수집.

    2시간마다 실행.
    """
    # 워치리스트
    watchlist_map = _get_watchlist_codes_and_names()

    # Scanner 상위
    scanner_map = await _get_scanner_top_stocks(50)

    # 합산 (scanner 우선)
    combined: dict[str, str] = {}
    combined.update(watchlist_map)
    combined.update(scanner_map)

    if not combined:
        logger.info("Tier 1 뉴스 수집: 대상 종목 없음")
        return

    stock_codes = list(combined.keys())
    logger.info(f"Tier 1 뉴스 수집 시작: {len(stock_codes)}종목")

    async with async_session_maker() as db:
        service = StockNewsService(db)
        try:
            saved = await service.collect_for_stocks(stock_codes, combined, max_per_stock=15)
            logger.info(f"Tier 1 뉴스 수집 완료: {saved}건 저장")
        finally:
            await service.close()


@track_job_execution("stock_news_collect_all")
async def collect_all_stock_news():
    """Tier 2: 테마맵 전체 종목 뉴스 수집.

    6시간마다 실행.
    """
    tms = get_theme_map_service()
    all_themes = tms.get_all_themes()

    # 종목코드 → 종목명 매핑
    stock_map: dict[str, str] = {}
    for stocks in all_themes.values():
        for s in stocks:
            code = s.get("code")
            name = s.get("name")
            if code and name and code not in stock_map:
                stock_map[code] = name

    if not stock_map:
        logger.info("Tier 2 뉴스 수집: 테마맵 종목 없음")
        return

    stock_codes = list(stock_map.keys())
    logger.info(f"Tier 2 뉴스 수집 시작: {len(stock_codes)}종목")

    async with async_session_maker() as db:
        service = StockNewsService(db)
        try:
            saved = await service.collect_for_stocks(stock_codes, stock_map, max_per_stock=10)
            logger.info(f"Tier 2 뉴스 수집 완료: {saved}건 저장")
        finally:
            await service.close()


@track_job_execution("stock_news_classify")
async def classify_stock_news():
    """미분류 뉴스 Gemini 분류.

    3시간마다 실행.
    """
    async with async_session_maker() as db:
        service = StockNewsService(db)
        try:
            classified = await service.classify_catalysts(limit=50)
            logger.info(f"뉴스 분류 완료: {classified}건")
        finally:
            await service.close()
