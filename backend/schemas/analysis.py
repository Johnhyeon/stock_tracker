from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from models.idea import IdeaType


class TimelineEntry(BaseModel):
    idea_id: UUID
    idea_type: IdeaType
    ticker: str
    entry_date: date
    exit_date: Optional[date]
    days_held: int
    expected_days: int
    time_diff_days: int
    return_pct: Optional[float]
    exit_reason: Optional[str]


class TimelineAnalysis(BaseModel):
    entries: List[TimelineEntry]
    avg_time_diff: float
    early_exits: int
    on_time_exits: int
    late_exits: int


class FomoExit(BaseModel):
    idea_id: UUID
    ticker: str
    exit_date: date
    exit_return_pct: float
    days_after_exit: int
    price_after_exit: Optional[Decimal]
    missed_return_pct: Optional[float]


class FomoAnalysis(BaseModel):
    fomo_exits: List[FomoExit]
    total_fomo_exits: int
    avg_missed_return_pct: Optional[float]
    total_missed_opportunity: Optional[Decimal]
    summary: Dict[str, Any]
