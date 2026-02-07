"""통합 데이터 상태 스키마."""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class DataCategory(str, Enum):
    """데이터 카테고리."""
    MARKET = "market"  # 시세 데이터
    ANALYSIS = "analysis"  # 분석 데이터
    EXTERNAL = "external"  # 외부 소스
    TELEGRAM = "telegram"  # 텔레그램


class ScheduleInfo(BaseModel):
    """스케줄 정보."""
    description: str  # "매일 16:40", "6시간마다" 등
    next_run: Optional[datetime] = None  # 다음 실행 예정 시간
    is_market_hours_only: bool = False  # 장중만 실행 여부


class DataStatusItemFull(BaseModel):
    """확장된 데이터 상태 항목."""
    key: str  # 데이터 타입 키
    name: str  # 표시 이름
    category: DataCategory  # 카테고리
    last_updated: Optional[datetime] = None  # 마지막 업데이트 시간
    record_count: int = 0  # 레코드 수
    is_stale: bool = False  # 오래된 데이터 여부
    status: str = "unknown"  # ok, stale, empty, error
    schedule: ScheduleInfo  # 스케줄 정보
    can_refresh: bool = True  # 수동 새로고침 가능 여부


class AllDataStatusResponse(BaseModel):
    """전체 데이터 상태 응답 (카테고리별 그룹화)."""
    market: list[DataStatusItemFull]  # 시세 데이터
    analysis: list[DataStatusItemFull]  # 분석 데이터
    external: list[DataStatusItemFull]  # 외부 소스
    telegram: list[DataStatusItemFull]  # 텔레그램
    overall_status: str  # ok, needs_refresh, critical
    checked_at: datetime
