"""일별 포트폴리오 스냅샷 수집 작업."""
import logging
from decimal import Decimal

from sqlalchemy import select

from core.database import async_session_maker
from core.timezone import today_kst
from models import InvestmentIdea, IdeaStatus, Position, TrackingSnapshot
from services.price_service import get_price_service
from scheduler.job_tracker import track_job_execution

logger = logging.getLogger(__name__)


@track_job_execution("snapshot_collect")
async def collect_daily_snapshots():
    """활성 아이디어의 일별 스냅샷 수집.

    장 마감 후 실행되어 각 ACTIVE 아이디어의 현재 상태를 기록합니다.
    - 포지션별 현재가, 투자금, 평가금
    - 보유 일수
    - 미실현 수익률
    """
    logger.info("일별 스냅샷 수집 시작")
    today = today_kst()

    async with async_session_maker() as session:
        # 활성 아이디어 조회
        result = await session.execute(
            select(InvestmentIdea).where(InvestmentIdea.status == IdeaStatus.ACTIVE)
        )
        active_ideas = result.scalars().all()

        if not active_ideas:
            logger.info("활성 아이디어 없음, 스냅샷 수집 건너뜀")
            return

        # 이미 오늘 스냅샷이 있는 아이디어 제외
        existing_result = await session.execute(
            select(TrackingSnapshot.idea_id).where(
                TrackingSnapshot.snapshot_date == today
            )
        )
        existing_ids = {row[0] for row in existing_result.all()}

        ideas_to_process = [i for i in active_ideas if i.id not in existing_ids]
        if not ideas_to_process:
            logger.info("오늘 스냅샷 이미 수집 완료")
            return

        logger.info(f"스냅샷 대상: {len(ideas_to_process)}개 아이디어")

        # 모든 활성 포지션의 종목코드 수집
        all_codes = set()
        idea_positions = {}
        for idea in ideas_to_process:
            pos_result = await session.execute(
                select(Position).where(
                    Position.idea_id == idea.id,
                    Position.exit_date.is_(None),
                )
            )
            positions = pos_result.scalars().all()
            idea_positions[idea.id] = positions
            for pos in positions:
                if pos.ticker:
                    all_codes.add(pos.ticker)

        # 현재가 일괄 조회
        price_map = {}
        if all_codes:
            price_service = get_price_service()
            for code in all_codes:
                try:
                    price_data = await price_service.get_current_price(code)
                    price_map[code] = price_data
                except Exception as e:
                    logger.warning(f"{code} 가격 조회 실패: {e}")

        created_count = 0
        for idea in ideas_to_process:
            try:
                positions = idea_positions.get(idea.id, [])
                if not positions:
                    continue

                total_invested = Decimal("0")
                total_eval = Decimal("0")
                position_data = []
                max_days_held = 0

                for pos in positions:
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
                        "stock_name": pos.stock_name,
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

                snapshot = TrackingSnapshot(
                    idea_id=idea.id,
                    snapshot_date=today,
                    price_data={
                        "positions": position_data,
                        "total_invested": float(total_invested),
                        "total_eval": float(total_eval),
                        "unrealized_profit": float(total_eval - total_invested),
                    },
                    days_held=max_days_held,
                    unrealized_return_pct=Decimal(str(round(unrealized_pct, 2))),
                )
                session.add(snapshot)
                created_count += 1

            except Exception as e:
                logger.error(f"아이디어 {idea.id} 스냅샷 생성 실패: {e}")

        await session.commit()
        logger.info(f"일별 스냅샷 수집 완료: {created_count}개 생성")
