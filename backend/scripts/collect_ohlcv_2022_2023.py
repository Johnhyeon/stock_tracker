"""DB 기존 종목의 2022~2023년 OHLCV 데이터 수집 (FinanceDataReader + 병렬).

ThreadPoolExecutor로 10개 워커 병렬 처리.
이미 충분한 데이터가 있는 종목은 스킵.
bulk upsert로 빠른 DB 저장.

실행: cd backend && python -u scripts/collect_ohlcv_2022_2023.py
"""
import asyncio
import sys
import os
import time
from datetime import datetime, date as date_type
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import FinanceDataReader as fdr
from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import insert
from core.database import async_session_maker
from models.stock_ohlcv import StockOHLCV

WORKERS = 10
BATCH_DB_SIZE = 500  # bulk upsert 단위


def log(msg: str):
    print(msg, flush=True)


def fetch_ohlcv_fdr(stock_code: str, start: str, end: str) -> list[dict]:
    """FinanceDataReader로 OHLCV 조회 (동기, ThreadPool용)."""
    try:
        df = fdr.DataReader(stock_code, start, end)
        if df is None or df.empty:
            return []

        results = []
        for idx, row in df.iterrows():
            trade_date = idx.strftime("%Y-%m-%d")
            open_val = int(row.get("Open", 0) or 0)
            if open_val <= 0:
                continue
            close_val = int(row.get("Close", 0) or 0)
            if close_val <= 0:
                continue
            dt = idx.to_pydatetime()
            if dt.weekday() >= 5:
                continue
            results.append({
                "stock_code": stock_code,
                "trade_date": trade_date,
                "open_price": open_val,
                "high_price": int(row.get("High", 0) or 0),
                "low_price": int(row.get("Low", 0) or 0),
                "close_price": close_val,
                "volume": int(row.get("Volume", 0) or 0),
            })
        return results
    except Exception:
        return []


async def get_stocks_needing_data() -> list[str]:
    """2022~2023년 데이터가 부족한 종목 목록 조회."""
    async with async_session_maker() as db:
        all_stmt = select(func.distinct(StockOHLCV.stock_code))
        all_result = await db.execute(all_stmt)
        all_codes = {row[0] for row in all_result.fetchall()}

        enough_stmt = (
            select(StockOHLCV.stock_code)
            .where(and_(
                StockOHLCV.trade_date >= date_type(2022, 1, 1),
                StockOHLCV.trade_date <= date_type(2023, 12, 31),
            ))
            .group_by(StockOHLCV.stock_code)
            .having(func.count() >= 400)
        )
        enough_result = await db.execute(enough_stmt)
        enough_codes = {row[0] for row in enough_result.fetchall()}

        need_codes = all_codes - enough_codes
        return sorted(need_codes)


async def bulk_upsert(rows: list[dict]) -> int:
    """bulk upsert으로 한 번에 다수 레코드 저장."""
    if not rows:
        return 0

    async with async_session_maker() as db:
        # 날짜 문자열 → date 변환
        for r in rows:
            if isinstance(r["trade_date"], str):
                r["trade_date"] = datetime.strptime(r["trade_date"], "%Y-%m-%d").date()

        stmt = insert(StockOHLCV).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_code", "trade_date"],
            set_={
                "open_price": stmt.excluded.open_price,
                "high_price": stmt.excluded.high_price,
                "low_price": stmt.excluded.low_price,
                "close_price": stmt.excluded.close_price,
                "volume": stmt.excluded.volume,
            },
        )
        await db.execute(stmt)
        await db.commit()
    return len(rows)


async def main():
    start_time = time.time()

    need_codes = await get_stocks_needing_data()
    total = len(need_codes)

    log(f"=== 2022~2023년 OHLCV 수집 (FinanceDataReader) ===")
    log(f"데이터 부족 종목: {total}개 | 워커: {WORKERS}개")
    log("")

    if total == 0:
        log("모든 종목의 2022~2023 데이터가 충분합니다!")
        return

    success = 0
    fail = 0
    total_records = 0
    pending_rows: list[dict] = []

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        future_to_code = {
            executor.submit(fetch_ohlcv_fdr, code, "2022-01-01", "2023-12-31"): code
            for code in need_codes
        }

        done_count = 0
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            done_count += 1

            try:
                data = future.result()
                if data:
                    pending_rows.extend(data)
                    success += 1
                    total_records += len(data)
                else:
                    fail += 1
            except Exception:
                fail += 1

            # bulk upsert: BATCH_DB_SIZE 도달 시 DB 저장
            if len(pending_rows) >= BATCH_DB_SIZE:
                try:
                    await bulk_upsert(pending_rows)
                except Exception as e:
                    log(f"  [DB ERROR] {e}")
                pending_rows.clear()

            # 진행률 (20개마다 또는 마지막)
            if done_count % 20 == 0 or done_count == total:
                elapsed = time.time() - start_time
                speed = done_count / elapsed if elapsed > 0 else 0
                eta = (total - done_count) / speed if speed > 0 else 0
                log(f"  [{done_count}/{total}] {done_count/total*100:.1f}% | "
                    f"ok={success} fail={fail} rec={total_records:,} | "
                    f"{speed:.1f}/s ETA {eta/60:.0f}m")

    # 남은 레코드 저장
    if pending_rows:
        try:
            await bulk_upsert(pending_rows)
        except Exception as e:
            log(f"  [DB ERROR] 최종 저장 실패: {e}")

    elapsed = time.time() - start_time
    log("")
    log("=" * 55)
    log(f"=== 완료 ({elapsed:.0f}초 = {elapsed/60:.1f}분) ===")
    log(f"성공: {success} | 실패: {fail}")
    log(f"총 레코드: {total_records:,}개")
    log("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
