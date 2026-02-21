from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from typing import Annotated, Optional, Dict, Any
from pydantic import BaseModel, BeforeValidator, Field


def _to_int(v):
    return round(v) if v is not None else None


IntMoney = Annotated[int, BeforeValidator(_to_int)]
OptIntMoney = Annotated[Optional[int], BeforeValidator(_to_int)]


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


class PositionUpdate(BaseModel):
    """포지션 수정 (부분 업데이트)"""
    entry_price: Optional[Decimal] = Field(default=None, gt=0)
    quantity: Optional[int] = Field(default=None, gt=0)
    entry_date: Optional[date] = None
    exit_price: Optional[Decimal] = Field(default=None, gt=0)
    exit_date: Optional[date] = None
    exit_reason: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = None


class TradeUpdate(BaseModel):
    """매매 기록 수정"""
    price: Optional[Decimal] = Field(default=None, gt=0)
    quantity: Optional[int] = Field(default=None, gt=0)
    trade_date: Optional[date] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


class PositionResponse(BaseModel):
    id: UUID
    idea_id: UUID
    ticker: str
    entry_price: IntMoney
    entry_date: date
    quantity: int
    exit_price: OptIntMoney = None
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
