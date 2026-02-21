"""전문가 관심종목 스키마."""
from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class ExpertMentionResponse(BaseModel):
    """전문가 언급 응답."""
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


class ExpertMentionListResponse(BaseModel):
    """전문가 언급 목록 응답."""
    items: list[ExpertMentionResponse]
    total: int


class ExpertHotStock(BaseModel):
    """핫 종목 (전문가 관심종목)."""
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


class ExpertRisingStock(BaseModel):
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


class ExpertPerformanceStats(BaseModel):
    """전문가 성과 통계."""
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


class ExpertPerformanceDetail(BaseModel):
    """전문가 성과 상세 (종목별)."""
    stock_name: str
    stock_code: str
    mention_date: date                          # 첫 언급일
    mention_price: int                          # 첫 언급일 종가 (매수가)
    current_price: int                          # 최신 종가 (현재가)
    return_rate: float                          # 수익률 (%)
    return_1d: Optional[float] = None           # 1일 후 수익률
    return_3d: Optional[float] = None           # 3일 후 수익률
    return_7d: Optional[float] = None           # 7일 후 수익률
    return_14d: Optional[float] = None          # 14일 후 수익률
    mention_count: int = 1                      # 기간 내 언급 횟수
    rank: int = 0                               # 수익률 순위


class ExpertPerformanceSummary(BaseModel):
    """전문가 성과 요약."""
    total: int
    avg_return: float
    win_rate: float
    median_return: float


class ExpertPerformanceDetailResponse(BaseModel):
    """전문가 성과 상세 응답."""
    items: list[ExpertPerformanceDetail]
    summary: ExpertPerformanceSummary


class SyncRequest(BaseModel):
    """동기화 요청."""
    file_path: str = ""


class SyncResponse(BaseModel):
    """동기화 응답."""
    total_stocks: int
    total_mentions: int
    new_mentions: int
    updated_stocks: int
