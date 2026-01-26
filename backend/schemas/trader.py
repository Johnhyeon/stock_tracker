"""트레이더 관심종목 스키마."""
from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class TraderMentionResponse(BaseModel):
    """트레이더 언급 응답."""
    id: UUID
    created_at: datetime
    stock_name: str
    stock_code: Optional[str]
    mention_date: date
    change_rate: Optional[float]
    source_link: Optional[str]
    mention_price: Optional[int]
    current_price: Optional[int]
    performance: Optional[float]

    class Config:
        from_attributes = True


class TraderMentionListResponse(BaseModel):
    """트레이더 언급 목록 응답."""
    items: list[TraderMentionResponse]
    total: int


class TraderHotStock(BaseModel):
    """핫 종목 (트레이더 관심종목)."""
    stock_name: str
    stock_code: Optional[str]
    mention_count: int              # 최근 언급 횟수
    first_mention_date: date        # 첫 언급일
    last_mention_date: date         # 최근 언급일
    is_new: bool = False            # 신규 등장 여부

    # KIS API 데이터
    current_price: Optional[int] = None
    price_change: Optional[int] = None
    price_change_rate: Optional[float] = None
    volume: Optional[int] = None

    # 성과
    avg_mention_change: Optional[float] = None  # 언급일 평균 등락률
    performance_since_first: Optional[float] = None  # 첫 언급 대비 성과

    # 가중치 점수
    weighted_score: Optional[float] = None


class TraderRisingStock(BaseModel):
    """급상승 종목 (언급 증가)."""
    stock_name: str
    stock_code: Optional[str]
    recent_mentions: int            # 최근 기간 언급
    prev_mentions: int              # 이전 기간 언급
    growth_rate: float              # 증가율
    is_new: bool = False

    # KIS API 데이터
    current_price: Optional[int] = None
    price_change_rate: Optional[float] = None
    volume: Optional[int] = None

    weighted_score: Optional[float] = None


class TraderPerformanceStats(BaseModel):
    """트레이더 성과 통계."""
    total_stocks: int               # 분석 종목 수
    avg_performance: float          # 평균 성과
    win_rate: float                 # 승률 (수익 종목 비율)
    best_stock: Optional[str]       # 최고 수익 종목
    best_performance: Optional[float]
    worst_stock: Optional[str]      # 최저 수익 종목
    worst_performance: Optional[float]

    # 기간별 성과
    performance_1d: Optional[float] = None  # 1일 후 평균 성과
    performance_3d: Optional[float] = None  # 3일 후
    performance_7d: Optional[float] = None  # 7일 후
    performance_14d: Optional[float] = None # 14일 후


class SyncRequest(BaseModel):
    """동기화 요청."""
    file_path: str = "/home/hyeon/project/88_bot/mentions.json"


class SyncResponse(BaseModel):
    """동기화 응답."""
    total_stocks: int
    total_mentions: int
    new_mentions: int
    updated_stocks: int
