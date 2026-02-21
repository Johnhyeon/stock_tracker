"""차트 기반 매매 분석 서비스."""
import calendar
import logging
from collections import defaultdict
from datetime import datetime, timedelta, date

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.trade import Trade, TradeType
from models.position import Position
from models.stock_ohlcv import StockOHLCV
from schemas.chart_analysis import (
    ChartAnalysisResponse,
    EntryTimingItem,
    EntryTimingSummary,
    ExitTimingItem,
    ExitTimingSummary,
    MFEMAEItem,
    MFEMAESummary,
    ScatterPoint,
    MiniChartCandle,
    MiniChartData,
    TradeMarkerData,
)

logger = logging.getLogger(__name__)


def _date_to_ts(d: date) -> int:
    return calendar.timegm(datetime.combine(d, datetime.min.time()).timetuple())


class ChartAnalysisService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze(self, start_date: date | None = None, end_date: date | None = None) -> ChartAnalysisResponse:
        # 1) 매매 기록 조회 (기간 필터)
        trade_query = select(Trade).order_by(Trade.trade_date.desc())
        if start_date:
            trade_query = trade_query.where(Trade.trade_date >= start_date)
        if end_date:
            trade_query = trade_query.where(Trade.trade_date <= end_date)
        result = await self.db.execute(trade_query)
        all_trades = result.scalars().all()

        if not all_trades:
            return ChartAnalysisResponse(
                entry_timing=EntryTimingSummary(),
                exit_timing=ExitTimingSummary(),
                mfe_mae=MFEMAESummary(),
                mini_charts=[],
            )

        # 2) 청산된 포지션 조회 (기간 필터)
        pos_query = select(Position).where(Position.exit_date.isnot(None))
        if start_date:
            pos_query = pos_query.where(Position.exit_date >= start_date)
        if end_date:
            pos_query = pos_query.where(Position.exit_date <= end_date)
        result = await self.db.execute(pos_query)
        closed_positions = result.scalars().all()

        # 3) OHLCV 벌크 조회
        stock_codes = set()
        earliest_date = None
        latest_date = None
        for t in all_trades:
            if t.stock_code:
                stock_codes.add(t.stock_code)
            td = t.trade_date
            if earliest_date is None or td < earliest_date:
                earliest_date = td
            if latest_date is None or td > latest_date:
                latest_date = td

        for p in closed_positions:
            if p.ticker:
                stock_codes.add(p.ticker)

        if not stock_codes or not earliest_date:
            return ChartAnalysisResponse(
                entry_timing=EntryTimingSummary(),
                exit_timing=ExitTimingSummary(),
                mfe_mae=MFEMAESummary(),
                mini_charts=[],
            )

        ohlcv_start = earliest_date - timedelta(days=270)
        ohlcv_end = latest_date + timedelta(days=130)

        result = await self.db.execute(
            select(StockOHLCV).where(
                and_(
                    StockOHLCV.stock_code.in_(stock_codes),
                    StockOHLCV.trade_date >= ohlcv_start,
                    StockOHLCV.trade_date <= ohlcv_end,
                )
            ).order_by(StockOHLCV.stock_code, StockOHLCV.trade_date)
        )
        ohlcv_rows = result.scalars().all()

        # 종목별 OHLCV 맵핑
        ohlcv_map: dict[str, list[StockOHLCV]] = defaultdict(list)
        for row in ohlcv_rows:
            ohlcv_map[row.stock_code].append(row)

        # 4) 분석 실행
        entry_timing = self._analyze_entry_timing(all_trades, ohlcv_map)
        exit_timing = self._analyze_exit_timing(all_trades, ohlcv_map)
        mfe_mae = self._analyze_mfe_mae(closed_positions, all_trades, ohlcv_map)
        mini_charts = self._build_mini_charts(all_trades, ohlcv_map)
        worst_mini_charts = self._build_mini_charts(all_trades, ohlcv_map, worst=True)

        return ChartAnalysisResponse(
            entry_timing=entry_timing,
            exit_timing=exit_timing,
            mfe_mae=mfe_mae,
            mini_charts=mini_charts,
            worst_mini_charts=worst_mini_charts,
        )

    def _get_ohlcv_index(self, candles: list[StockOHLCV], target_date: date) -> int | None:
        for i, c in enumerate(candles):
            if c.trade_date == target_date:
                return i
            if c.trade_date > target_date:
                # 거래일이 아닌 날(휴장)은 직전 거래일 사용
                return i - 1 if i > 0 else None
        return None

    def _analyze_entry_timing(
        self, trades: list[Trade], ohlcv_map: dict[str, list[StockOHLCV]]
    ) -> EntryTimingSummary:
        buy_trades = [t for t in trades if t.trade_type in (TradeType.BUY, TradeType.ADD_BUY) and t.stock_code]
        items: list[EntryTimingItem] = []

        for t in buy_trades:
            candles = ohlcv_map.get(t.stock_code, [])
            idx = self._get_ohlcv_index(candles, t.trade_date)
            if idx is None or idx < 20:
                items.append(EntryTimingItem(
                    trade_date=str(t.trade_date),
                    stock_code=t.stock_code,
                    stock_name=t.stock_name or t.stock_code,
                    price=float(t.price),
                ))
                continue

            price = float(t.price)

            # MA20
            closes_20 = [float(candles[i].close_price) for i in range(idx - 19, idx + 1)]
            ma20 = sum(closes_20) / 20
            ma20_pct = round((price - ma20) / ma20 * 100, 2) if ma20 > 0 else None

            # MA60
            ma60_pct = None
            if idx >= 60:
                closes_60 = [float(candles[i].close_price) for i in range(idx - 59, idx + 1)]
                ma60 = sum(closes_60) / 60
                ma60_pct = round((price - ma60) / ma60 * 100, 2) if ma60 > 0 else None

            # 볼린저밴드 위치
            bb_position = None
            if len(closes_20) == 20:
                ma = sum(closes_20) / 20
                std = (sum((c - ma) ** 2 for c in closes_20) / 20) ** 0.5
                if std > 0:
                    upper = ma + 2 * std
                    lower = ma - 2 * std
                    bb_position = round((price - lower) / (upper - lower), 3) if (upper - lower) > 0 else 0.5

            # 20일 고가 대비
            highs_20 = [float(candles[i].high_price) for i in range(idx - 19, idx + 1)]
            high_20 = max(highs_20) if highs_20 else price
            high20_pct = round((price - high_20) / high_20 * 100, 2) if high_20 > 0 else None

            # 거래량비
            volume_ratio = None
            if idx >= 20:
                today_vol = float(candles[idx].volume)
                avg_vol = sum(float(candles[i].volume) for i in range(idx - 19, idx)) / 20
                volume_ratio = round(today_vol / avg_vol, 2) if avg_vol > 0 else None

            items.append(EntryTimingItem(
                trade_date=str(t.trade_date),
                stock_code=t.stock_code,
                stock_name=t.stock_name or t.stock_code,
                price=price,
                ma20_pct=ma20_pct,
                ma60_pct=ma60_pct,
                bb_position=bb_position,
                high20_pct=high20_pct,
                volume_ratio=volume_ratio,
            ))

        # 요약 계산
        valid_ma20 = [i for i in items if i.ma20_pct is not None]
        valid_ma60 = [i for i in items if i.ma60_pct is not None]
        valid_bb = [i for i in items if i.bb_position is not None]
        valid_vol = [i for i in items if i.volume_ratio is not None]

        return EntryTimingSummary(
            total_entries=len(items),
            above_ma20_pct=round(len([i for i in valid_ma20 if i.ma20_pct > 0]) / len(valid_ma20) * 100, 1) if valid_ma20 else 0,
            above_ma60_pct=round(len([i for i in valid_ma60 if i.ma60_pct > 0]) / len(valid_ma60) * 100, 1) if valid_ma60 else 0,
            avg_ma20_pct=round(sum(i.ma20_pct for i in valid_ma20) / len(valid_ma20), 2) if valid_ma20 else 0,
            avg_ma60_pct=round(sum(i.ma60_pct for i in valid_ma60) / len(valid_ma60), 2) if valid_ma60 else 0,
            bb_lower_pct=round(len([i for i in valid_bb if i.bb_position < 0.33]) / len(valid_bb) * 100, 1) if valid_bb else 0,
            bb_middle_pct=round(len([i for i in valid_bb if 0.33 <= i.bb_position <= 0.67]) / len(valid_bb) * 100, 1) if valid_bb else 0,
            bb_upper_pct=round(len([i for i in valid_bb if i.bb_position > 0.67]) / len(valid_bb) * 100, 1) if valid_bb else 0,
            avg_volume_ratio=round(sum(i.volume_ratio for i in valid_vol) / len(valid_vol), 2) if valid_vol else 0,
            high_volume_pct=round(len([i for i in valid_vol if i.volume_ratio > 1.5]) / len(valid_vol) * 100, 1) if valid_vol else 0,
            items=sorted(items, key=lambda x: x.trade_date, reverse=True),
        )

    def _analyze_exit_timing(
        self, trades: list[Trade], ohlcv_map: dict[str, list[StockOHLCV]]
    ) -> ExitTimingSummary:
        sell_trades = [t for t in trades if t.trade_type in (TradeType.SELL, TradeType.PARTIAL_SELL) and t.stock_code]
        items: list[ExitTimingItem] = []

        for t in sell_trades:
            candles = ohlcv_map.get(t.stock_code, [])
            idx = self._get_ohlcv_index(candles, t.trade_date)

            price = float(t.price)
            after_5d = None
            after_10d = None
            after_20d = None

            if idx is not None:
                n = len(candles)
                if idx + 5 < n:
                    after_5d = round((float(candles[idx + 5].close_price) - price) / price * 100, 2)
                if idx + 10 < n:
                    after_10d = round((float(candles[idx + 10].close_price) - price) / price * 100, 2)
                if idx + 20 < n:
                    after_20d = round((float(candles[idx + 20].close_price) - price) / price * 100, 2)

            # 보유 중 고점 대비 (position에서 진입일 찾아서)
            peak_vs_exit = None
            # position의 매수 trades 찾기
            buy_trades_for_pos = [
                bt for bt in trades
                if bt.position_id == t.position_id
                and bt.trade_type in (TradeType.BUY, TradeType.ADD_BUY)
            ]
            if buy_trades_for_pos and idx is not None:
                first_buy_date = min(bt.trade_date for bt in buy_trades_for_pos)
                buy_idx = self._get_ohlcv_index(candles, first_buy_date)
                if buy_idx is not None and buy_idx < idx:
                    peak = max(float(candles[i].high_price) for i in range(buy_idx, idx + 1))
                    if peak > 0:
                        peak_vs_exit = round((price - peak) / peak * 100, 2)

            items.append(ExitTimingItem(
                trade_date=str(t.trade_date),
                stock_code=t.stock_code,
                stock_name=t.stock_name or t.stock_code,
                price=price,
                realized_return_pct=float(t.realized_return_pct) if t.realized_return_pct else None,
                after_5d_pct=after_5d,
                after_10d_pct=after_10d,
                after_20d_pct=after_20d,
                peak_vs_exit_pct=peak_vs_exit,
            ))

        # 요약
        valid_5d = [i for i in items if i.after_5d_pct is not None]
        valid_10d = [i for i in items if i.after_10d_pct is not None]
        valid_20d = [i for i in items if i.after_20d_pct is not None]
        valid_peak = [i for i in items if i.peak_vs_exit_pct is not None]

        early_sell = len([i for i in valid_10d if i.after_10d_pct > 5]) if valid_10d else 0
        good_sell = len([i for i in valid_10d if i.after_10d_pct <= 0]) if valid_10d else 0

        return ExitTimingSummary(
            total_exits=len(items),
            avg_after_5d=round(sum(i.after_5d_pct for i in valid_5d) / len(valid_5d), 2) if valid_5d else 0,
            avg_after_10d=round(sum(i.after_10d_pct for i in valid_10d) / len(valid_10d), 2) if valid_10d else 0,
            avg_after_20d=round(sum(i.after_20d_pct for i in valid_20d) / len(valid_20d), 2) if valid_20d else 0,
            early_sell_pct=round(early_sell / len(valid_10d) * 100, 1) if valid_10d else 0,
            good_sell_pct=round(good_sell / len(valid_10d) * 100, 1) if valid_10d else 0,
            avg_peak_vs_exit=round(sum(i.peak_vs_exit_pct for i in valid_peak) / len(valid_peak), 2) if valid_peak else 0,
            items=sorted(items, key=lambda x: x.trade_date, reverse=True),
        )

    def _analyze_mfe_mae(
        self,
        positions: list[Position],
        trades: list[Trade],
        ohlcv_map: dict[str, list[StockOHLCV]],
    ) -> MFEMAESummary:
        items: list[MFEMAEItem] = []
        scatter: list[ScatterPoint] = []

        for p in positions:
            candles = ohlcv_map.get(p.ticker, [])
            if not candles or p.entry_date is None or p.exit_date is None:
                continue

            entry_idx = self._get_ohlcv_index(candles, p.entry_date)
            exit_idx = self._get_ohlcv_index(candles, p.exit_date)
            if entry_idx is None or exit_idx is None or entry_idx >= exit_idx:
                continue

            entry_price = float(p.entry_price)
            exit_price = float(p.exit_price) if p.exit_price else entry_price
            realized_pct = round((exit_price - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0

            # MFE: 보유 기간 중 최고 수익률
            max_high = max(float(candles[i].high_price) for i in range(entry_idx, exit_idx + 1))
            mfe_pct = round((max_high - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0

            # MAE: 보유 기간 중 최대 손실률
            min_low = min(float(candles[i].low_price) for i in range(entry_idx, exit_idx + 1))
            mae_pct = round((min_low - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0

            # 수익실현율
            capture = round(realized_pct / mfe_pct * 100, 1) if mfe_pct > 0 else None

            # 종목명 (trades에서 찾기)
            stock_name = p.ticker
            pos_trades = [t for t in trades if t.position_id == p.id]
            if pos_trades and pos_trades[0].stock_name:
                stock_name = pos_trades[0].stock_name

            items.append(MFEMAEItem(
                stock_code=p.ticker,
                stock_name=stock_name,
                entry_price=entry_price,
                exit_price=exit_price,
                entry_date=str(p.entry_date),
                exit_date=str(p.exit_date),
                realized_return_pct=realized_pct,
                mfe_pct=mfe_pct,
                mae_pct=mae_pct,
                capture_ratio=capture,
            ))

            scatter.append(ScatterPoint(
                x=mae_pct,
                y=realized_pct,
                stock_name=stock_name,
                is_winner=realized_pct > 0,
            ))

        valid_capture = [i for i in items if i.capture_ratio is not None]

        return MFEMAESummary(
            total_positions=len(items),
            avg_mfe=round(sum(i.mfe_pct for i in items) / len(items), 2) if items else 0,
            avg_mae=round(sum(i.mae_pct for i in items) / len(items), 2) if items else 0,
            avg_capture_ratio=round(sum(i.capture_ratio for i in valid_capture) / len(valid_capture), 1) if valid_capture else 0,
            scatter_data=scatter,
            items=sorted(items, key=lambda x: x.exit_date, reverse=True),
        )

    def _build_mini_charts(
        self, trades: list[Trade], ohlcv_map: dict[str, list[StockOHLCV]], worst: bool = False
    ) -> list[MiniChartData]:
        # 수익률 기준 Best/Worst 매매 선별 (포지션별 대표 건만, 종목 중복 제거)
        sell_trades = [
            t for t in trades
            if t.stock_code and t.realized_return_pct is not None
        ]
        # 포지션별 대표 건만 남기기 (best=최고수익, worst=최저수익)
        repr_by_pos: dict[str, Trade] = {}
        for t in sell_trades:
            pid = str(t.position_id)
            if pid not in repr_by_pos:
                repr_by_pos[pid] = t
            else:
                cur = float(t.realized_return_pct)
                prev = float(repr_by_pos[pid].realized_return_pct)
                if (not worst and cur > prev) or (worst and cur < prev):
                    repr_by_pos[pid] = t
        # 종목 중복 제거 (같은 종목 여러 포지션이면 대표 건만)
        repr_by_stock: dict[str, Trade] = {}
        for t in repr_by_pos.values():
            code = t.stock_code
            if code not in repr_by_stock:
                repr_by_stock[code] = t
            else:
                cur = float(t.realized_return_pct)
                prev = float(repr_by_stock[code].realized_return_pct)
                if (not worst and cur > prev) or (worst and cur < prev):
                    repr_by_stock[code] = t
        best_trades = sorted(
            repr_by_stock.values(),
            key=lambda t: float(t.realized_return_pct),
            reverse=not worst,
        )[:12]
        charts: list[MiniChartData] = []

        for t in best_trades:
            candles = ohlcv_map.get(t.stock_code, [])
            idx = self._get_ohlcv_index(candles, t.trade_date)
            if idx is None:
                continue

            # 전후 90거래일 (약 180 거래일 = ~9개월)
            start_idx = max(0, idx - 90)
            end_idx = min(len(candles), idx + 91)
            chart_candles = candles[start_idx:end_idx]

            mini_candles = [
                MiniChartCandle(
                    time=_date_to_ts(c.trade_date),
                    open=float(c.open_price),
                    high=float(c.high_price),
                    low=float(c.low_price),
                    close=float(c.close_price),
                    volume=float(c.volume),
                )
                for c in chart_candles
            ]

            # 같은 종목의 모든 매매 마커 (이 차트 범위 내)
            chart_start_date = chart_candles[0].trade_date if chart_candles else t.trade_date
            chart_end_date = chart_candles[-1].trade_date if chart_candles else t.trade_date

            markers: list[TradeMarkerData] = []
            for other_t in trades:
                if (other_t.stock_code == t.stock_code
                        and chart_start_date <= other_t.trade_date <= chart_end_date):
                    markers.append(TradeMarkerData(
                        time=_date_to_ts(other_t.trade_date),
                        type=other_t.trade_type.value if hasattr(other_t.trade_type, 'value') else str(other_t.trade_type),
                        price=float(other_t.price),
                    ))

            charts.append(MiniChartData(
                stock_code=t.stock_code,
                stock_name=t.stock_name or t.stock_code,
                trade_type=t.trade_type.value if hasattr(t.trade_type, 'value') else str(t.trade_type),
                trade_date=str(t.trade_date),
                price=float(t.price),
                realized_return_pct=float(t.realized_return_pct) if t.realized_return_pct else None,
                candles=mini_candles,
                markers=markers,
            ))

        return charts
