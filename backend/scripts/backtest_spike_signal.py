"""수급 급증(Spike) 신호 백테스트.

과거 1년 데이터를 활용하여 급증 신호 발생 후 N일 수익률 분석.

실행: cd backend && python scripts/backtest_spike_signal.py
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from core.database import async_session_maker


async def get_spike_signals(
    recent_days: int = 2,
    base_days: int = 20,
    min_ratio: float = 3.0,
    min_amount: int = 1_000_000_000,  # 10억
    investor_type: str = "all",  # all, foreign, institution
):
    """과거 데이터에서 모든 급증 신호를 찾습니다."""

    async with async_session_maker() as db:
        # 모든 종목의 모든 날짜에 대해 급증 여부 체크
        # 각 날짜를 기준으로 최근 N일 vs 이전 M일 비교

        if investor_type == "foreign":
            amount_col = "foreign_net_amount"
        elif investor_type == "institution":
            amount_col = "institution_net_amount"
        else:
            amount_col = f"(foreign_net_amount + institution_net_amount)"

        query = text(f"""
            WITH daily_flow AS (
                SELECT
                    stock_code,
                    stock_name,
                    flow_date,
                    {amount_col} as net_amount
                FROM stock_investor_flows
                WHERE {amount_col} IS NOT NULL
            ),
            flow_with_stats AS (
                SELECT
                    stock_code,
                    stock_name,
                    flow_date,
                    net_amount,
                    -- 최근 N일 합계 (당일 포함)
                    SUM(net_amount) OVER (
                        PARTITION BY stock_code
                        ORDER BY flow_date
                        ROWS BETWEEN {recent_days - 1} PRECEDING AND CURRENT ROW
                    ) as recent_sum,
                    -- 최근 N일 카운트
                    COUNT(*) OVER (
                        PARTITION BY stock_code
                        ORDER BY flow_date
                        ROWS BETWEEN {recent_days - 1} PRECEDING AND CURRENT ROW
                    ) as recent_count,
                    -- 기준 기간 평균 (최근 N일 이전 M일)
                    AVG(net_amount) OVER (
                        PARTITION BY stock_code
                        ORDER BY flow_date
                        ROWS BETWEEN {recent_days + base_days - 1} PRECEDING AND {recent_days} PRECEDING
                    ) as base_avg,
                    -- 기준 기간 카운트
                    COUNT(*) OVER (
                        PARTITION BY stock_code
                        ORDER BY flow_date
                        ROWS BETWEEN {recent_days + base_days - 1} PRECEDING AND {recent_days} PRECEDING
                    ) as base_count
                FROM daily_flow
            )
            SELECT
                stock_code,
                stock_name,
                flow_date,
                recent_sum,
                base_avg,
                CASE
                    WHEN base_avg > 0 THEN recent_sum / (base_avg * {recent_days})
                    ELSE 0
                END as spike_ratio
            FROM flow_with_stats
            WHERE recent_count = {recent_days}
              AND base_count >= {base_days - 5}  -- 최소 15일 이상 데이터
              AND recent_sum >= :min_amount
              AND base_avg > 0
              AND recent_sum / (base_avg * {recent_days}) >= :min_ratio
            ORDER BY flow_date, spike_ratio DESC
        """)

        result = await db.execute(query, {
            "min_amount": min_amount,
            "min_ratio": min_ratio,
        })

        signals = []
        for row in result.fetchall():
            signals.append({
                "stock_code": row.stock_code,
                "stock_name": row.stock_name,
                "signal_date": row.flow_date,
                "recent_amount": int(row.recent_sum),
                "base_avg": float(row.base_avg),
                "spike_ratio": float(row.spike_ratio),
            })

        return signals


async def get_price_data():
    """OHLCV 데이터에서 가격 정보를 가져옵니다."""
    async with async_session_maker() as db:
        query = text("""
            SELECT stock_code, trade_date, close_price
            FROM stock_ohlcv
            ORDER BY stock_code, trade_date
        """)
        result = await db.execute(query)

        # stock_code -> {date -> close_price}
        price_data = defaultdict(dict)
        for row in result.fetchall():
            price_data[row.stock_code][row.trade_date] = row.close_price

        return price_data


def calculate_returns(signals: list, price_data: dict, holding_days: list = [5, 10, 20]):
    """급증 신호 발생 후 N일 수익률 계산."""

    results = []

    for signal in signals:
        stock_code = signal["stock_code"]
        signal_date = signal["signal_date"]

        if stock_code not in price_data:
            continue

        prices = price_data[stock_code]

        # 신호 날짜의 종가 찾기
        entry_price = prices.get(signal_date)
        if not entry_price:
            # 신호 날짜에 가격이 없으면 가장 가까운 다음 날짜 찾기
            sorted_dates = sorted(prices.keys())
            for d in sorted_dates:
                if d >= signal_date:
                    entry_price = prices[d]
                    signal_date = d
                    break

        if not entry_price:
            continue

        # N일 후 수익률 계산
        returns = {}
        sorted_dates = sorted(prices.keys())
        try:
            signal_idx = sorted_dates.index(signal_date)
        except ValueError:
            continue

        for days in holding_days:
            target_idx = signal_idx + days
            if target_idx < len(sorted_dates):
                exit_date = sorted_dates[target_idx]
                exit_price = prices[exit_date]
                ret = (exit_price - entry_price) / entry_price * 100
                returns[f"{days}d"] = ret
            else:
                returns[f"{days}d"] = None

        results.append({
            **signal,
            "entry_price": entry_price,
            **returns,
        })

    return results


def analyze_results(results: list, holding_days: list = [5, 10, 20]):
    """백테스트 결과 분석."""

    print("\n" + "="*70)
    print("수급 급증(Spike) 신호 백테스트 결과")
    print("="*70)

    print(f"\n총 급증 신호 수: {len(results)}개")

    # 날짜별 분포
    date_counts = defaultdict(int)
    for r in results:
        date_counts[r["signal_date"]] += 1

    print(f"신호 발생 일수: {len(date_counts)}일")
    print(f"일평균 신호 수: {len(results) / max(len(date_counts), 1):.1f}개")

    # 수익률 분석
    for days in holding_days:
        key = f"{days}d"
        valid_returns = [r[key] for r in results if r.get(key) is not None]

        if not valid_returns:
            print(f"\n[{days}일 후 수익률] 데이터 없음")
            continue

        avg_ret = sum(valid_returns) / len(valid_returns)
        positive_count = sum(1 for r in valid_returns if r > 0)
        win_rate = positive_count / len(valid_returns) * 100

        # 분위수 계산
        sorted_rets = sorted(valid_returns)
        median = sorted_rets[len(sorted_rets) // 2]
        q1 = sorted_rets[len(sorted_rets) // 4]
        q3 = sorted_rets[3 * len(sorted_rets) // 4]

        print(f"\n[{days}일 후 수익률]")
        print(f"  샘플 수: {len(valid_returns)}개")
        print(f"  평균 수익률: {avg_ret:+.2f}%")
        print(f"  중앙값: {median:+.2f}%")
        print(f"  승률 (수익 > 0): {win_rate:.1f}%")
        print(f"  25% 분위: {q1:+.2f}%")
        print(f"  75% 분위: {q3:+.2f}%")
        print(f"  최대 수익: {max(valid_returns):+.2f}%")
        print(f"  최대 손실: {min(valid_returns):+.2f}%")

    # 급증 배율별 분석
    print("\n" + "-"*70)
    print("급증 배율별 성과 분석 (10일 수익률 기준)")
    print("-"*70)

    ratio_buckets = [
        (3, 5, "3x~5x"),
        (5, 10, "5x~10x"),
        (10, 20, "10x~20x"),
        (20, float('inf'), "20x 이상"),
    ]

    for low, high, label in ratio_buckets:
        bucket_results = [r for r in results if low <= r["spike_ratio"] < high and r.get("10d") is not None]
        if not bucket_results:
            continue

        returns = [r["10d"] for r in bucket_results]
        avg_ret = sum(returns) / len(returns)
        win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100

        print(f"  {label}: 샘플 {len(bucket_results)}개, 평균 {avg_ret:+.2f}%, 승률 {win_rate:.1f}%")

    # 월별 분석
    print("\n" + "-"*70)
    print("월별 성과 분석 (10일 수익률 기준)")
    print("-"*70)

    monthly_results = defaultdict(list)
    for r in results:
        if r.get("10d") is not None:
            month_key = r["signal_date"].strftime("%Y-%m")
            monthly_results[month_key].append(r["10d"])

    for month in sorted(monthly_results.keys()):
        returns = monthly_results[month]
        avg_ret = sum(returns) / len(returns)
        win_rate = sum(1 for r in returns if r > 0) / len(returns) * 100
        print(f"  {month}: 신호 {len(returns)}개, 평균 {avg_ret:+.2f}%, 승률 {win_rate:.1f}%")

    # 상위 성과 종목
    print("\n" + "-"*70)
    print("상위 10 성과 종목 (10일 수익률 기준)")
    print("-"*70)

    sorted_by_return = sorted(
        [r for r in results if r.get("10d") is not None],
        key=lambda x: x["10d"],
        reverse=True
    )[:10]

    for i, r in enumerate(sorted_by_return, 1):
        print(f"  {i}. {r['stock_name']}({r['stock_code']}) "
              f"| 신호일: {r['signal_date']} "
              f"| 급증배율: {r['spike_ratio']:.1f}x "
              f"| 10일 수익률: {r['10d']:+.2f}%")

    # 하위 성과 종목
    print("\n" + "-"*70)
    print("하위 10 성과 종목 (10일 수익률 기준)")
    print("-"*70)

    sorted_by_return_asc = sorted(
        [r for r in results if r.get("10d") is not None],
        key=lambda x: x["10d"]
    )[:10]

    for i, r in enumerate(sorted_by_return_asc, 1):
        print(f"  {i}. {r['stock_name']}({r['stock_code']}) "
              f"| 신호일: {r['signal_date']} "
              f"| 급증배율: {r['spike_ratio']:.1f}x "
              f"| 10일 수익률: {r['10d']:+.2f}%")

    return {
        "total_signals": len(results),
        "signal_days": len(date_counts),
    }


async def main():
    print("=== 수급 급증(Spike) 신호 백테스트 ===")
    print()

    # 파라미터 설정
    recent_days = 2
    base_days = 20
    min_ratio = 3.0
    min_amount = 1_000_000_000  # 10억

    print(f"파라미터:")
    print(f"  - 최근 기간: {recent_days}일")
    print(f"  - 기준 기간: {base_days}일")
    print(f"  - 최소 급증 배율: {min_ratio}x")
    print(f"  - 최소 순매수금액: {min_amount / 100_000_000:.0f}억원")
    print()

    # 1. 급증 신호 찾기
    print("1. 과거 급증 신호 검색 중...")
    signals = await get_spike_signals(
        recent_days=recent_days,
        base_days=base_days,
        min_ratio=min_ratio,
        min_amount=min_amount,
        investor_type="all",
    )
    print(f"   -> {len(signals)}개 신호 발견")

    if not signals:
        print("급증 신호가 없습니다.")
        return

    # 2. 가격 데이터 로드
    print("2. 가격 데이터 로드 중...")
    price_data = await get_price_data()
    print(f"   -> {len(price_data)}개 종목 가격 데이터 로드")

    # 3. 수익률 계산
    print("3. 수익률 계산 중...")
    holding_days = [5, 10, 20]
    results = calculate_returns(signals, price_data, holding_days)
    print(f"   -> {len(results)}개 신호 수익률 계산 완료")

    # 4. 결과 분석
    analyze_results(results, holding_days)

    # 외국인 급증 vs 기관 급증 비교
    print("\n" + "="*70)
    print("투자자별 급증 신호 비교")
    print("="*70)

    for investor_type in ["foreign", "institution"]:
        type_label = "외국인" if investor_type == "foreign" else "기관"
        print(f"\n[{type_label} 급증 신호]")

        type_signals = await get_spike_signals(
            recent_days=recent_days,
            base_days=base_days,
            min_ratio=min_ratio,
            min_amount=min_amount,
            investor_type=investor_type,
        )

        if not type_signals:
            print(f"  {type_label} 급증 신호 없음")
            continue

        type_results = calculate_returns(type_signals, price_data, holding_days)

        for days in holding_days:
            key = f"{days}d"
            valid_returns = [r[key] for r in type_results if r.get(key) is not None]
            if valid_returns:
                avg_ret = sum(valid_returns) / len(valid_returns)
                win_rate = sum(1 for r in valid_returns if r > 0) / len(valid_returns) * 100
                print(f"  {days}일: 샘플 {len(valid_returns)}개, 평균 {avg_ret:+.2f}%, 승률 {win_rate:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
