from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from core.cache import api_cache
from schemas.market_intel import MarketIntelResponse
from services.market_intel_service import MarketIntelService

router = APIRouter()

MARKET_INTEL_CACHE_TTL = 120  # 2분


@router.get("/feed", response_model=MarketIntelResponse)
async def get_market_intel_feed(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db),
):
    cache_key = f"market_intel:{limit}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    service = MarketIntelService(db)
    result = await service.get_feed(limit=limit)
    api_cache.set(cache_key, result, ttl=MARKET_INTEL_CACHE_TTL)
    return result
