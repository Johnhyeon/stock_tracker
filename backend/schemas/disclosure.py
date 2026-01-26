"""공시 스키마."""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from models.disclosure import DisclosureType, DisclosureImportance


class DisclosureResponse(BaseModel):
    """공시 응답."""
    id: UUID
    created_at: datetime
    rcept_no: str
    rcept_dt: str
    corp_code: str
    corp_name: str
    stock_code: Optional[str]
    report_nm: str
    flr_nm: Optional[str]
    disclosure_type: DisclosureType
    importance: DisclosureImportance
    summary: Optional[str]
    is_read: bool
    url: Optional[str]

    class Config:
        from_attributes = True


class DisclosureListResponse(BaseModel):
    """공시 목록 응답."""
    items: list[DisclosureResponse]
    total: int
    skip: int
    limit: int


class DisclosureCollectRequest(BaseModel):
    """공시 수집 요청."""
    bgn_de: Optional[str] = None
    end_de: Optional[str] = None
    stock_codes: Optional[list[str]] = None
    min_importance: DisclosureImportance = DisclosureImportance.MEDIUM


class DisclosureCollectResponse(BaseModel):
    """공시 수집 응답."""
    collected: int
    new: int
    skipped: int


class DisclosureStatsResponse(BaseModel):
    """공시 통계 응답."""
    total: int
    unread: int
    by_importance: dict[str, int]
    by_type: dict[str, int]
