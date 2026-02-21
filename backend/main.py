import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from core.config import get_settings
from core.database import engine, Base
from core.event_handlers import register_event_handlers
from api.v1 import ideas, positions, positions_bulk, dashboard, dashboard_v2, analysis, uploads, stocks, data, disclosures, youtube, health, alerts, experts, themes, theme_setup, flow_ranking, telegram_monitor, data_status, etf_rotation, sector_flow, snapshots, financial_statements, telegram_ideas, pullback, stock_profile, mentions, trades, signal_scanner, watchlist, smart_scanner, stock_news, catalyst, theme_pulse, company_profile, recovery, market_intel, value_screener, backtest
from scheduler import get_scheduler_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)

    # narrative_briefings 테이블에 새 컬럼 추가 (존재하지 않을 때만)
    from sqlalchemy import text as sa_text, inspect as sa_inspect
    insp = sa_inspect(engine)
    if "narrative_briefings" in insp.get_table_names():
        existing_cols = {c["name"] for c in insp.get_columns("narrative_briefings")}
        with engine.begin() as conn:
            if "market_outlook" not in existing_cols:
                conn.execute(sa_text("ALTER TABLE narrative_briefings ADD COLUMN market_outlook VARCHAR(20)"))
            if "financial_highlight" not in existing_cols:
                conn.execute(sa_text("ALTER TABLE narrative_briefings ADD COLUMN financial_highlight TEXT"))

    # rising_chart_patterns 테이블에 새 컬럼 추가 (존재하지 않을 때만)
    if "rising_chart_patterns" in insp.get_table_names():
        rcp_cols = {c["name"] for c in insp.get_columns("rising_chart_patterns")}
        with engine.begin() as conn:
            if "pre_analysis" not in rcp_cols:
                conn.execute(sa_text("ALTER TABLE rising_chart_patterns ADD COLUMN pre_analysis JSONB DEFAULT '{}'"))
            if "trigger_info" not in rcp_cols:
                conn.execute(sa_text("ALTER TABLE rising_chart_patterns ADD COLUMN trigger_info JSONB DEFAULT '{}'"))

    # watchlist_items 테이블에 group_id 컬럼 추가 (존재하지 않을 때만)
    if "watchlist_items" in insp.get_table_names():
        wi_cols = {c["name"] for c in insp.get_columns("watchlist_items")}
        if "group_id" not in wi_cols:
            with engine.begin() as conn:
                conn.execute(sa_text("ALTER TABLE watchlist_items ADD COLUMN group_id INTEGER REFERENCES watchlist_groups(id) ON DELETE SET NULL"))

    # Register event handlers
    register_event_handlers()

    # Start scheduler
    scheduler = get_scheduler_manager()
    scheduler.start()
    logger.info("Application started")

    # Catch-up: 서버 중단 기간 동안 놓친 데이터 자동 보정 (백그라운드)
    async def _safe_catchup():
        try:
            from services.catchup_service import run_catchup
            await run_catchup()
        except Exception as e:
            logger.error(f"Catch-up 실패 (서버 운영에 영향 없음): {e}")

    asyncio.get_running_loop().create_task(_safe_catchup())

    yield

    # Shutdown
    scheduler.shutdown()
    logger.info("Application shutdown")


app = FastAPI(
    title="Investment Tracker API",
    description="투자 아이디어 추적 및 관리 시스템",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ideas.router, prefix="/api/v1/ideas", tags=["ideas"])
app.include_router(positions.router, prefix="/api/v1/positions", tags=["positions"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["analysis"])
app.include_router(uploads.router, prefix="/api/v1/uploads", tags=["uploads"])
app.include_router(stocks.router, prefix="/api/v1/stocks", tags=["stocks"])
app.include_router(data.router, prefix="/api/v1/data", tags=["data"])
app.include_router(disclosures.router, prefix="/api/v1/disclosures", tags=["disclosures"])
app.include_router(youtube.router, prefix="/api/v1/youtube", tags=["youtube"])
app.include_router(experts.router, prefix="/api/v1/experts", tags=["experts"])
app.include_router(themes.router, prefix="/api/v1/themes", tags=["themes"])
app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(positions_bulk.router, prefix="/api/v1", tags=["positions-bulk"])
app.include_router(theme_setup.router, prefix="/api/v1", tags=["theme-setup"])
app.include_router(flow_ranking.router, prefix="/api/v1", tags=["flow-ranking"])
app.include_router(telegram_monitor.router, prefix="/api/v1", tags=["telegram-monitor"])
app.include_router(data_status.router, prefix="/api/v1/data-status", tags=["data-status"])
app.include_router(etf_rotation.router, prefix="/api/v1", tags=["etf-rotation"])
app.include_router(sector_flow.router, prefix="/api/v1", tags=["sector-flow"])
app.include_router(snapshots.router, prefix="/api/v1", tags=["snapshots"])
app.include_router(financial_statements.router, prefix="/api/v1/financial", tags=["financial-statements"])
app.include_router(telegram_ideas.router, prefix="/api/v1/telegram-ideas", tags=["telegram-ideas"])
app.include_router(pullback.router, prefix="/api/v1", tags=["pullback"])
app.include_router(stock_profile.router, prefix="/api/v1/stocks", tags=["stock-profile"])
app.include_router(mentions.router, prefix="/api/v1/mentions", tags=["mentions"])
app.include_router(trades.router, prefix="/api/v1/trades", tags=["trades"])
app.include_router(signal_scanner.router, prefix="/api/v1", tags=["signal-scanner"])
app.include_router(watchlist.router, prefix="/api/v1/watchlist", tags=["watchlist"])
app.include_router(smart_scanner.router, prefix="/api/v1", tags=["smart-scanner"])
app.include_router(stock_news.router, prefix="/api/v1", tags=["stock-news"])
app.include_router(catalyst.router, prefix="/api/v1", tags=["catalyst"])
app.include_router(theme_pulse.router, prefix="/api/v1", tags=["theme-pulse"])
app.include_router(company_profile.router, prefix="/api/v1", tags=["company-profile"])
app.include_router(recovery.router, prefix="/api/v1", tags=["recovery"])
app.include_router(dashboard_v2.router, prefix="/api/v1/dashboard/v2", tags=["dashboard-v2"])
app.include_router(market_intel.router, prefix="/api/v1/market-intel", tags=["market-intel"])
app.include_router(value_screener.router, prefix="/api/v1", tags=["value-screener"])
app.include_router(backtest.router, prefix="/api/v1", tags=["backtest"])

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/v1/features")
async def get_feature_flags():
    """피처 플래그 조회. 프론트엔드에서 UI 동적 제어에 사용."""
    return {
        "telegram": settings.telegram_feature_enabled,
        "expert": settings.expert_feature_enabled,
    }


@app.post("/api/v1/features")
async def toggle_feature_flags(body: dict):
    """피처 플래그 런타임 토글. 서버 재시작 없이 즉시 반영."""
    for key in ("telegram", "expert"):
        if key in body:
            attr = f"{key}_feature_enabled"
            setattr(settings, attr, bool(body[key]))
            logger.info(f"Feature flag toggled: {attr} = {body[key]}")
    return {
        "telegram": settings.telegram_feature_enabled,
        "expert": settings.expert_feature_enabled,
    }


@app.get("/api/v1/cache/stats")
async def cache_stats():
    """서버 사이드 캐시 통계 조회."""
    from core.cache import api_cache
    return api_cache.stats()


@app.post("/api/v1/cache/clear")
async def cache_clear():
    """서버 사이드 캐시 전체 초기화."""
    from core.cache import api_cache
    api_cache.clear()
    return {"status": "cleared"}


@app.post("/api/v1/daily-report/send")
async def send_daily_report_manual():
    """일일 리포트 수동 발송."""
    from scheduler.jobs.daily_report import send_daily_report
    try:
        await send_daily_report()
        return {"status": "sent"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/api/v1/daily-report/preview")
async def preview_daily_report():
    """일일 리포트 미리보기 (발송하지 않음)."""
    from core.database import async_session_maker
    from services.daily_report_service import DailyReportService

    async with async_session_maker() as session:
        service = DailyReportService(session)
        message = await service.generate_report()
        return {"message": message or "리포트에 포함할 데이터가 없습니다."}


@app.post("/api/v1/stock-news/collect-hot")
async def collect_hot_news_manual():
    """종목 뉴스 수동 수집 (Tier 1: 워치리스트 + 스캐너 상위)."""
    from scheduler.jobs.stock_news_collect import collect_hot_stock_news
    try:
        await collect_hot_stock_news()
        return {"status": "done"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/api/v1/stock-news/collect-all")
async def collect_all_news_manual():
    """종목 뉴스 수동 수집 (Tier 2: 테마맵 전체)."""
    from scheduler.jobs.stock_news_collect import collect_all_stock_news
    try:
        await collect_all_stock_news()
        return {"status": "done"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/api/v1/catalyst/detect")
async def detect_catalysts_manual():
    """카탈리스트 수동 감지 (3%+ 변동 + 뉴스/공시)."""
    from core.database import async_session_maker
    from services.catalyst_service import CatalystService
    try:
        async with async_session_maker() as db:
            service = CatalystService(db)
            created = await service.detect_new_catalysts()
        return {"status": "done", "created": created}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/api/v1/catalyst/update")
async def update_catalysts_manual():
    """카탈리스트 추적 수동 업데이트."""
    from core.database import async_session_maker
    from services.catalyst_service import CatalystService
    try:
        async with async_session_maker() as db:
            service = CatalystService(db)
            updated = await service.update_tracking()
        return {"status": "done", "updated": updated}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/api/v1/catalyst/backfill")
async def backfill_catalysts(days: int = 7):
    """과거 N일간 카탈리스트 백필 (뉴스 수집 + 날짜별 감지 + 추적 업데이트)."""
    from core.database import async_session_maker
    from services.catalyst_service import CatalystService
    try:
        async with async_session_maker() as db:
            service = CatalystService(db)
            result = await service.backfill(days=min(days, 30))
        return {"status": "done", **result}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/api/v1/catalyst/reclassify")
async def reclassify_catalysts():
    """catalyst_type이 'other'인 이벤트를 키워드 기반으로 재분류."""
    from core.database import async_session_maker
    from services.catalyst_service import CatalystService
    try:
        async with async_session_maker() as db:
            service = CatalystService(db)
            reclassified = await service.reclassify_other_events()
        return {"status": "done", "reclassified": reclassified}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/api/v1/scheduler/status")
async def scheduler_status():
    """스케줄러 상태 조회 (실행 이력 + catch-up 상태 포함)."""
    from scheduler.job_tracker import get_all_job_stats, catchup_status

    scheduler = get_scheduler_manager()
    job_stats = await get_all_job_stats()

    return {
        "running": scheduler.is_running,
        "jobs": scheduler.get_jobs(),
        "job_execution_stats": job_stats,
        "catchup": catchup_status,
    }
