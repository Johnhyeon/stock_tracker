"""이벤트 핸들러 등록 모듈.

EventBus를 통해 도메인 이벤트에 반응하는 핸들러들을 정의합니다.
- 아이디어 생성 → 자동 가격 수집
- 포지션 진입/청산 → 스냅샷 갱신
- 가격 업데이트/공시 수집 후 로깅
"""
import logging
from datetime import date
from decimal import Decimal

from core.timezone import today_kst

from sqlalchemy import select

from core.events import event_bus, Event, EventType
from core.database import async_session_maker
from core.cache import api_cache

logger = logging.getLogger(__name__)


async def on_idea_created(event: Event):
    """아이디어 생성 시 해당 종목의 가격 데이터를 자동 수집합니다."""
    # 대시보드 캐시 무효화
    api_cache.invalidate("dashboard")
    api_cache.invalidate("dashboard_signals")
    api_cache.invalidate("idea_stock_sparklines")

    tickers = event.payload.get("tickers", [])
    idea_id = event.payload.get("idea_id")
    if not tickers:
        return

    # 종목코드 추출
    import re
    stock_codes = []
    for ticker in tickers:
        match = re.search(r'\(([A-Za-z0-9]{6})\)', ticker)
        if match:
            stock_codes.append(match.group(1))
        elif re.match(r'^[A-Za-z0-9]{6}$', ticker):
            stock_codes.append(ticker)

    if not stock_codes:
        return

    logger.info(f"[EventBus] 아이디어 {idea_id} 생성 → {len(stock_codes)}개 종목 가격 수집 시작")

    try:
        from services.price_service import get_price_service
        price_service = get_price_service()
        prices = await price_service.get_multiple_prices(stock_codes, use_cache=False)
        logger.info(f"[EventBus] 가격 수집 완료: {list(prices.keys())}")
    except Exception as e:
        logger.warning(f"[EventBus] 자동 가격 수집 실패: {e}")


async def on_position_changed(event: Event):
    """포지션 진입/청산/추가매수/부분매도 시 해당 아이디어의 스냅샷을 갱신합니다."""
    # 대시보드/리스크/습관 캐시 무효화
    api_cache.invalidate("dashboard")
    api_cache.invalidate("dashboard_signals")
    api_cache.invalidate("risk_metrics")
    api_cache.invalidate("trade_habits")

    idea_id = event.payload.get("idea_id")
    if not idea_id:
        return

    action = event.type.value
    logger.info(f"[EventBus] 포지션 변경({action}) → 아이디어 {idea_id} 스냅샷 갱신 시작")

    async with async_session_maker() as db:
        try:
            from models import InvestmentIdea, Position, TrackingSnapshot
            from services.price_service import get_price_service

            stmt = select(InvestmentIdea).where(InvestmentIdea.id == idea_id)
            result = await db.execute(stmt)
            idea = result.scalar_one_or_none()
            if not idea:
                return

            # 포지션 조회
            pos_stmt = select(Position).where(
                Position.idea_id == idea_id,
                Position.exit_date.is_(None),
            )
            pos_result = await db.execute(pos_stmt)
            open_positions = pos_result.scalars().all()

            if not open_positions:
                logger.info(f"[EventBus] 아이디어 {idea_id}: 열린 포지션 없음, 스냅샷 건너뜀")
                return

            # 종목코드 수집 및 현재가 병렬 조회
            codes = list(set(p.ticker for p in open_positions if p.ticker))
            price_map = {}
            if codes:
                try:
                    import asyncio
                    price_service = get_price_service()

                    async def _fetch(code):
                        try:
                            return code, await price_service.get_current_price(code)
                        except Exception:
                            return code, None

                    results = await asyncio.gather(*[_fetch(c) for c in codes])
                    price_map = {code: data for code, data in results if data}
                except Exception as e:
                    logger.warning(f"[EventBus] 스냅샷용 가격 조회 실패: {e}")

            # 스냅샷 데이터 구성
            today = today_kst()
            total_invested = Decimal("0")
            total_eval = Decimal("0")
            position_data = []
            max_days_held = 0

            for pos in open_positions:
                entry_price = Decimal(str(pos.entry_price))
                invested = entry_price * pos.quantity
                total_invested += invested

                current_price = None
                if pos.ticker in price_map:
                    cp = price_map[pos.ticker].get("current_price")
                    if cp is not None:
                        current_price = Decimal(str(cp))

                eval_amount = current_price * pos.quantity if current_price else invested
                total_eval += eval_amount

                days_held = (today - pos.entry_date).days if pos.entry_date else 0
                max_days_held = max(max_days_held, days_held)

                position_data.append({
                    "ticker": pos.ticker,
                    "quantity": pos.quantity,
                    "entry_price": float(entry_price),
                    "current_price": float(current_price) if current_price else None,
                    "invested": float(invested),
                    "eval": float(eval_amount),
                    "days_held": days_held,
                })

            unrealized_pct = (
                float((total_eval - total_invested) / total_invested * 100)
                if total_invested > 0
                else 0
            )

            # 기존 오늘 스냅샷 있으면 업데이트, 없으면 생성
            snap_stmt = select(TrackingSnapshot).where(
                TrackingSnapshot.idea_id == idea_id,
                TrackingSnapshot.snapshot_date == today,
            )
            snap_result = await db.execute(snap_stmt)
            existing = snap_result.scalar_one_or_none()

            price_data_dict = {
                "positions": position_data,
                "total_invested": float(total_invested),
                "total_eval": float(total_eval),
                "unrealized_profit": float(total_eval - total_invested),
            }

            if existing:
                existing.price_data = price_data_dict
                existing.days_held = max_days_held
                existing.unrealized_return_pct = Decimal(str(round(unrealized_pct, 2)))
            else:
                snapshot = TrackingSnapshot(
                    idea_id=idea_id,
                    snapshot_date=today,
                    price_data=price_data_dict,
                    days_held=max_days_held,
                    unrealized_return_pct=Decimal(str(round(unrealized_pct, 2))),
                )
                db.add(snapshot)

            await db.commit()
            logger.info(f"[EventBus] 아이디어 {idea_id} 스냅샷 {'갱신' if existing else '생성'} 완료")

        except Exception as e:
            logger.error(f"[EventBus] 스냅샷 갱신 실패: {e}", exc_info=True)
            await db.rollback()


async def on_price_updated(event: Event):
    """가격 업데이트 완료 후 로깅."""
    stock_codes = event.payload.get("stock_codes", [])
    logger.info(f"[EventBus] 가격 업데이트 완료: {len(stock_codes)}개 종목")


async def on_disclosure_collected(event: Event):
    """새 공시 수집 시 로깅 + 실적 공시면 재무제표 자동 갱신."""
    new_count = event.payload.get("new_count", 0)
    earnings_codes = event.payload.get("earnings_stock_codes", [])
    logger.info(f"[EventBus] 신규 공시 {new_count}건 수집 완료")

    if not earnings_codes:
        return

    logger.info(f"[EventBus] 실적 공시 감지 → {len(earnings_codes)}개 종목 재무제표 자동 갱신: {earnings_codes}")

    async with async_session_maker() as db:
        try:
            from services.financial_statement_service import FinancialStatementService
            service = FinancialStatementService(db)
            for stock_code in earnings_codes:
                try:
                    result = await service.collect_financial_statements(stock_code, years=1)
                    logger.info(f"[EventBus] {stock_code} 재무제표 자동 갱신: {result['collected_count']}건")
                except Exception as e:
                    logger.warning(f"[EventBus] {stock_code} 재무제표 자동 갱신 실패: {e}")
        except Exception as e:
            logger.error(f"[EventBus] 재무제표 자동 갱신 오류: {e}", exc_info=True)


async def on_youtube_collected(event: Event):
    """YouTube 수집 완료 시 로깅."""
    new_count = event.payload.get("new_count", 0)
    with_mentions = event.payload.get("with_mentions", 0)
    logger.info(f"[EventBus] YouTube {new_count}건 수집, 종목 언급 {with_mentions}건")


def register_event_handlers():
    """모든 이벤트 핸들러를 EventBus에 등록합니다.

    앱 시작 시(lifespan) 호출됩니다.
    """
    # 아이디어 생성 → 자동 가격 수집
    event_bus.subscribe(EventType.IDEA_CREATED, on_idea_created)

    # 포지션 변경 → 스냅샷 갱신
    event_bus.subscribe(EventType.POSITION_ENTERED, on_position_changed)
    event_bus.subscribe(EventType.POSITION_EXITED, on_position_changed)
    event_bus.subscribe(EventType.POSITION_ADDED_BUY, on_position_changed)
    event_bus.subscribe(EventType.POSITION_PARTIAL_EXIT, on_position_changed)

    # 데이터 수집 이벤트 로깅
    event_bus.subscribe(EventType.PRICE_UPDATED, on_price_updated)
    event_bus.subscribe(EventType.DISCLOSURE_COLLECTED, on_disclosure_collected)
    event_bus.subscribe(EventType.YOUTUBE_COLLECTED, on_youtube_collected)

    logger.info("[EventBus] 이벤트 핸들러 등록 완료 (8개)")
