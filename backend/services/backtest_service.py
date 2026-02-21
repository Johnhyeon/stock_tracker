"""시그널 전략 백테스트 서비스.

전 종목 OHLCV를 메모리 로드 → 슬라이딩 윈도우로 시그널 스캔 → 모의 매매 시뮬레이션.
핵심 원칙: 봇은 매매 시점에서 미래 데이터를 절대 볼 수 없음 (look-ahead bias 차단).
"""
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import StockOHLCV
from models.market_index_ohlcv import MarketIndexOHLCV
from schemas.backtest import (
    BacktestRequest,
    BacktestResponse,
    BacktestTrade,
    BacktestSummary,
    EquityCurvePoint,
    IndexPoint,
    SignalPerformance,
    MonthlyPerformance,
)
from services.pullback_service import PullbackService
from services.theme_map_service import get_theme_map_service

logger = logging.getLogger(__name__)

DETECTOR_MAP = {
    "pullback": "_detect_pullback",
    "high_breakout": "_detect_high_breakout",
    "resistance_test": "_detect_resistance_test",
    "support_test": "_detect_support_test",
    "mss_proximity": "_detect_mss_proximity",
    "momentum_zone": "_detect_momentum_zone",
    "candle_squeeze": "_detect_candle_squeeze",
    "candle_expansion": "_detect_candle_expansion",
    "ma120_turn": "_detect_ma120_turn",
}


@dataclass
class Position:
    stock_code: str
    stock_name: str
    signal_type: str
    signal_score: float
    entry_date: date
    entry_price: float
    shares: int
    entry_day_idx: int
    trailing: bool = False   # 트레일링 모드 전환 여부
    peak_price: float = 0.0  # 보유 중 최고가 (트레일링 기준)
    warning_zone: bool = False   # 이격도 경고구간 진입 여부
    peak_deviation: float = 0.0  # 경고구간 내 최대 MA120 이격도


@dataclass
class SimState:
    cash: float
    positions: list = field(default_factory=list)
    closed_trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)
    cooldown: dict = field(default_factory=dict)  # code -> unblock_day_idx


def params_hash(params: BacktestRequest) -> str:
    raw = json.dumps(params.model_dump(), default=str, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


class BacktestService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._ps = PullbackService(db)

    async def run_backtest(self, params: BacktestRequest) -> BacktestResponse:
        stocks = self._get_all_stocks()
        ohlcv_map, code_to_name = await self._load_ohlcv(
            [s["code"] for s in stocks],
            params.start_date,
            params.end_date,
        )
        code_to_name.update({s["code"]: s["name"] for s in stocks})

        # 마스터 거래일 리스트
        all_dates: set[date] = set()
        for data in ohlcv_map.values():
            all_dates.update(data["dates"])
        trading_days = sorted(all_dates)

        # 범위 내 거래일만
        trading_days = [d for d in trading_days if params.start_date <= d <= params.end_date]
        if len(trading_days) < 10:
            return self._empty_response(params)

        state = self._simulate(params, ohlcv_map, code_to_name, trading_days)
        summary = self._calculate_metrics(params, state)
        signal_perf = self._signal_performance(state.closed_trades)
        monthly_perf = self._monthly_performance(state.closed_trades)

        # 코스피/코스닥 지수 로드
        kospi_curve, kosdaq_curve = await self._load_index_curves(
            params.start_date, params.end_date
        )

        return BacktestResponse(
            params=params,
            summary=summary,
            equity_curve=state.equity_curve,
            kospi_curve=kospi_curve,
            kosdaq_curve=kosdaq_curve,
            signal_performance=signal_perf,
            monthly_performance=monthly_perf,
            trades=state.closed_trades,
        )

    # ── 데이터 로드 ──

    def _get_all_stocks(self) -> list[dict]:
        tms = get_theme_map_service()
        stocks, seen = [], set()
        for theme_stocks in tms.get_all_themes().values():
            for stock in theme_stocks:
                code = stock.get("code")
                name = stock.get("name", "")
                if code and code not in seen and "스팩" not in name:
                    seen.add(code)
                    stocks.append({"code": code, "name": name})
        return stocks

    async def _load_ohlcv(
        self, stock_codes: list[str], start: date, end: date,
    ) -> tuple[dict, dict]:
        load_start = start - timedelta(days=220)
        code_set = set(stock_codes)

        if len(stock_codes) > 500:
            stmt = (
                select(StockOHLCV)
                .where(and_(
                    StockOHLCV.trade_date >= load_start,
                    StockOHLCV.trade_date <= end,
                ))
                .order_by(StockOHLCV.stock_code, StockOHLCV.trade_date.asc())
            )
        else:
            stmt = (
                select(StockOHLCV)
                .where(and_(
                    StockOHLCV.stock_code.in_(stock_codes),
                    StockOHLCV.trade_date >= load_start,
                    StockOHLCV.trade_date <= end,
                ))
                .order_by(StockOHLCV.stock_code, StockOHLCV.trade_date.asc())
            )

        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        grouped = defaultdict(list)
        for row in rows:
            if row.stock_code in code_set:
                grouped[row.stock_code].append(row)

        ohlcv_map, code_to_name = {}, {}
        for code, candles in grouped.items():
            if len(candles) < 40:
                continue
            dates, opens, highs, lows, closes, volumes = [], [], [], [], [], []
            for c in candles:
                dates.append(c.trade_date)
                opens.append(float(c.open_price))
                highs.append(float(c.high_price))
                lows.append(float(c.low_price))
                closes.append(float(c.close_price))
                volumes.append(float(c.volume))
            ohlcv_map[code] = {
                "dates": dates,
                "opens": np.array(opens),
                "highs": np.array(highs),
                "lows": np.array(lows),
                "closes": np.array(closes),
                "volumes": np.array(volumes),
            }
        return ohlcv_map, code_to_name

    async def _load_index_curves(
        self, start: date, end: date,
    ) -> tuple[list[IndexPoint], list[IndexPoint]]:
        """코스피/코스닥 지수 종가를 백테스트 기간에 맞춰 로드."""
        stmt = (
            select(MarketIndexOHLCV)
            .where(and_(
                MarketIndexOHLCV.index_code.in_(["0001", "1001"]),
                MarketIndexOHLCV.trade_date >= start,
                MarketIndexOHLCV.trade_date <= end,
            ))
            .order_by(MarketIndexOHLCV.index_code, MarketIndexOHLCV.trade_date.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        kospi, kosdaq = [], []
        for row in rows:
            pt = IndexPoint(date=row.trade_date.isoformat(), value=float(row.close_value or 0))
            if row.index_code == "0001":
                kospi.append(pt)
            elif row.index_code == "1001":
                kosdaq.append(pt)
        return kospi, kosdaq

    # ── 시뮬레이션 엔진 ──

    def _simulate(
        self,
        params: BacktestRequest,
        ohlcv_map: dict,
        code_to_name: dict,
        trading_days: list[date],
    ) -> SimState:
        state = SimState(cash=float(params.initial_capital))
        per_slot = params.initial_capital / params.max_positions
        is_top_mode = "top" in params.signal_types
        if is_top_mode:
            # TOP 모드: 전체 디텍터 사용 + TOP 필터 적용
            active_detectors = [
                (name, getattr(self._ps, DETECTOR_MAP[name]))
                for name in DETECTOR_MAP
            ]
        else:
            active_detectors = [
                (name, getattr(self._ps, DETECTOR_MAP[name]))
                for name in params.signal_types
                if name in DETECTOR_MAP
            ]

        # 종목별 date→index 매핑
        code_date_idx: dict[str, dict[date, int]] = {}
        for code, data in ohlcv_map.items():
            code_date_idx[code] = {d: i for i, d in enumerate(data["dates"])}

        # 전체 trading_days에서 day index 매핑 (쿨다운에 사용)
        td_idx_map = {d: i for i, d in enumerate(trading_days)}

        for day_idx, today in enumerate(trading_days):
            # STEP 1: 청산 체크
            remaining = []
            for pos in state.positions:
                ohlcv_idx = code_date_idx.get(pos.stock_code, {}).get(today)
                if ohlcv_idx is None:
                    remaining.append(pos)
                    continue

                data = ohlcv_map[pos.stock_code]
                low = float(data["lows"][ohlcv_idx])
                high = float(data["highs"][ohlcv_idx])
                close = float(data["closes"][ohlcv_idx])
                holding = day_idx - pos.entry_day_idx

                # 보유 중 최고가 갱신 (트레일링 기준)
                if high > pos.peak_price:
                    pos.peak_price = high

                is_last_day = (day_idx == len(trading_days) - 1)
                exit_price, exit_reason = None, None
                sl_price = pos.entry_price * (1 - params.stop_loss_pct / 100)

                if params.adaptive_trailing:
                    # ── 적응형 트레일링: 이격도 비례 + 피크 반전 ──

                    # MA120 이격도 계산
                    ma120_deviation = 0.0
                    if ohlcv_idx >= 120:
                        ma120_val = float(np.mean(data["closes"][ohlcv_idx - 119:ohlcv_idx + 1]))
                        if ma120_val > 0:
                            ma120_deviation = (close - ma120_val) / ma120_val * 100

                    # 이격도 비례 트레일링 %
                    if ma120_deviation >= params.adaptive_dev_high:
                        eff_trail_pct = params.adaptive_trail_high
                    elif ma120_deviation >= params.adaptive_dev_mid:
                        eff_trail_pct = params.adaptive_trail_mid
                    else:
                        eff_trail_pct = params.adaptive_trail_low
                    eff_trail_price = pos.peak_price * (1 - eff_trail_pct / 100) if pos.trailing else 0

                    # 경고구간 & 피크 이격도 추적
                    if ma120_deviation >= params.adaptive_dev_mid:
                        pos.warning_zone = True
                        if ma120_deviation > pos.peak_deviation:
                            pos.peak_deviation = ma120_deviation
                    peak_reversal = pos.warning_zone and (pos.peak_deviation - ma120_deviation >= params.adaptive_peak_drop)

                    unrealized_pct = (close - pos.entry_price) / pos.entry_price * 100

                    if low <= sl_price:
                        exit_price, exit_reason = sl_price, "stop_loss"
                    elif pos.trailing:
                        # 적응형 트레일링 모드
                        if low <= eff_trail_price:
                            exit_price, exit_reason = eff_trail_price, "trailing_stop"
                        elif peak_reversal:
                            exit_price, exit_reason = close, "ma_deviation"
                        elif is_last_day:
                            exit_price, exit_reason = close, "end_of_test"
                    else:
                        # 수익 N%+ 또는 TP 도달 → 트레일링 전환 (청산 X, 큰 수익 추구)
                        tp_price = pos.entry_price * (1 + params.take_profit_pct / 100)
                        if unrealized_pct >= params.adaptive_profit_trigger or high >= tp_price:
                            pos.trailing = True
                            pos.peak_price = max(pos.peak_price, high)
                            remaining.append(pos)
                            continue
                        elif peak_reversal:
                            exit_price, exit_reason = close, "ma_deviation"
                        elif holding >= params.max_holding_days:
                            if close > pos.entry_price:
                                pos.trailing = True
                                pos.peak_price = max(pos.peak_price, close)
                                remaining.append(pos)
                                continue
                            else:
                                exit_price, exit_reason = close, "max_holding"
                        elif is_last_day:
                            exit_price, exit_reason = close, "end_of_test"
                else:
                    # ── 기본 모드: 고정 트레일링 + 고정 MA 이격도 ──
                    tp_price = pos.entry_price * (1 + params.take_profit_pct / 100)
                    trailing_price = pos.peak_price * (1 - params.trailing_stop_pct / 100) if pos.trailing else 0

                    ma_deviation_triggered = False
                    if params.ma_deviation_exit_pct > 0 and ohlcv_idx >= 120:
                        ma120 = float(np.mean(data["closes"][ohlcv_idx - 119:ohlcv_idx + 1]))
                        if ma120 > 0:
                            deviation = (close - ma120) / ma120 * 100
                            if deviation >= params.ma_deviation_exit_pct:
                                ma_deviation_triggered = True

                    if pos.trailing:
                        if low <= trailing_price:
                            exit_price, exit_reason = trailing_price, "trailing_stop"
                        elif ma_deviation_triggered:
                            exit_price, exit_reason = close, "ma_deviation"
                        elif is_last_day:
                            exit_price, exit_reason = close, "end_of_test"
                    else:
                        if low <= sl_price:
                            exit_price, exit_reason = sl_price, "stop_loss"
                        elif ma_deviation_triggered:
                            exit_price, exit_reason = close, "ma_deviation"
                        elif high >= tp_price:
                            exit_price, exit_reason = tp_price, "take_profit"
                        elif holding >= params.max_holding_days:
                            if close > pos.entry_price:
                                pos.trailing = True
                                pos.peak_price = max(pos.peak_price, close)
                                remaining.append(pos)
                                continue
                            else:
                                exit_price, exit_reason = close, "max_holding"
                        elif is_last_day:
                            exit_price, exit_reason = close, "end_of_test"

                if exit_price is not None:
                    profit = (exit_price - pos.entry_price) * pos.shares
                    ret_pct = round((exit_price - pos.entry_price) / pos.entry_price * 100, 2)
                    state.closed_trades.append(BacktestTrade(
                        stock_code=pos.stock_code,
                        stock_name=code_to_name.get(pos.stock_code, pos.stock_code),
                        signal_type=pos.signal_type,
                        signal_score=pos.signal_score,
                        entry_date=pos.entry_date.isoformat(),
                        entry_price=pos.entry_price,
                        exit_date=today.isoformat(),
                        exit_price=round(exit_price, 0),
                        exit_reason=exit_reason,
                        return_pct=ret_pct,
                        profit=round(profit, 0),
                        holding_days=holding,
                    ))
                    state.cash += exit_price * pos.shares
                    state.cooldown[pos.stock_code] = day_idx + params.cooldown_days
                else:
                    remaining.append(pos)
            state.positions = remaining

            # STEP 2: 시그널 스캔 & 진입
            slots = params.max_positions - len(state.positions)
            if (
                slots > 0
                and day_idx % params.step_days == 0
                and day_idx < len(trading_days) - 1
            ):
                signals = self._scan_signals_for_day(
                    today, day_idx, ohlcv_map, code_date_idx,
                    code_to_name, active_detectors, state, params,
                    top_mode=is_top_mode,
                )
                signals.sort(key=lambda s: s["score"], reverse=True)

                next_day = trading_days[day_idx + 1]
                for sig in signals[:slots]:
                    code = sig["code"]
                    next_idx = code_date_idx.get(code, {}).get(next_day)
                    if next_idx is None:
                        continue
                    entry_price = float(ohlcv_map[code]["opens"][next_idx])
                    if entry_price <= 0:
                        continue
                    shares = int(per_slot // entry_price)
                    if shares <= 0:
                        continue
                    cost = shares * entry_price
                    if cost > state.cash:
                        shares = int(state.cash // entry_price)
                        if shares <= 0:
                            continue
                        cost = shares * entry_price
                    state.cash -= cost
                    state.positions.append(Position(
                        stock_code=code,
                        stock_name=sig["name"],
                        signal_type=sig["signal_type"],
                        signal_score=sig["score"],
                        entry_date=next_day,
                        entry_price=entry_price,
                        shares=shares,
                        entry_day_idx=day_idx + 1,
                        peak_price=entry_price,
                    ))
                    slots -= 1
                    if slots <= 0:
                        break

            # STEP 3: 일별 자산 기록
            pos_val = self._positions_market_value(state.positions, ohlcv_map, code_date_idx, today)
            state.equity_curve.append(EquityCurvePoint(
                date=today.isoformat(),
                value=round(state.cash + pos_val, 0),
                cash=round(state.cash, 0),
                positions_value=round(pos_val, 0),
            ))

        return state

    def _scan_signals_for_day(
        self,
        today: date,
        day_idx: int,
        ohlcv_map: dict,
        code_date_idx: dict,
        code_to_name: dict,
        active_detectors: list,
        state: SimState,
        params: BacktestRequest,
        top_mode: bool = False,
    ) -> list[dict]:
        """오늘까지의 데이터만으로 시그널 스캔. ★미래 완전 차단★"""
        active_codes = {p.stock_code for p in state.positions}
        results = []

        for code, data in ohlcv_map.items():
            if code in active_codes:
                continue
            # 쿨다운 체크
            cooldown_until = state.cooldown.get(code)
            if cooldown_until is not None and day_idx < cooldown_until:
                continue

            today_idx = code_date_idx.get(code, {}).get(today)
            if today_idx is None:
                continue

            # ★★★ 미래 차단: today_idx까지만 슬라이스 ★★★
            end = today_idx + 1
            sliced = {
                "dates": data["dates"][:end],
                "opens": data["opens"][:end],
                "highs": data["highs"][:end],
                "lows": data["lows"][:end],
                "closes": data["closes"][:end],
                "volumes": data["volumes"][:end],
            }

            if len(sliced["closes"]) < 40:
                continue

            # 기본 잡주 필터
            current_price = float(sliced["closes"][-1])
            if current_price < 2000:
                continue
            avg_vol_20d = float(np.mean(sliced["volumes"][-20:])) if len(sliced["volumes"]) >= 20 else float(np.mean(sliced["volumes"]))

            # TOP 필터 (강화): 거래대금>=10억, 60일위치<70%, 거래량비>1.5
            min_trading_value = 1_000_000_000 if top_mode else 1_000_000_000
            if current_price * avg_vol_20d < min_trading_value:
                continue
            n60 = min(60, len(sliced["closes"]))
            high_60d = float(np.max(sliced["highs"][-n60:]))
            low_60d = float(np.min(sliced["lows"][-n60:]))
            pct_60d = (current_price - low_60d) / (high_60d - low_60d) * 100 if high_60d > low_60d else 50
            max_pct = 70 if top_mode else 70
            if pct_60d > max_pct:
                continue
            vol_ratio = 1.0
            if len(sliced["volumes"]) >= 20:
                vol_5d = float(np.mean(sliced["volumes"][-5:]))
                vol_20d = float(np.mean(sliced["volumes"][-20:]))
                vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 0
                min_vol_ratio = 1.5 if top_mode else 1.5
                if vol_ratio < min_vol_ratio:
                    continue

            common = self._ps._calc_common(sliced)

            if top_mode:
                # TOP 모드: 전체 디텍터 돌린 뒤 최고 점수만 취하고 score>=60 필터
                best_sig = None
                for sig_name, detector in active_detectors:
                    try:
                        result = detector(sliced, common)
                    except Exception:
                        continue
                    if result and result.get("total_score", 0) >= 60:
                        if best_sig is None or result["total_score"] > best_sig["score"]:
                            best_sig = {
                                "code": code,
                                "name": code_to_name.get(code, code),
                                "signal_type": sig_name,
                                "score": result["total_score"],
                            }
                if best_sig:
                    results.append(best_sig)
            else:
                for sig_name, detector in active_detectors:
                    try:
                        result = detector(sliced, common)
                    except Exception:
                        continue
                    if result and result.get("total_score", 0) >= params.min_signal_score:
                        results.append({
                            "code": code,
                            "name": code_to_name.get(code, code),
                            "signal_type": sig_name,
                            "score": result["total_score"],
                        })
                        break

        return results

    def _positions_market_value(
        self, positions: list, ohlcv_map: dict, code_date_idx: dict, today: date,
    ) -> float:
        total = 0.0
        for pos in positions:
            oi = code_date_idx.get(pos.stock_code, {}).get(today)
            price = float(ohlcv_map[pos.stock_code]["closes"][oi]) if oi is not None else pos.entry_price
            total += price * pos.shares
        return total

    # ── 메트릭 ──

    def _calculate_metrics(self, params: BacktestRequest, state: SimState) -> BacktestSummary:
        trades = state.closed_trades
        equity = state.equity_curve
        initial = params.initial_capital

        if not equity:
            return self._empty_summary(initial)

        final = equity[-1].value
        total_return = round((final - initial) / initial * 100, 2)

        days_span = max(1, len(equity))
        annual_return = round(((final / initial) ** (252 / days_span) - 1) * 100, 2) if final > 0 else 0.0

        # MDD
        peak = float(initial)
        max_dd = 0.0
        for pt in equity:
            if pt.value > peak:
                peak = pt.value
            dd = (peak - pt.value) / peak * 100
            if dd > max_dd:
                max_dd = dd

        total_trades = len(trades)
        wins = [t for t in trades if t.profit > 0]
        losses = [t for t in trades if t.profit <= 0]
        win_rate = round(len(wins) / total_trades * 100, 2) if total_trades > 0 else 0.0
        avg_return = round(float(np.mean([t.return_pct for t in trades])), 2) if trades else 0.0
        avg_holding = round(float(np.mean([t.holding_days for t in trades])), 1) if trades else 0.0

        total_profit = sum(t.profit for t in wins) if wins else 0
        total_loss = abs(sum(t.profit for t in losses)) if losses else 0
        pf = round(total_profit / total_loss, 2) if total_loss > 0 else (99.99 if total_profit > 0 else 0.0)

        sharpe = 0.0
        if len(equity) > 1:
            values = [pt.value for pt in equity]
            dr = [(values[i] - values[i - 1]) / values[i - 1] for i in range(1, len(values)) if values[i - 1] > 0]
            if dr:
                std = float(np.std(dr))
                if std > 0:
                    sharpe = round(float(np.mean(dr)) / std * float(np.sqrt(252)), 2)

        return BacktestSummary(
            initial_capital=initial,
            final_capital=int(final),
            total_return_pct=total_return,
            annualized_return_pct=annual_return,
            mdd_pct=round(max_dd, 2),
            win_rate=win_rate,
            total_trades=total_trades,
            avg_return_pct=avg_return,
            avg_holding_days=avg_holding,
            profit_factor=pf,
            sharpe_ratio=sharpe,
        )

    def _signal_performance(self, trades: list[BacktestTrade]) -> list[SignalPerformance]:
        by_type: dict[str, list] = defaultdict(list)
        for t in trades:
            by_type[t.signal_type].append(t)
        return [
            SignalPerformance(
                signal_type=st,
                count=len(tl),
                win_rate=round(sum(1 for t in tl if t.profit > 0) / len(tl) * 100, 2) if tl else 0,
                avg_return_pct=round(float(np.mean([t.return_pct for t in tl])), 2),
                total_profit=round(sum(t.profit for t in tl), 0),
            )
            for st, tl in sorted(by_type.items())
        ]

    def _monthly_performance(self, trades: list[BacktestTrade]) -> list[MonthlyPerformance]:
        by_month: dict[str, list] = defaultdict(list)
        for t in trades:
            by_month[t.exit_date[:7]].append(t)
        return [
            MonthlyPerformance(
                month=m,
                return_pct=round(float(np.mean([t.return_pct for t in tl])), 2),
                trades=len(tl),
                win_rate=round(sum(1 for t in tl if t.profit > 0) / len(tl) * 100, 2) if tl else 0,
            )
            for m, tl in sorted(by_month.items())
        ]

    def _empty_summary(self, initial: int) -> BacktestSummary:
        return BacktestSummary(
            initial_capital=initial, final_capital=initial,
            total_return_pct=0, annualized_return_pct=0, mdd_pct=0,
            win_rate=0, total_trades=0, avg_return_pct=0,
            avg_holding_days=0, profit_factor=0, sharpe_ratio=0,
        )

    def _empty_response(self, params: BacktestRequest) -> BacktestResponse:
        return BacktestResponse(
            params=params, summary=self._empty_summary(params.initial_capital),
            equity_curve=[], kospi_curve=[], kosdaq_curve=[],
            signal_performance=[], monthly_performance=[], trades=[],
        )
