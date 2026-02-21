from pydantic import BaseModel
from typing import Optional


class EntryTimingItem(BaseModel):
    trade_date: str
    stock_code: str
    stock_name: str
    price: float
    ma20_pct: Optional[float] = None
    ma60_pct: Optional[float] = None
    bb_position: Optional[float] = None
    high20_pct: Optional[float] = None
    volume_ratio: Optional[float] = None


class EntryTimingSummary(BaseModel):
    total_entries: int = 0
    above_ma20_pct: float = 0
    above_ma60_pct: float = 0
    avg_ma20_pct: float = 0
    avg_ma60_pct: float = 0
    bb_lower_pct: float = 0  # BB 하단 (0~0.33)
    bb_middle_pct: float = 0  # BB 중앙 (0.33~0.67)
    bb_upper_pct: float = 0  # BB 상단 (0.67~1.0)
    avg_volume_ratio: float = 0
    high_volume_pct: float = 0  # 거래량비 > 1.5 비율
    items: list[EntryTimingItem] = []


class ExitTimingItem(BaseModel):
    trade_date: str
    stock_code: str
    stock_name: str
    price: float
    realized_return_pct: Optional[float] = None
    after_5d_pct: Optional[float] = None
    after_10d_pct: Optional[float] = None
    after_20d_pct: Optional[float] = None
    peak_vs_exit_pct: Optional[float] = None  # 보유 중 고점 대비


class ExitTimingSummary(BaseModel):
    total_exits: int = 0
    avg_after_5d: float = 0
    avg_after_10d: float = 0
    avg_after_20d: float = 0
    early_sell_pct: float = 0  # 매도 후 10일 내 +5% 이상 오른 비율
    good_sell_pct: float = 0  # 매도 후 10일 내 하락/보합인 비율
    avg_peak_vs_exit: float = 0  # 평균 고점 대비 매도 효율
    items: list[ExitTimingItem] = []


class MFEMAEItem(BaseModel):
    stock_code: str
    stock_name: str
    entry_price: float
    exit_price: float
    entry_date: str
    exit_date: str
    realized_return_pct: float
    mfe_pct: float  # 최대 순간 수익률
    mae_pct: float  # 최대 순간 손실률
    capture_ratio: Optional[float] = None  # 수익실현율 = realized / MFE


class ScatterPoint(BaseModel):
    x: float  # MAE
    y: float  # 실현수익률
    stock_name: str
    is_winner: bool


class MFEMAESummary(BaseModel):
    total_positions: int = 0
    avg_mfe: float = 0
    avg_mae: float = 0
    avg_capture_ratio: float = 0
    scatter_data: list[ScatterPoint] = []
    items: list[MFEMAEItem] = []


class MiniChartCandle(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class TradeMarkerData(BaseModel):
    time: int
    type: str  # BUY, ADD_BUY, SELL, PARTIAL_SELL
    price: float


class MiniChartData(BaseModel):
    stock_code: str
    stock_name: str
    trade_type: str
    trade_date: str
    price: float
    realized_return_pct: Optional[float] = None
    candles: list[MiniChartCandle] = []
    markers: list[TradeMarkerData] = []


class ChartAnalysisResponse(BaseModel):
    entry_timing: EntryTimingSummary
    exit_timing: ExitTimingSummary
    mfe_mae: MFEMAESummary
    mini_charts: list[MiniChartData] = []
    worst_mini_charts: list[MiniChartData] = []
