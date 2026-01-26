"""가격 업데이트 작업."""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models import InvestmentIdea, Position, IdeaStatus
from services.price_service import get_price_service
from core.events import event_bus, Event, EventType

logger = logging.getLogger(__name__)


async def update_active_position_prices() -> dict:
    """활성 포지션의 가격을 업데이트합니다.

    ACTIVE 상태의 아이디어에 속한 모든 열린 포지션의
    현재가를 KIS API에서 조회하여 캐시에 저장합니다.

    Returns:
        {"updated_count": N, "errors": [...]}
    """
    db: Session = SessionLocal()
    price_service = get_price_service()
    results = {"updated_count": 0, "errors": [], "timestamp": datetime.now().isoformat()}

    try:
        # ACTIVE 아이디어의 열린 포지션 조회
        active_positions = (
            db.query(Position)
            .join(InvestmentIdea)
            .filter(
                InvestmentIdea.status == IdeaStatus.ACTIVE,
                Position.exit_date.is_(None),
            )
            .all()
        )

        if not active_positions:
            logger.debug("No active positions to update")
            return results

        # 고유한 종목코드 추출
        stock_codes = list(set(p.ticker for p in active_positions))
        logger.info(f"Updating prices for {len(stock_codes)} stocks")

        # 일괄 가격 조회 (캐시 우회)
        prices = await price_service.get_multiple_prices(
            stock_codes,
            use_cache=False,
        )

        results["updated_count"] = len(prices)

        # 실패한 종목 기록
        failed_codes = set(stock_codes) - set(prices.keys())
        if failed_codes:
            results["errors"] = list(failed_codes)
            logger.warning(f"Failed to fetch prices for: {failed_codes}")

        # 이벤트 발행 (선택적)
        if prices:
            await event_bus.publish(Event(
                type=EventType.PRICE_UPDATED,
                payload={
                    "stock_codes": list(prices.keys()),
                    "timestamp": results["timestamp"],
                }
            ))

        logger.info(
            f"Price update completed: {results['updated_count']} updated, "
            f"{len(results['errors'])} errors"
        )

    except Exception as e:
        logger.error(f"Price update job failed: {e}")
        results["errors"].append(str(e))
    finally:
        db.close()

    return results


async def update_single_position_price(ticker: str) -> dict:
    """단일 종목 가격 업데이트.

    수동으로 특정 종목의 가격을 갱신할 때 사용합니다.

    Args:
        ticker: 종목코드

    Returns:
        가격 정보 또는 에러
    """
    price_service = get_price_service()

    try:
        price = await price_service.get_current_price(ticker, use_cache=False)
        return {"success": True, "data": price}
    except Exception as e:
        logger.error(f"Failed to update price for {ticker}: {e}")
        return {"success": False, "error": str(e)}
