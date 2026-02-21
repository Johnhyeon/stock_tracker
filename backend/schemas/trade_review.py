"""매매 복기 분석 응답 스키마."""
from pydantic import BaseModel


# ── What-If ──────────────────────────────────────────────

class WhatIfAlternative(BaseModel):
    """단일 대안 시뮬레이션 결과."""
    rule: str  # e.g. "+5일 보유", "-5% 손절"
    triggered: bool  # 규칙이 트리거됐는가
    exit_date: str | None = None
    exit_price: float | None = None
    return_pct: float | None = None
    diff_pct: float | None = None  # 실제 대비 차이


class WhatIfPosition(BaseModel):
    """포지션별 What-If 결과."""
    position_id: str
    stock_code: str
    stock_name: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    actual_return_pct: float
    holding_days: int
    alternatives: list[WhatIfAlternative] = []


class WhatIfRuleSummary(BaseModel):
    """규칙별 전체 집계."""
    rule: str
    applicable_count: int  # 적용 가능한 포지션 수
    triggered_count: int  # 실제 트리거된 수
    avg_return_pct: float
    total_diff_pct: float  # 실제 대비 평균 차이
    better_count: int  # 실제보다 나은 경우
    worse_count: int  # 실제보다 나쁜 경우


class WhatIfResponse(BaseModel):
    positions: list[WhatIfPosition] = []
    rule_summaries: list[WhatIfRuleSummary] = []
    actual_avg_return_pct: float = 0.0


# ── Trade Context ────────────────────────────────────────

class FlowBar(BaseModel):
    date: str
    foreign_net: float
    institution_net: float


class RelativeStrengthPoint(BaseModel):
    date: str
    value: float  # 초과수익률


class TradeContextResponse(BaseModel):
    position_id: str
    stock_code: str
    stock_name: str
    entry_date: str
    exit_date: str | None = None
    entry_price: float
    exit_price: float | None = None
    return_pct: float | None = None
    ohlcv: list[dict] = []  # StockChart ohlcvData 형식
    trade_markers: list[dict] = []  # {time, type, price}
    flow_bars: list[FlowBar] = []
    relative_strength: list[RelativeStrengthPoint] = []
    summary: dict = {}  # 텍스트 요약


# ── Flow Win Rate ────────────────────────────────────────

class FlowQuadrant(BaseModel):
    name: str  # e.g. "외인+기관+"
    label: str  # e.g. "쌍끌이 매수"
    trade_count: int
    win_count: int
    win_rate: float
    avg_return_pct: float


class ContraTrade(BaseModel):
    stock_code: str
    stock_name: str
    entry_date: str
    return_pct: float
    foreign_net: float
    institution_net: float


class FlowWinRateResponse(BaseModel):
    quadrants: list[FlowQuadrant] = []
    contra_trades: list[ContraTrade] = []
    total_trades: int = 0
    flow_available_trades: int = 0
    insight: str = ""


# ── Clustering ───────────────────────────────────────────

class ClusterTrade(BaseModel):
    stock_code: str
    stock_name: str
    entry_date: str
    return_pct: float
    holding_days: int


class TradeCluster(BaseModel):
    pattern_key: str  # e.g. "MA20위_BB중_거래량보통_단기"
    conditions: dict  # {ma20: "위", bb: "중", volume: "보통", holding: "단기"}
    trade_count: int
    win_count: int
    win_rate: float
    avg_return_pct: float
    trades: list[ClusterTrade] = []


class ClusterResponse(BaseModel):
    clusters: list[TradeCluster] = []
    best_pattern: TradeCluster | None = None
    worst_pattern: TradeCluster | None = None
    total_clustered: int = 0
    total_positions: int = 0
