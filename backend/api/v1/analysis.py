from datetime import date as date_cls
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db, get_async_db
from core.cache import api_cache
from core.timezone import now_kst, today_kst
from schemas import TimelineAnalysis, FomoAnalysis
from schemas.chart_analysis import ChartAnalysisResponse
from services import AnalysisService
from services.cross_reference_service import get_convergence_signals

router = APIRouter()


@router.get("/timeline", response_model=TimelineAnalysis)
def get_timeline_analysis(db: Session = Depends(get_db)):
    service = AnalysisService(db)
    return service.get_timeline_analysis()


@router.get("/fomo", response_model=FomoAnalysis)
def get_fomo_analysis(db: Session = Depends(get_db)):
    service = AnalysisService(db)
    return service.get_fomo_analysis()


@router.get("/performance")
def get_performance_by_type(db: Session = Depends(get_db)):
    service = AnalysisService(db)
    return service.get_performance_by_type()


@router.get("/risk-metrics")
def get_risk_metrics(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """리스크 지표 종합 조회: MDD, 샤프비율, 승률추이, 연속손실, 집중도."""
    cache_key = f"risk_metrics:{start_date or ''}:{end_date or ''}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sd = date_cls.fromisoformat(start_date) if start_date else None
    ed = date_cls.fromisoformat(end_date) if end_date else None
    service = AnalysisService(db)
    result = service.get_risk_metrics(start_date=sd, end_date=ed)
    api_cache.set(cache_key, result, ttl=120)
    return result


@router.get("/trade-habits")
def get_trade_habits(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """매매 습관/심리 분석."""
    cache_key = f"trade_habits:{start_date or ''}:{end_date or ''}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    sd = date_cls.fromisoformat(start_date) if start_date else None
    ed = date_cls.fromisoformat(end_date) if end_date else None
    service = AnalysisService(db)
    result = service.get_trade_habits(start_date=sd, end_date=ed)
    api_cache.set(cache_key, result, ttl=120)
    return result


@router.get("/chart-analysis", response_model=ChartAnalysisResponse)
async def get_chart_analysis(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
):
    """차트 기반 매매 분석: 진입/청산 타이밍, MFE/MAE, 미니차트."""
    cache_key = f"chart_analysis:{start_date or ''}:{end_date or ''}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    from services.chart_analysis_service import ChartAnalysisService

    sd = date_cls.fromisoformat(start_date) if start_date else None
    ed = date_cls.fromisoformat(end_date) if end_date else None
    service = ChartAnalysisService(db)
    result = await service.analyze(start_date=sd, end_date=ed)
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/review/what-if")
async def get_review_what_if(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
):
    """What-If 시뮬레이터: 대안 전략 시뮬레이션."""
    cache_key = f"review_what_if:{start_date or ''}:{end_date or ''}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    from services.trade_review_service import TradeReviewService

    sd = date_cls.fromisoformat(start_date) if start_date else None
    ed = date_cls.fromisoformat(end_date) if end_date else None
    service = TradeReviewService(db)
    result = await service.what_if_analysis(start_date=sd, end_date=ed)
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/review/context/{position_id}")
async def get_review_context(
    position_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """매매 컨텍스트 타임라인: 매매 시점 시장 상황 복원."""
    cache_key = f"review_context:{position_id}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    from services.trade_review_service import TradeReviewService

    service = TradeReviewService(db)
    result = await service.trade_context(position_id=position_id)
    api_cache.set(cache_key, result, ttl=120)
    return result


@router.get("/review/flow-winrate")
async def get_review_flow_winrate(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
):
    """수급 연동 승률 분석: 4분면 교차분석."""
    cache_key = f"review_flow_winrate:{start_date or ''}:{end_date or ''}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    from services.trade_review_service import TradeReviewService

    sd = date_cls.fromisoformat(start_date) if start_date else None
    ed = date_cls.fromisoformat(end_date) if end_date else None
    service = TradeReviewService(db)
    result = await service.flow_linked_winrate(start_date=sd, end_date=ed)
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/review/clusters")
async def get_review_clusters(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
):
    """유사 매매 클러스터링: 기술적 조건별 패턴 그룹핑."""
    cache_key = f"review_clusters:{start_date or ''}:{end_date or ''}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    from services.trade_review_service import TradeReviewService

    sd = date_cls.fromisoformat(start_date) if start_date else None
    ed = date_cls.fromisoformat(end_date) if end_date else None
    service = TradeReviewService(db)
    result = await service.trade_clusters(start_date=sd, end_date=ed)
    api_cache.set(cache_key, result, ttl=300)
    return result


@router.get("/backtest/spike")
async def run_spike_backtest(
    recent_days: int = 2,
    base_days: int = 20,
    min_ratio: float = 3.0,
    min_amount: int = 1_000_000_000,
    investor_type: str = "all",
    holding_days: str = "5,10,20",
    db: AsyncSession = Depends(get_async_db),
):
    """수급 급증 신호 백테스트.

    Args:
        recent_days: 최근 비교 기간 (일)
        base_days: 기준 기간 (일)
        min_ratio: 최소 급증 배율
        min_amount: 최소 순매수 금액 (원)
        investor_type: 투자자 유형 (all, foreign, institution)
        holding_days: 보유 기간 (쉼표 구분, 예: "5,10,20")
    """
    from services.backtest_service import BacktestService

    days_list = [int(d.strip()) for d in holding_days.split(",") if d.strip().isdigit()]
    if not days_list:
        days_list = [5, 10, 20]

    service = BacktestService(db)
    return await service.run_spike_backtest(
        recent_days=recent_days,
        base_days=base_days,
        min_ratio=min_ratio,
        min_amount=min_amount,
        investor_type=investor_type,
        holding_days=days_list,
    )


@router.get("/dashboard-signals")
async def get_dashboard_signals(db: AsyncSession = Depends(get_async_db)):
    """대시보드 핵심 시그널 통합 조회.

    한 번의 API 호출로 교차 시그널, 신규 아이디어 수, 최근 차트 패턴 등을 반환.
    """
    from models import InvestmentIdea, ThemeChartPattern, ThemeSetup, StockInvestorFlow
    from sqlalchemy import select, func, desc, and_
    from datetime import date, timedelta, datetime
    import asyncio

    async def _get_convergence():
        try:
            return await get_convergence_signals(db, days=7, min_sources=2)
        except Exception:
            return []

    async def _get_recent_ideas_count():
        try:
            since = now_kst().replace(tzinfo=None) - timedelta(days=7)
            result = await db.execute(
                select(func.count(InvestmentIdea.id)).where(
                    InvestmentIdea.created_at >= since
                )
            )
            return result.scalar() or 0
        except Exception:
            return 0

    async def _get_recent_ideas_stocks():
        """최근 7일 내 생성된 투자아이디어 종목 목록."""
        try:
            since = now_kst().replace(tzinfo=None) - timedelta(days=7)
            result = await db.execute(
                select(
                    InvestmentIdea.stock_code,
                    InvestmentIdea.stock_name,
                    func.count(InvestmentIdea.id).label("idea_count"),
                    func.max(InvestmentIdea.created_at).label("latest"),
                )
                .where(and_(
                    InvestmentIdea.created_at >= since,
                    InvestmentIdea.stock_code.isnot(None),
                ))
                .group_by(InvestmentIdea.stock_code, InvestmentIdea.stock_name)
                .order_by(desc("idea_count"))
                .limit(20)
            )
            return [
                {
                    "stock_code": r.stock_code,
                    "stock_name": r.stock_name or "",
                    "idea_count": r.idea_count,
                }
                for r in result
            ]
        except Exception:
            return []

    async def _get_chart_patterns():
        try:
            since = today_kst() - timedelta(days=7)
            result = await db.execute(
                select(ThemeChartPattern)
                .where(ThemeChartPattern.analysis_date >= since)
                .order_by(desc(ThemeChartPattern.confidence))
                .limit(10)
            )
            patterns = result.scalars().all()
            return [
                {
                    "stock_code": p.stock_code,
                    "stock_name": p.stock_name,
                    "pattern_type": p.pattern_type,
                    "confidence": float(p.confidence) if p.confidence else None,
                    "analysis_date": str(p.analysis_date) if p.analysis_date else None,
                }
                for p in patterns
            ]
        except Exception:
            return []

    async def _get_flow_spikes():
        try:
            today = today_kst()
            recent_days = 2
            base_days = 20
            since_recent = today - timedelta(days=recent_days)
            since_base = today - timedelta(days=base_days)

            # 최근 2일 합산
            recent_q = (
                select(
                    StockInvestorFlow.stock_code,
                    func.sum(StockInvestorFlow.foreign_net_amount + StockInvestorFlow.institution_net_amount).label("recent_sum"),
                )
                .where(StockInvestorFlow.flow_date >= since_recent)
                .group_by(StockInvestorFlow.stock_code)
            )
            recent_result = await db.execute(recent_q)
            recent_map = {r.stock_code: float(r.recent_sum or 0) for r in recent_result}

            # 기준기간 일평균
            base_q = (
                select(
                    StockInvestorFlow.stock_code,
                    (func.sum(StockInvestorFlow.foreign_net_amount + StockInvestorFlow.institution_net_amount)
                     / func.count(func.distinct(StockInvestorFlow.flow_date))).label("daily_avg"),
                )
                .where(
                    and_(
                        StockInvestorFlow.flow_date >= since_base,
                        StockInvestorFlow.flow_date < since_recent,
                    )
                )
                .group_by(StockInvestorFlow.stock_code)
            )
            base_result = await db.execute(base_q)
            base_map = {r.stock_code: float(r.daily_avg or 0) for r in base_result}

            spikes = []
            for code, recent_sum in recent_map.items():
                base_avg = base_map.get(code, 0)
                if base_avg > 0 and recent_sum > 300_000_000:
                    ratio = (recent_sum / recent_days) / base_avg
                    if ratio >= 2.0:
                        spikes.append({
                            "stock_code": code,
                            "spike_ratio": round(ratio, 1),
                            "recent_amount": round(recent_sum),
                        })
            spikes.sort(key=lambda x: x["spike_ratio"], reverse=True)
            return spikes[:10]
        except Exception:
            return []

    async def _get_top_emerging():
        try:
            result = await db.execute(
                select(ThemeSetup)
                .order_by(desc(ThemeSetup.setup_score))
                .limit(3)
            )
            themes = result.scalars().all()
            return [
                {
                    "theme_name": t.theme_name,
                    "setup_score": float(t.setup_score) if t.setup_score else 0,
                }
                for t in themes
            ]
        except Exception:
            return []

    # 캐시 확인 (60초 TTL)
    cached = api_cache.get("dashboard_signals")
    if cached:
        return cached

    convergence, new_ideas_count, ideas_stocks, patterns, spikes, emerging = await asyncio.gather(
        _get_convergence(),
        _get_recent_ideas_count(),
        _get_recent_ideas_stocks(),
        _get_chart_patterns(),
        _get_flow_spikes(),
        _get_top_emerging(),
    )

    result = {
        "convergence_signals": convergence[:8],
        "flow_spikes": spikes,
        "chart_patterns": patterns,
        "recent_ideas_stocks": ideas_stocks,
        "emerging_themes": emerging,
        "new_ideas_7d": new_ideas_count,
        "generated_at": now_kst().isoformat(),
    }
    api_cache.set("dashboard_signals", result, ttl=60)
    return result
