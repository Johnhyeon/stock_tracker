from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from typing import Annotated, List, Optional
from pydantic import BaseModel, BeforeValidator
from models.idea import IdeaType, IdeaStatus, FundamentalHealth


def _to_int(v):
    return round(v) if v is not None else None


IntMoney = Annotated[int, BeforeValidator(_to_int)]
OptIntMoney = Annotated[Optional[int], BeforeValidator(_to_int)]


class PositionBrief(BaseModel):
    id: UUID
    ticker: str
    stock_name: Optional[str] = None  # 종목명
    entry_price: IntMoney
    entry_date: Optional[date] = None  # 매수일
    quantity: int
    days_held: int
    current_price: OptIntMoney = None  # 현재가
    unrealized_profit: OptIntMoney = None  # 미실현 손익
    unrealized_return_pct: Optional[float] = None  # 미실현 수익률

    class Config:
        from_attributes = True


class IdeaSummary(BaseModel):
    id: UUID
    type: IdeaType
    sector: Optional[str]
    tickers: List[str]
    thesis: str
    status: IdeaStatus
    fundamental_health: FundamentalHealth
    expected_timeframe_days: int
    target_return_pct: Decimal
    created_at: datetime
    positions: List[PositionBrief]
    total_invested: IntMoney
    total_unrealized_return_pct: Optional[float]
    days_active: int
    time_remaining_days: int

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_ideas: int
    active_ideas: int
    watching_ideas: int
    research_ideas: int
    chart_ideas: int
    total_invested: IntMoney
    total_unrealized_return: IntMoney
    avg_return_pct: Optional[float]


class DashboardResponse(BaseModel):
    stats: DashboardStats
    research_ideas: List[IdeaSummary]
    chart_ideas: List[IdeaSummary]
    watching_ideas: List[IdeaSummary]
