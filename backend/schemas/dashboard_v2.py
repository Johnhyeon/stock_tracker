"""대시보드 V2 스키마 - 포트폴리오 중심 통합 대시보드."""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, List, Optional
from uuid import UUID

from pydantic import BaseModel, BeforeValidator

from models.idea import IdeaType, IdeaStatus, FundamentalHealth


def _to_int(v):
    return round(v) if v is not None else None


IntMoney = Annotated[int, BeforeValidator(_to_int)]
OptIntMoney = Annotated[Optional[int], BeforeValidator(_to_int)]


class SmartScoreBadge(BaseModel):
    composite_score: float = 0.0
    composite_grade: str = "D"
    chart_grade: str = "D"
    narrative_grade: str = "D"
    flow_grade: str = "D"
    social_grade: str = "D"


class PortfolioPosition(BaseModel):
    id: UUID
    ticker: str
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    entry_price: IntMoney
    entry_date: Optional[date] = None
    quantity: int
    days_held: int
    current_price: OptIntMoney = None
    unrealized_profit: OptIntMoney = None
    unrealized_return_pct: Optional[float] = None
    invested: OptIntMoney = None
    smart_score: Optional[SmartScoreBadge] = None
    price_trend_7d: List[int] = []

    class Config:
        from_attributes = True


class PortfolioIdea(BaseModel):
    id: UUID
    type: IdeaType
    sector: Optional[str] = None
    tickers: List[str]
    thesis: str
    status: IdeaStatus
    fundamental_health: FundamentalHealth
    expected_timeframe_days: int
    target_return_pct: Decimal
    created_at: datetime
    positions: List[PortfolioPosition]
    total_invested: IntMoney
    total_eval: OptIntMoney = None
    total_unrealized_profit: OptIntMoney = None
    total_unrealized_return_pct: Optional[float] = None
    days_active: int
    time_remaining_days: int

    class Config:
        from_attributes = True


class PortfolioTrendPoint(BaseModel):
    date: date
    total_invested: int
    total_eval: int
    unrealized_profit: int
    return_pct: float


class PerformerInfo(BaseModel):
    stock_code: str
    stock_name: str
    return_pct: float


class PortfolioStats(BaseModel):
    total_ideas: int
    active_ideas: int
    watching_ideas: int
    total_invested: IntMoney
    total_eval: OptIntMoney = None
    total_unrealized_profit: OptIntMoney = None
    total_return_pct: Optional[float] = None
    avg_return_pct: Optional[float] = None
    best_performer: Optional[PerformerInfo] = None
    worst_performer: Optional[PerformerInfo] = None


class PortfolioDashboardResponse(BaseModel):
    stats: PortfolioStats
    active_ideas: List[PortfolioIdea]
    watching_ideas: List[PortfolioIdea]
    portfolio_trend: List[PortfolioTrendPoint]
