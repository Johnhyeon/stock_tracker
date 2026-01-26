from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class PositionCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    entry_price: Decimal = Field(gt=0)
    quantity: int = Field(gt=0)
    entry_date: Optional[date] = None
    strategy_params: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class PositionExit(BaseModel):
    exit_price: Decimal = Field(gt=0)
    exit_date: Optional[date] = None
    exit_reason: Optional[str] = Field(default=None, max_length=50)


class PositionAddBuy(BaseModel):
    """추가매수"""
    price: Decimal = Field(gt=0, description="추가 매수가")
    quantity: int = Field(gt=0, description="추가 매수 수량")
    buy_date: Optional[date] = None


class PositionPartialExit(BaseModel):
    """부분매도"""
    exit_price: Decimal = Field(gt=0, description="매도가")
    quantity: int = Field(gt=0, description="매도 수량")
    exit_date: Optional[date] = None
    exit_reason: Optional[str] = Field(default=None, max_length=50)


class PositionResponse(BaseModel):
    id: UUID
    idea_id: UUID
    ticker: str
    entry_price: Decimal
    entry_date: date
    quantity: int
    exit_price: Optional[Decimal]
    exit_date: Optional[date]
    exit_reason: Optional[str]
    days_held: int
    is_open: bool
    realized_return_pct: Optional[float]
    strategy_params: Optional[Dict[str, Any]]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
