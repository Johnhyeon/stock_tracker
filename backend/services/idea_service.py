import asyncio
import re
import logging
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import InvestmentIdea, Position, IdeaStatus, IdeaType, FundamentalHealth, Stock
from models.stock_ohlcv import StockOHLCV
from schemas import IdeaCreate, IdeaUpdate, ExitCheckResult
from core.events import event_bus, Event, EventType
from core.timezone import now_kst, today_kst

logger = logging.getLogger(__name__)


class IdeaService:
    def __init__(self, db: Session):
        self.db = db

    def _fire_event(self, event_type: EventType, payload: dict):
        """동기 컨텍스트에서 이벤트를 fire-and-forget으로 발행합니다."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(event_bus.publish(Event(type=event_type, payload=payload)))
        except RuntimeError:
            # 이벤트 루프가 없으면 무시 (테스트 등)
            pass

    def create(self, data: IdeaCreate) -> InvestmentIdea:
        # 종목 코드 파싱 및 현재가 조회
        initial_prices = self._fetch_initial_prices(data.tickers)

        # metadata에 초기 가격 저장
        metadata = dict(data.metadata_) if data.metadata_ else {}
        if initial_prices:
            metadata["initial_prices"] = initial_prices

        idea = InvestmentIdea(
            type=data.type,
            sector=data.sector,
            tickers=data.tickers,
            thesis=data.thesis,
            expected_timeframe_days=data.expected_timeframe_days,
            target_return_pct=data.target_return_pct,
            tags=data.tags,
            metadata_=metadata if metadata else None,
        )

        # 과거 날짜로 생성 시 created_at 설정
        if data.created_at:
            idea.created_at = data.created_at

        self.db.add(idea)
        self.db.commit()
        self.db.refresh(idea)

        # 이벤트 발행 (비동기 핸들러를 fire-and-forget으로 실행)
        self._fire_event(EventType.IDEA_CREATED, {
            "idea_id": str(idea.id),
            "tickers": data.tickers,
            "type": data.type.value if hasattr(data.type, 'value') else str(data.type),
        })

        return idea

    def _extract_stock_code(self, ticker: str) -> Optional[str]:
        """'삼성전자(005930)' 형식에서 종목코드 추출."""
        match = re.search(r'\(([A-Za-z0-9]{6})\)', ticker)
        return match.group(1) if match else None

    def _get_db_prices(self, stock_codes: list[str]) -> dict:
        """DB(stock_ohlcv)에서 최신 종가 일괄 조회."""
        if not stock_codes:
            return {}
        result = {}
        for code in stock_codes:
            row = (
                self.db.query(StockOHLCV)
                .filter(StockOHLCV.stock_code == code)
                .order_by(StockOHLCV.trade_date.desc())
                .first()
            )
            if row:
                result[code] = {
                    "current_price": row.close_price,
                    "volume": row.volume,
                }
        return result

    def _fetch_initial_prices(self, tickers: List[str]) -> dict:
        """종목들의 현재가를 조회하여 초기 가격 정보 반환."""
        initial_prices = {}
        stock_codes = []

        for ticker in tickers:
            code = self._extract_stock_code(ticker)
            if code:
                stock_codes.append(code)

        if not stock_codes:
            return initial_prices

        try:
            prices = self._get_db_prices(stock_codes)
            for code, price_data in prices.items():
                current_price = price_data.get("current_price")
                if current_price is not None:
                    initial_prices[code] = {
                        "price": float(current_price) if isinstance(current_price, Decimal) else current_price,
                        "date": now_kst().isoformat(),
                    }
        except Exception as e:
            logger.warning(f"초기 가격 조회 실패: {e}")

        return initial_prices

    def get(self, idea_id: UUID) -> Optional[InvestmentIdea]:
        return self.db.query(InvestmentIdea).filter(InvestmentIdea.id == idea_id).first()

    def get_all(
        self,
        status: Optional[IdeaStatus] = None,
        idea_type: Optional[IdeaType] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[InvestmentIdea]:
        query = self.db.query(InvestmentIdea)
        if status:
            query = query.filter(InvestmentIdea.status == status)
        if idea_type:
            query = query.filter(InvestmentIdea.type == idea_type)
        return query.order_by(InvestmentIdea.created_at.desc()).offset(skip).limit(limit).all()

    def update(self, idea_id: UUID, data: IdeaUpdate) -> Optional[InvestmentIdea]:
        idea = self.get(idea_id)
        if not idea:
            return None

        update_data = data.model_dump(exclude_unset=True, by_alias=False)
        for field, value in update_data.items():
            if field == "metadata_":
                setattr(idea, "metadata_", value)
            else:
                setattr(idea, field, value)

        idea.version += 1
        self.db.commit()
        self.db.refresh(idea)

        self._fire_event(EventType.IDEA_UPDATED, {
            "idea_id": str(idea.id),
            "updated_fields": list(update_data.keys()),
        })

        return idea

    def delete(self, idea_id: UUID) -> bool:
        idea = self.get(idea_id)
        if not idea:
            return False

        idea_tickers = idea.tickers
        self.db.delete(idea)
        self.db.commit()

        self._fire_event(EventType.IDEA_DELETED, {
            "idea_id": str(idea_id),
            "tickers": idea_tickers,
        })

        return True

    def check_exit_criteria(self, idea_id: UUID) -> Optional[ExitCheckResult]:
        idea = self.get(idea_id)
        if not idea:
            return None

        open_positions = [p for p in idea.positions if p.is_open]
        if not open_positions:
            return ExitCheckResult(
                should_exit=False,
                reasons={},
                warnings=["포지션이 없습니다."],
            )

        max_days_held = max(p.days_held for p in open_positions) if open_positions else 0

        checks = {
            "fundamental_broken": idea.fundamental_health == FundamentalHealth.BROKEN,
            "time_expired": max_days_held > idea.expected_timeframe_days,
            "fundamental_deteriorating": idea.fundamental_health == FundamentalHealth.DETERIORATING,
        }

        warnings = []
        fomo_stats = None

        if not any(checks.values()) and idea.type == IdeaType.RESEARCH:
            warnings.append("청산 조건을 충족하지 않습니다. FOMO 청산을 피하세요!")
            fomo_stats = self._get_fomo_stats()

        should_exit = checks["fundamental_broken"] or checks["time_expired"]

        return ExitCheckResult(
            should_exit=should_exit,
            reasons=checks,
            warnings=warnings,
            fomo_stats=fomo_stats,
        )

    def _get_fomo_stats(self) -> dict:
        fomo_exits = (
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

        if not fomo_exits:
            return {
                "count": 0,
                "avg_return_at_exit": None,
                "message": "과거 FOMO 청산 기록이 없습니다.",
            }

        returns = [p.realized_return_pct for p in fomo_exits if p.realized_return_pct is not None]
        avg_return = sum(returns) / len(returns) if returns else None

        return {
            "count": len(fomo_exits),
            "avg_return_at_exit": avg_return,
            "message": f"과거 {len(fomo_exits)}건의 FOMO 청산 중 평균 수익률: {avg_return:.2f}%" if avg_return else None,
        }

    def get_dashboard_data(self) -> dict:
        """동기 버전 (deprecated - 비동기 버전 사용 권장)."""
        active_ideas = self.get_all(status=IdeaStatus.ACTIVE)
        watching_ideas = self.get_all(status=IdeaStatus.WATCHING)

        research_ideas = [i for i in active_ideas if i.type == IdeaType.RESEARCH]
        chart_ideas = [i for i in active_ideas if i.type == IdeaType.CHART]

        # 모든 열린 포지션의 종목 코드 수집
        all_stock_codes = set()
        for idea in active_ideas:
            for pos in idea.positions:
                if pos.is_open:
                    code = self._extract_stock_code_from_ticker(pos.ticker)
                    if code:
                        all_stock_codes.add(code)

        # 현재가 조회 (DB stock_ohlcv)
        current_prices = {}
        if all_stock_codes:
            try:
                current_prices = self._get_db_prices(list(all_stock_codes))
            except Exception as e:
                logger.warning(f"현재가 조회 실패: {e}")

        # 종목명 조회
        stock_names = {}
        if all_stock_codes:
            stocks = self.db.query(Stock).filter(Stock.code.in_(all_stock_codes)).all()
            for stock in stocks:
                stock_names[stock.code] = stock.name

        total_invested = Decimal("0")
        total_unrealized = Decimal("0")
        all_return_pcts = []

        for idea in active_ideas:
            for pos in idea.positions:
                if pos.is_open:
                    invested = pos.entry_price * pos.quantity
                    total_invested += invested

                    code = self._extract_stock_code_from_ticker(pos.ticker)
                    if code and code in current_prices:
                        price_data = current_prices[code]
                        current_price = price_data.get("current_price")
                        if current_price is not None:
                            current_value = Decimal(str(current_price)) * pos.quantity
                            profit = current_value - invested
                            total_unrealized += profit
                            return_pct = float(profit / invested * 100)
                            all_return_pcts.append(return_pct)

        avg_return_pct = sum(all_return_pcts) / len(all_return_pcts) if all_return_pcts else None

        return {
            "stats": {
                "total_ideas": len(active_ideas) + len(watching_ideas),
                "active_ideas": len(active_ideas),
                "watching_ideas": len(watching_ideas),
                "research_ideas": len(research_ideas),
                "chart_ideas": len(chart_ideas),
                "total_invested": round(total_invested),
                "total_unrealized_return": round(total_unrealized),
                "avg_return_pct": avg_return_pct,
            },
            "research_ideas": self._format_ideas_for_dashboard(research_ideas, current_prices, stock_names),
            "chart_ideas": self._format_ideas_for_dashboard(chart_ideas, current_prices, stock_names),
            "watching_ideas": self._format_ideas_for_dashboard(watching_ideas, current_prices, stock_names),
        }

    async def get_dashboard_data_async(self) -> dict:
        """비동기 버전 대시보드 데이터 조회."""
        active_ideas = self.get_all(status=IdeaStatus.ACTIVE)
        watching_ideas = self.get_all(status=IdeaStatus.WATCHING)

        research_ideas = [i for i in active_ideas if i.type == IdeaType.RESEARCH]
        chart_ideas = [i for i in active_ideas if i.type == IdeaType.CHART]

        # 모든 열린 포지션의 종목 코드 수집
        all_stock_codes = set()
        for idea in active_ideas:
            for pos in idea.positions:
                if pos.is_open:
                    code = self._extract_stock_code_from_ticker(pos.ticker)
                    if code:
                        all_stock_codes.add(code)

        # 현재가 조회 (DB stock_ohlcv)
        current_prices = {}
        if all_stock_codes:
            try:
                current_prices = self._get_db_prices(list(all_stock_codes))
            except Exception as e:
                logger.warning(f"현재가 조회 실패: {e}")

        # 종목명 조회
        stock_names = {}
        if all_stock_codes:
            stocks = self.db.query(Stock).filter(Stock.code.in_(all_stock_codes)).all()
            for stock in stocks:
                stock_names[stock.code] = stock.name

        total_invested = Decimal("0")
        total_unrealized = Decimal("0")
        all_return_pcts = []

        for idea in active_ideas:
            for pos in idea.positions:
                if pos.is_open:
                    invested = pos.entry_price * pos.quantity
                    total_invested += invested

                    code = self._extract_stock_code_from_ticker(pos.ticker)
                    if code and code in current_prices:
                        price_data = current_prices[code]
                        current_price = price_data.get("current_price")
                        if current_price is not None:
                            current_value = Decimal(str(current_price)) * pos.quantity
                            profit = current_value - invested
                            total_unrealized += profit
                            return_pct = float(profit / invested * 100)
                            all_return_pcts.append(return_pct)

        avg_return_pct = sum(all_return_pcts) / len(all_return_pcts) if all_return_pcts else None

        return {
            "stats": {
                "total_ideas": len(active_ideas) + len(watching_ideas),
                "active_ideas": len(active_ideas),
                "watching_ideas": len(watching_ideas),
                "research_ideas": len(research_ideas),
                "chart_ideas": len(chart_ideas),
                "total_invested": round(total_invested),
                "total_unrealized_return": round(total_unrealized),
                "avg_return_pct": avg_return_pct,
            },
            "research_ideas": self._format_ideas_for_dashboard(research_ideas, current_prices, stock_names),
            "chart_ideas": self._format_ideas_for_dashboard(chart_ideas, current_prices, stock_names),
            "watching_ideas": self._format_ideas_for_dashboard(watching_ideas, current_prices, stock_names),
        }

    def _extract_stock_code_from_ticker(self, ticker: str) -> Optional[str]:
        """티커에서 종목코드 추출 (6자리 숫자 또는 '이름(코드)' 형식)."""
        # 먼저 괄호 형식 확인
        match = re.search(r'\(([A-Za-z0-9]{6})\)', ticker)
        if match:
            return match.group(1)
        # 6자리 숫자인 경우
        if re.match(r'^[A-Za-z0-9]{6}$', ticker):
            return ticker
        return None

    def _format_ideas_for_dashboard(
        self, ideas: List[InvestmentIdea], current_prices: dict = None, stock_names: dict = None
    ) -> List[dict]:
        current_prices = current_prices or {}
        stock_names = stock_names or {}
        result = []

        for idea in ideas:
            open_positions = [p for p in idea.positions if p.is_open]
            total_invested = sum(p.entry_price * p.quantity for p in open_positions)
            days_active = (today_kst() - idea.created_at.date()).days
            time_remaining = idea.expected_timeframe_days - days_active

            # 포지션별 현재가 및 수익률 계산
            formatted_positions = []
            idea_return_pcts = []
            for p in open_positions:
                code = self._extract_stock_code_from_ticker(p.ticker)
                invested = p.entry_price * p.quantity

                current_price = None
                unrealized_profit = None
                unrealized_return_pct = None
                stock_name = stock_names.get(code) if code else None

                if code and code in current_prices:
                    price_data = current_prices[code]
                    cp = price_data.get("current_price")
                    if cp is not None:
                        current_price = Decimal(str(cp))
                        current_value = current_price * p.quantity
                        unrealized_profit = current_value - invested
                        unrealized_return_pct = float(unrealized_profit / invested * 100)
                        idea_return_pcts.append(unrealized_return_pct)
                        # stock_name이 없으면 price_data에서 가져옴
                        if not stock_name:
                            stock_name = price_data.get("stock_name")

                formatted_positions.append({
                    "id": p.id,
                    "ticker": p.ticker,
                    "stock_name": stock_name,
                    "entry_price": round(p.entry_price),
                    "entry_date": p.entry_date,
                    "quantity": p.quantity,
                    "days_held": p.days_held,
                    "current_price": round(current_price) if current_price is not None else None,
                    "unrealized_profit": round(unrealized_profit) if unrealized_profit is not None else None,
                    "unrealized_return_pct": unrealized_return_pct,
                })

            # 아이디어 전체 수익률 (포지션별 가중평균)
            total_unrealized_return_pct = None
            if idea_return_pcts and total_invested > 0:
                total_profit = sum(
                    fp["unrealized_profit"] for fp in formatted_positions if fp["unrealized_profit"]
                )
                if total_profit is not None:
                    total_unrealized_return_pct = float(total_profit / total_invested * 100)

            result.append({
                "id": idea.id,
                "type": idea.type,
                "sector": idea.sector,
                "tickers": idea.tickers,
                "thesis": idea.thesis,
                "status": idea.status,
                "fundamental_health": idea.fundamental_health,
                "expected_timeframe_days": idea.expected_timeframe_days,
                "target_return_pct": idea.target_return_pct,
                "created_at": idea.created_at,
                "positions": formatted_positions,
                "total_invested": round(total_invested),
                "total_unrealized_return_pct": total_unrealized_return_pct,
                "days_active": days_active,
                "time_remaining_days": time_remaining,
            })
        return result
