"""테마 셋업 API 엔드포인트."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db
from core.timezone import now_kst
from services.theme_setup_service import ThemeSetupService
from services.chart_pattern_service import ChartPatternService
from services.news_collector_service import NewsCollectorService
from services.investor_flow_service import InvestorFlowService
from services.collection_status import get_collection_status
from schemas.theme_setup import (
    ThemeSetupResponse,
    ThemeSetupDetailResponse,
    ChartPatternResponse,
    NewsTrendResponse,
    EmergingThemesResponse,
    ThemeSetupCalculateResponse,
)

router = APIRouter(prefix="/theme-setup", tags=["theme-setup"])


@router.get("/collection-status")
async def get_collection_status_api():
    """수집 작업 상태 조회."""
    status_manager = get_collection_status()
    return status_manager.get_all_status()


@router.get("/emerging", response_model=EmergingThemesResponse)
async def get_emerging_themes(
    limit: int = Query(default=20, le=50),
    min_score: float = Query(default=30.0, ge=0.0),
    db: AsyncSession = Depends(get_async_db),
):
    """자리 잡는 테마 목록 조회.

    셋업 점수가 높은 순으로 테마를 반환합니다.
    """
    service = ThemeSetupService(db)
    themes = await service.get_emerging_themes(limit=limit, min_score=min_score)

    return EmergingThemesResponse(
        themes=[ThemeSetupResponse(**t) for t in themes],
        total_count=len(themes),
        generated_at=now_kst().isoformat(),
    )


@router.get("/{theme_name}/detail", response_model=ThemeSetupDetailResponse)
async def get_theme_setup_detail(
    theme_name: str,
    db: AsyncSession = Depends(get_async_db),
):
    """테마 셋업 상세 정보 조회."""
    service = ThemeSetupService(db)
    detail = await service.get_theme_setup_detail(theme_name)

    if not detail:
        raise HTTPException(status_code=404, detail=f"Theme '{theme_name}' not found or no setup data")

    return ThemeSetupDetailResponse(**detail)


@router.get("/{theme_name}/patterns", response_model=list[ChartPatternResponse])
async def get_theme_patterns(
    theme_name: str,
    db: AsyncSession = Depends(get_async_db),
):
    """테마 내 차트 패턴 조회."""
    service = ChartPatternService(db)
    patterns = await service.get_theme_patterns(theme_name)

    return [ChartPatternResponse(**p) for p in patterns]


@router.get("/{theme_name}/news-trend", response_model=list[NewsTrendResponse])
async def get_theme_news_trend(
    theme_name: str,
    days: int = Query(default=14, le=30),
    db: AsyncSession = Depends(get_async_db),
):
    """테마 뉴스 빈도 추이 조회."""
    service = NewsCollectorService(db)
    trend = await service.get_theme_news_trend(theme_name, days=days)
    await service.close()

    return [NewsTrendResponse(**t) for t in trend]


@router.get("/{theme_name}/news")
async def get_theme_recent_news(
    theme_name: str,
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_async_db),
):
    """테마 최근 뉴스 조회."""
    service = NewsCollectorService(db)
    news = await service.get_recent_news(theme_name, limit=limit)
    await service.close()

    return {"news": news, "count": len(news)}


@router.get("/stock/{stock_code}/pattern")
async def get_stock_pattern(
    stock_code: str,
    db: AsyncSession = Depends(get_async_db),
):
    """종목 패턴 조회."""
    service = ChartPatternService(db)
    pattern = await service.get_stock_pattern(stock_code)

    if not pattern:
        raise HTTPException(status_code=404, detail=f"No pattern found for stock {stock_code}")

    return ChartPatternResponse(**pattern)


@router.get("/{theme_name}/history")
async def get_theme_setup_history(
    theme_name: str,
    days: int = Query(default=30, le=90),
    db: AsyncSession = Depends(get_async_db),
):
    """테마 셋업 히스토리 조회."""
    service = ThemeSetupService(db)
    history = await service.get_setup_history(theme_name, days=days)

    return {"theme_name": theme_name, "history": history}


@router.post("/calculate", response_model=ThemeSetupCalculateResponse)
async def calculate_setups(
    db: AsyncSession = Depends(get_async_db),
):
    """테마 셋업 점수 수동 계산.

    모든 테마의 셋업 점수를 계산합니다.
    """
    status_manager = get_collection_status()

    if status_manager.get_status("calculate")["is_running"]:
        raise HTTPException(status_code=409, detail="점수 재계산이 이미 진행 중입니다.")

    status_manager.start("calculate", "점수 계산 중...")
    try:
        service = ThemeSetupService(db)
        result = await service.calculate_all_setups()
        return ThemeSetupCalculateResponse(**result)
    finally:
        status_manager.finish("calculate")


@router.post("/collect-news")
async def collect_news(
    db: AsyncSession = Depends(get_async_db),
):
    """테마 뉴스 수동 수집.

    네이버 검색 API와 RSS 피드에서 뉴스를 수집합니다.
    """
    service = NewsCollectorService(db)
    result = await service.collect_all()
    await service.close()

    return result


@router.post("/analyze-patterns")
async def analyze_patterns(
    db: AsyncSession = Depends(get_async_db),
):
    """차트 패턴 수동 분석.

    모든 테마의 종목에 대해 차트 패턴 분석을 수행합니다.
    """
    status_manager = get_collection_status()

    if status_manager.get_status("patterns")["is_running"]:
        raise HTTPException(status_code=409, detail="패턴 분석이 이미 진행 중입니다.")

    status_manager.start("patterns", "패턴 분석 중...")
    try:
        service = ChartPatternService(db)
        result = await service.analyze_all_themes()
        return result
    finally:
        status_manager.finish("patterns")


@router.post("/collect-investor-flow")
async def collect_investor_flow(
    db: AsyncSession = Depends(get_async_db),
):
    """투자자 수급 데이터 수동 수집.

    언급된 종목들의 외국인/기관 순매수 데이터를 수집합니다.
    """
    import json
    from services.theme_map_service import get_theme_map_service

    status_manager = get_collection_status()

    if status_manager.get_status("investor_flow")["is_running"]:
        raise HTTPException(status_code=409, detail="수급 수집이 이미 진행 중입니다.")

    # 테마맵에서 모든 종목 코드 추출
    tms = get_theme_map_service()
    all_stocks = {}
    for stocks in tms.get_all_themes().values():
        for stock in stocks:
            code = stock.get("code")
            name = stock.get("name", "")
            if code:
                all_stocks[code] = name

    stock_codes = list(all_stocks.keys())

    status_manager.start("investor_flow", f"수급 수집 중... ({len(stock_codes)}개 종목)")
    try:
        service = InvestorFlowService(db)
        result = await service.collect_investor_flow(stock_codes, all_stocks)

        return {
            "collected_count": result["collected_count"],
            "failed_count": result["failed_count"],
            "records_saved": result.get("records_saved", 0),
            "skipped_stocks": result.get("skipped_stocks", 0),
            "total_stocks": len(stock_codes),
            "collected_at": now_kst().isoformat(),
        }
    finally:
        status_manager.finish("investor_flow")


@router.post("/recalculate-flow-scores")
async def recalculate_flow_scores(
    db: AsyncSession = Depends(get_async_db),
):
    """수급 점수 재계산.

    DB에 저장된 수급 데이터의 flow_score를 현재 기준으로 재계산합니다.
    수집 없이 점수만 업데이트합니다.
    """
    service = InvestorFlowService(db)
    result = await service.recalculate_all_flow_scores()

    return {
        "total_records": result["total"],
        "updated_records": result["updated"],
        "recalculated_at": now_kst().isoformat(),
    }


@router.get("/{theme_name}/investor-flow")
async def get_theme_investor_flow(
    theme_name: str,
    days: int = Query(default=5, le=30),
    db: AsyncSession = Depends(get_async_db),
):
    """테마 투자자 수급 현황 조회.

    테마 내 종목들의 외국인/기관 순매수 데이터를 반환합니다.
    """
    import json
    from pathlib import Path

    # 테마맵에서 종목 코드 추출
    theme_map_path = Path(__file__).parent.parent.parent / "data" / "theme_map.json"
    try:
        with open(theme_map_path, "r", encoding="utf-8") as f:
            theme_map = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load theme map: {e}")

    stocks = theme_map.get(theme_name, [])
    if not stocks:
        raise HTTPException(status_code=404, detail=f"Theme '{theme_name}' not found")

    stock_codes = [s.get("code") for s in stocks if s.get("code")]

    service = InvestorFlowService(db)
    summary = await service.get_theme_investor_flow(stock_codes, days)
    stock_flows = await service.get_theme_stock_flows(stock_codes, days)

    return {
        "theme_name": theme_name,
        "days": days,
        "summary": summary,
        "stocks": stock_flows,
    }


@router.get("/stock/{stock_code}/investor-flow")
async def get_stock_investor_flow(
    stock_code: str,
    days: int = Query(default=30, le=90),
    db: AsyncSession = Depends(get_async_db),
):
    """종목 수급 히스토리 조회.

    종목의 일별 외국인/기관 순매수 데이터를 반환합니다.
    """
    service = InvestorFlowService(db)
    history = await service.get_stock_flow_history(stock_code, days)

    return {
        "stock_code": stock_code,
        "days": days,
        "history": history,
    }


@router.get("/stock/{stock_code}/ohlcv")
async def get_stock_ohlcv(
    stock_code: str,
    days: int = Query(default=90, le=1000),  # DB 저장으로 더 긴 기간 지원
    before_date: Optional[str] = Query(default=None, description="이 날짜 이전 데이터 조회 (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_async_db),
):
    """종목 OHLCV 데이터 조회 (차트용).

    DB에서 조회하며, 데이터가 없으면 KIS API에서 수집 후 반환합니다.
    lightweight-charts 차트 라이브러리에서 사용할 수 있는 형식으로 반환합니다.

    - before_date가 지정되면 해당 날짜 이전 데이터만 반환 (스크롤 로딩용)
    """
    from datetime import date as date_type
    from services.ohlcv_service import OHLCVService

    ohlcv_service = OHLCVService(db)

    # before_date 파싱
    end_date = None
    if before_date:
        try:
            end_date = date_type.fromisoformat(before_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid before_date format. Use YYYY-MM-DD")

    # DB에서 조회
    candles = await ohlcv_service.get_ohlcv(stock_code, days=days, end_date=end_date)

    # DB에 데이터가 부족하면 KIS API에서 수집 (최초 로딩 시에만)
    if not before_date and len(candles) < days * 0.5:
        collected = await ohlcv_service.collect_ohlcv(stock_code, days=max(days, 240))
        if collected > 0:
            candles = await ohlcv_service.get_ohlcv(stock_code, days=days, end_date=end_date)

    # 더 로딩할 데이터가 있는지 확인
    has_more = len(candles) >= days
    oldest_date = candles[0]["time"] if candles else None

    return {
        "stock_code": stock_code,
        "candles": candles,
        "count": len(candles),
        "has_more": has_more,
        "oldest_date": oldest_date,
    }


@router.get("/rank-trend")
async def get_rank_trend(
    days: int = Query(default=14, ge=1, le=30),
    top_n: int = Query(default=10, ge=1, le=20),
    db: AsyncSession = Depends(get_async_db),
):
    """상위 테마들의 순위 추이 조회.

    최근 기준 상위 N개 테마의 일별 순위/점수 변화를 반환합니다.
    라인 차트 시각화에 적합한 형태로 데이터를 제공합니다.

    Args:
        days: 조회 기간 (기본 14일, 최대 30일)
        top_n: 조회할 테마 수 (기본 10개, 최대 20개)

    Returns:
        {
            "dates": ["2026-01-22", ...],
            "themes": [
                {
                    "name": "테마명",
                    "data": [{"date": "...", "rank": 1, "score": 75.5}, ...]
                },
                ...
            ]
        }
    """
    service = ThemeSetupService(db)
    return await service.get_rank_trend(days=days, top_n=top_n)
