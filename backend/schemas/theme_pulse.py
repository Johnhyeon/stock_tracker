"""테마 펄스 API 스키마."""

from pydantic import BaseModel
from typing import Optional


class TopStock(BaseModel):
    code: str
    name: str
    news_count: int


class ThemePulseItem(BaseModel):
    rank: int
    theme_name: str
    news_count: int
    high_importance_count: int
    momentum: float
    catalyst_types: dict[str, int]
    top_stocks: list[TopStock]
    setup_score: float = 0.0
    setup_rank: Optional[int] = None


class ThemePulseResponse(BaseModel):
    items: list[ThemePulseItem]
    total_themes: int
    total_news: int
    period_days: int
    generated_at: str


class TimelineDataPoint(BaseModel):
    date: str
    count: int


class TimelineTheme(BaseModel):
    name: str
    data: list[TimelineDataPoint]


class TimelineResponse(BaseModel):
    dates: list[str]
    themes: list[TimelineTheme]
    generated_at: str


class CatalystDistItem(BaseModel):
    type: str
    count: int
    ratio: float


class ImportanceDistItem(BaseModel):
    level: str
    count: int
    ratio: float


class CatalystDistributionResponse(BaseModel):
    catalyst_distribution: list[CatalystDistItem]
    importance_distribution: list[ImportanceDistItem]
    total_news: int
    period_days: int
    generated_at: str
