"""Smart Scanner 스키마 - 4차원 복합 점수 기반 교차검증."""
from typing import Optional

from pydantic import BaseModel


class SmartSignalDimension(BaseModel):
    score: float = 0.0
    max_score: float = 0.0
    grade: str = "D"
    details: dict = {}


class SmartScannerStock(BaseModel):
    stock_code: str
    stock_name: str
    themes: list[str] = []
    current_price: int = 0

    # 복합 점수
    composite_score: float = 0.0
    composite_grade: str = "D"

    # 4차원 점수
    chart: SmartSignalDimension = SmartSignalDimension()
    narrative: SmartSignalDimension = SmartSignalDimension()
    flow: SmartSignalDimension = SmartSignalDimension()
    social: SmartSignalDimension = SmartSignalDimension()

    # 시그널 정보
    signal_type: Optional[str] = None
    aligned_count: int = 0  # 50% 이상 득점 차원 수

    # 표시용 주요 데이터
    expert_mention_count: int = 0
    youtube_count: int = 0
    telegram_count: int = 0
    news_count_7d: int = 0
    disclosure_count_30d: int = 0
    foreign_net_5d: int = 0
    institution_net_5d: int = 0
    consecutive_foreign_buy: int = 0
    sentiment_avg: float = 0.0

    # 차트 부가 정보
    change_rate: Optional[float] = None
    volume_ratio: Optional[float] = None
    ma20_distance_pct: Optional[float] = None


class SmartScannerResponse(BaseModel):
    stocks: list[SmartScannerStock]
    count: int
    summary: dict = {}
    generated_at: str


class NarrativeBriefingResponse(BaseModel):
    stock_code: str
    stock_name: str
    one_liner: str = ""
    why_moving: str = ""
    theme_context: str = ""
    expert_perspective: str = ""
    financial_highlight: str = ""
    catalysts: list[str] = []
    risk_factors: list[str] = []
    narrative_strength: str = "weak"
    market_outlook: str = "neutral"
    generated_at: str = ""
