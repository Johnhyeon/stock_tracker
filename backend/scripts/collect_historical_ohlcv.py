"""pykrx를 이용한 과거 1년치 OHLCV 데이터 수집.

실행: cd backend && python scripts/collect_historical_ohlcv.py
"""
import asyncio
import json
import sys
import os
from datetime import datetime, timedelta, date
from pathlib import Path
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pykrx import stock
from sqlalchemy.dialects.postgresql import insert
from core.database import async_session_maker
from models.stock_ohlcv import StockOHLCV


THEME_MAP_PATH = Path(__file__).parent.parent / "data" / "theme_map.json"


def load_theme_stocks() -> dict[str, str]:
    """테마맵에서 종목코드 -> 종목명 딕셔너리 로드."""
    with open(THEME_MAP_PATH, "r", encoding="utf-8") as f:
        theme_map = json.load(f)

    stocks = {}
    for theme_stocks in theme_map.values():
        for stock_info in theme_stocks:
            code = stock_info.get("code")
            name = stock_info.get("name", "")
            if code:
                stocks[code] = name
    return stocks


def get_ohlcv_pykrx(stock_code: str, start_date: str, end_date: str) -> list[dict]:
    """pykrx로 종목의 OHLCV 데이터 조회.

    Returns:
        [
            {
                "date": "2025-01-15",
                "open": 10000,
                "high": 10500,
                "low": 9800,
                "close": 10200,
                "volume": 1234567,
            },
            ...
        ]
    """
    try:
        df = stock.get_market_ohlcv_by_date(start_date, end_date, stock_code)
        if df.empty:
            return []

        results = []
        for date_idx, row in df.iterrows():
            date_str = date_idx.strftime("%Y-%m-%d")
            # 시가가 0이면 거래 없는 날로 간주 (스킵)
            if row.get("시가", 0) == 0:
                continue
            results.append({
                "date": date_str,
                "open": int(row.get("시가", 0) or 0),
                "high": int(row.get("고가", 0) or 0),
                "low": int(row.get("저가", 0) or 0),
                "close": int(row.get("종가", 0) or 0),
                "volume": int(row.get("거래량", 0) or 0),
            })
        return results
    except Exception as e:
        print(f"  {stock_code} 조회 실패: {e}")
        return []


async def save_ohlcv_data(stock_code: str, ohlcv_data: list[dict]):
    """OHLCV 데이터 DB 저장."""
    if not ohlcv_data:
        return 0

    async with async_session_maker() as db:
        saved_count = 0
        for item in ohlcv_data:
            trade_date = datetime.strptime(item["date"], "%Y-%m-%d").date()

            stmt = insert(StockOHLCV).values(
                stock_code=stock_code,
                trade_date=trade_date,
                open_price=item["open"],
                high_price=item["high"],
                low_price=item["low"],
                close_price=item["close"],
                volume=item["volume"],
            ).on_conflict_do_update(
                index_elements=['stock_code', 'trade_date'],
                set_={
                    'open_price': item["open"],
                    'high_price': item["high"],
                    'low_price': item["low"],
                    'close_price': item["close"],
                    'volume': item["volume"],
                }
            )

            await db.execute(stmt)
            saved_count += 1

        await db.commit()
        return saved_count


async def main():
    # 종목 로드
    stocks = load_theme_stocks()
    stock_codes = list(stocks.keys())
    total = len(stock_codes)

    print(f"=== 과거 1년치 OHLCV 데이터 수집 ===")
    print(f"대상 종목: {total}개")
    print()

    # 날짜 범위 (1년)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    print(f"수집 기간: {start_str} ~ {end_str}")
    print()

    success_count = 0
    fail_count = 0
    total_records = 0

    for i, code in enumerate(stock_codes):
        name = stocks[code]
        print(f"[{i+1}/{total}] {name}({code})...", end=" ", flush=True)

        # pykrx 호출 (동기)
        ohlcv_data = get_ohlcv_pykrx(code, start_str, end_str)

        if ohlcv_data:
            saved = await save_ohlcv_data(code, ohlcv_data)
            total_records += saved
            success_count += 1
            print(f"{saved}일 저장")
        else:
            fail_count += 1
            print("데이터 없음")

        # API 속도 제한 (0.2초 대기 - OHLCV는 더 빠름)
        time.sleep(0.2)

        # 진행률 출력 (100개마다)
        if (i + 1) % 100 == 0:
            print(f"\n--- 진행률: {i+1}/{total} ({(i+1)/total*100:.1f}%) ---\n")

    print()
    print("=== 수집 완료 ===")
    print(f"성공: {success_count}개 종목")
    print(f"실패: {fail_count}개 종목")
    print(f"총 레코드: {total_records}개")


if __name__ == "__main__":
    asyncio.run(main())
