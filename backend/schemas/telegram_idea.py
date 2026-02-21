"""텔레그램 아이디어 스키마."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TelegramIdeaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    channel_id: int
    channel_name: str
    source_type: str
    message_id: int
    message_text: str
    original_date: datetime
    is_forwarded: bool
    forward_from_name: Optional[str] = None
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None


class TelegramIdeaListResponse(BaseModel):
    items: list[TelegramIdeaResponse]
    total: int
    offset: int
    limit: int


class StockMentionStats(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    mention_count: int
    latest_date: Optional[datetime] = None
    sources: Optional[list[str]] = None


class StockStatsResponse(BaseModel):
    stocks: list[StockMentionStats]
    total_count: int


class TopStockItem(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    count: int


class AuthorStats(BaseModel):
    name: str
    idea_count: int
    top_stocks: Optional[list[TopStockItem]] = None
    latest_idea_date: Optional[datetime] = None


class AuthorStatsResponse(BaseModel):
    authors: list[AuthorStats]
    total_count: int


class TraderPick(BaseModel):
    stock_code: str
    stock_name: str
    return_pct: float
    mention_date: str


class TraderRankingItem(BaseModel):
    rank: int
    name: str
    idea_count: int
    avg_return_pct: float
    win_rate: float
    total_return_pct: float
    best_pick: Optional[TraderPick] = None
    worst_pick: Optional[TraderPick] = None
    picks: list[TraderPick] = []


class TraderRankingResponse(BaseModel):
    traders: list[TraderRankingItem]
    total_traders: int
    analysis_period_days: int
    min_mentions: int


class CollectResult(BaseModel):
    channel_name: str
    messages_collected: int
    ideas_created: int
    errors: list[str]


class CollectResponse(BaseModel):
    results: list[CollectResult]
    total_messages: int
    total_ideas: int
