"""장중 갭다운 회복 분석 API."""
from fastapi import APIRouter, Query

from services.recovery_analysis_service import RecoveryAnalysisService

router = APIRouter()


@router.get("/analysis/recovery/realtime")
async def get_realtime_recovery(
    min_gap_pct: float = Query(0.5, ge=0.1, le=10.0, description="최소 갭다운 %"),
    limit: int = Query(30, ge=1, le=100),
):
    """갭다운 후 장중 회복 빠른 종목 실시간 랭킹."""
    service = RecoveryAnalysisService()
    return await service.get_realtime_recovery(min_gap_pct=min_gap_pct, limit=limit)
