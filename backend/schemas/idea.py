from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from models.idea import IdeaType, IdeaStatus, FundamentalHealth


class IdeaCreate(BaseModel):
    type: IdeaType
    sector: Optional[str] = None
    tickers: List[str] = Field(default_factory=list)
    thesis: str
    expected_timeframe_days: int = Field(gt=0)
    target_return_pct: Decimal = Field(ge=0)
    tags: Optional[List[str]] = None
    metadata_: Optional[Dict[str, Any]] = Field(default=None, alias="metadata")
    created_at: Optional[datetime] = None  # 과거 날짜로 생성 시 사용

    class Config:
        populate_by_name = True


class IdeaUpdate(BaseModel):
    sector: Optional[str] = None
    tickers: Optional[List[str]] = None
    thesis: Optional[str] = None
    expected_timeframe_days: Optional[int] = Field(default=None, gt=0)
    target_return_pct: Optional[Decimal] = Field(default=None, ge=0)
    status: Optional[IdeaStatus] = None
    fundamental_health: Optional[FundamentalHealth] = None
    tags: Optional[List[str]] = None
    metadata_: Optional[Dict[str, Any]] = Field(default=None, alias="metadata")

    class Config:
        populate_by_name = True


class IdeaResponse(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    type: IdeaType
    sector: Optional[str]
    tickers: List[str]
    thesis: str
    expected_timeframe_days: int
    target_return_pct: Decimal
    status: IdeaStatus
    fundamental_health: FundamentalHealth
    tags: Optional[List[str]]
    metadata_: Optional[Dict[str, Any]] = Field(default=None, serialization_alias="metadata")

    class Config:
        from_attributes = True
        populate_by_name = True


class PositionSummary(BaseModel):
    id: UUID
    ticker: str
    stock_name: Optional[str] = None
    entry_price: Decimal
    entry_date: Optional[date] = None
    quantity: int
    exit_price: Optional[Decimal] = None
    exit_date: Optional[date] = None
    exit_reason: Optional[str] = None
    days_held: int
    is_open: bool
    current_price: Optional[Decimal] = None
    unrealized_profit: Optional[float] = None
    unrealized_return_pct: Optional[float] = None
    realized_return_pct: Optional[float] = None

    class Config:
        from_attributes = True


class IdeaWithPositions(IdeaResponse):
    positions: List[PositionSummary] = Field(default_factory=list)
    total_invested: Optional[Decimal] = None
    total_return_pct: Optional[float] = None


class ExitCheckResult(BaseModel):
    should_exit: bool
    reasons: Dict[str, bool]
    warnings: List[str]
    fomo_stats: Optional[Dict[str, Any]] = None
