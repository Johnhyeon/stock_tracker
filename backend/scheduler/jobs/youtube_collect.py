"""YouTube 수집 작업."""
import logging

from core.database import async_session_maker
from core.timezone import now_kst
from services.youtube_service import YouTubeService
from core.events import event_bus, Event, EventType
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


@track_job_execution("youtube_collect")
async def collect_youtube_videos() -> dict:
    """YouTube 영상 수집 작업 (아이디어 종목 대상).

    활성/관찰 중인 아이디어 종목명으로 최근 24시간 내 영상을 수집하고
    종목 언급을 분석합니다.

    Returns:
        {"collected": N, "new": M, "with_mentions": K, "timestamp": "..."}
    """
    result = {
        "collected": 0,
        "new": 0,
        "with_mentions": 0,
        "timestamp": now_kst().isoformat()
    }

    try:
        async with async_session_maker() as db:
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

    return result


@track_job_execution("youtube_hot_collect")
async def collect_youtube_hot_videos() -> dict:
    """YouTube 핫 영상 수집 작업 (키워드 기반 범용 수집).

    주식 관련 키워드 + 인기 채널에서 최근 48시간 내 영상을 수집하고
    종목 언급을 분석합니다. 보유 종목과 무관하게 시장 전반을 커버합니다.

    Returns:
        {"collected": N, "new": M, "with_mentions": K, "timestamp": "..."}
    """
    result = {
        "collected": 0,
        "new": 0,
        "with_mentions": 0,
        "timestamp": now_kst().isoformat()
    }

    try:
        async with async_session_maker() as db:
            service = YouTubeService(db)
            collection_result = await service.collect_hot_videos(
                hours_back=48,
                mode="normal",
            )
            result.update(collection_result)

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
            f"YouTube hot collection completed: {result['new']} new videos, "
            f"{result['with_mentions']} with stock mentions"
        )

    except Exception as e:
        logger.error(f"YouTube hot collection job failed: {e}")
        result["error"] = str(e)

    return result
