"""차트 시그널 스캐너 API."""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from core.cache import api_cache
from core.timezone import now_kst
from services.pullback_service import PullbackService
from schemas.pullback import SignalResponse, SignalDetailResponse

router = APIRouter(prefix="/pullback", tags=["pullback"])


class StockCodesRequest(BaseModel):
    stock_codes: List[str]
    min_score: float = 0.0
    limit: int = 50


@router.get("/signals", response_model=SignalResponse)
async def get_signals(
    signal_type: Optional[str] = None,
    min_score: float = 0.0,
    limit: int = 200,
    only_profitable: bool = False,
    only_growing: bool = False,
    only_institutional: bool = False,
    only_surge_pullback: bool = False,
    mss_timeframe: Optional[str] = "daily",
    db: AsyncSession = Depends(get_async_db),
):
    """시그널 목록 조회.

    Args:
        signal_type: pullback | high_breakout | resistance_test | support_test | mss_proximity | momentum_zone | ma120_turn | candle_squeeze | candle_expansion (None이면 전체)
        min_score: 최소 점수 (0-100)
        limit: 최대 반환 개수
        only_profitable: 수익성 필터
        only_growing: 매출 성장 필터
        only_institutional: 기관매수 필터
        only_surge_pullback: 급등 후 눌림만 (surge_pct >= 25%)
        mss_timeframe: MSS 근접 타임프레임 (daily|weekly|monthly)
    """
    valid_types = {"pullback", "high_breakout", "resistance_test", "support_test", "mss_proximity", "momentum_zone", "ma120_turn", "candle_squeeze", "candle_expansion", None}
    if signal_type not in valid_types:
        raise HTTPException(status_code=400, detail="signal_type must be one of: pullback, high_breakout, resistance_test, support_test, mss_proximity, momentum_zone, ma120_turn, candle_squeeze, candle_expansion")

    tf = mss_timeframe or "daily"
    cache_key = f"signals:{signal_type}:{min_score}:{limit}:{only_profitable}:{only_growing}:{only_institutional}:{only_surge_pullback}:{tf}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    service = PullbackService(db)
    stocks = await service.get_signals(
        signal_type=signal_type,
        min_score=min_score,
        limit=limit,
        only_profitable=only_profitable,
        only_growing=only_growing,
        only_institutional=only_institutional,
        mss_timeframe=tf,
    )

    # 급등 후 눌림 필터 (surge_pct >= 25%)
    if only_surge_pullback:
        stocks = [s for s in stocks if s.signal_type.value == "pullback" and (s.surge_pct or 0) >= 25]

    result = SignalResponse(
        stocks=stocks,
        count=len(stocks),
        signal_type=signal_type or "all",
        generated_at=now_kst().isoformat(),
    )
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/signals/summary")
async def get_signals_summary(
    db: AsyncSession = Depends(get_async_db),
):
    """시그널 타입별 카운트 요약."""
    cached = api_cache.get("signals:summary")
    if cached:
        return cached

    service = PullbackService(db)
    counts = await service.get_summary()

    trend_themes = counts.pop("trend_themes", [])
    squeeze_themes = counts.pop("squeeze_themes", [])
    top_picks = counts.pop("top_picks", 0)
    result = {
        "pullback": counts["pullback"],
        "high_breakout": counts["high_breakout"],
        "resistance_test": counts["resistance_test"],
        "support_test": counts["support_test"],
        "mss_proximity": counts["mss_proximity"],
        "momentum_zone": counts["momentum_zone"],
        "ma120_turn": counts["ma120_turn"],
        "candle_squeeze": counts["candle_squeeze"],
        "candle_expansion": counts["candle_expansion"],
        "top_picks": top_picks,
        "total": sum(counts.values()),
        "trend_themes": trend_themes,
        "squeeze_themes": squeeze_themes,
        "generated_at": now_kst().isoformat(),
    }
    api_cache.set("signals:summary", result, ttl=300)
    return result


@router.get("/top-picks", response_model=SignalResponse)
async def get_top_picks(
    limit: int = 20,
    db: AsyncSession = Depends(get_async_db),
):
    """TOP 필터 기반 오늘의 매매 후보."""
    cache_key = f"top_picks:{limit}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    service = PullbackService(db)
    stocks = await service.get_top_picks(limit=limit)

    result = SignalResponse(
        stocks=stocks,
        count=len(stocks),
        signal_type="top_picks",
        generated_at=now_kst().isoformat(),
    )
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/backtest/momentum-zone")
async def backtest_momentum_zone(
    lookback_days: int = 365,
    holding_days: str = "5,10,20",
    min_score: int = 40,
    step_days: int = 1,
    db: AsyncSession = Depends(get_async_db),
):
    """관성 구간 시그널 백테스트.

    Args:
        lookback_days: 분석 기간 (일)
        holding_days: 보유기간 목록 (쉼표 구분)
        min_score: 최소 점수
        step_days: 슬라이딩 윈도우 스텝 (1=매일, 3=3일마다)
    """
    hd_list = [int(d.strip()) for d in holding_days.split(",") if d.strip().isdigit()]
    if not hd_list:
        hd_list = [5, 10, 20]

    cache_key = f"mz_backtest:{lookback_days}:{','.join(map(str, hd_list))}:{min_score}:{step_days}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    service = PullbackService(db)
    result = await service.run_momentum_zone_backtest(
        lookback_days=lookback_days,
        holding_days=hd_list,
        min_score=min_score,
        step_days=step_days,
    )
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/signals/{stock_code}", response_model=SignalDetailResponse)
async def get_signal_detail(
    stock_code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """종목 시그널 상세 (60일 차트 + 20일 수급표)."""
    service = PullbackService(db)
    detail = await service.get_stock_detail(stock_code)

    if detail is None:
        raise HTTPException(status_code=404, detail="Stock not found or insufficient data")

    return SignalDetailResponse(
        stock=detail["stock"],
        price_history=detail["price_history"],
        flow_history=detail["flow_history"],
        analysis_summary=detail["analysis_summary"],
        generated_at=now_kst().isoformat(),
    )


@router.post("/signals/by-codes", response_model=SignalResponse)
async def get_signals_by_codes(
    request: StockCodesRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """지정 종목 시그널 분석."""
    if not request.stock_codes:
        return SignalResponse(
            stocks=[],
            count=0,
            signal_type="by_codes",
            generated_at=now_kst().isoformat(),
        )

    service = PullbackService(db)
    stocks = await service.get_by_stock_codes(
        stock_codes=request.stock_codes,
        min_score=request.min_score,
        limit=request.limit,
    )

    return SignalResponse(
        stocks=stocks,
        count=len(stocks),
        signal_type="by_codes",
        generated_at=now_kst().isoformat(),
    )
