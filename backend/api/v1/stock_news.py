"""종목별 뉴스 API."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from services.stock_news_service import StockNewsService

router = APIRouter()


@router.get("/stock-news/{stock_code}")
async def get_stock_news(
    stock_code: str,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
):
    """종목별 최근 뉴스 조회."""
    service = StockNewsService(db)
    return await service.get_stock_news(stock_code, days=days, limit=limit)


@router.get("/stock-news/{stock_code}/catalyst-summary")
async def get_catalyst_summary(
    stock_code: str,
    days: int = Query(14, ge=1, le=90),
    db: AsyncSession = Depends(get_async_db),
):
    """종목별 재료 요약."""
    service = StockNewsService(db)
    return await service.get_catalyst_summary(stock_code, days=days)


@router.get("/stock-news/hot/ranking")
async def get_hot_news_stocks(
    limit: int = Query(30, ge=1, le=100),
    days: int = Query(3, ge=1, le=14),
    db: AsyncSession = Depends(get_async_db),
):
    """뉴스가 많은 종목 순위."""
    service = StockNewsService(db)
    return await service.get_hot_stocks_by_news(limit=limit, days=days)
