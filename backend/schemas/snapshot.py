from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from typing import Optional, Dict, Any
from pydantic import BaseModel


class SnapshotCreate(BaseModel):
    snapshot_date: Optional[date] = None
    price_data: Optional[Dict[str, Any]] = None
    days_held: Optional[int] = None
    unrealized_return_pct: Optional[Decimal] = None
    news_sentiment: Optional[Dict[str, Any]] = None
    chart_signals: Optional[Dict[str, Any]] = None
    plugin_data: Optional[Dict[str, Any]] = None


class SnapshotResponse(BaseModel):
    id: UUID
    idea_id: UUID
    snapshot_date: date
    price_data: Optional[Dict[str, Any]]
    days_held: Optional[int]
    unrealized_return_pct: Optional[Decimal]
    news_sentiment: Optional[Dict[str, Any]]
    chart_signals: Optional[Dict[str, Any]]
    plugin_data: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True
