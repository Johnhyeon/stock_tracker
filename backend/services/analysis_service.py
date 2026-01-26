from datetime import date
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import InvestmentIdea, Position, IdeaType, IdeaStatus
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
