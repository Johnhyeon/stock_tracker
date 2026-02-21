import math
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
from collections import defaultdict, Counter
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import InvestmentIdea, Position, IdeaType, IdeaStatus, Trade, TradeType
from schemas.analysis import TimelineAnalysis, TimelineEntry, FomoAnalysis, FomoExit


class AnalysisService:
    def __init__(self, db: Session):
        self.db = db

    def get_timeline_analysis(self) -> TimelineAnalysis:
        positions = (
            self.db.query(Position)
            .join(InvestmentIdea)
            .filter(Position.exit_date.isnot(None))
            .all()
        )

        entries = []
        early_exits = 0
        on_time_exits = 0
        late_exits = 0
        time_diffs = []

        for pos in positions:
            idea = pos.idea
            expected_exit_date = pos.entry_date.toordinal() + idea.expected_timeframe_days
            actual_exit_date = pos.exit_date.toordinal()
            time_diff = actual_exit_date - expected_exit_date

            if time_diff < -7:
                early_exits += 1
            elif time_diff > 7:
                late_exits += 1
            else:
                on_time_exits += 1

            time_diffs.append(time_diff)

            entries.append(TimelineEntry(
                idea_id=idea.id,
                idea_type=idea.type,
                ticker=pos.ticker,
                entry_date=pos.entry_date,
                exit_date=pos.exit_date,
                days_held=pos.days_held,
                expected_days=idea.expected_timeframe_days,
                time_diff_days=time_diff,
                return_pct=pos.realized_return_pct,
                exit_reason=pos.exit_reason,
            ))

        avg_time_diff = sum(time_diffs) / len(time_diffs) if time_diffs else 0

        return TimelineAnalysis(
            entries=entries,
            avg_time_diff=avg_time_diff,
            early_exits=early_exits,
            on_time_exits=on_time_exits,
            late_exits=late_exits,
        )

    def get_fomo_analysis(self) -> FomoAnalysis:
        fomo_positions = (
            self.db.query(Position)
            .join(InvestmentIdea)
            .filter(
                and_(
                    Position.exit_reason == "fomo",
                    InvestmentIdea.type == IdeaType.RESEARCH,
                )
            )
            .all()
        )

        fomo_exits = []
        missed_returns = []

        for pos in fomo_positions:
            exit_return = pos.realized_return_pct or 0

            fomo_exits.append(FomoExit(
                idea_id=pos.idea_id,
                ticker=pos.ticker,
                exit_date=pos.exit_date,
                exit_return_pct=exit_return,
                days_after_exit=0,
                price_after_exit=None,
                missed_return_pct=None,
            ))

        avg_missed = sum(missed_returns) / len(missed_returns) if missed_returns else None

        return FomoAnalysis(
            fomo_exits=fomo_exits,
            total_fomo_exits=len(fomo_exits),
            avg_missed_return_pct=avg_missed,
            total_missed_opportunity=None,
            summary={
                "message": f"총 {len(fomo_exits)}건의 FOMO 청산이 있었습니다.",
                "recommendation": "리서치 기반 투자는 논리가 유효한 동안 보유하세요." if fomo_exits else None,
            },
        )

    def get_performance_by_type(self) -> dict:
        ideas = self.db.query(InvestmentIdea).filter(InvestmentIdea.status == IdeaStatus.EXITED).all()

        research_returns = []
        chart_returns = []

        for idea in ideas:
            for pos in idea.positions:
                if pos.realized_return_pct is not None:
                    if idea.type == IdeaType.RESEARCH:
                        research_returns.append(pos.realized_return_pct)
                    else:
                        chart_returns.append(pos.realized_return_pct)

        return {
            "research": {
                "count": len(research_returns),
                "avg_return": sum(research_returns) / len(research_returns) if research_returns else None,
                "win_rate": len([r for r in research_returns if r > 0]) / len(research_returns) if research_returns else None,
            },
            "chart": {
                "count": len(chart_returns),
                "avg_return": sum(chart_returns) / len(chart_returns) if chart_returns else None,
                "win_rate": len([r for r in chart_returns if r > 0]) / len(chart_returns) if chart_returns else None,
            },
        }

    def get_risk_metrics(self, start_date: date | None = None, end_date: date | None = None) -> dict:
        """리스크 지표 종합 분석.

        MDD, 샤프 비율, 승률 추이, 연속 손실, 포지션 집중도를 계산합니다.
        """
        # 청산된 포지션 (날짜순)
        query = (
            self.db.query(Position)
            .filter(Position.exit_date.isnot(None))
            .order_by(Position.exit_date)
        )
        if start_date:
            query = query.filter(Position.exit_date >= start_date)
        if end_date:
            query = query.filter(Position.exit_date <= end_date)
        closed_positions = query.all()

        returns = []
        for pos in closed_positions:
            if pos.realized_return_pct is not None:
                returns.append({
                    "return_pct": float(pos.realized_return_pct),
                    "exit_date": pos.exit_date.isoformat() if pos.exit_date else None,
                    "ticker": pos.ticker,
                    "profit": float((pos.exit_price - pos.entry_price) * pos.quantity) if pos.exit_price else 0,
                })

        # 1. MDD (Maximum Drawdown) - 누적 수익 기반
        mdd = self._calc_mdd(returns)

        # 2. 샤프 비율 (무위험 수익률 3% 가정)
        sharpe = self._calc_sharpe(returns, risk_free_annual=3.0)

        # 3. 승률 추이 (최근 10건씩 롤링)
        win_rate_trend = self._calc_win_rate_trend(returns, window=10)

        # 4. 연속 손실/승리
        streak = self._calc_streaks(returns)

        # 5. 포지션 집중도 (현재 활성 포지션 기준)
        concentration = self._calc_concentration()

        # 6. 손익비 (Profit Factor)
        profit_factor = self._calc_profit_factor(returns)

        return {
            "mdd": mdd,
            "sharpe_ratio": sharpe,
            "win_rate_trend": win_rate_trend,
            "streak": streak,
            "concentration": concentration,
            "profit_factor": profit_factor,
            "total_closed_trades": len(returns),
        }

    def _calc_mdd(self, returns: list) -> dict:
        if not returns:
            return {"max_drawdown_pct": 0, "peak_date": None, "trough_date": None}

        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        peak_date = returns[0]["exit_date"] if returns else None
        trough_date = None

        for r in returns:
            cumulative += r["return_pct"]
            if cumulative > peak:
                peak = cumulative
                peak_date = r["exit_date"]
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
                trough_date = r["exit_date"]

        return {
            "max_drawdown_pct": round(max_dd, 2),
            "peak_date": peak_date,
            "trough_date": trough_date,
        }

    def _calc_sharpe(self, returns: list, risk_free_annual: float = 3.0) -> Optional[float]:
        if len(returns) < 2:
            return None
        pcts = [r["return_pct"] for r in returns]
        avg = sum(pcts) / len(pcts)
        std = math.sqrt(sum((x - avg) ** 2 for x in pcts) / (len(pcts) - 1))
        if std == 0:
            return None
        # 거래당 수익률 기준 샤프 (연환산 아닌 거래 단위)
        risk_free_per_trade = risk_free_annual / max(len(pcts), 1)
        return round((avg - risk_free_per_trade) / std, 2)

    def _calc_win_rate_trend(self, returns: list, window: int = 10) -> list:
        if not returns:
            return []
        trend = []
        for i in range(window, len(returns) + 1):
            window_returns = returns[i - window:i]
            wins = sum(1 for r in window_returns if r["return_pct"] > 0)
            trend.append({
                "trade_index": i,
                "date": window_returns[-1]["exit_date"],
                "win_rate": round(wins / window * 100, 1),
            })
        return trend

    def _calc_streaks(self, returns: list) -> dict:
        if not returns:
            return {"max_win_streak": 0, "max_loss_streak": 0, "current_streak": 0, "current_type": None}

        max_win = 0
        max_loss = 0
        current = 0
        current_type = None

        for r in returns:
            is_win = r["return_pct"] > 0
            if current_type is None:
                current_type = "win" if is_win else "loss"
                current = 1
            elif (current_type == "win" and is_win) or (current_type == "loss" and not is_win):
                current += 1
            else:
                if current_type == "win":
                    max_win = max(max_win, current)
                else:
                    max_loss = max(max_loss, current)
                current_type = "win" if is_win else "loss"
                current = 1

        # 마지막 streak 반영
        if current_type == "win":
            max_win = max(max_win, current)
        elif current_type == "loss":
            max_loss = max(max_loss, current)

        return {
            "max_win_streak": max_win,
            "max_loss_streak": max_loss,
            "current_streak": current,
            "current_type": current_type,
        }

    def _calc_concentration(self) -> dict:
        active_positions = (
            self.db.query(Position)
            .join(InvestmentIdea)
            .filter(
                InvestmentIdea.status == IdeaStatus.ACTIVE,
                Position.exit_date.is_(None),
            )
            .all()
        )

        if not active_positions:
            return {"hhi": 0, "top_holding_pct": 0, "holdings": []}

        holdings = defaultdict(float)
        total = 0.0
        for pos in active_positions:
            amount = float(pos.entry_price) * pos.quantity
            holdings[pos.ticker] += amount
            total += amount

        if total == 0:
            return {"hhi": 0, "top_holding_pct": 0, "holdings": []}

        sorted_holdings = sorted(holdings.items(), key=lambda x: x[1], reverse=True)
        weights = [(ticker, amount / total * 100) for ticker, amount in sorted_holdings]

        # HHI (Herfindahl-Hirschman Index): 0~10000, 높을수록 집중
        hhi = sum(w ** 2 for _, w in weights)

        return {
            "hhi": round(hhi, 0),
            "top_holding_pct": round(weights[0][1], 1) if weights else 0,
            "holdings": [
                {"ticker": t, "weight_pct": round(w, 1)}
                for t, w in weights[:10]
            ],
        }

    def _calc_profit_factor(self, returns: list) -> Optional[float]:
        total_profit = sum(r["return_pct"] for r in returns if r["return_pct"] > 0)
        total_loss = abs(sum(r["return_pct"] for r in returns if r["return_pct"] < 0))
        if total_loss == 0:
            return None if total_profit == 0 else float("inf")
        return round(total_profit / total_loss, 2)

    # ── 매매 습관/심리 분석 ──

    def get_trade_habits(self, start_date: date | None = None, end_date: date | None = None) -> dict:
        """매매 습관/심리 분석 종합."""
        # 매도 거래 (실현손익이 있는 건)
        sell_query = (
            self.db.query(Trade)
            .filter(
                Trade.trade_type.in_([TradeType.SELL, TradeType.PARTIAL_SELL]),
                Trade.realized_profit.isnot(None),
            )
            .order_by(Trade.trade_date, Trade.created_at)
        )
        if start_date:
            sell_query = sell_query.filter(Trade.trade_date >= start_date)
        if end_date:
            sell_query = sell_query.filter(Trade.trade_date <= end_date)
        sell_trades = sell_query.all()

        # 청산 포지션
        pos_query = (
            self.db.query(Position)
            .filter(Position.exit_date.isnot(None))
            .order_by(Position.exit_date)
        )
        if start_date:
            pos_query = pos_query.filter(Position.exit_date >= start_date)
        if end_date:
            pos_query = pos_query.filter(Position.exit_date <= end_date)
        closed_positions = pos_query.all()

        total_sell_trades = len(sell_trades)

        if total_sell_trades < 2:
            return {
                "total_sell_trades": total_sell_trades,
                "expectancy": None,
                "win_loss_ratio": None,
                "holding_period": None,
                "sequential_pattern": None,
                "weekday_performance": None,
                "frequency_analysis": None,
            }

        return {
            "total_sell_trades": total_sell_trades,
            "expectancy": self._calc_expectancy(sell_trades),
            "win_loss_ratio": self._calc_win_loss_ratio(sell_trades),
            "holding_period": self._calc_holding_period(closed_positions),
            "sequential_pattern": self._calc_sequential_pattern(sell_trades),
            "weekday_performance": self._calc_weekday_performance(sell_trades),
            "frequency_analysis": self._calc_frequency_analysis(sell_trades),
        }

    def _calc_expectancy(self, trades: list) -> dict:
        """기대값: (승률 × 평균수익) - (패률 × 평균손실)."""
        wins = [t for t in trades if float(t.realized_profit or 0) > 0]
        losses = [t for t in trades if float(t.realized_profit or 0) < 0]
        total = len(trades)

        win_rate = len(wins) / total if total else 0
        loss_rate = len(losses) / total if total else 0

        avg_win_amount = sum(float(t.realized_profit) for t in wins) / len(wins) if wins else 0
        avg_loss_amount = abs(sum(float(t.realized_profit) for t in losses) / len(losses)) if losses else 0

        avg_win_pct = sum(float(t.realized_return_pct or 0) for t in wins) / len(wins) if wins else 0
        avg_loss_pct = abs(sum(float(t.realized_return_pct or 0) for t in losses) / len(losses)) if losses else 0

        expectancy = (win_rate * avg_win_amount) - (loss_rate * avg_loss_amount)
        expectancy_pct = (win_rate * avg_win_pct) - (loss_rate * avg_loss_pct)

        return {
            "expectancy": round(expectancy, 0),
            "expectancy_pct": round(expectancy_pct, 2),
            "avg_win_amount": round(avg_win_amount, 0),
            "avg_loss_amount": round(avg_loss_amount, 0),
            "avg_win_pct": round(avg_win_pct, 2),
            "avg_loss_pct": round(avg_loss_pct, 2),
            "win_rate": round(win_rate * 100, 1),
            "loss_rate": round(loss_rate * 100, 1),
            "is_positive": expectancy > 0,
        }

    def _calc_win_loss_ratio(self, trades: list) -> dict:
        """평균 손익비 = 평균수익률 / 평균손실률."""
        wins = [t for t in trades if float(t.realized_return_pct or 0) > 0]
        losses = [t for t in trades if float(t.realized_return_pct or 0) < 0]

        avg_win_pct = sum(float(t.realized_return_pct) for t in wins) / len(wins) if wins else 0
        avg_loss_pct = abs(sum(float(t.realized_return_pct) for t in losses) / len(losses)) if losses else 0

        ratio = avg_win_pct / avg_loss_pct if avg_loss_pct > 0 else 0

        if ratio >= 2:
            grade, comment = "excellent", "우수한 손익비입니다. 수익 매매에서 충분히 이익을 취하고 있습니다."
        elif ratio >= 1.5:
            grade, comment = "good", "양호한 손익비입니다. 손절을 잘 하고 있습니다."
        elif ratio >= 1:
            grade, comment = "average", "보통 수준입니다. 수익 시 더 오래 보유하는 연습이 필요합니다."
        else:
            grade, comment = "poor", "손익비가 낮습니다. 손실이 이익보다 크므로 손절 라인을 점검하세요."

        return {
            "ratio": round(ratio, 2),
            "avg_win_pct": round(avg_win_pct, 2),
            "avg_loss_pct": round(avg_loss_pct, 2),
            "grade": grade,
            "comment": comment,
        }

    def _calc_holding_period(self, positions: list) -> dict:
        """보유기간 분석: 수익/손실 매매별 평균 보유일, 구간별 통계."""
        if not positions:
            return {
                "avg_win_days": 0, "avg_loss_days": 0,
                "diagnosis": "데이터 부족", "by_period": [],
            }

        win_days = []
        loss_days = []
        period_buckets = {
            "1주 이내": {"min": 0, "max": 7, "trades": []},
            "1-2주": {"min": 8, "max": 14, "trades": []},
            "2-4주": {"min": 15, "max": 28, "trades": []},
            "1개월+": {"min": 29, "max": 9999, "trades": []},
        }

        for pos in positions:
            days = pos.days_held or 0
            ret = pos.realized_return_pct
            if ret is None:
                continue
            ret = float(ret)
            is_win = ret > 0

            if is_win:
                win_days.append(days)
            else:
                loss_days.append(days)

            for label, bucket in period_buckets.items():
                if bucket["min"] <= days <= bucket["max"]:
                    bucket["trades"].append({"is_win": is_win, "return_pct": ret})
                    break

        avg_win = sum(win_days) / len(win_days) if win_days else 0
        avg_loss = sum(loss_days) / len(loss_days) if loss_days else 0

        # 진단
        if avg_loss > 0 and avg_win > 0:
            if avg_loss > avg_win * 1.5:
                diagnosis = "손절이 느린 편입니다. 손실 매매 보유기간이 수익 매매보다 {:.0f}일 깁니다.".format(avg_loss - avg_win)
            elif avg_win < avg_loss * 0.7:
                diagnosis = "익절이 빠른 편입니다. 수익 매매를 좀 더 보유하는 것을 고려하세요."
            else:
                diagnosis = "보유기간 관리가 양호합니다."
        else:
            diagnosis = "분석에 필요한 데이터가 부족합니다."

        by_period = []
        for label, bucket in period_buckets.items():
            ts = bucket["trades"]
            count = len(ts)
            if count == 0:
                by_period.append({"period": label, "count": 0, "win_rate": 0, "avg_return_pct": 0})
                continue
            wins = sum(1 for t in ts if t["is_win"])
            avg_ret = sum(t["return_pct"] for t in ts) / count
            by_period.append({
                "period": label,
                "count": count,
                "win_rate": round(wins / count * 100, 1),
                "avg_return_pct": round(avg_ret, 2),
            })

        return {
            "avg_win_days": round(avg_win, 1),
            "avg_loss_days": round(avg_loss, 1),
            "diagnosis": diagnosis,
            "by_period": by_period,
        }

    def _calc_sequential_pattern(self, trades: list) -> dict:
        """승패 후 매매 패턴 분석: 복수매매/자만매매 감지."""
        if len(trades) < 3:
            return {
                "after_win": None, "after_loss": None, "after_streak_loss": None,
                "revenge_trading_detected": False, "overconfidence_detected": False,
            }

        results = [float(t.realized_return_pct or 0) for t in trades]
        overall_win_rate = sum(1 for r in results if r > 0) / len(results) * 100
        overall_avg_return = sum(results) / len(results)

        after_win_results = []
        after_loss_results = []
        after_streak_loss_results = []

        for i in range(1, len(results)):
            prev = results[i - 1]
            curr = results[i]

            if prev > 0:
                after_win_results.append(curr)
            else:
                after_loss_results.append(curr)

            # 2연패 후
            if i >= 2 and results[i - 1] <= 0 and results[i - 2] <= 0:
                after_streak_loss_results.append(curr)

        def _stats(rs):
            if not rs:
                return {"count": 0, "win_rate": 0, "avg_return_pct": 0}
            wins = sum(1 for r in rs if r > 0)
            return {
                "count": len(rs),
                "win_rate": round(wins / len(rs) * 100, 1),
                "avg_return_pct": round(sum(rs) / len(rs), 2),
            }

        after_win = _stats(after_win_results)
        after_loss = _stats(after_loss_results)
        after_streak = _stats(after_streak_loss_results)

        # 복수매매 감지: 2연패 후 승률이 전체보다 15%p 이상 낮음
        revenge = (
            after_streak["count"] >= 3
            and after_streak["win_rate"] < overall_win_rate - 15
        )

        # 자만매매 감지: 승리 후 평균수익이 전체보다 2%p 이상 악화
        overconfidence = (
            after_win["count"] >= 3
            and after_win["avg_return_pct"] < overall_avg_return - 2
        )

        return {
            "after_win": after_win,
            "after_loss": after_loss,
            "after_streak_loss": after_streak,
            "revenge_trading_detected": revenge,
            "overconfidence_detected": overconfidence,
        }

    def _calc_weekday_performance(self, trades: list) -> dict:
        """요일별 매매 성과."""
        weekday_names = ["월", "화", "수", "목", "금"]
        buckets: dict = {i: [] for i in range(5)}

        for t in trades:
            td = t.trade_date
            if td is None:
                continue
            wd = td.weekday()
            if wd < 5:
                buckets[wd].append({
                    "return_pct": float(t.realized_return_pct or 0),
                    "profit": float(t.realized_profit or 0),
                })

        by_weekday = []
        for i in range(5):
            ts = buckets[i]
            count = len(ts)
            if count == 0:
                by_weekday.append({
                    "day": weekday_names[i], "count": 0,
                    "win_rate": 0, "avg_return_pct": 0, "total_profit": 0,
                })
                continue
            wins = sum(1 for t in ts if t["return_pct"] > 0)
            by_weekday.append({
                "day": weekday_names[i],
                "count": count,
                "win_rate": round(wins / count * 100, 1),
                "avg_return_pct": round(sum(t["return_pct"] for t in ts) / count, 2),
                "total_profit": round(sum(t["profit"] for t in ts), 0),
            })

        active = [d for d in by_weekday if d["count"] > 0]
        best_day = max(active, key=lambda d: d["win_rate"])["day"] if active else None
        worst_day = min(active, key=lambda d: d["win_rate"])["day"] if active else None

        return {
            "by_weekday": by_weekday,
            "best_day": best_day,
            "worst_day": worst_day,
        }

    def _calc_frequency_analysis(self, trades: list) -> dict:
        """매매 빈도 분석: 주간별 그룹핑, 과매매 경고."""
        weekly: dict = defaultdict(list)

        for t in trades:
            td = t.trade_date
            if td is None:
                continue
            iso = td.isocalendar()
            week_key = f"{iso[0]}-W{iso[1]:02d}"
            weekly[week_key].append(float(t.realized_return_pct or 0))

        if not weekly:
            return {
                "avg_trades_per_week": 0,
                "high_freq_stats": None, "low_freq_stats": None,
                "overtrading_warning": False, "weekly_data": [],
            }

        weeks_sorted = sorted(weekly.keys())
        counts = [len(weekly[w]) for w in weeks_sorted]
        avg_per_week = sum(counts) / len(counts)
        median_count = sorted(counts)[len(counts) // 2]

        high_freq_returns = []
        low_freq_returns = []
        for w in weeks_sorted:
            rs = weekly[w]
            if len(rs) > median_count:
                high_freq_returns.extend(rs)
            else:
                low_freq_returns.extend(rs)

        def _freq_stats(rs):
            if not rs:
                return {"count": 0, "win_rate": 0, "avg_return_pct": 0}
            wins = sum(1 for r in rs if r > 0)
            return {
                "count": len(rs),
                "win_rate": round(wins / len(rs) * 100, 1),
                "avg_return_pct": round(sum(rs) / len(rs), 2),
            }

        high_stats = _freq_stats(high_freq_returns)
        low_stats = _freq_stats(low_freq_returns)

        overtrading = (
            high_stats["count"] >= 5
            and low_stats["count"] >= 5
            and high_stats["win_rate"] < low_stats["win_rate"] - 10
        )

        # 최근 12주 데이터
        recent_weeks = weeks_sorted[-12:]
        weekly_data = []
        for w in recent_weeks:
            rs = weekly[w]
            wins = sum(1 for r in rs if r > 0)
            weekly_data.append({
                "week": w,
                "trade_count": len(rs),
                "win_rate": round(wins / len(rs) * 100, 1) if rs else 0,
                "avg_return_pct": round(sum(rs) / len(rs), 2) if rs else 0,
            })

        return {
            "avg_trades_per_week": round(avg_per_week, 1),
            "high_freq_stats": high_stats,
            "low_freq_stats": low_stats,
            "overtrading_warning": overtrading,
            "weekly_data": weekly_data,
        }
