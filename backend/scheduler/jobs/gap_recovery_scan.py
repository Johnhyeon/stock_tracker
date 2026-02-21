"""장중 갭다운 회복 스캔 스케줄러 작업."""
import asyncio
import logging

from services.recovery_analysis_service import run_gap_recovery_scan

logger = logging.getLogger(__name__)


async def scan_gap_recovery():
    """전 종목 갭다운 회복 스캔 (장 시간 2분마다)."""
    try:
        await run_gap_recovery_scan()
    except asyncio.CancelledError:
        logger.info("갭 회복 스캔 작업이 취소되었습니다 (스케줄러 종료 또는 타임아웃)")
    except Exception as e:
        logger.error(f"갭 회복 스캔 실패: {e}")
