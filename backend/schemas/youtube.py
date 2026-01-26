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
