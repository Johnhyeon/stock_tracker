"""트레이더 관심종목 데이터 동기화 작업."""
import logging

from core.database import SessionLocal
from services.trader_service import TraderService

logger = logging.getLogger(__name__)


async def sync_trader_mentions():
    """
    mentions.json 파일과 DB 동기화.

    텔레그램 봇에서 수집된 트레이더 관심종목 데이터를
    주기적으로 DB에 반영합니다.
    """
    logger.info("Starting trader mentions sync job...")

    db = SessionLocal()
    try:
        service = TraderService(db)
        result = service.sync_mentions()

        logger.info(
            f"Trader mentions sync completed: "
            f"{result['total_stocks']} stocks, "
            f"{result['new_mentions']} new mentions"
        )

        # 신규 언급이 있으면 알림 체크 트리거 (선택적)
        if result['new_mentions'] > 0:
            logger.info(f"New trader mentions detected: {result['new_mentions']}")

    except FileNotFoundError:
        logger.warning("mentions.json file not found, skipping sync")
    except Exception as e:
        logger.error(f"Trader mentions sync failed: {e}")
    finally:
        db.close()
