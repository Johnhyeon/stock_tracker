"""테마 관련 스키마."""
from typing import Optional
from pydantic import BaseModel


class ThemeStock(BaseModel):
    """테마 내 종목."""
    code: str
    name: Optional[str] = None
    source: Optional[str] = None  # youtube, expert, both
    mentions: int = 0
    price_change: Optional[float] = None
    volume: Optional[int] = None


class HotTheme(BaseModel):
    """핫 테마."""
    theme_name: str
    total_score: float
    stock_count: int
    youtube_mentions: int
    expert_mentions: int
    avg_price_change: float
    total_volume: int
    stocks: list[ThemeStock]


class ThemeCategory(BaseModel):
    """테마 카테고리."""
    name: str
    themes: list[HotTheme]


class ThemeSummary(BaseModel):
    """테마 분석 요약."""
    total_themes_detected: int
    top_theme: Optional[str]
    avg_theme_score: float


class ThemeRotationResponse(BaseModel):
    """테마 순환매 분석 응답."""
    hot_themes: list[HotTheme]
    theme_count: int
    categories: dict[str, list[HotTheme]]
    analyzed_at: str
    summary: ThemeSummary


class ThemeListItem(BaseModel):
    """테마 목록 아이템."""
    name: str
    stock_count: int


class ThemeSearchResult(BaseModel):
    """테마 검색 결과."""
    name: str
    stock_count: int
    stocks: list[dict]


class ThemeHistoryItem(BaseModel):
    """테마 히스토리 아이템."""
    date: str
    stock_count: int
    total_mentions: int
