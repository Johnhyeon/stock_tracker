import asyncio
import logging
from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import Optional, List
from sqlalchemy.orm import Session

from models import Position, InvestmentIdea, IdeaStatus, Stock
from models.trade import Trade, TradeType
from schemas import PositionCreate, PositionExit, PositionAddBuy, PositionPartialExit, PositionUpdate
from core.events import event_bus, Event, EventType
from core.timezone import today_kst

logger = logging.getLogger(__name__)


class PositionService:
    def __init__(self, db: Session):
        self.db = db

    def _get_stock_name(self, ticker: str) -> str | None:
        stock = self.db.query(Stock).filter(Stock.code == ticker).first()
        return stock.name if stock else None

    def _fire_event(self, event_type: EventType, payload: dict):
        """동기 컨텍스트에서 이벤트를 fire-and-forget으로 발행합니다."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(event_bus.publish(Event(type=event_type, payload=payload)))
        except RuntimeError:
            pass

    def create(self, idea_id: UUID, data: PositionCreate) -> Optional[Position]:
        idea = self.db.query(InvestmentIdea).filter(InvestmentIdea.id == idea_id).first()
        if not idea:
            return None

        position = Position(
            idea_id=idea_id,
            ticker=data.ticker,
            entry_price=data.entry_price,
            quantity=data.quantity,
            entry_date=data.entry_date or today_kst(),
            strategy_params=data.strategy_params,
            notes=data.notes,
        )

        if idea.status == IdeaStatus.WATCHING:
            idea.status = IdeaStatus.ACTIVE

        self.db.add(position)
        self.db.flush()

        # Trade 기록
        trade = Trade(
            position_id=position.id,
            trade_type=TradeType.BUY,
            trade_date=position.entry_date,
            price=data.entry_price,
            quantity=data.quantity,
            avg_price_after=data.entry_price,
            quantity_after=data.quantity,
            stock_code=data.ticker,
            stock_name=self._get_stock_name(data.ticker),
        )
        self.db.add(trade)
        self.db.commit()
        self.db.refresh(position)

        self._fire_event(EventType.POSITION_ENTERED, {
            "idea_id": str(idea_id),
            "position_id": str(position.id),
            "ticker": data.ticker,
            "quantity": data.quantity,
            "entry_price": float(data.entry_price),
        })

        return position

    def get(self, position_id: UUID) -> Optional[Position]:
        return self.db.query(Position).filter(Position.id == position_id).first()

    def get_by_idea(self, idea_id: UUID) -> List[Position]:
        return self.db.query(Position).filter(Position.idea_id == idea_id).all()

    def update(self, position_id: UUID, data: PositionUpdate) -> Optional[Position]:
        """포지션 직접 수정 (잘못 입력한 매매내역 수정용)"""
        position = self.get(position_id)
        if not position:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return position

        for field, value in update_data.items():
            setattr(position, field, value)

        # 최초 매수 Trade도 동기화 (entry_price, quantity, entry_date 변경 시)
        if any(k in update_data for k in ("entry_price", "quantity", "entry_date")):
            first_trade = (
                self.db.query(Trade)
                .filter(Trade.position_id == position_id, Trade.trade_type == TradeType.BUY)
                .order_by(Trade.created_at)
                .first()
            )
            if first_trade:
                if "entry_price" in update_data:
                    first_trade.price = update_data["entry_price"]
                    first_trade.avg_price_after = update_data["entry_price"]
                if "quantity" in update_data:
                    first_trade.quantity = update_data["quantity"]
                    first_trade.quantity_after = update_data["quantity"]
                if "entry_date" in update_data:
                    first_trade.trade_date = update_data["entry_date"]

        self.db.commit()
        self.db.refresh(position)

        self._fire_event(EventType.POSITION_ENTERED, {
            "idea_id": str(position.idea_id),
            "position_id": str(position_id),
            "ticker": position.ticker,
            "quantity": position.quantity,
            "entry_price": float(position.entry_price),
        })

        return position

    def exit(self, position_id: UUID, data: PositionExit) -> Optional[Position]:
        position = self.get(position_id)
        if not position:
            return None

        position.exit_price = data.exit_price
        position.exit_date = data.exit_date or today_kst()
        position.exit_reason = data.exit_reason

        # 실현손익 계산
        realized_profit = float(data.exit_price - position.entry_price) * position.quantity
        realized_pct = float((data.exit_price - position.entry_price) / position.entry_price * 100)

        # Trade 기록
        trade = Trade(
            position_id=position.id,
            trade_type=TradeType.SELL,
            trade_date=data.exit_date or today_kst(),
            price=data.exit_price,
            quantity=position.quantity,
            realized_profit=realized_profit,
            realized_return_pct=round(realized_pct, 2),
            avg_price_after=None,
            quantity_after=0,
            reason=data.exit_reason,
            stock_code=position.ticker,
            stock_name=self._get_stock_name(position.ticker),
        )
        self.db.add(trade)

        idea = position.idea
        open_positions = [p for p in idea.positions if p.is_open and p.id != position_id]
        if not open_positions:
            idea.status = IdeaStatus.EXITED

        self.db.commit()
        self.db.refresh(position)

        self._fire_event(EventType.POSITION_EXITED, {
            "idea_id": str(idea.id),
            "position_id": str(position_id),
            "ticker": position.ticker,
            "exit_price": float(data.exit_price),
            "exit_reason": data.exit_reason,
        })

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
        buy_date_str = (data.buy_date or today_kst()).isoformat()
        add_note = f"[추가매수] {buy_date_str}: {data.quantity}주 @ {data.price:,}원"
        if position.notes:
            position.notes = f"{position.notes}\n{add_note}"
        else:
            position.notes = add_note

        # Trade 기록
        trade = Trade(
            position_id=position.id,
            trade_type=TradeType.ADD_BUY,
            trade_date=data.buy_date or today_kst(),
            price=data.price,
            quantity=data.quantity,
            avg_price_after=position.entry_price,
            quantity_after=total_quantity,
            stock_code=position.ticker,
            stock_name=self._get_stock_name(position.ticker),
        )
        self.db.add(trade)

        self.db.commit()
        self.db.refresh(position)

        self._fire_event(EventType.POSITION_ADDED_BUY, {
            "idea_id": str(position.idea_id),
            "position_id": str(position_id),
            "ticker": position.ticker,
            "added_quantity": data.quantity,
            "added_price": float(data.price),
        })

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
        remaining_quantity = position.quantity - data.quantity
        position.quantity = remaining_quantity

        # 부분매도 기록을 notes에 추가
        exit_date_str = (data.exit_date or today_kst()).isoformat()
        exit_note = f"[부분매도] {exit_date_str}: {data.quantity}주 @ {data.exit_price:,}원 (수익률: {realized_return_pct:+.2f}%, 손익: {realized_profit:+,.0f}원)"
        if data.exit_reason:
            exit_note += f" - {data.exit_reason}"
        if position.notes:
            position.notes = f"{position.notes}\n{exit_note}"
        else:
            position.notes = exit_note

        # Trade 기록
        trade = Trade(
            position_id=position.id,
            trade_type=TradeType.PARTIAL_SELL,
            trade_date=data.exit_date or today_kst(),
            price=data.exit_price,
            quantity=data.quantity,
            realized_profit=float(realized_profit),
            realized_return_pct=round(realized_return_pct, 2),
            avg_price_after=position.entry_price,
            quantity_after=remaining_quantity,
            reason=data.exit_reason,
            stock_code=position.ticker,
            stock_name=self._get_stock_name(position.ticker),
        )
        self.db.add(trade)

        self.db.commit()
        self.db.refresh(position)

        self._fire_event(EventType.POSITION_PARTIAL_EXIT, {
            "idea_id": str(position.idea_id),
            "position_id": str(position_id),
            "ticker": position.ticker,
            "exit_quantity": data.quantity,
            "exit_price": float(data.exit_price),
            "realized_return_pct": realized_return_pct,
        })

        return position
