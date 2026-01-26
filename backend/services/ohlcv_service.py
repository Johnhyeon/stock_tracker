"""OHLCV 데이터 서비스.

DB에서 일봉 데이터를 조회하고, 필요시 KIS API에서 수집합니다.
"""
import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from models import StockOHLCV
from services.price_service import get_price_service

logger = logging.getLogger(__name__)


class OHLCVService:
    """OHLCV 데이터 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.price_service = get_price_service()

    async def get_ohlcv(
        self,
        stock_code: str,
        days: int = 90,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """DB에서 OHLCV 데이터 조회.

        Args:
            stock_code: 종목코드
            days: 조회 일수
            end_date: 종료일 (기본: 오늘)

        Returns:
            lightweight-charts 형식의 캔들 데이터 리스트
        """
        if end_date is None:
            end_date = date.today()
        start_date = end_date - timedelta(days=days + 30)  # 여유분

        stmt = (
            select(StockOHLCV)
            .where(
                and_(
                    StockOHLCV.stock_code == stock_code,
                    StockOHLCV.trade_date >= start_date,
                    StockOHLCV.trade_date <= end_date,
                )
            )
            .order_by(StockOHLCV.trade_date.asc())
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        # 최근 days일만 반환
        candles = [row.to_chart_dict() for row in rows]
        return candles[-days:] if len(candles) > days else candles

    async def get_ohlcv_count(self, stock_code: str) -> int:
        """종목의 저장된 OHLCV 데이터 개수 조회."""
        from sqlalchemy import func
        stmt = (
            select(func.count())
            .select_from(StockOHLCV)
            .where(StockOHLCV.stock_code == stock_code)
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def collect_ohlcv(
        self,
        stock_code: str,
        days: int = 240,
        force: bool = False,
    ) -> int:
        """KIS API에서 OHLCV 수집 후 DB 저장.

        Args:
            stock_code: 종목코드
            days: 수집 일수 (기본 240일)
            force: 기존 데이터 있어도 강제 수집

        Returns:
            저장된 레코드 수
        """
        # 이미 데이터가 있으면 스킵 (force가 아닌 경우)
        if not force:
            existing_count = await self.get_ohlcv_count(stock_code)
            if existing_count >= days * 0.8:  # 80% 이상 있으면 스킵
                logger.debug(f"{stock_code}: 이미 {existing_count}일 데이터 존재, 스킵")
                return 0

        end_date = date.today()
        start_date = end_date - timedelta(days=days + 30)

        try:
            data = await self.price_service.get_ohlcv(
                stock_code=stock_code,
                period="D",
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                use_cache=False,
            )

            if not data:
                logger.warning(f"{stock_code}: OHLCV 데이터 없음")
                return 0

            # Upsert (중복 시 업데이트)
            saved_count = 0
            for row in data:
                trade_date = date(
                    int(row["date"][:4]),
                    int(row["date"][4:6]),
                    int(row["date"][6:8]),
                )
                stmt = insert(StockOHLCV).values(
                    stock_code=stock_code,
                    trade_date=trade_date,
                    open_price=int(row["open"]),
                    high_price=int(row["high"]),
                    low_price=int(row["low"]),
                    close_price=int(row["close"]),
                    volume=int(row["volume"]),
                ).on_conflict_do_update(
                    index_elements=["stock_code", "trade_date"],
                    set_={
                        "open_price": int(row["open"]),
                        "high_price": int(row["high"]),
                        "low_price": int(row["low"]),
                        "close_price": int(row["close"]),
                        "volume": int(row["volume"]),
                    }
                )
                await self.db.execute(stmt)
                saved_count += 1

            await self.db.commit()
            logger.info(f"{stock_code}: {saved_count}일 OHLCV 저장 완료")
            return saved_count

        except Exception as e:
            logger.error(f"{stock_code}: OHLCV 수집 실패 - {e}")
            await self.db.rollback()
            return 0

    async def collect_daily_update(self, stock_code: str) -> bool:
        """오늘 데이터만 수집 (일별 업데이트용).

        Returns:
            성공 여부
        """
        today = date.today()

        # 이미 오늘 데이터가 있으면 스킵
        stmt = select(StockOHLCV).where(
            and_(
                StockOHLCV.stock_code == stock_code,
                StockOHLCV.trade_date == today,
            )
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            return True  # 이미 있음

        try:
            # 최근 5일 조회 (주말/휴일 고려)
            data = await self.price_service.get_ohlcv(
                stock_code=stock_code,
                period="D",
                start_date=(today - timedelta(days=7)).strftime("%Y%m%d"),
                end_date=today.strftime("%Y%m%d"),
                use_cache=False,
            )

            if not data:
                return False

            # 가장 최근 데이터만 저장
            latest = data[-1]
            trade_date = date(
                int(latest["date"][:4]),
                int(latest["date"][4:6]),
                int(latest["date"][6:8]),
            )

            stmt = insert(StockOHLCV).values(
                stock_code=stock_code,
                trade_date=trade_date,
                open_price=int(latest["open"]),
                high_price=int(latest["high"]),
                low_price=int(latest["low"]),
                close_price=int(latest["close"]),
                volume=int(latest["volume"]),
            ).on_conflict_do_update(
                index_elements=["stock_code", "trade_date"],
                set_={
                    "open_price": int(latest["open"]),
                    "high_price": int(latest["high"]),
                    "low_price": int(latest["low"]),
                    "close_price": int(latest["close"]),
                    "volume": int(latest["volume"]),
                }
            )
            await self.db.execute(stmt)
            await self.db.commit()
            return True

        except Exception as e:
            logger.error(f"{stock_code}: 일별 업데이트 실패 - {e}")
            await self.db.rollback()
            return False

    async def get_stats(self) -> dict:
        """OHLCV 저장 통계."""
        from sqlalchemy import func

        # 총 레코드 수
        total_stmt = select(func.count()).select_from(StockOHLCV)
        total_result = await self.db.execute(total_stmt)
        total_count = total_result.scalar() or 0

        # 종목 수
        stock_stmt = select(func.count(func.distinct(StockOHLCV.stock_code)))
        stock_result = await self.db.execute(stock_stmt)
        stock_count = stock_result.scalar() or 0

        # 날짜 범위
        date_stmt = select(
            func.min(StockOHLCV.trade_date),
            func.max(StockOHLCV.trade_date),
        )
        date_result = await self.db.execute(date_stmt)
        min_date, max_date = date_result.one()

        return {
            "total_records": total_count,
            "stock_count": stock_count,
            "min_date": min_date.isoformat() if min_date else None,
            "max_date": max_date.isoformat() if max_date else None,
        }
