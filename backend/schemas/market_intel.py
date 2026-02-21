"""시장 인텔리전스 스키마 - 통합 시그널 피드."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class IntelFeedItem(BaseModel):
    signal_type: str  # catalyst | flow_spike | chart_pattern | emerging_theme | youtube | convergence | telegram
    severity: str  # critical | high | medium | info
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    title: str
    description: str = ""
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class IntelSummary(BaseModel):
    catalyst: int = 0
    flow_spike: int = 0
    chart_pattern: int = 0
    emerging_theme: int = 0
    youtube: int = 0
    convergence: int = 0
    telegram: int = 0
    total: int = 0
    critical_count: int = 0
    high_count: int = 0


class MarketIntelResponse(BaseModel):
    feed: List[IntelFeedItem]
    summary: IntelSummary
    generated_at: str
