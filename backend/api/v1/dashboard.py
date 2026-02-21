from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from core.cache import api_cache
from schemas import DashboardResponse
from services import IdeaService

router = APIRouter()

DASHBOARD_CACHE_TTL = 30  # 30초


@router.get("", response_model=DashboardResponse)
async def get_dashboard(db: Session = Depends(get_db)):
    cached = api_cache.get("dashboard")
    if cached:
        return cached

    service = IdeaService(db)
    result = await service.get_dashboard_data_async()
    api_cache.set("dashboard", result, ttl=DASHBOARD_CACHE_TTL)
    return result
