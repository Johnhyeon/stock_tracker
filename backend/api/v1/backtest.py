"""시그널 전략 백테스트 API."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import api_cache
from core.database import get_async_db
from schemas.backtest import BacktestRequest, BacktestResponse
from services.backtest_service import BacktestService, params_hash

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    req: BacktestRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """시그널 전략 백테스트 실행.

    전 종목 OHLCV 슬라이딩 윈도우 스캔. 1~3분 소요될 수 있음.
    """
    # 검증
    if req.start_date >= req.end_date:
        raise HTTPException(400, "start_date must be before end_date")
    if (req.end_date - req.start_date).days > 730:
        raise HTTPException(400, "Maximum period is 2 years (730 days)")

    # 캐시 확인
    cache_key = f"bt:{params_hash(req)}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    service = BacktestService(db)
    result = await service.run_backtest(req)
    api_cache.set(cache_key, result, ttl=600)
    return result
