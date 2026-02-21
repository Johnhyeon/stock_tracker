"""종목 프로필 스키마."""
from typing import Optional
from pydantic import BaseModel


class StockInfo(BaseModel):
    code: str
    name: str
    market: Optional[str] = None


class OHLCVSummary(BaseModel):
    has_data: bool
    latest_price: Optional[int] = None
    change_rate: Optional[float] = None
    volume: Optional[int] = None
    trade_date: Optional[str] = None
    data_count: Optional[int] = None


class FlowSummary(BaseModel):
    has_data: bool
    days: Optional[int] = None
    foreign_net_total: Optional[int] = None
    institution_net_total: Optional[int] = None
    consecutive_foreign_buy: Optional[int] = None
    latest_date: Optional[str] = None


class YoutubeMentionSummary(BaseModel):
    video_count: int = 0
    period_days: int = 14
    is_trending: bool = False


class ExpertMentionSummary(BaseModel):
    mention_count: int = 0
    total_mentions: int = 0
    period_days: int = 14


class DisclosureItem(BaseModel):
    title: Optional[str] = None
    date: Optional[str] = None
    type: Optional[str] = None


class TelegramIdeaItem(BaseModel):
    message_text: str = ""
    author: Optional[str] = None
    date: Optional[str] = None
    source_type: Optional[str] = None


class SentimentSummary(BaseModel):
    analysis_count: int = 0
    avg_score: float = 0.0
    period_days: int = 14


class ChartPatternItem(BaseModel):
    pattern_type: Optional[str] = None
    confidence: Optional[float] = None
    analysis_date: Optional[str] = None


class StockProfileResponse(BaseModel):
    stock_code: str
    stock_info: Optional[StockInfo] = None
    ohlcv: OHLCVSummary
    investor_flow: FlowSummary
    youtube_mentions: YoutubeMentionSummary
    expert_mentions: ExpertMentionSummary
    disclosures: list[DisclosureItem] = []
    telegram_ideas: list[TelegramIdeaItem] = []
    sentiment: SentimentSummary
    chart_patterns: list[ChartPatternItem] = []
    themes: list[str] = []


class TrendingMentionItem(BaseModel):
    stock_code: str
    stock_name: str = ""
    youtube_count: int = 0
    expert_count: int = 0
    telegram_count: int = 0
    total_mentions: int = 0
    source_count: int = 0
