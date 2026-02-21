"""투자자 수급 데이터 수집 작업."""
import logging

from core.database import async_session_maker
from core.timezone import now_kst
from services.investor_flow_service import InvestorFlowService
from services.theme_map_service import get_theme_map_service
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


@track_job_execution("investor_flow_collect")
async def collect_investor_flow() -> dict:
    """투자자 수급 데이터 수집 작업.

    장 마감 후 (16:30) 모든 테마의 종목들에 대해 수급 데이터를 수집합니다.
    평일에만 실행됩니다.

    Returns:
        {"collected_count": N, "failed_count": M, "timestamp": "..."}
    """
    result = {
        "collected_count": 0,
        "failed_count": 0,
        "timestamp": now_kst().isoformat(),
    }

    # 테마맵에서 모든 종목 코드 추출
    tms = get_theme_map_service()
    all_stocks = {}
    for stocks in tms.get_all_themes().values():
        for stock in stocks:
            code = stock.get("code")
            name = stock.get("name", "")
            if code:
                all_stocks[code] = name

    stock_codes = list(all_stocks.keys())

    async with async_session_maker() as db:
        try:
            service = InvestorFlowService(db)
            collect_result = await service.collect_investor_flow(stock_codes, all_stocks)
            result.update(collect_result)

            logger.info(
                f"Investor flow collection completed: "
                f"{result['collected_count']} collected, "
                f"{result['failed_count']} failed"
            )

        except Exception as e:
            logger.error(f"Investor flow collection job failed: {e}")
            result["error"] = str(e)

    return result
