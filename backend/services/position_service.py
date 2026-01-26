from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import Optional, List
from sqlalchemy.orm import Session

from models import Position, InvestmentIdea, IdeaStatus
from schemas import PositionCreate, PositionExit, PositionAddBuy, PositionPartialExit


class PositionService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, idea_id: UUID, data: PositionCreate) -> Optional[Position]:
        idea = self.db.query(InvestmentIdea).filter(InvestmentIdea.id == idea_id).first()
        if not idea:
            return None

        position = Position(
            idea_id=idea_id,
            ticker=data.ticker,
            entry_price=data.entry_price,
            quantity=data.quantity,
            entry_date=data.entry_date or date.today(),
            strategy_params=data.strategy_params,
            notes=data.notes,
        )

        if idea.status == IdeaStatus.WATCHING:
            idea.status = IdeaStatus.ACTIVE

        self.db.add(position)
        self.db.commit()
        self.db.refresh(position)
        return position

    def get(self, position_id: UUID) -> Optional[Position]:
        return self.db.query(Position).filter(Position.id == position_id).first()

    def get_by_idea(self, idea_id: UUID) -> List[Position]:
        return self.db.query(Position).filter(Position.idea_id == idea_id).all()

    def exit(self, position_id: UUID, data: PositionExit) -> Optional[Position]:
        position = self.get(position_id)
        if not position:
            return None

        position.exit_price = data.exit_price
        position.exit_date = data.exit_date or date.today()
        position.exit_reason = data.exit_reason

        idea = position.idea
        open_positions = [p for p in idea.positions if p.is_open and p.id != position_id]
        if not open_positions:
            idea.status = IdeaStatus.EXITED

        self.db.commit()
        self.db.refresh(position)
        return position

    def delete(self, position_id: UUID) -> bool:
        position = self.get(position_id)
        if not position:
            return False
        self.db.delete(position)
        self.db.commit()
        return True

    def add_buy(self, position_id: UUID, data: PositionAddBuy) -> Optional[Position]:
        """추가매수: 평균단가 재계산"""
        position = self.get(position_id)
        if not position or not position.is_open:
            return None

        # 기존 총액과 새로운 매수 총액
        old_total = position.entry_price * position.quantity
        new_total = data.price * data.quantity

        # 새로운 평균단가와 수량
        total_quantity = position.quantity + data.quantity
        new_avg_price = (old_total + new_total) / total_quantity

        # 포지션 업데이트
        position.entry_price = Decimal(str(round(float(new_avg_price), 2)))
        position.quantity = total_quantity

        # 추가매수 기록을 notes에 추가
        buy_date_str = (data.buy_date or date.today()).isoformat()
        add_note = f"[추가매수] {buy_date_str}: {data.quantity}주 @ {data.price:,}원"
        if position.notes:
            position.notes = f"{position.notes}\n{add_note}"
        else:
            position.notes = add_note

        self.db.commit()
        self.db.refresh(position)
        return position

    def partial_exit(self, position_id: UUID, data: PositionPartialExit) -> Optional[Position]:
        """부분매도: 일부 수량만 매도"""
        position = self.get(position_id)
        if not position or not position.is_open:
            return None

        if data.quantity > position.quantity:
            return None  # 보유 수량보다 많이 매도할 수 없음

        if data.quantity == position.quantity:
            # 전량 매도면 일반 청산 처리
            exit_data = PositionExit(
                exit_price=data.exit_price,
                exit_date=data.exit_date,
                exit_reason=data.exit_reason or "partial_exit_full"
            )
            return self.exit(position_id, exit_data)

        # 부분매도 실현손익 계산
        realized_profit = (data.exit_price - position.entry_price) * data.quantity
        realized_return_pct = float((data.exit_price - position.entry_price) / position.entry_price * 100)

        # 수량 감소
        position.quantity = position.quantity - data.quantity

        # 부분매도 기록을 notes에 추가
        exit_date_str = (data.exit_date or date.today()).isoformat()
        exit_note = f"[부분매도] {exit_date_str}: {data.quantity}주 @ {data.exit_price:,}원 (수익률: {realized_return_pct:+.2f}%, 손익: {realized_profit:+,.0f}원)"
        if data.exit_reason:
            exit_note += f" - {data.exit_reason}"
        if position.notes:
            position.notes = f"{position.notes}\n{exit_note}"
        else:
            position.notes = exit_note

        self.db.commit()
        self.db.refresh(position)
        return position
