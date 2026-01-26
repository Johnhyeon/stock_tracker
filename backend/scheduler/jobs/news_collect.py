"""테마 뉴스 수집 작업."""
import logging
from datetime import datetime

from core.database import async_session_maker
from services.news_collector_service import NewsCollectorService

logger = logging.getLogger(__name__)


async def collect_theme_news() -> dict:
    """테마 뉴스 수집 작업.

    네이버 검색 API와 RSS 피드에서 테마 관련 뉴스를 수집합니다.
    6시간마다 실행됩니다.

    Returns:
        {"naver_count": N, "rss_count": M, "total_count": K, "timestamp": "..."}
    """
    result = {
        "naver_count": 0,
        "rss_count": 0,
        "total_count": 0,
        "timestamp": datetime.now().isoformat(),
    }

    async with async_session_maker() as db:
        try:
            service = NewsCollectorService(db)
            collection_result = await service.collect_all()
            result.update(collection_result)

            logger.info(
                f"Theme news collection completed: "
                f"naver={result['naver_count']}, rss={result['rss_count']}, "
                f"total={result['total_count']}"
            )

        except Exception as e:
            logger.error(f"Theme news collection job failed: {e}")
            result["error"] = str(e)
        finally:
            await service.close()

    return result
