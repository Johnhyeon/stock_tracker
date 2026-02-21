"""테마 펄스 API 라우터."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from services.theme_pulse_service import ThemePulseService
from schemas.theme_pulse import (
    ThemePulseResponse,
    TimelineResponse,
    CatalystDistributionResponse,
)

router = APIRouter(prefix="/theme-pulse", tags=["theme-pulse"])


@router.get("/pulse", response_model=ThemePulseResponse)
async def get_theme_pulse(
    days: int = Query(default=7, ge=1, le=30),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
):
    service = ThemePulseService(db)
    return await service.get_theme_pulse(days=days, limit=limit)


@router.get("/timeline", response_model=TimelineResponse)
async def get_theme_timeline(
    days: int = Query(default=14, ge=1, le=30),
    top_n: int = Query(default=8, ge=1, le=20),
    db: AsyncSession = Depends(get_async_db),
):
    service = ThemePulseService(db)
    return await service.get_theme_timeline(days=days, top_n=top_n)


@router.get("/catalyst-distribution", response_model=CatalystDistributionResponse)
async def get_catalyst_distribution(
    days: int = Query(default=7, ge=1, le=30),
    db: AsyncSession = Depends(get_async_db),
):
    service = ThemePulseService(db)
    return await service.get_catalyst_distribution(days=days)
