"""관심종목 스키마."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WatchlistToggleRequest(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    group_id: Optional[int] = None


class WatchlistToggleResponse(BaseModel):
    stock_code: str
    is_watched: bool


class WatchlistItemResponse(BaseModel):
    id: int
    stock_code: str
    stock_name: Optional[str] = None
    memo: Optional[str] = None
    group_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WatchlistGroupCreate(BaseModel):
    name: str
    color: Optional[str] = "#6366f1"


class WatchlistGroupUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


class WatchlistGroupResponse(BaseModel):
    id: int
    name: str
    color: Optional[str] = None
    order: int
    created_at: datetime

    class Config:
        from_attributes = True


class WatchlistMoveRequest(BaseModel):
    stock_codes: list[str]
    group_id: Optional[int] = None  # None means ungroup


class WatchlistGroupReorderRequest(BaseModel):
    group_ids: list[int]  # ordered list of group IDs
