"""테마 셋업 스키마."""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class TopStockItem(BaseModel):
    """상위 패턴 종목."""
    code: str
    name: str
    pattern: str
    confidence: int


class ScoreBreakdownNews(BaseModel):
    """뉴스 점수 상세."""
    score: float
    count_7d: Optional[int] = None
    wow_change: Optional[int] = None
    source_diversity: Optional[float] = None


class ScoreBreakdownChart(BaseModel):
    """차트 패턴 점수 상세."""
    score: float
    pattern_ratio: Optional[float] = None
    avg_confidence: Optional[float] = None
    patterns: Optional[list[str]] = None
    pattern_count: Optional[int] = None
    total_stocks: Optional[int] = None


class ScoreBreakdownMention(BaseModel):
    """언급 점수 상세."""
    score: float
    youtube_count: Optional[int] = None
    trader_count: Optional[int] = None


class ScoreBreakdownPrice(BaseModel):
    """가격 액션 점수 상세."""
    score: float
    avg_change: Optional[float] = None
    volume_change: Optional[float] = None


class ScoreBreakdownFlow(BaseModel):
    """수급 점수 상세."""
    score: float
    foreign_net_sum: Optional[int] = None
    institution_net_sum: Optional[int] = None
    positive_foreign: Optional[int] = None
    positive_institution: Optional[int] = None
    total_stocks: Optional[int] = None
    avg_flow_score: Optional[float] = None


class ScoreBreakdown(BaseModel):
    """점수 상세 breakdown."""
    news: Optional[dict] = None
    chart: Optional[dict] = None
    mention: Optional[dict] = None
    price: Optional[dict] = None
    flow: Optional[dict] = None


class ThemeSetupResponse(BaseModel):
    """테마 셋업 응답."""
    theme_name: str
    rank: int
    total_score: float
    news_momentum_score: float
    chart_pattern_score: float
    mention_score: float
    price_action_score: float
    investor_flow_score: float = 0.0
    top_stocks: list[dict]
    stocks_with_pattern: int
    total_stocks: int
    is_emerging: int
    score_breakdown: Optional[dict] = None
    explanation: Optional[str] = None  # 점수 산출 이유 한글 설명


class ThemeSetupDetailResponse(BaseModel):
    """테마 셋업 상세 응답."""
    theme_name: str
    rank: int
    total_score: float
    news_momentum_score: float
    chart_pattern_score: float
    mention_score: float
    price_action_score: float
    investor_flow_score: float = 0.0
    score_breakdown: Optional[dict] = None
    top_stocks: list[dict]
    stocks_with_pattern: int
    total_stocks: int
    is_emerging: int
    setup_date: str
    history: list[dict]


class ChartPatternResponse(BaseModel):
    """차트 패턴 응답."""
    stock_code: str
    stock_name: str
    pattern_type: str
    confidence: int
    pattern_data: dict
    current_price: int
    price_from_support_pct: Optional[float] = None
    price_from_resistance_pct: Optional[float] = None


class NewsTrendResponse(BaseModel):
    """뉴스 추이 응답."""
    date: str
    mention_count: int
    unique_sources: int
    top_keywords: list[dict]
    wow_change_pct: Optional[int] = None


class EmergingThemesResponse(BaseModel):
    """이머징 테마 목록 응답."""
    themes: list[ThemeSetupResponse]
    total_count: int
    generated_at: str


class ThemeSetupCalculateRequest(BaseModel):
    """셋업 계산 요청."""
    theme_names: Optional[list[str]] = None  # None이면 전체


class ThemeSetupCalculateResponse(BaseModel):
    """셋업 계산 응답."""
    calculated_count: int
    emerging_count: int
    timestamp: str
