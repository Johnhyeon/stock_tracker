#!/usr/bin/env python3
"""OHLCV 데이터 수집 스크립트.

초기 240일치 데이터를 수집하거나, 일별 업데이트를 수행합니다.

사용법:
    # 아이디어에 등록된 종목들의 초기 데이터 수집
    python scripts/collect_ohlcv.py --init

    # 특정 종목 수집
    python scripts/collect_ohlcv.py --stock 005930

    # 일별 업데이트 (스케줄러용)
    python scripts/collect_ohlcv.py --daily

    # 통계 확인
    python scripts/collect_ohlcv.py --stats
"""
import sys
import re
import asyncio
import argparse
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from core.database import async_session_maker, async_engine, Base
from models import InvestmentIdea, StockOHLCV
from services.ohlcv_service import OHLCVService


def extract_stock_code(ticker: str) -> str | None:
    """'삼성전자(005930)' 형식에서 종목코드 추출."""
    match = re.search(r'\((\d{6})\)', ticker)
    return match.group(1) if match else None


async def get_idea_stock_codes() -> list[str]:
    """아이디어에 등록된 모든 종목 코드 조회."""
    async with async_session_maker() as session:
        stmt = select(InvestmentIdea.tickers)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        codes = set()
        for tickers in rows:
            if tickers:
                for ticker in tickers:
                    code = extract_stock_code(ticker)
                    if code:
                        codes.add(code)

        return list(codes)


async def collect_initial(days: int = 240, delay: float = 0.5):
    """아이디어 종목들의 초기 OHLCV 수집."""
    codes = await get_idea_stock_codes()
    print(f"수집 대상: {len(codes)}개 종목")
    print(f"종목 목록: {codes}")
    print()

    success = 0
    failed = []

    async with async_session_maker() as session:
        service = OHLCVService(session)

        for i, code in enumerate(codes, 1):
            print(f"[{i}/{len(codes)}] {code} 수집 중...", end=" ")

            try:
                count = await service.collect_ohlcv(code, days=days)
                if count > 0:
                    print(f"OK ({count}일)")
                    success += 1
                else:
                    print("스킵 (이미 존재)")
                    success += 1
            except Exception as e:
                print(f"실패: {e}")
                failed.append(code)

            # API 속도 제한 회피
            if i < len(codes):
                time.sleep(delay)

    print()
    print(f"완료: {success}개 성공, {len(failed)}개 실패")
    if failed:
        print(f"실패 종목: {failed}")


async def collect_single(stock_code: str, days: int = 240):
    """단일 종목 OHLCV 수집."""
    async with async_session_maker() as session:
        service = OHLCVService(session)
        count = await service.collect_ohlcv(stock_code, days=days, force=True)
        print(f"{stock_code}: {count}일 데이터 수집 완료")


async def collect_daily():
    """일별 업데이트 (모든 저장된 종목)."""
    async with async_session_maker() as session:
        # 저장된 종목 목록 조회
        from sqlalchemy import distinct
        stmt = select(distinct(StockOHLCV.stock_code))
        result = await session.execute(stmt)
        codes = [row[0] for row in result.all()]

        print(f"일별 업데이트: {len(codes)}개 종목")

        service = OHLCVService(session)
        success = 0

        for code in codes:
            try:
                if await service.collect_daily_update(code):
                    success += 1
            except Exception as e:
                print(f"{code} 실패: {e}")

            time.sleep(0.3)  # API 속도 제한

        print(f"완료: {success}/{len(codes)}개 업데이트")


async def show_stats():
    """OHLCV 저장 통계."""
    async with async_session_maker() as session:
        service = OHLCVService(session)
        stats = await service.get_stats()

        print("=== OHLCV 저장 통계 ===")
        print(f"총 레코드: {stats['total_records']:,}개")
        print(f"종목 수: {stats['stock_count']}개")
        print(f"기간: {stats['min_date']} ~ {stats['max_date']}")

        if stats['total_records'] > 0 and stats['stock_count'] > 0:
            avg_days = stats['total_records'] / stats['stock_count']
            print(f"종목당 평균: {avg_days:.1f}일")


async def main():
    parser = argparse.ArgumentParser(description="OHLCV 데이터 수집")
    parser.add_argument("--init", action="store_true", help="초기 데이터 수집 (아이디어 종목)")
    parser.add_argument("--stock", type=str, help="특정 종목 수집")
    parser.add_argument("--daily", action="store_true", help="일별 업데이트")
    parser.add_argument("--stats", action="store_true", help="통계 확인")
    parser.add_argument("--days", type=int, default=240, help="수집 일수 (기본: 240)")
    parser.add_argument("--delay", type=float, default=0.5, help="API 호출 간격 (초)")

    args = parser.parse_args()

    # 테이블 생성 확인
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if args.init:
        await collect_initial(days=args.days, delay=args.delay)
    elif args.stock:
        await collect_single(args.stock, days=args.days)
    elif args.daily:
        await collect_daily()
    elif args.stats:
        await show_stats()
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
