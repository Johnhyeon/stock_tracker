"""YouTube 스키마."""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class YouTubeMentionResponse(BaseModel):
    """YouTube 언급 응답."""
    id: UUID
    created_at: datetime
    video_id: str
    video_title: str
    channel_id: str
    channel_name: Optional[str]
    published_at: datetime
    view_count: Optional[int]
    like_count: Optional[int]
    comment_count: Optional[int]
    duration: Optional[str]
    mentioned_tickers: list[str]
    ticker_context: Optional[str]
    thumbnail_url: Optional[str]

    class Config:
        from_attributes = True


class YouTubeMentionListResponse(BaseModel):
    """YouTube 언급 목록 응답."""
    items: list[YouTubeMentionResponse]
    total: int
    skip: int
    limit: int


class TrendingTickerResponse(BaseModel):
    """트렌딩 종목 응답."""
    stock_code: str
    stock_name: Optional[str]
    mention_count: int
    total_views: int


class TickerMentionHistoryItem(BaseModel):
    """종목 언급 히스토리 항목."""
    date: str
    mention_count: int
    total_views: int


class YouTubeCollectRequest(BaseModel):
    """YouTube 수집 요청."""
    hours_back: int = 24


class HotCollectRequest(BaseModel):
    """핫 영상 수집 요청."""
    hours_back: int = 48
    mode: str = "normal"  # "quick", "normal", "full"


class YouTubeCollectResponse(BaseModel):
    """YouTube 수집 응답."""
    collected: int
    new: int
    with_mentions: int
    tickers_searched: list[str] = []


class HotCollectResponse(BaseModel):
    """핫 영상 수집 응답."""
    collected: int
    new: int
    with_mentions: int
    tickers_found: list[str] = []
    mode: str = "normal"


class RisingTickerResponse(BaseModel):
    """급상승 종목 응답."""
    stock_code: str
    stock_name: Optional[str]
    recent_mentions: int
    prev_mentions: int
    growth_rate: float  # 언급 증가율 (%)
    total_views: int
    is_new: bool = False
    # KIS API 데이터
    current_price: Optional[int] = None
    price_change: Optional[int] = None
    price_change_rate: Optional[float] = None  # 등락률 (%)
    volume: Optional[int] = None
    volume_ratio: Optional[float] = None  # 거래량 비율 (평균 대비)
    # 가중치 점수
    weighted_score: Optional[float] = None  # 종합 점수


# ===== 미디어 타임라인 =====

class MediaTimelineDay(BaseModel):
    date: str
    close_price: Optional[int] = None
    mention_count: int
    total_views: int


class MediaTimelineVideo(BaseModel):
    video_id: str
    video_title: str
    channel_name: Optional[str] = None
    published_at: str
    view_count: Optional[int] = None
    thumbnail_url: Optional[str] = None


class MediaTimelineSummary(BaseModel):
    total_mentions: int
    mention_days: int
    avg_daily: float
    price_at_first_mention: Optional[int] = None
    price_now: Optional[int] = None
    price_change_pct: Optional[float] = None


class MediaTimelineResponse(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    daily: list[MediaTimelineDay]
    videos: list[MediaTimelineVideo]
    summary: MediaTimelineSummary


# ===== 언급 백테스트 =====

class MentionBacktestItem(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    signal_date: str
    mention_count: int
    entry_price: int
    returns: dict[str, Optional[float]]  # {"3d": 2.5, "7d": -1.3, ...}


class HoldingPeriodStats(BaseModel):
    sample_count: int
    avg_return: float
    median: float
    win_rate: float
    max_return: float
    max_loss: float


class MentionBacktestResponse(BaseModel):
    params: dict
    total_signals: int
    holding_stats: dict[str, HoldingPeriodStats]
    items: list[MentionBacktestItem]
    summary: dict


# ===== 과열 경고 =====

class OverheatStock(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    status: str  # OVERHEAT, FRENZY, CONTRARIAN, COOLING, NORMAL
    recent_mentions: int
    baseline_avg_daily: float
    overheat_ratio: float
    price_change_pct: Optional[float] = None
    mention_count_total: int
    recent_videos_count: int


class OverheatSummary(BaseModel):
    total: int
    overheat_count: int
    frenzy_count: int
    contrarian_count: int
    cooling_count: int


class OverheatResponse(BaseModel):
    items: list[OverheatStock]
    summary: OverheatSummary
