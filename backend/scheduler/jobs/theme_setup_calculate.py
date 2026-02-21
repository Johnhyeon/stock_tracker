"""테마 셋업 점수 계산 작업."""
import logging

from core.database import async_session_maker
from core.timezone import now_kst
from services.theme_setup_service import ThemeSetupService
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


@track_job_execution("theme_setup_calculate")
async def calculate_theme_setups() -> dict:
    """테마 셋업 종합 점수 계산 작업.

    뉴스 모멘텀, 차트 패턴, 언급 데이터를 종합하여
    모든 테마의 셋업 점수를 계산합니다.
    6시간마다 실행됩니다.

    Returns:
        {"calculated_count": N, "emerging_count": M, "timestamp": "..."}
    """
    result = {
        "calculated_count": 0,
        "emerging_count": 0,
        "timestamp": now_kst().isoformat(),
    }

    async with async_session_maker() as db:
        try:
            service = ThemeSetupService(db)
            calc_result = await service.calculate_all_setups()
            result.update(calc_result)

            logger.info(
                f"Theme setup calculation completed: "
                f"{result['calculated_count']} themes, "
                f"{result['emerging_count']} emerging"
            )

        except Exception as e:
            logger.error(f"Theme setup calculation job failed: {e}")
            result["error"] = str(e)

    return result
