"""텔레그램 아이디어 API."""
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import api_cache
from core.database import get_async_db
from models.telegram_idea import TelegramIdea
from models.stock_ohlcv import StockOHLCV
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
    TraderPick,
    TraderRankingItem,
    TraderRankingResponse,
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


@router.get("/stats/trader-ranking", response_model=TraderRankingResponse)
async def get_trader_ranking(
    days: int = Query(90, ge=7, le=365),
    min_mentions: int = Query(3, ge=1, le=20),
    db: AsyncSession = Depends(get_async_db),
):
    """트레이더별 종목 추천 성과 랭킹."""
    cache_key = f"trader_ranking_{days}_{min_mentions}"
    cached = api_cache.get(cache_key)
    if cached is not None:
        return cached

    # 1) 기간 내 stock_code, forward_from_name이 있는 아이디어 조회
    since = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(TelegramIdea)
        .where(
            TelegramIdea.stock_code.isnot(None),
            TelegramIdea.forward_from_name.isnot(None),
            TelegramIdea.original_date >= since,
        )
    )
    result = await db.execute(stmt)
    ideas = result.scalars().all()

    if not ideas:
        resp = TraderRankingResponse(
            traders=[], total_traders=0,
            analysis_period_days=days, min_mentions=min_mentions,
        )
        api_cache.set(cache_key, resp, ttl=600)
        return resp

    # 2) 유니크 종목코드 추출 → OHLCV 일괄 조회
    stock_codes = list({idea.stock_code for idea in ideas})
    ohlcv_stmt = (
        select(StockOHLCV)
        .where(StockOHLCV.stock_code.in_(stock_codes))
        .order_by(StockOHLCV.stock_code, StockOHLCV.trade_date)
    )
    ohlcv_result = await db.execute(ohlcv_stmt)
    ohlcv_rows = ohlcv_result.scalars().all()

    # 3) 종목별 {date→close_price} 딕셔너리
    price_map: dict[str, dict[str, int]] = defaultdict(dict)
    for row in ohlcv_rows:
        price_map[row.stock_code][row.trade_date.isoformat()] = row.close_price

    # 4) 각 아이디어별 수익률 계산
    trader_picks: dict[str, list[TraderPick]] = defaultdict(list)

    for idea in ideas:
        prices = price_map.get(idea.stock_code)
        if not prices:
            continue

        sorted_dates = sorted(prices.keys())
        idea_date_str = idea.original_date.strftime("%Y-%m-%d")

        # entry: 아이디어 날짜 이후 가장 가까운 종가
        entry_price = None
        for d in sorted_dates:
            if d >= idea_date_str:
                entry_price = prices[d]
                break
        if entry_price is None or entry_price == 0:
            continue

        # current: 최신 종가
        current_price = prices[sorted_dates[-1]]
        return_pct = round((current_price - entry_price) / entry_price * 100, 2)

        trader_picks[idea.forward_from_name].append(
            TraderPick(
                stock_code=idea.stock_code,
                stock_name=idea.stock_name or idea.stock_code,
                return_pct=return_pct,
                mention_date=idea_date_str,
            )
        )

    # 5) 트레이더별 통계 계산
    ranking_items: list[TraderRankingItem] = []
    for name, picks in trader_picks.items():
        if len(picks) < min_mentions:
            continue

        returns = [p.return_pct for p in picks]
        avg_return = round(sum(returns) / len(returns), 2)
        win_count = sum(1 for r in returns if r > 0)
        win_rate = round(win_count / len(picks) * 100, 1)
        total_return = round(sum(returns), 2)

        sorted_picks = sorted(picks, key=lambda p: p.return_pct, reverse=True)
        best = sorted_picks[0] if sorted_picks else None
        worst = sorted_picks[-1] if sorted_picks else None

        ranking_items.append(
            TraderRankingItem(
                rank=0,
                name=name,
                idea_count=len(picks),
                avg_return_pct=avg_return,
                win_rate=win_rate,
                total_return_pct=total_return,
                best_pick=best,
                worst_pick=worst,
                picks=sorted_picks,
            )
        )

    # 6) avg_return 내림차순 정렬 + rank 부여
    ranking_items.sort(key=lambda x: x.avg_return_pct, reverse=True)
    for i, item in enumerate(ranking_items, 1):
        item.rank = i

    resp = TraderRankingResponse(
        traders=ranking_items,
        total_traders=len(ranking_items),
        analysis_period_days=days,
        min_mentions=min_mentions,
    )
    api_cache.set(cache_key, resp, ttl=600)
    return resp


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
