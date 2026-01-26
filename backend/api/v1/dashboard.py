from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from schemas import DashboardResponse
from services import IdeaService

router = APIRouter()


@router.get("", response_model=DashboardResponse)
async def get_dashboard(db: Session = Depends(get_db)):
    service = IdeaService(db)
    return await service.get_dashboard_data_async()
