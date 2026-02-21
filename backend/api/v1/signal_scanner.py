"""시그널 스캐너 API."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from core.cache import api_cache
from core.timezone import now_kst
from services.signal_scanner_service import SignalScannerService
from schemas.signal_scanner import (
    ScannerSignalResponse,
    ScannerDetailResponse,
    ScannerAIAdviceResponse,
)

router = APIRouter(prefix="/signal-scanner", tags=["signal-scanner"])


@router.get("/signals", response_model=ScannerSignalResponse)
async def get_signals(
    min_score: float = 0.0,
    limit: int = 200,
    db: AsyncSession = Depends(get_async_db),
):
    """시그널 배치 스캔."""
    cache_key = f"signal-scanner:signals:{min_score}:{limit}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    service = SignalScannerService(db)
    signals = await service.analyze_batch(min_score=min_score, limit=limit)

    result = ScannerSignalResponse(
        signals=signals,
        count=len(signals),
        generated_at=now_kst().isoformat(),
    )
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/proven-patterns")
async def get_proven_patterns(
    db: AsyncSession = Depends(get_async_db),
):
    """실전 검증 패턴 - 매매 복기 클러스터링에서 승률 50%+ & 2건+ 패턴."""
    cache_key = "signal-scanner:proven-patterns"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    from services.trade_review_service import TradeReviewService
    review_service = TradeReviewService(db)
    cluster_result = await review_service.trade_clusters()

    # 보유기간 제외 후 동일 조건 클러스터 병합
    merged: dict[str, dict] = {}
    for cluster in cluster_result.clusters:
        if cluster.trade_count < 3 or cluster.win_rate < 60.0:
            continue
        conditions = {k: v for k, v in cluster.conditions.items() if k != "holding"}
        if not conditions:
            continue
        key = "|".join(f"{k}:{v}" for k, v in sorted(conditions.items()))
        if key in merged:
            # 동일 조건 → 건수 합산, 가중평균
            m = merged[key]
            total = m["trade_count"] + cluster.trade_count
            m["win_rate"] = round(
                (m["win_rate"] * m["trade_count"] + cluster.win_rate * cluster.trade_count) / total, 1
            )
            m["avg_return_pct"] = round(
                (m["avg_return_pct"] * m["trade_count"] + cluster.avg_return_pct * cluster.trade_count) / total, 2
            )
            m["trade_count"] = total
        else:
            merged[key] = {
                "conditions": conditions,
                "win_rate": cluster.win_rate,
                "avg_return_pct": cluster.avg_return_pct,
                "trade_count": cluster.trade_count,
            }

    patterns = list(merged.values())
    # 승률 내림차순
    patterns.sort(key=lambda p: p["win_rate"], reverse=True)

    result = {
        "patterns": patterns,
        "generated_at": now_kst().isoformat(),
    }
    api_cache.set(cache_key, result, ttl=600)
    return result


@router.get("/signals/{stock_code}", response_model=ScannerDetailResponse)
async def get_signal_detail(
    stock_code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """종목 시그널 상세 (signal + checklist + price_history)."""
    cache_key = f"signal-scanner:detail:{stock_code}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    service = SignalScannerService(db)
    detail = await service.get_stock_detail(stock_code)

    if detail is None:
        raise HTTPException(status_code=404, detail="Stock not found or insufficient data")

    result = ScannerDetailResponse(
        signal=detail["signal"],
        checklist=detail["checklist"],
        price_history=detail["price_history"],
        generated_at=now_kst().isoformat(),
    )
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/checklist/{stock_code}")
async def get_checklist(
    stock_code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """종목 체크리스트만 조회."""
    service = SignalScannerService(db)
    checklist = await service.get_checklist(stock_code)

    if checklist is None:
        raise HTTPException(status_code=404, detail="Stock not found or insufficient data")

    return {
        "stock_code": stock_code,
        "checklist": [item.model_dump() for item in checklist],
        "total_score": sum(item.score for item in checklist),
        "max_score": sum(item.max_score for item in checklist),
        "generated_at": now_kst().isoformat(),
    }


@router.get("/ai-advice/{stock_code}", response_model=ScannerAIAdviceResponse)
async def get_ai_advice(
    stock_code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Gemini AI 시그널 분석."""
    cache_key = f"signal-scanner:ai:{stock_code}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    from integrations.gemini.client import get_gemini_client

    gemini = get_gemini_client()
    if not gemini.is_configured:
        raise HTTPException(status_code=503, detail="Gemini API not configured")

    service = SignalScannerService(db)

    signal = await service.analyze_stock(stock_code)
    if signal is None:
        raise HTTPException(status_code=404, detail="Stock not found or insufficient data")

    ohlcv_summary = await service.get_ohlcv_summary(stock_code)
    if ohlcv_summary is None:
        raise HTTPException(status_code=404, detail="OHLCV data not found")

    signal_data = {
        "abcd_phase": signal.abcd_phase.value,
        "ma_alignment": signal.ma_alignment.value,
        "gap_type": signal.gap_type.value,
        "has_kkandolji": signal.has_kkandolji,
        "total_score": signal.total_score,
        "grade": signal.grade,
    }

    advice = await gemini.analyze_chart_signal(
        stock_code=stock_code,
        stock_name=signal.stock_name,
        ohlcv_summary=ohlcv_summary,
        signal_data=signal_data,
    )

    if advice is None:
        raise HTTPException(status_code=500, detail="AI analysis failed")

    result = ScannerAIAdviceResponse(
        stock_code=stock_code,
        stock_name=signal.stock_name,
        advice=advice,
        generated_at=now_kst().isoformat(),
    )
    api_cache.set(cache_key, result, ttl=600)
    return result
