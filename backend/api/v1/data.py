"""데이터 API 엔드포인트.

실시간 가격 조회 및 OHLCV 데이터 제공.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from services.price_service import get_price_service
from schemas.data import (
    PriceResponse,
    OHLCVResponse,
    OHLCVItem,
    MultiplePriceRequest,
)

router = APIRouter()


@router.get("/price/{stock_code}", response_model=PriceResponse)
async def get_current_price(
    stock_code: str,
    use_cache: bool = Query(default=True, description="캐시 사용 여부"),
):
    """종목 현재가 조회.

    KIS API를 통해 실시간 가격 정보를 조회합니다.
    캐시 TTL: 60초
    """
    price_service = get_price_service()

    try:
        data = await price_service.get_current_price(stock_code, use_cache=use_cache)
        return PriceResponse(**data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"가격 조회 실패: {str(e)}"
        )


@router.post("/prices", response_model=dict[str, PriceResponse])
async def get_multiple_prices(
    request: MultiplePriceRequest,
    use_cache: bool = Query(default=True, description="캐시 사용 여부"),
):
    """복수 종목 현재가 일괄 조회.

    최대 20개 종목까지 조회 가능.
    """
    price_service = get_price_service()

    try:
        data = await price_service.get_multiple_prices(
            request.stock_codes,
            use_cache=use_cache
        )
        return {code: PriceResponse(**price) for code, price in data.items()}
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"가격 조회 실패: {str(e)}"
        )


@router.get("/ohlcv/{stock_code}", response_model=OHLCVResponse)
async def get_ohlcv(
    stock_code: str,
    period: str = Query(default="D", regex="^[DWM]$", description="D: 일봉, W: 주봉, M: 월봉"),
    start_date: Optional[str] = Query(
        default=None,
        regex="^\\d{8}$",
        description="시작일 (YYYYMMDD)"
    ),
    end_date: Optional[str] = Query(
        default=None,
        regex="^\\d{8}$",
        description="종료일 (YYYYMMDD)"
    ),
    use_cache: bool = Query(default=True, description="캐시 사용 여부"),
):
    """일봉/주봉/월봉 시세 조회.

    기본적으로 최근 100일(영업일 기준) 데이터를 반환합니다.
    캐시 TTL: 300초 (5분)
    """
    price_service = get_price_service()

    try:
        data = await price_service.get_ohlcv(
            stock_code=stock_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            use_cache=use_cache,
        )
        return OHLCVResponse(
            stock_code=stock_code,
            period=period,
            data=[OHLCVItem(**item) for item in data],
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"OHLCV 조회 실패: {str(e)}"
        )


@router.post("/cache/clear")
async def clear_cache():
    """가격 캐시 초기화."""
    price_service = get_price_service()
    await price_service.clear_cache()
    return {"message": "Cache cleared"}
