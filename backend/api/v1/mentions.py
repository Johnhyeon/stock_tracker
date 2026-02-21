"""통합 멘션 API."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from services.cross_reference_service import get_trending_mentions, get_convergence_signals
from schemas.stock_profile import TrendingMentionItem

router = APIRouter()


@router.get("/trending", response_model=list[TrendingMentionItem])
async def trending_mentions(
    days: int = Query(default=7, ge=1, le=30, description="조회 기간 (일)"),
    limit: int = Query(default=20, ge=1, le=50, description="결과 수"),
    db: AsyncSession = Depends(get_async_db),
):
    """전체 소스 합산 인기 종목.

    YouTube, 전문가, 텔레그램 아이디어에서 종합적으로 많이 언급된 종목을 조회합니다.
    """
    return await get_trending_mentions(db, days=days, limit=limit)


@router.get("/convergence", response_model=list[TrendingMentionItem])
async def convergence_signals(
    days: int = Query(default=7, ge=1, le=30, description="조회 기간 (일)"),
    min_sources: int = Query(default=2, ge=2, le=3, description="최소 소스 수"),
    db: AsyncSession = Depends(get_async_db),
):
    """교차 시그널 종목.

    2개 이상 소스(유튜브, 전문가, 텔레그램)에서 동시에 언급된 종목을 조회합니다.
    """
    return await get_convergence_signals(db, days=days, min_sources=min_sources)
