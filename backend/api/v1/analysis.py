from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from schemas import TimelineAnalysis, FomoAnalysis
from services import AnalysisService

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
