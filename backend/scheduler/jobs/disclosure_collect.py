"""공시 수집 작업."""
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from core.database import SessionLocal
from models import InvestmentIdea, Position, IdeaStatus, DisclosureImportance
from services.disclosure_service import DisclosureService
from core.events import event_bus, Event, EventType

logger = logging.getLogger(__name__)


async def collect_disclosures_for_active_positions() -> dict:
    """활성 포지션 관련 공시 수집.

    ACTIVE 상태의 아이디어에 속한 종목들의 공시를 수집합니다.

    Returns:
        {"collected": N, "new": M, "skipped": K, "timestamp": "..."}
    """
    db: Session = SessionLocal()
    result = {
        "collected": 0,
        "new": 0,
        "skipped": 0,
        "timestamp": datetime.now().isoformat()
    }

    try:
        # ACTIVE 아이디어의 열린 포지션에서 종목코드 수집
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
            logger.debug("No active positions for disclosure collection")
            return result

        stock_codes = list(set(p.ticker for p in active_positions))
        logger.info(f"Collecting disclosures for {len(stock_codes)} stocks")

        # 최근 7일 공시 수집
        service = DisclosureService(db)
        end_de = datetime.now().strftime("%Y%m%d")
        bgn_de = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

        collection_result = await service.collect_disclosures(
            bgn_de=bgn_de,
            end_de=end_de,
            stock_codes=stock_codes,
            min_importance=DisclosureImportance.MEDIUM,
        )

        result.update(collection_result)

        # 새 공시가 있으면 이벤트 발행
        if result["new"] > 0:
            await event_bus.publish(Event(
                type=EventType.DISCLOSURE_COLLECTED,
                payload={
                    "stock_codes": stock_codes,
                    "new_count": result["new"],
                    "timestamp": result["timestamp"],
                }
            ))

        logger.info(
            f"Disclosure collection completed: {result['new']} new, "
            f"{result['skipped']} skipped"
        )

    except Exception as e:
        logger.error(f"Disclosure collection job failed: {e}")
        result["error"] = str(e)
    finally:
        db.close()

    return result


async def collect_all_disclosures() -> dict:
    """전체 공시 수집 (관심 종목 무관).

    최근 3일간의 모든 중요 공시를 수집합니다.
    주로 새로운 투자 아이디어 발굴용으로 사용됩니다.

    Returns:
        {"collected": N, "new": M, "skipped": K}
    """
    db: Session = SessionLocal()
    result = {
        "collected": 0,
        "new": 0,
        "skipped": 0,
        "timestamp": datetime.now().isoformat()
    }

    try:
        service = DisclosureService(db)
        end_de = datetime.now().strftime("%Y%m%d")
        bgn_de = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")

        result = await service.collect_disclosures(
            bgn_de=bgn_de,
            end_de=end_de,
            stock_codes=None,  # 전체
            min_importance=DisclosureImportance.HIGH,  # 중요 공시만
        )

        logger.info(
            f"All disclosure collection completed: {result['new']} new"
        )

    except Exception as e:
        logger.error(f"All disclosure collection failed: {e}")
        result["error"] = str(e)
    finally:
        db.close()

    return result
