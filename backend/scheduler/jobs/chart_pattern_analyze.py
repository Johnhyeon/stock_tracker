"""차트 패턴 분석 작업."""
import logging

from core.database import async_session_maker
from core.timezone import now_kst
from services.chart_pattern_service import ChartPatternService
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


@track_job_execution("chart_pattern_analyze")
async def analyze_chart_patterns() -> dict:
    """차트 패턴 분석 작업.

    장 마감 후 (16:30) 모든 테마의 종목들에 대해 패턴 분석을 수행합니다.
    평일에만 실행됩니다.

    Returns:
        {"analyzed_themes": N, "stocks_with_pattern": M, "timestamp": "..."}
    """
    result = {
        "analyzed_themes": 0,
        "stocks_with_pattern": 0,
        "timestamp": now_kst().isoformat(),
    }

    async with async_session_maker() as db:
        try:
            service = ChartPatternService(db)
            analysis_result = await service.analyze_all_themes()
            result.update(analysis_result)

            logger.info(
                f"Chart pattern analysis completed: "
                f"{result['analyzed_themes']} themes, "
                f"{result['stocks_with_pattern']} patterns detected"
            )

        except Exception as e:
            logger.error(f"Chart pattern analysis job failed: {e}")
            result["error"] = str(e)

    return result
