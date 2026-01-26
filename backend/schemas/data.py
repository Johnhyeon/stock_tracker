"""데이터 API 스키마."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class PriceResponse(BaseModel):
    """현재가 응답."""
    stock_code: str
    stock_name: str
    current_price: Decimal
    change: Decimal
    change_rate: Decimal
    volume: int
    high_price: Decimal
    low_price: Decimal
    open_price: Decimal
    prev_close: Decimal
    market_cap: Optional[int] = None
    updated_at: str


class OHLCVItem(BaseModel):
    """OHLCV 데이터."""
    date: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    change: Optional[Decimal] = None
    change_rate: Optional[Decimal] = None


class OHLCVResponse(BaseModel):
    """OHLCV 응답."""
    stock_code: str
    period: str = Field(description="D: 일봉, W: 주봉, M: 월봉")
    data: list[OHLCVItem]


class MultiplePriceRequest(BaseModel):
    """복수 종목 가격 요청."""
    stock_codes: list[str] = Field(..., min_length=1, max_length=20)


class SchedulerStatusResponse(BaseModel):
    """스케줄러 상태."""
    running: bool
    jobs: list[dict]
