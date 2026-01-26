import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from core.config import get_settings
from core.database import engine, Base
from api.v1 import ideas, positions, positions_bulk, dashboard, analysis, uploads, stocks, data, disclosures, youtube, health, alerts, traders, themes, theme_setup, flow_ranking, telegram_monitor, data_status, etf_rotation, sector_flow
from scheduler import get_scheduler_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Base.metadata.create_all(bind=engine)

    # Start scheduler
    scheduler = get_scheduler_manager()
    scheduler.start()
    logger.info("Application started")

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
app.include_router(traders.router, prefix="/api/v1/traders", tags=["traders"])
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

UPLOAD_DIR = Path("/home/hyeon/project/my_stock/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/v1/scheduler/status")
async def scheduler_status():
    """스케줄러 상태 조회."""
    scheduler = get_scheduler_manager()
    return {
        "running": scheduler.is_running,
        "jobs": scheduler.get_jobs(),
    }
