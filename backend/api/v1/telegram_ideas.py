"""텔레그램 아이디어 API."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from services.telegram_idea_service import TelegramIdeaService
from schemas.telegram_idea import (
    TelegramIdeaResponse,
    TelegramIdeaListResponse,
    StockMentionStats,
    StockStatsResponse,
    AuthorStats,
    AuthorStatsResponse,
    CollectResponse,
    CollectResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=TelegramIdeaListResponse)
async def list_telegram_ideas(
    source: Optional[str] = Query(None, description="my 또는 others"),
    days: int = Query(7, ge=1, le=365),
    stock_code: Optional[str] = Query(None),
    author: Optional[str] = Query(None, description="발신자 필터 (타인 아이디어용)"),
    sentiment: Optional[str] = Query(None, description="POSITIVE, NEGATIVE, NEUTRAL"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_db),
):
    """텔레그램 아이디어 목록 조회."""
    service = TelegramIdeaService(db)
    ideas, total = await service.get_ideas(
        source_type=source,
        days=days,
        stock_code=stock_code,
        author=author,
        sentiment=sentiment,
        limit=limit,
        offset=offset,
    )

    return TelegramIdeaListResponse(
        items=[TelegramIdeaResponse.model_validate(idea) for idea in ideas],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/stats/stocks", response_model=StockStatsResponse)
async def get_stock_stats(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_db),
):
    """종목별 언급 통계."""
    service = TelegramIdeaService(db)
    stats = await service.get_stock_stats(days=days)

    return StockStatsResponse(
        stocks=[
            StockMentionStats(
                stock_code=s["stock_code"],
                stock_name=s["stock_name"],
                mention_count=s["mention_count"],
                latest_date=s["latest_date"],
                sources=s["sources"],
            )
            for s in stats
        ],
        total_count=len(stats),
    )


@router.get("/stats/authors", response_model=AuthorStatsResponse)
async def get_author_stats(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_async_db),
):
    """발신자별 통계 (타인 아이디어용)."""
    service = TelegramIdeaService(db)
    stats = await service.get_author_stats(days=days)

    return AuthorStatsResponse(
        authors=[
            AuthorStats(
                name=s["name"],
                idea_count=s["idea_count"],
                top_stocks=s["top_stocks"],
                latest_idea_date=s["latest_idea_date"],
            )
            for s in stats
        ],
        total_count=len(stats),
    )


@router.post("/collect", response_model=CollectResponse)
async def collect_ideas(
    limit: int = Query(100, ge=1, le=500),
    collect_all: bool = Query(False, description="True면 기존 데이터보다 오래된 메시지 수집"),
    db: AsyncSession = Depends(get_async_db),
):
    """수동 수집 트리거."""
    service = TelegramIdeaService(db)

    try:
        result = await service.collect_ideas(limit=limit, collect_all=collect_all)
    finally:
        await service.disconnect()

    return CollectResponse(
        results=[
            CollectResult(
                channel_name=r["channel_name"],
                messages_collected=r["messages_collected"],
                ideas_created=r["ideas_created"],
                errors=r["errors"],
            )
            for r in result.get("results", [])
        ],
        total_messages=result.get("total_messages", 0),
        total_ideas=result.get("total_ideas", 0),
    )
