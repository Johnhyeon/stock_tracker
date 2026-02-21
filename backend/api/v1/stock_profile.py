"""종목 프로필 API."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from services.cross_reference_service import CrossReferenceService
from schemas.stock_profile import StockProfileResponse

router = APIRouter()


@router.get("/{stock_code}/profile", response_model=StockProfileResponse)
async def get_stock_profile(
    stock_code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """종목 통합 프로필 조회.

    하나의 종목코드로 OHLCV, 수급, 유튜브/전문가/텔레그램 언급,
    공시, 감정분석, 차트패턴, 소속 테마를 한번에 조회합니다.
    """
    service = CrossReferenceService(db)
    return await service.get_stock_profile(stock_code)
