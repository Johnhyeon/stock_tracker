"""Catalyst Tracker API."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from services.catalyst_service import CatalystService

router = APIRouter()


@router.get("/catalyst/active")
async def get_active_catalysts(
    status: Optional[str] = Query(None, description="active/weakening/expired"),
    catalyst_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db),
):
    """활성 카탈리스트 목록."""
    service = CatalystService(db)
    return await service.get_active_catalysts(status=status, catalyst_type=catalyst_type, limit=limit)


@router.get("/catalyst/stock/{stock_code}")
async def get_stock_catalysts(
    stock_code: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
):
    """종목별 카탈리스트 이력."""
    service = CatalystService(db)
    return await service.get_stock_catalysts(stock_code, limit=limit)


@router.get("/catalyst/enriched")
async def get_enriched_catalysts(
    status: Optional[str] = Query(None),
    catalyst_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db),
):
    """관련도 점수 + 가격 맥락 포함 카탈리스트 목록."""
    service = CatalystService(db)
    return await service.get_enriched_catalysts(status=status, catalyst_type=catalyst_type, limit=limit)


@router.get("/catalyst/{event_id}/impact")
async def get_catalyst_impact(
    event_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """AI 비즈니스 임팩트 분석."""
    service = CatalystService(db)
    return await service.get_business_impact(event_id)


@router.get("/catalyst/{event_id}/similar")
async def get_similar_catalysts(
    event_id: str,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_async_db),
):
    """유사 과거 이벤트."""
    service = CatalystService(db)
    return await service.get_similar_events(event_id, limit=limit)


@router.get("/catalyst/stats")
async def get_catalyst_stats(
    db: AsyncSession = Depends(get_async_db),
):
    """유형별 카탈리스트 통계."""
    service = CatalystService(db)
    return await service.get_catalyst_stats()
