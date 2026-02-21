"""OHLCV 수집 현황 확인."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import async_session_maker
from sqlalchemy import text

async def main():
    async with async_session_maker() as db:
        r = await db.execute(text("""
            SELECT COUNT(*), COUNT(DISTINCT stock_code),
                   MIN(trade_date), MAX(trade_date)
            FROM stock_ohlcv
        """))
        row = r.fetchone()
        print("=== DB OHLCV ===")
        print(f"records: {row[0]:,} | stocks: {row[1]:,} | range: {row[2]} ~ {row[3]}")

        r2 = await db.execute(text("""
            SELECT EXTRACT(YEAR FROM trade_date)::int as yr,
                   COUNT(*) as cnt,
                   COUNT(DISTINCT stock_code) as stocks
            FROM stock_ohlcv GROUP BY yr ORDER BY yr
        """))
        print("\nYear   | Records    | Stocks")
        print("------+------------+-------")
        for yr, cnt, stocks in r2.fetchall():
            print(f" {yr}  | {cnt:>10,} | {stocks:>5,}")

asyncio.run(main())
