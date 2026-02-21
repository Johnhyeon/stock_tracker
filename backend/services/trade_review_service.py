"""매매 복기 분석 서비스.

청산된 포지션 + OHLCV + 수급 + 시장지수를 교차 활용하여
What-If 시뮬레이션, 매매 컨텍스트 복원, 수급 연동 승률, 유사 매매 클러스터링을 제공.
"""
import calendar
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.trade import Trade, TradeType
from models.position import Position
from models.stock_ohlcv import StockOHLCV
from models.stock_investor_flow import StockInvestorFlow
from models.market_index_ohlcv import MarketIndexOHLCV
from schemas.trade_review import (
    WhatIfResponse, WhatIfPosition, WhatIfAlternative, WhatIfRuleSummary,
    TradeContextResponse, FlowBar, RelativeStrengthPoint,
    FlowWinRateResponse, FlowQuadrant, ContraTrade,
    ClusterResponse, TradeCluster, ClusterTrade,
)

logger = logging.getLogger(__name__)


def _date_to_ts(d: date) -> int:
    return calendar.timegm(datetime.combine(d, datetime.min.time()).timetuple())


class TradeReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── 공통 데이터 로딩 ─────────────────────────────────

    async def _load_closed_positions(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> list[Position]:
        q = select(Position).where(Position.exit_date.isnot(None))
        if start_date:
            q = q.where(Position.exit_date >= start_date)
        if end_date:
            q = q.where(Position.exit_date <= end_date)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def _load_trades_for_positions(self, position_ids: list) -> dict[str, list[Trade]]:
        if not position_ids:
            return {}
        result = await self.db.execute(
            select(Trade).where(Trade.position_id.in_(position_ids))
        )
        trades = result.scalars().all()
        trade_map: dict[str, list[Trade]] = defaultdict(list)
        for t in trades:
            trade_map[str(t.position_id)].append(t)
        return trade_map

    async def _load_ohlcv_bulk(
        self, stock_codes: set[str], earliest: date, latest: date
    ) -> dict[str, list[StockOHLCV]]:
        if not stock_codes:
            return {}
        ohlcv_start = earliest - timedelta(days=270)
        ohlcv_end = latest + timedelta(days=130)
        result = await self.db.execute(
            select(StockOHLCV).where(
                and_(
                    StockOHLCV.stock_code.in_(stock_codes),
                    StockOHLCV.trade_date >= ohlcv_start,
                    StockOHLCV.trade_date <= ohlcv_end,
                )
            ).order_by(StockOHLCV.stock_code, StockOHLCV.trade_date)
        )
        ohlcv_map: dict[str, list[StockOHLCV]] = defaultdict(list)
        for row in result.scalars().all():
            ohlcv_map[row.stock_code].append(row)
        return ohlcv_map

    async def _load_investor_flow_bulk(
        self, stock_codes: set[str], earliest: date, latest: date
    ) -> dict[str, list[StockInvestorFlow]]:
        if not stock_codes:
            return {}
        flow_start = earliest - timedelta(days=30)
        flow_end = latest + timedelta(days=10)
        result = await self.db.execute(
            select(StockInvestorFlow).where(
                and_(
                    StockInvestorFlow.stock_code.in_(stock_codes),
                    StockInvestorFlow.flow_date >= flow_start,
                    StockInvestorFlow.flow_date <= flow_end,
                )
            ).order_by(StockInvestorFlow.stock_code, StockInvestorFlow.flow_date)
        )
        flow_map: dict[str, list[StockInvestorFlow]] = defaultdict(list)
        for row in result.scalars().all():
            flow_map[row.stock_code].append(row)
        return flow_map

    async def _load_market_index(
        self, index_code: str, earliest: date, latest: date
    ) -> list[MarketIndexOHLCV]:
        result = await self.db.execute(
            select(MarketIndexOHLCV).where(
                and_(
                    MarketIndexOHLCV.index_code == index_code,
                    MarketIndexOHLCV.trade_date >= earliest - timedelta(days=30),
                    MarketIndexOHLCV.trade_date <= latest + timedelta(days=10),
                )
            ).order_by(MarketIndexOHLCV.trade_date)
        )
        return list(result.scalars().all())

    def _get_ohlcv_index(self, candles: list[StockOHLCV], target_date: date) -> int | None:
        for i, c in enumerate(candles):
            if c.trade_date == target_date:
                return i
            if c.trade_date > target_date:
                return i - 1 if i > 0 else None
        return None

    def _get_stock_name(self, pos: Position, trade_map: dict[str, list[Trade]]) -> str:
        trades = trade_map.get(str(pos.id), [])
        for t in trades:
            if t.stock_name:
                return t.stock_name
        return pos.ticker

    # ── Feature 1: What-If 시뮬레이터 ────────────────────

    async def what_if_analysis(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> WhatIfResponse:
        positions = await self._load_closed_positions(start_date, end_date)
        if not positions:
            return WhatIfResponse()

        pos_ids = [p.id for p in positions]
        trade_map = await self._load_trades_for_positions(pos_ids)

        stock_codes = {p.ticker for p in positions}
        dates = [d for p in positions for d in [p.entry_date, p.exit_date] if d]
        if not dates:
            return WhatIfResponse()

        ohlcv_map = await self._load_ohlcv_bulk(stock_codes, min(dates), max(dates))

        # 시뮬레이션 규칙 정의
        hold_shifts = [-10, -5, 5, 10, 20]
        stop_losses = [-3, -5, -7, -10]
        take_profits = [5, 10, 15, 20]
        half_profits = [5, 10, 15]

        result_positions: list[WhatIfPosition] = []
        rule_results: dict[str, list[dict]] = defaultdict(list)

        for pos in positions:
            candles = ohlcv_map.get(pos.ticker, [])
            if not candles or not pos.entry_date or not pos.exit_date:
                continue

            entry_idx = self._get_ohlcv_index(candles, pos.entry_date)
            exit_idx = self._get_ohlcv_index(candles, pos.exit_date)
            if entry_idx is None or exit_idx is None or entry_idx >= exit_idx:
                continue

            entry_price = float(pos.entry_price)
            exit_price = float(pos.exit_price) if pos.exit_price else entry_price
            actual_return = round((exit_price - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0
            holding_days = (pos.exit_date - pos.entry_date).days
            stock_name = self._get_stock_name(pos, trade_map)

            alternatives: list[WhatIfAlternative] = []

            # 보유기간 변동
            for shift in hold_shifts:
                alt = self._simulate_hold_shift(candles, entry_idx, exit_idx, entry_price, shift)
                alternatives.append(alt)
                rule_results[alt.rule].append({
                    "actual": actual_return,
                    "alt_return": alt.return_pct,
                    "triggered": alt.triggered,
                })

            # 손절 규칙
            for pct in stop_losses:
                alt = self._simulate_stop_loss(candles, entry_idx, exit_idx, entry_price, pct)
                alternatives.append(alt)
                rule_results[alt.rule].append({
                    "actual": actual_return,
                    "alt_return": alt.return_pct,
                    "triggered": alt.triggered,
                })

            # 익절 규칙
            for pct in take_profits:
                alt = self._simulate_take_profit(candles, entry_idx, exit_idx, entry_price, pct)
                alternatives.append(alt)
                rule_results[alt.rule].append({
                    "actual": actual_return,
                    "alt_return": alt.return_pct,
                    "triggered": alt.triggered,
                })

            # 반익절
            for pct in half_profits:
                alt = self._simulate_half_profit(candles, entry_idx, exit_idx, entry_price, exit_price, pct)
                alternatives.append(alt)
                rule_results[alt.rule].append({
                    "actual": actual_return,
                    "alt_return": alt.return_pct,
                    "triggered": alt.triggered,
                })

            result_positions.append(WhatIfPosition(
                position_id=str(pos.id),
                stock_code=pos.ticker,
                stock_name=stock_name,
                entry_date=str(pos.entry_date),
                exit_date=str(pos.exit_date),
                entry_price=entry_price,
                exit_price=exit_price,
                actual_return_pct=actual_return,
                holding_days=holding_days,
                alternatives=alternatives,
            ))

        # 규칙별 집계
        rule_summaries: list[WhatIfRuleSummary] = []
        for rule_name, results in rule_results.items():
            applicable = [r for r in results if r["alt_return"] is not None]
            triggered = [r for r in applicable if r["triggered"]]
            if not applicable:
                continue
            avg_return = round(sum(r["alt_return"] for r in applicable) / len(applicable), 2)
            diffs = [r["alt_return"] - r["actual"] for r in applicable]
            avg_diff = round(sum(diffs) / len(diffs), 2) if diffs else 0
            better = len([d for d in diffs if d > 0])
            worse = len([d for d in diffs if d < 0])
            rule_summaries.append(WhatIfRuleSummary(
                rule=rule_name,
                applicable_count=len(applicable),
                triggered_count=len(triggered),
                avg_return_pct=avg_return,
                total_diff_pct=avg_diff,
                better_count=better,
                worse_count=worse,
            ))

        actual_returns = [p.actual_return_pct for p in result_positions]
        actual_avg = round(sum(actual_returns) / len(actual_returns), 2) if actual_returns else 0

        return WhatIfResponse(
            positions=result_positions,
            rule_summaries=rule_summaries,
            actual_avg_return_pct=actual_avg,
        )

    def _simulate_hold_shift(
        self, candles: list[StockOHLCV], entry_idx: int, exit_idx: int,
        entry_price: float, day_shift: int
    ) -> WhatIfAlternative:
        new_exit_idx = exit_idx + day_shift
        rule = f"{'+' if day_shift > 0 else ''}{day_shift}일 보유"
        if new_exit_idx < entry_idx + 1 or new_exit_idx >= len(candles):
            return WhatIfAlternative(rule=rule, triggered=False)
        new_exit_price = float(candles[new_exit_idx].close_price)
        ret = round((new_exit_price - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0
        actual_ret = round((float(candles[exit_idx].close_price) - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0
        return WhatIfAlternative(
            rule=rule,
            triggered=True,
            exit_date=str(candles[new_exit_idx].trade_date),
            exit_price=new_exit_price,
            return_pct=ret,
            diff_pct=round(ret - actual_ret, 2),
        )

    def _simulate_stop_loss(
        self, candles: list[StockOHLCV], entry_idx: int, exit_idx: int,
        entry_price: float, stop_pct: int
    ) -> WhatIfAlternative:
        rule = f"{stop_pct}% 손절"
        threshold = entry_price * (1 + stop_pct / 100)
        actual_exit_price = float(candles[exit_idx].close_price)
        actual_ret = round((actual_exit_price - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0

        for i in range(entry_idx + 1, exit_idx + 1):
            if float(candles[i].low_price) <= threshold:
                exit_price = threshold
                ret = round((exit_price - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0
                return WhatIfAlternative(
                    rule=rule,
                    triggered=True,
                    exit_date=str(candles[i].trade_date),
                    exit_price=round(exit_price, 2),
                    return_pct=ret,
                    diff_pct=round(ret - actual_ret, 2),
                )
        # 트리거되지 않음 → 원래 결과
        return WhatIfAlternative(
            rule=rule,
            triggered=False,
            exit_date=str(candles[exit_idx].trade_date),
            exit_price=actual_exit_price,
            return_pct=actual_ret,
            diff_pct=0,
        )

    def _simulate_take_profit(
        self, candles: list[StockOHLCV], entry_idx: int, exit_idx: int,
        entry_price: float, target_pct: int
    ) -> WhatIfAlternative:
        rule = f"+{target_pct}% 익절"
        threshold = entry_price * (1 + target_pct / 100)
        actual_exit_price = float(candles[exit_idx].close_price)
        actual_ret = round((actual_exit_price - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0

        for i in range(entry_idx + 1, exit_idx + 1):
            if float(candles[i].high_price) >= threshold:
                ret = float(target_pct)
                return WhatIfAlternative(
                    rule=rule,
                    triggered=True,
                    exit_date=str(candles[i].trade_date),
                    exit_price=round(threshold, 2),
                    return_pct=ret,
                    diff_pct=round(ret - actual_ret, 2),
                )
        return WhatIfAlternative(
            rule=rule,
            triggered=False,
            exit_date=str(candles[exit_idx].trade_date),
            exit_price=actual_exit_price,
            return_pct=actual_ret,
            diff_pct=0,
        )

    def _simulate_half_profit(
        self, candles: list[StockOHLCV], entry_idx: int, exit_idx: int,
        entry_price: float, actual_exit_price: float, target_pct: int
    ) -> WhatIfAlternative:
        rule = f"+{target_pct}% 반익절"
        threshold = entry_price * (1 + target_pct / 100)
        actual_ret = round((actual_exit_price - entry_price) / entry_price * 100, 2) if entry_price > 0 else 0

        for i in range(entry_idx + 1, exit_idx + 1):
            if float(candles[i].high_price) >= threshold:
                # 50%는 목표가에 청산
                half_ret = float(target_pct)
                # 나머지 50%는 원래 청산일에 청산
                other_ret = actual_ret
                blended = round((half_ret + other_ret) / 2, 2)
                return WhatIfAlternative(
                    rule=rule,
                    triggered=True,
                    exit_date=str(candles[i].trade_date),
                    exit_price=round(threshold, 2),
                    return_pct=blended,
                    diff_pct=round(blended - actual_ret, 2),
                )
        return WhatIfAlternative(
            rule=rule,
            triggered=False,
            exit_date=str(candles[exit_idx].trade_date),
            exit_price=actual_exit_price,
            return_pct=actual_ret,
            diff_pct=0,
        )

    # ── Feature 2: 매매 컨텍스트 타임라인 ─────────────────

    async def trade_context(self, position_id: str) -> TradeContextResponse:
        from uuid import UUID
        pid = UUID(position_id)
        result = await self.db.execute(
            select(Position).where(Position.id == pid)
        )
        pos = result.scalar_one_or_none()
        if not pos:
            return TradeContextResponse(position_id=position_id, stock_code="", stock_name="", entry_date="", entry_price=0)

        # 매매 기록
        result = await self.db.execute(
            select(Trade).where(Trade.position_id == pid).order_by(Trade.trade_date)
        )
        trades = list(result.scalars().all())
        stock_name = pos.ticker
        for t in trades:
            if t.stock_name:
                stock_name = t.stock_name
                break

        entry_price = float(pos.entry_price)
        exit_price = float(pos.exit_price) if pos.exit_price else None
        return_pct = round((exit_price - entry_price) / entry_price * 100, 2) if exit_price and entry_price > 0 else None

        # OHLCV
        earliest = pos.entry_date - timedelta(days=60)
        latest = pos.exit_date or pos.entry_date
        latest_ext = latest + timedelta(days=30)
        ohlcv_result = await self.db.execute(
            select(StockOHLCV).where(
                and_(
                    StockOHLCV.stock_code == pos.ticker,
                    StockOHLCV.trade_date >= earliest,
                    StockOHLCV.trade_date <= latest_ext,
                )
            ).order_by(StockOHLCV.trade_date)
        )
        candles = list(ohlcv_result.scalars().all())

        ohlcv_data = [c.to_chart_dict() for c in candles]

        # 매매 마커
        trade_markers = []
        for t in trades:
            trade_markers.append({
                "time": _date_to_ts(t.trade_date),
                "type": t.trade_type.value if hasattr(t.trade_type, 'value') else str(t.trade_type),
                "price": float(t.price),
            })

        # 수급 데이터
        flow_result = await self.db.execute(
            select(StockInvestorFlow).where(
                and_(
                    StockInvestorFlow.stock_code == pos.ticker,
                    StockInvestorFlow.flow_date >= earliest,
                    StockInvestorFlow.flow_date <= latest_ext,
                )
            ).order_by(StockInvestorFlow.flow_date)
        )
        flows = list(flow_result.scalars().all())
        flow_bars = [
            FlowBar(
                date=str(f.flow_date),
                foreign_net=float(f.foreign_net_amount),
                institution_net=float(f.institution_net_amount),
            )
            for f in flows
        ]

        # KOSPI 지수 (상대강도 계산)
        index_candles = await self._load_market_index("0001", earliest, latest_ext)
        relative_strength = self._calc_relative_strength(candles, index_candles, pos.entry_date)

        # 요약 생성
        summary = self._build_context_summary(pos, trades, flows, candles, index_candles)

        return TradeContextResponse(
            position_id=str(pos.id),
            stock_code=pos.ticker,
            stock_name=stock_name,
            entry_date=str(pos.entry_date),
            exit_date=str(pos.exit_date) if pos.exit_date else None,
            entry_price=entry_price,
            exit_price=exit_price,
            return_pct=return_pct,
            ohlcv=ohlcv_data,
            trade_markers=trade_markers,
            flow_bars=flow_bars,
            relative_strength=relative_strength,
            summary=summary,
        )

    def _calc_relative_strength(
        self, stock_candles: list[StockOHLCV], index_candles: list[MarketIndexOHLCV],
        base_date: date
    ) -> list[RelativeStrengthPoint]:
        if not stock_candles or not index_candles:
            return []

        # 기준일 종가 찾기
        stock_base = None
        for c in stock_candles:
            if c.trade_date <= base_date:
                stock_base = float(c.close_price)
            elif stock_base is None:
                stock_base = float(c.close_price)
                break

        index_base = None
        for c in index_candles:
            if c.trade_date <= base_date:
                index_base = float(c.close_value) if c.close_value else None
            elif index_base is None and c.close_value:
                index_base = float(c.close_value)
                break

        if not stock_base or not index_base:
            return []

        # 지수 날짜별 맵
        index_map = {c.trade_date: float(c.close_value) for c in index_candles if c.close_value}

        points = []
        for c in stock_candles:
            idx_val = index_map.get(c.trade_date)
            if idx_val is None:
                continue
            stock_ret = (float(c.close_price) - stock_base) / stock_base * 100
            index_ret = (idx_val - index_base) / index_base * 100
            excess = round(stock_ret - index_ret, 2)
            points.append(RelativeStrengthPoint(date=str(c.trade_date), value=excess))

        return points

    def _build_context_summary(
        self, pos: Position, trades: list[Trade], flows: list[StockInvestorFlow],
        candles: list[StockOHLCV], index_candles: list[MarketIndexOHLCV]
    ) -> dict:
        summary: dict = {}

        # 진입 시 외인 연속 순매수
        if flows and pos.entry_date:
            streak, direction = self._calc_flow_streak(flows, pos.entry_date, "foreign")
            if streak > 0:
                summary["entry_foreign_streak"] = f"외인 {streak}일 연속 순{direction}"

            streak_inst, dir_inst = self._calc_flow_streak(flows, pos.entry_date, "institution")
            if streak_inst > 0:
                summary["entry_institution_streak"] = f"기관 {streak_inst}일 연속 순{dir_inst}"

        # KOSPI 대비 수익률
        if candles and index_candles and pos.entry_date and pos.exit_date:
            entry_idx = self._get_ohlcv_index(candles, pos.entry_date)
            exit_idx = self._get_ohlcv_index(candles, pos.exit_date)
            if entry_idx is not None and exit_idx is not None:
                stock_ret = (float(candles[exit_idx].close_price) - float(candles[entry_idx].close_price)) / float(candles[entry_idx].close_price) * 100
                idx_map = {c.trade_date: float(c.close_value) for c in index_candles if c.close_value}
                idx_entry = idx_map.get(pos.entry_date)
                idx_exit = idx_map.get(pos.exit_date)
                if idx_entry and idx_exit:
                    idx_ret = (idx_exit - idx_entry) / idx_entry * 100
                    excess = round(stock_ret - idx_ret, 1)
                    summary["vs_kospi"] = f"KOSPI 대비 {'+' if excess >= 0 else ''}{excess}%"

        return summary

    def _calc_flow_streak(
        self, flows: list[StockInvestorFlow], target_date: date, investor: str
    ) -> tuple[int, str]:
        # target_date 이전 수급 데이터 역순
        past_flows = [f for f in flows if f.flow_date <= target_date]
        past_flows.sort(key=lambda f: f.flow_date, reverse=True)
        if not past_flows:
            return 0, ""

        field = "foreign_net_amount" if investor == "foreign" else "institution_net_amount"
        first_val = getattr(past_flows[0], field, 0)
        if first_val == 0:
            return 0, ""

        direction = "매수" if first_val > 0 else "매도"
        streak = 0
        for f in past_flows:
            val = getattr(f, field, 0)
            if (first_val > 0 and val > 0) or (first_val < 0 and val < 0):
                streak += 1
            else:
                break
        return streak, direction

    # ── Feature 3: 수급 연동 승률 ────────────────────────

    async def flow_linked_winrate(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> FlowWinRateResponse:
        positions = await self._load_closed_positions(start_date, end_date)
        if not positions:
            return FlowWinRateResponse()

        pos_ids = [p.id for p in positions]
        trade_map = await self._load_trades_for_positions(pos_ids)

        stock_codes = {p.ticker for p in positions}
        dates = [d for p in positions for d in [p.entry_date, p.exit_date] if d]
        if not dates:
            return FlowWinRateResponse()

        flow_map = await self._load_investor_flow_bulk(stock_codes, min(dates), max(dates))

        # 4분면 분류
        quadrant_data: dict[str, list[dict]] = {
            "both_buy": [],
            "foreign_buy": [],
            "institution_buy": [],
            "both_sell": [],
        }
        contra_list: list[ContraTrade] = []

        flow_available = 0

        for pos in positions:
            if not pos.entry_date or not pos.exit_price or not pos.entry_price:
                continue

            flows = flow_map.get(pos.ticker, [])
            # 진입일 전후 3일 수급 합산
            entry_flows = [
                f for f in flows
                if pos.entry_date - timedelta(days=3) <= f.flow_date <= pos.entry_date
            ]
            if not entry_flows:
                continue

            flow_available += 1
            foreign_sum = sum(f.foreign_net_amount for f in entry_flows)
            inst_sum = sum(f.institution_net_amount for f in entry_flows)

            return_pct = float(pos.realized_return_pct) if pos.realized_return_pct is not None else 0
            is_win = return_pct > 0
            stock_name = self._get_stock_name(pos, trade_map)

            quadrant = self._categorize_flow(foreign_sum, inst_sum)
            quadrant_data[quadrant].append({
                "return_pct": return_pct,
                "is_win": is_win,
            })

            # 수급 역행 매매
            if quadrant == "both_sell":
                contra_list.append(ContraTrade(
                    stock_code=pos.ticker,
                    stock_name=stock_name,
                    entry_date=str(pos.entry_date),
                    return_pct=round(return_pct, 2),
                    foreign_net=float(foreign_sum),
                    institution_net=float(inst_sum),
                ))

        # 분면별 집계
        quadrant_labels = {
            "both_buy": ("외인+기관+", "쌍끌이 매수"),
            "foreign_buy": ("외인+기관-", "외인 주도"),
            "institution_buy": ("외인-기관+", "기관 주도"),
            "both_sell": ("외인-기관-", "수급 역행"),
        }

        quadrants: list[FlowQuadrant] = []
        for key, (name, label) in quadrant_labels.items():
            data = quadrant_data[key]
            trade_count = len(data)
            win_count = len([d for d in data if d["is_win"]])
            win_rate = round(win_count / trade_count * 100, 1) if trade_count > 0 else 0
            avg_ret = round(sum(d["return_pct"] for d in data) / trade_count, 2) if trade_count > 0 else 0
            quadrants.append(FlowQuadrant(
                name=name, label=label,
                trade_count=trade_count,
                win_count=win_count,
                win_rate=win_rate,
                avg_return_pct=avg_ret,
            ))

        # 인사이트
        insight = self._generate_flow_insight(quadrants, contra_list)

        return FlowWinRateResponse(
            quadrants=quadrants,
            contra_trades=sorted(contra_list, key=lambda x: x.return_pct),
            total_trades=len(positions),
            flow_available_trades=flow_available,
            insight=insight,
        )

    def _categorize_flow(self, foreign_sum: float, inst_sum: float) -> str:
        if foreign_sum >= 0 and inst_sum >= 0:
            return "both_buy"
        elif foreign_sum >= 0 and inst_sum < 0:
            return "foreign_buy"
        elif foreign_sum < 0 and inst_sum >= 0:
            return "institution_buy"
        else:
            return "both_sell"

    def _generate_flow_insight(self, quadrants: list[FlowQuadrant], contras: list[ContraTrade]) -> str:
        parts = []
        best = max(quadrants, key=lambda q: q.win_rate) if quadrants else None
        worst = min(quadrants, key=lambda q: q.win_rate) if quadrants else None

        if best and best.trade_count >= 2:
            parts.append(f"최고 승률: {best.label} ({best.win_rate}%, {best.trade_count}건)")
        if worst and worst.trade_count >= 2:
            parts.append(f"최저 승률: {worst.label} ({worst.win_rate}%, {worst.trade_count}건)")
        if contras:
            win_contras = len([c for c in contras if c.return_pct > 0])
            parts.append(f"수급 역행 매매 {len(contras)}건 중 {win_contras}건 수익")

        return " | ".join(parts) if parts else "수급 데이터 부족"

    # ── Feature 4: 유사 매매 클러스터링 ──────────────────

    async def trade_clusters(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> ClusterResponse:
        positions = await self._load_closed_positions(start_date, end_date)
        if not positions:
            return ClusterResponse()

        pos_ids = [p.id for p in positions]
        trade_map = await self._load_trades_for_positions(pos_ids)

        stock_codes = {p.ticker for p in positions}
        dates = [d for p in positions for d in [p.entry_date, p.exit_date] if d]
        if not dates:
            return ClusterResponse()

        ohlcv_map = await self._load_ohlcv_bulk(stock_codes, min(dates), max(dates))

        cluster_map: dict[str, list[dict]] = defaultdict(list)
        classified_count = 0

        for pos in positions:
            candles = ohlcv_map.get(pos.ticker, [])
            if not candles or not pos.entry_date or not pos.exit_date:
                continue

            entry_idx = self._get_ohlcv_index(candles, pos.entry_date)
            if entry_idx is None or entry_idx < 20:
                continue

            entry_price = float(pos.entry_price)
            holding_days = (pos.exit_date - pos.entry_date).days
            return_pct = float(pos.realized_return_pct) if pos.realized_return_pct is not None else 0
            stock_name = self._get_stock_name(pos, trade_map)

            classification = self._classify_entry(candles, entry_idx, entry_price, holding_days)
            if not classification:
                continue

            classified_count += 1
            pattern_key = f"MA20{classification['ma20']}_BB{classification['bb']}_거래량{classification['volume']}_보유{classification['holding']}"

            cluster_map[pattern_key].append({
                "stock_code": pos.ticker,
                "stock_name": stock_name,
                "entry_date": str(pos.entry_date),
                "return_pct": round(return_pct, 2),
                "holding_days": holding_days,
                "is_win": return_pct > 0,
            })

        # 클러스터 집계
        clusters: list[TradeCluster] = []
        for key, items in cluster_map.items():
            parts = key.split("_")
            conditions = {}
            for part in parts:
                if part.startswith("MA20"):
                    conditions["ma20"] = part[4:]
                elif part.startswith("BB"):
                    conditions["bb"] = part[2:]
                elif part.startswith("거래량"):
                    conditions["volume"] = part[3:]
                elif part.startswith("보유"):
                    conditions["holding"] = part[2:]

            win_count = len([i for i in items if i["is_win"]])
            trade_count = len(items)
            win_rate = round(win_count / trade_count * 100, 1) if trade_count > 0 else 0
            avg_ret = round(sum(i["return_pct"] for i in items) / trade_count, 2) if trade_count > 0 else 0

            cluster_trades = [
                ClusterTrade(
                    stock_code=i["stock_code"],
                    stock_name=i["stock_name"],
                    entry_date=i["entry_date"],
                    return_pct=i["return_pct"],
                    holding_days=i["holding_days"],
                )
                for i in items
            ]

            clusters.append(TradeCluster(
                pattern_key=key,
                conditions=conditions,
                trade_count=trade_count,
                win_count=win_count,
                win_rate=win_rate,
                avg_return_pct=avg_ret,
                trades=cluster_trades,
            ))

        clusters.sort(key=lambda c: c.trade_count, reverse=True)

        # 2건 이상인 클러스터에서 최적/최악
        valid_clusters = [c for c in clusters if c.trade_count >= 2]
        best = max(valid_clusters, key=lambda c: c.avg_return_pct) if valid_clusters else None
        worst = min(valid_clusters, key=lambda c: c.avg_return_pct) if valid_clusters else None

        return ClusterResponse(
            clusters=clusters,
            best_pattern=best,
            worst_pattern=worst,
            total_clustered=classified_count,
            total_positions=len(positions),
        )

    def _classify_entry(
        self, candles: list[StockOHLCV], entry_idx: int, entry_price: float, holding_days: int
    ) -> dict | None:
        if entry_idx < 20:
            return None

        # MA20 위치
        closes_20 = [float(candles[i].close_price) for i in range(entry_idx - 19, entry_idx + 1)]
        ma20 = sum(closes_20) / 20
        ma20_pct = (entry_price - ma20) / ma20 * 100 if ma20 > 0 else 0

        if ma20_pct > 3:
            ma20_pos = "위"
        elif ma20_pct < -3:
            ma20_pos = "아래"
        else:
            ma20_pos = "근접"

        # 볼린저밴드 위치
        std = (sum((c - ma20) ** 2 for c in closes_20) / 20) ** 0.5
        if std > 0:
            upper = ma20 + 2 * std
            lower = ma20 - 2 * std
            bb_pos_val = (entry_price - lower) / (upper - lower) if (upper - lower) > 0 else 0.5
        else:
            bb_pos_val = 0.5

        if bb_pos_val > 0.67:
            bb_pos = "상"
        elif bb_pos_val < 0.33:
            bb_pos = "하"
        else:
            bb_pos = "중"

        # 거래량 비율
        if entry_idx >= 20:
            today_vol = float(candles[entry_idx].volume)
            avg_vol = sum(float(candles[i].volume) for i in range(entry_idx - 19, entry_idx)) / 20
            vol_ratio = today_vol / avg_vol if avg_vol > 0 else 1
        else:
            vol_ratio = 1

        if vol_ratio > 2:
            vol_cat = "고"
        elif vol_ratio < 0.5:
            vol_cat = "저"
        else:
            vol_cat = "보통"

        # 보유기간 분류
        if holding_days <= 5:
            hold_cat = "단기"
        elif holding_days <= 20:
            hold_cat = "중기"
        else:
            hold_cat = "장기"

        return {
            "ma20": ma20_pos,
            "bb": bb_pos,
            "volume": vol_cat,
            "holding": hold_cat,
        }
