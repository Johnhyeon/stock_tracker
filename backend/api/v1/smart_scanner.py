"""Smart Scanner API - 4차원 교차검증 스캔."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from core.cache import api_cache
from core.timezone import now_kst
from services.smart_scanner_service import SmartScannerService
from schemas.smart_scanner import SmartScannerResponse, NarrativeBriefingResponse

router = APIRouter(prefix="/smart-scanner", tags=["smart-scanner"])


@router.get("/scan", response_model=SmartScannerResponse)
async def scan(
    min_score: float = 0.0,
    limit: int = 100,
    sort_by: str = "composite",
    exclude_expert: bool = False,
    db: AsyncSession = Depends(get_async_db),
):
    """4차원 복합 점수 기반 전체 스캔."""
    cache_key = f"smart-scanner:scan:{min_score}:{limit}:{sort_by}:ex={exclude_expert}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    service = SmartScannerService(db)
    stocks = await service.scan_all(min_score=min_score, limit=limit, sort_by=sort_by, exclude_expert=exclude_expert)

    # 요약 통계
    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    aligned_3_plus = 0
    for s in stocks:
        grade_counts[s.composite_grade] = grade_counts.get(s.composite_grade, 0) + 1
        if s.aligned_count >= 3:
            aligned_3_plus += 1

    result = SmartScannerResponse(
        stocks=stocks,
        count=len(stocks),
        summary={
            "grade_counts": grade_counts,
            "aligned_3_plus": aligned_3_plus,
        },
        generated_at=now_kst().isoformat(),
    )
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/stock/{stock_code}")
async def get_stock_detail(
    stock_code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """단일 종목 4차원 상세."""
    cache_key = f"smart-scanner:stock:{stock_code}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    service = SmartScannerService(db)
    detail = await service.get_stock_detail(stock_code)

    if detail is None:
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없거나 차트 시그널 데이터가 없습니다")

    result = detail.model_dump()
    result["generated_at"] = now_kst().isoformat()
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/narrative/{stock_code}", response_model=NarrativeBriefingResponse)
async def get_narrative(
    stock_code: str,
    force_refresh: bool = False,
    db: AsyncSession = Depends(get_async_db),
):
    """종목 내러티브 AI 브리핑."""
    if not force_refresh:
        cache_key = f"smart-scanner:narrative:{stock_code}"
        cached = api_cache.get(cache_key)
        if cached:
            return cached

    from services.narrative_service import NarrativeService

    service = NarrativeService(db)
    briefing = await service.get_briefing(stock_code, force_refresh=force_refresh)

    if briefing is None:
        raise HTTPException(status_code=404, detail="내러티브 브리핑 생성 실패")

    result = NarrativeBriefingResponse(
        stock_code=stock_code,
        stock_name=briefing.get("stock_name", ""),
        one_liner=briefing.get("one_liner", ""),
        why_moving=briefing.get("why_moving", ""),
        theme_context=briefing.get("theme_context", ""),
        expert_perspective=briefing.get("expert_perspective", ""),
        financial_highlight=briefing.get("financial_highlight", ""),
        catalysts=briefing.get("catalysts", []),
        risk_factors=briefing.get("risk_factors", []),
        narrative_strength=briefing.get("narrative_strength", "weak"),
        market_outlook=briefing.get("market_outlook", "neutral"),
        generated_at=briefing.get("generated_at", now_kst().isoformat()),
    )

    api_cache.set(f"smart-scanner:narrative:{stock_code}", result, ttl=600)
    return result
