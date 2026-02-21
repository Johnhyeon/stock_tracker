"""시그널 전략 백테스트 스키마."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    start_date: date
    end_date: date
    initial_capital: int = 10_000_000
    max_positions: int = Field(5, ge=1, le=30)
    min_signal_score: float = Field(60, ge=0, le=100)
    stop_loss_pct: float = Field(7.0, ge=1, le=30)
    take_profit_pct: float = Field(15.0, ge=5)
    max_holding_days: int = Field(20, ge=5)
    signal_types: list[str] = Field(default_factory=lambda: [
        "pullback", "high_breakout", "support_test",
        "mss_proximity", "ma120_turn",
        "candle_squeeze", "candle_expansion",
        "momentum_zone", "resistance_test",
    ])
    trailing_stop_pct: float = Field(5.0, ge=1, le=30)
    ma_deviation_exit_pct: float = Field(0.0, ge=0, le=100)  # MA120 이격도 %, 0=비활성
    # 적응형 트레일링
    adaptive_trailing: bool = Field(False)
    adaptive_dev_mid: float = Field(25.0, ge=5, le=60)  # 중간 구간 이격도 %
    adaptive_dev_high: float = Field(40.0, ge=10, le=80)  # 높음 구간 이격도 %
    adaptive_trail_low: float = Field(8.0, ge=1, le=20)  # 낮은 이격도 트레일링 %
    adaptive_trail_mid: float = Field(5.0, ge=1, le=15)  # 중간 이격도 트레일링 %
    adaptive_trail_high: float = Field(3.0, ge=1, le=10)  # 높은 이격도 트레일링 %
    adaptive_peak_drop: float = Field(10.0, ge=3, le=30)  # 피크 반전 감지 하락폭 %p
    adaptive_profit_trigger: float = Field(30.0, ge=5, le=100)  # 수익률 N%+ 시 트레일링 전환
    step_days: int = Field(2, ge=1, le=5)
    cooldown_days: int = Field(5, ge=0, le=20)


class BacktestTrade(BaseModel):
    stock_code: str
    stock_name: str
    signal_type: str
    signal_score: float
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    exit_reason: str  # stop_loss, take_profit, trailing_stop, ma_deviation, max_holding, end_of_test
    return_pct: float
    profit: float
    holding_days: int


class BacktestSummary(BaseModel):
    initial_capital: int
    final_capital: int
    total_return_pct: float
    annualized_return_pct: float
    mdd_pct: float
    win_rate: float
    total_trades: int
    avg_return_pct: float
    avg_holding_days: float
    profit_factor: float
    sharpe_ratio: float


class EquityCurvePoint(BaseModel):
    date: str
    value: float
    cash: float
    positions_value: float


class SignalPerformance(BaseModel):
    signal_type: str
    count: int
    win_rate: float
    avg_return_pct: float
    total_profit: float


class MonthlyPerformance(BaseModel):
    month: str
    return_pct: float
    trades: int
    win_rate: float


class IndexPoint(BaseModel):
    date: str
    value: float


class BacktestResponse(BaseModel):
    params: BacktestRequest
    summary: BacktestSummary
    equity_curve: list[EquityCurvePoint]
    kospi_curve: list[IndexPoint]
    kosdaq_curve: list[IndexPoint]
    signal_performance: list[SignalPerformance]
    monthly_performance: list[MonthlyPerformance]
    trades: list[BacktestTrade]
