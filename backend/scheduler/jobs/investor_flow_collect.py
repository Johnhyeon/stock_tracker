"""투자자 수급 데이터 수집 작업."""
import json
import logging
from datetime import datetime
from pathlib import Path

from core.database import async_session_maker
from services.investor_flow_service import InvestorFlowService

logger = logging.getLogger(__name__)

THEME_MAP_PATH = Path(__file__).parent.parent.parent / "data" / "theme_map.json"


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
        "timestamp": datetime.now().isoformat(),
    }

    # 테마맵에서 모든 종목 코드 추출
    try:
        with open(THEME_MAP_PATH, "r", encoding="utf-8") as f:
            theme_map = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load theme map: {e}")
        result["error"] = str(e)
        return result

    # 모든 종목 코드와 이름 수집
    all_stocks = {}
    for stocks in theme_map.values():
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
