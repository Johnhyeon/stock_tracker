"""YouTube 수집 작업."""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from core.database import SessionLocal
from services.youtube_service import YouTubeService
from core.events import event_bus, Event, EventType

logger = logging.getLogger(__name__)


async def collect_youtube_videos() -> dict:
    """YouTube 영상 수집 작업.

    설정된 채널들에서 최근 24시간 내 영상을 수집하고
    종목 언급을 분석합니다.

    Returns:
        {"collected": N, "new": M, "with_mentions": K, "timestamp": "..."}
    """
    db: Session = SessionLocal()
    result = {
        "collected": 0,
        "new": 0,
        "with_mentions": 0,
        "timestamp": datetime.now().isoformat()
    }

    try:
        service = YouTubeService(db)
        collection_result = await service.collect_videos(hours_back=24)
        result.update(collection_result)

        # 새 언급이 있으면 이벤트 발행
        if result["new"] > 0:
            await event_bus.publish(Event(
                type=EventType.YOUTUBE_COLLECTED,
                payload={
                    "new_count": result["new"],
                    "with_mentions": result["with_mentions"],
                    "timestamp": result["timestamp"],
                }
            ))

        logger.info(
            f"YouTube collection completed: {result['new']} new videos, "
            f"{result['with_mentions']} with stock mentions"
        )

    except Exception as e:
        logger.error(f"YouTube collection job failed: {e}")
        result["error"] = str(e)
    finally:
        db.close()

    return result
