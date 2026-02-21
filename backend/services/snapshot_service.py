"""일별 트래킹 스냅샷 서비스."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import TrackingSnapshot, InvestmentIdea, IdeaStatus, Position
from schemas import SnapshotCreate
from core.timezone import today_kst


class SnapshotService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, idea_id: UUID, data: SnapshotCreate) -> Optional[TrackingSnapshot]:
        idea = self.db.query(InvestmentIdea).filter(InvestmentIdea.id == idea_id).first()
        if not idea:
            return None

        snapshot = TrackingSnapshot(
            idea_id=idea_id,
            snapshot_date=data.snapshot_date or today_kst(),
            price_data=data.price_data,
            days_held=data.days_held,
            unrealized_return_pct=data.unrealized_return_pct,
            news_sentiment=data.news_sentiment,
            chart_signals=data.chart_signals,
            plugin_data=data.plugin_data,
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def get(self, snapshot_id: UUID) -> Optional[TrackingSnapshot]:
        return self.db.query(TrackingSnapshot).filter(TrackingSnapshot.id == snapshot_id).first()

    def get_by_idea(self, idea_id: UUID, limit: int = 30) -> List[TrackingSnapshot]:
        return (
            self.db.query(TrackingSnapshot)
            .filter(TrackingSnapshot.idea_id == idea_id)
            .order_by(TrackingSnapshot.snapshot_date.desc())
            .limit(limit)
            .all()
        )

    def get_latest(self, idea_id: UUID) -> Optional[TrackingSnapshot]:
        return (
            self.db.query(TrackingSnapshot)
            .filter(TrackingSnapshot.idea_id == idea_id)
            .order_by(TrackingSnapshot.snapshot_date.desc())
            .first()
        )

    def delete(self, snapshot_id: UUID) -> bool:
        snapshot = self.get(snapshot_id)
        if not snapshot:
            return False
        self.db.delete(snapshot)
        self.db.commit()
        return True

    def delete_old(self, idea_id: UUID, keep_days: int = 90) -> int:
        cutoff = today_kst() - timedelta(days=keep_days)
        deleted = (
            self.db.query(TrackingSnapshot)
            .filter(
                and_(
                    TrackingSnapshot.idea_id == idea_id,
                    TrackingSnapshot.snapshot_date < cutoff,
                )
            )
            .delete()
        )
        self.db.commit()
        return deleted

    def get_portfolio_summary(self) -> dict:
        """전체 포트폴리오의 최신 스냅샷 요약."""
        active_ideas = (
            self.db.query(InvestmentIdea)
            .filter(InvestmentIdea.status == IdeaStatus.ACTIVE)
            .all()
        )

        total_invested = Decimal("0")
        total_eval = Decimal("0")
        idea_summaries = []

        for idea in active_ideas:
            latest = self.get_latest(idea.id)
            if not latest or not latest.price_data:
                continue

            invested = Decimal(str(latest.price_data.get("total_invested", 0)))
            eval_amount = Decimal(str(latest.price_data.get("total_eval", 0)))
            total_invested += invested
            total_eval += eval_amount

            idea_summaries.append({
                "idea_id": str(idea.id),
                "tickers": idea.tickers,
                "snapshot_date": str(latest.snapshot_date),
                "invested": float(invested),
                "eval": float(eval_amount),
                "unrealized_return_pct": float(latest.unrealized_return_pct) if latest.unrealized_return_pct else 0,
                "days_held": latest.days_held,
            })

        total_return_pct = (
            float((total_eval - total_invested) / total_invested * 100)
            if total_invested > 0
            else 0
        )

        return {
            "total_invested": float(total_invested),
            "total_eval": float(total_eval),
            "total_unrealized_profit": float(total_eval - total_invested),
            "total_return_pct": round(total_return_pct, 2),
            "active_ideas_count": len(active_ideas),
            "ideas": idea_summaries,
        }
