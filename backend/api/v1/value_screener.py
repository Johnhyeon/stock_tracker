"""재무 저평가 스크리너 API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from core.cache import api_cache
from core.timezone import now_kst
from services.value_screener_service import ValueScreenerService
from schemas.value_screener import ValueScreenerResponse, ValueMetrics

router = APIRouter(prefix="/value-screener", tags=["value-screener"])

# 연간 재무데이터 기반이므로 장 마감 후까지 캐시 유지 (6시간)
_CACHE_TTL = 6 * 3600


@router.get("/scan", response_model=ValueScreenerResponse)
async def scan(
    min_score: int = 0,
    limit: int = 100,
    sort_by: str = "total",
    db: AsyncSession = Depends(get_async_db),
):
    """재무 저평가 종목 스크리닝."""
    cache_key = f"value-screener:scan:{min_score}:{limit}:{sort_by}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    service = ValueScreenerService(db)
    result = await service.scan(min_score=min_score, limit=limit, sort_by=sort_by)

    api_cache.set(cache_key, result, ttl=_CACHE_TTL)
    return result


@router.get("/stock/{stock_code}", response_model=ValueMetrics)
async def get_stock_detail(
    stock_code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """단일 종목 재무 스코어 상세."""
    cache_key = f"value-screener:stock:{stock_code}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    service = ValueScreenerService(db)
    detail = await service.get_stock_detail(stock_code)

    if detail is None:
        raise HTTPException(status_code=404, detail="재무 데이터를 찾을 수 없습니다")

    api_cache.set(cache_key, detail, ttl=_CACHE_TTL)
    return detail
