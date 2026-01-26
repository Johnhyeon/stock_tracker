"""pykrx를 이용한 과거 1년치 투자자별 매매동향 수집.

실행: cd backend && python scripts/collect_historical_flow.py
"""
import asyncio
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import time

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pykrx import stock
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from core.database import async_session_maker
from models.stock_investor_flow import StockInvestorFlow


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


def get_investor_flow_pykrx(stock_code: str, start_date: str, end_date: str) -> list[dict]:
    """pykrx로 종목의 투자자별 매매동향 조회.

    Returns:
        [
            {
                "date": "2025-01-15",
                "foreign_net_amount": 1000000000,  # 외국인 순매수금액
                "institution_net_amount": -500000000,  # 기관 순매수금액
                "individual_net_amount": -400000000,  # 개인 순매수금액
            },
            ...
        ]
    """
    try:
        df = stock.get_market_trading_value_by_date(start_date, end_date, stock_code)
        if df.empty:
            return []

        results = []
        for date_idx, row in df.iterrows():
            date_str = date_idx.strftime("%Y-%m-%d")
            results.append({
                "date": date_str,
                "foreign_net_amount": int(row.get("외국인합계", 0) or 0),
                "institution_net_amount": int(row.get("기관합계", 0) or 0),
                "individual_net_amount": int(row.get("개인", 0) or 0),
            })
        return results
    except Exception as e:
        print(f"  {stock_code} 조회 실패: {e}")
        return []


def calculate_flow_score(foreign_amount: int, institution_amount: int) -> float:
    """수급 점수 계산 (0-100)."""
    # 금액 기준 점수 (10억 단위)
    score = 50.0

    # 외국인 (최대 ±25점)
    foreign_score = min(25, max(-25, foreign_amount / 10_000_000_000 * 25))
    score += foreign_score

    # 기관 (최대 ±25점)
    institution_score = min(25, max(-25, institution_amount / 10_000_000_000 * 25))
    score += institution_score

    return max(0, min(100, score))


async def save_flow_data(stock_code: str, stock_name: str, flow_data: list[dict]):
    """수급 데이터 DB 저장."""
    if not flow_data:
        return 0

    async with async_session_maker() as db:
        saved_count = 0
        for item in flow_data:
            flow_date = datetime.strptime(item["date"], "%Y-%m-%d").date()
            foreign_amount = item["foreign_net_amount"]
            institution_amount = item["institution_net_amount"]
            individual_amount = item["individual_net_amount"]

            # 수량은 금액/주가로 추정 (정확하지 않으므로 0으로 설정)
            # pykrx는 금액만 제공
            flow_score = calculate_flow_score(foreign_amount, institution_amount)

            stmt = insert(StockInvestorFlow).values(
                stock_code=stock_code,
                stock_name=stock_name,
                flow_date=flow_date,
                foreign_net=0,  # pykrx는 수량 미제공
                institution_net=0,
                individual_net=0,
                foreign_net_amount=foreign_amount,
                institution_net_amount=institution_amount,
                individual_net_amount=individual_amount,
                flow_score=flow_score,
            ).on_conflict_do_update(
                index_elements=['stock_code', 'flow_date'],
                set_={
                    'stock_name': stock_name,
                    'foreign_net_amount': foreign_amount,
                    'institution_net_amount': institution_amount,
                    'individual_net_amount': individual_amount,
                    'flow_score': flow_score,
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

    print(f"=== 과거 1년치 투자자별 매매동향 수집 ===")
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
        flow_data = get_investor_flow_pykrx(code, start_str, end_str)

        if flow_data:
            saved = await save_flow_data(code, name, flow_data)
            total_records += saved
            success_count += 1
            print(f"{saved}일 저장")
        else:
            fail_count += 1
            print("데이터 없음")

        # API 속도 제한 (0.5초 대기)
        time.sleep(0.3)

        # 진행률 출력 (50개마다)
        if (i + 1) % 50 == 0:
            print(f"\n--- 진행률: {i+1}/{total} ({(i+1)/total*100:.1f}%) ---\n")

    print()
    print("=== 수집 완료 ===")
    print(f"성공: {success_count}개 종목")
    print(f"실패: {fail_count}개 종목")
    print(f"총 레코드: {total_records}개")


if __name__ == "__main__":
    asyncio.run(main())
