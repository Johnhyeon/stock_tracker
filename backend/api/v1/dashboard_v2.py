from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.cache import api_cache
from schemas.dashboard_v2 import PortfolioDashboardResponse
from services.dashboard_v2_service import DashboardV2Service

router = APIRouter()

DASHBOARD_V2_CACHE_TTL = 30


@router.get("", response_model=PortfolioDashboardResponse)
async def get_dashboard_v2(db: Session = Depends(get_db)):
    cached = api_cache.get("dashboard_v2")
    if cached:
        return cached

    service = DashboardV2Service(db)
    result = await service.get_portfolio_dashboard()
    api_cache.set("dashboard_v2", result, ttl=DASHBOARD_V2_CACHE_TTL)
    return result
