"""눌림목 분석 API."""
from datetime import datetime
from typing import Optional, List

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from services.pullback_service import PullbackService
from schemas.pullback import PullbackResponse, PullbackDetailResponse

# 서버사이드 캐시 (5분 TTL)
_pullback_cache = TTLCache(maxsize=32, ttl=300)

router = APIRouter(prefix="/pullback", tags=["pullback"])


class StockCodesRequest(BaseModel):
    """종목 코드 목록 요청."""
    stock_codes: List[str]
    min_score: float = 0.0
    limit: int = 50


@router.get("/ma-support", response_model=PullbackResponse)
async def get_ma_support_stocks(
    ma_type: str = "ma20",
    max_distance_pct: float = 5.0,
    require_above_ma: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
):
    """이평선 지지 종목 조회.

    Args:
        ma_type: 이평선 종류 (ma20, ma50, ma200)
        max_distance_pct: 이평선 대비 최대 거리 (%)
        require_above_ma: 이평선 위에 있어야 하는지 여부
        limit: 최대 반환 개수

    Returns:
        이평선 지지 종목 목록
    """
    if ma_type not in ["ma20", "ma50", "ma200"]:
        raise HTTPException(status_code=400, detail="ma_type must be one of: ma20, ma50, ma200")

    service = PullbackService(db)
    stocks = await service.get_ma_support_stocks(
        ma_type=ma_type,
        max_distance_pct=max_distance_pct,
        require_above_ma=require_above_ma,
        limit=limit,
    )

    return PullbackResponse(
        stocks=stocks,
        count=len(stocks),
        filter_type="ma_support",
        generated_at=datetime.now().isoformat(),
    )


@router.get("/support-line", response_model=PullbackResponse)
async def get_support_line_stocks(
    max_distance_pct: float = 10.0,
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
):
    """지지선 근처 종목 조회.

    Args:
        max_distance_pct: 지지선 대비 최대 거리 (%)
        limit: 최대 반환 개수

    Returns:
        지지선 근처 종목 목록
    """
    service = PullbackService(db)
    stocks = await service.get_support_line_stocks(
        max_distance_pct=max_distance_pct,
        limit=limit,
    )

    return PullbackResponse(
        stocks=stocks,
        count=len(stocks),
        filter_type="support_line",
        generated_at=datetime.now().isoformat(),
    )


@router.get("/depth", response_model=PullbackResponse)
async def get_pullback_depth_stocks(
    min_pullback_pct: float = 10.0,
    max_pullback_pct: float = 30.0,
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
):
    """눌림 깊이순 종목 조회.

    Args:
        min_pullback_pct: 최소 눌림 깊이 (%)
        max_pullback_pct: 최대 눌림 깊이 (%)
        limit: 최대 반환 개수

    Returns:
        눌림 깊이 기준 종목 목록
    """
    service = PullbackService(db)
    stocks = await service.get_pullback_depth_stocks(
        min_pullback_pct=min_pullback_pct,
        max_pullback_pct=max_pullback_pct,
        limit=limit,
    )

    return PullbackResponse(
        stocks=stocks,
        count=len(stocks),
        filter_type="depth",
        generated_at=datetime.now().isoformat(),
    )


@router.get("/ranking", response_model=PullbackResponse)
async def get_pullback_ranking(
    min_score: float = 0.0,
    min_grade: str = "D",
    require_positive_flow: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
):
    """눌림목 종합 랭킹 조회.

    Args:
        min_score: 최소 종합 점수 (0-100)
        min_grade: 최소 등급 (A, B, C, D)
        require_positive_flow: 수급 양호 필수 여부
        limit: 최대 반환 개수

    Returns:
        종합 점수순 눌림목 종목 목록
    """
    if min_grade not in ["A", "B", "C", "D"]:
        raise HTTPException(status_code=400, detail="min_grade must be one of: A, B, C, D")

    # 서버사이드 캐시 확인
    cache_key = f"ranking:{min_score}:{min_grade}:{require_positive_flow}:{limit}"
    if cache_key in _pullback_cache:
        return _pullback_cache[cache_key]

    service = PullbackService(db)
    stocks = await service.get_ranking(
        min_score=min_score,
        min_grade=min_grade,
        require_positive_flow=require_positive_flow,
        limit=limit,
    )

    result = PullbackResponse(
        stocks=stocks,
        count=len(stocks),
        filter_type="ranking",
        generated_at=datetime.now().isoformat(),
    )
    _pullback_cache[cache_key] = result
    return result


@router.post("/by-codes", response_model=PullbackResponse)
async def get_pullback_by_codes(
    request: StockCodesRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """특정 종목 코드들의 눌림목 분석 조회.

    Args:
        request: 종목 코드 목록과 필터 옵션

    Returns:
        지정된 종목들의 눌림목 분석 결과
    """
    if not request.stock_codes:
        return PullbackResponse(
            stocks=[],
            count=0,
            filter_type="by_codes",
            generated_at=datetime.now().isoformat(),
        )

    service = PullbackService(db)
    stocks = await service.get_by_stock_codes(
        stock_codes=request.stock_codes,
        min_score=request.min_score,
        limit=request.limit,
    )

    return PullbackResponse(
        stocks=stocks,
        count=len(stocks),
        filter_type="by_codes",
        generated_at=datetime.now().isoformat(),
    )


@router.get("/{stock_code}", response_model=PullbackDetailResponse)
async def get_stock_pullback_detail(
    stock_code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """종목 눌림목 상세 분석.

    Args:
        stock_code: 종목코드

    Returns:
        종목 눌림목 상세 분석 결과
    """
    service = PullbackService(db)
    detail = await service.get_stock_detail(stock_code)

    if detail is None:
        raise HTTPException(status_code=404, detail="Stock not found or insufficient data")

    return PullbackDetailResponse(
        stock=detail["stock"],
        price_history=detail["price_history"],
        flow_history=detail["flow_history"],
        analysis_summary=detail["analysis_summary"],
        generated_at=datetime.now().isoformat(),
    )
