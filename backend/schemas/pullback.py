"""차트 시그널 스캐너 스키마."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class SignalType(str, Enum):
    PULLBACK = "pullback"
    HIGH_BREAKOUT = "high_breakout"
    RESISTANCE_TEST = "resistance_test"
    SUPPORT_TEST = "support_test"
    MSS_PROXIMITY = "mss_proximity"
    MOMENTUM_ZONE = "momentum_zone"
    MA120_TURN = "ma120_turn"
    CANDLE_SQUEEZE = "candle_squeeze"
    CANDLE_EXPANSION = "candle_expansion"


class SignalStock(BaseModel):
    stock_code: str
    stock_name: str
    signal_type: SignalType
    current_price: int
    total_score: float = 0.0
    grade: str = "D"
    themes: list[str] = []
    ma20: Optional[int] = None
    ma50: Optional[int] = None
    ma20_distance_pct: Optional[float] = None
    ma50_distance_pct: Optional[float] = None
    volume_ratio: Optional[float] = None
    high_price_60d: Optional[int] = None
    low_price_60d: Optional[int] = None
    percentile_60d: Optional[float] = None
    score_breakdown: dict = {}

    # 눌림목 전용
    pullback_pct: Optional[float] = None
    support_line: Optional[int] = None
    support_distance_pct: Optional[float] = None
    volume_decreasing: bool = False
    surge_pct: Optional[float] = None  # 급등률 (눌림 전 최대 상승률)

    # 전고점 돌파 전용
    prev_high_price: Optional[int] = None
    prev_high_date: Optional[str] = None
    breakout_pct: Optional[float] = None
    breakout_volume_ratio: Optional[float] = None

    # 저항 돌파 시도 전용
    resistance_price: Optional[int] = None
    resistance_touch_count: Optional[int] = None
    resistance_distance_pct: Optional[float] = None

    # 지지선 테스트 전용
    support_price: Optional[int] = None
    support_touch_count: Optional[int] = None
    consolidation_days: Optional[int] = None
    ma_support_aligned: Optional[bool] = None

    # MSS 근접 전용
    mss_level: Optional[int] = None
    mss_type: Optional[str] = None
    mss_distance_pct: Optional[float] = None
    mss_touch_count: Optional[int] = None
    mss_timeframe: Optional[str] = None

    # 관성 구간 전용
    mz_surge_pct: Optional[float] = None
    mz_surge_days: Optional[int] = None
    mz_consolidation_days: Optional[int] = None
    mz_consolidation_range_pct: Optional[float] = None
    mz_atr_contraction_ratio: Optional[float] = None
    mz_volume_shrink_ratio: Optional[float] = None
    mz_upper_bound: Optional[int] = None
    mz_distance_to_upper_pct: Optional[float] = None

    # 120일선 전환 전용
    ma120: Optional[int] = None
    ma120_slope_pct: Optional[float] = None
    ma120_distance_pct: Optional[float] = None
    recovery_pct: Optional[float] = None
    has_double_bottom: bool = False
    resistance_broken: bool = False
    has_new_high_volume: bool = False
    volume_surge_ratio: Optional[float] = None

    # 캔들 수축 전용
    cs_contraction_pct: Optional[float] = None
    cs_body_contraction_pct: Optional[float] = None
    cs_volume_shrink_ratio: Optional[float] = None
    cs_correction_days: Optional[int] = None
    cs_correction_depth_pct: Optional[float] = None

    # 캔들 확장 전용
    ce_expansion_pct: Optional[float] = None
    ce_body_expansion_pct: Optional[float] = None
    ce_volume_surge_ratio: Optional[float] = None
    ce_bullish_pct: Optional[float] = None

    # 수급 (점수 불포함, 참조만)
    foreign_net_5d: int = 0
    institution_net_5d: int = 0

    # 거래대금 (20일 평균, 원 단위)
    avg_trading_value: Optional[float] = None

    # 품질 필터
    is_profitable: Optional[bool] = None
    is_growing: Optional[bool] = None
    has_institutional_buying: Optional[bool] = None
    quality_score: Optional[float] = None
    roe: Optional[float] = None
    debt_ratio: Optional[float] = None
    revenue_growth: Optional[float] = None


class SignalResponse(BaseModel):
    stocks: list[SignalStock]
    count: int
    signal_type: str
    generated_at: str


class SignalDetailResponse(BaseModel):
    stock: dict
    price_history: list[dict]
    flow_history: list[dict]
    analysis_summary: str
    generated_at: str
