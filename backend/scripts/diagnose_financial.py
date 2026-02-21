"""재무 데이터 진단 스크립트 - JTC(950170) 및 전체 종목 검증."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, and_, func, text
from core.database import async_session_maker
from models.financial_statement import FinancialStatement


REVENUE_NAMES = ["매출액", "수익(매출액)", "영업수익", "매출"]


async def diagnose_stock(stock_code: str):
    """특정 종목의 DB 재무 원시 데이터 덤프."""
    async with async_session_maker() as db:
        # 1) 저장된 모든 보고서 기간
        stmt = (
            select(
                FinancialStatement.bsns_year,
                FinancialStatement.reprt_code,
                FinancialStatement.fs_div,
                func.count().label("cnt"),
            )
            .where(FinancialStatement.stock_code == stock_code)
            .group_by(
                FinancialStatement.bsns_year,
                FinancialStatement.reprt_code,
                FinancialStatement.fs_div,
            )
            .order_by(
                FinancialStatement.bsns_year.desc(),
                FinancialStatement.reprt_code,
            )
        )
        result = await db.execute(stmt)
        periods = result.all()

        print(f"\n{'='*80}")
        print(f"종목: {stock_code} - 저장된 보고서 기간 ({len(periods)}건)")
        print(f"{'='*80}")
        for year, rc, fs_div, cnt in periods:
            rc_name = {"11011": "연간", "11012": "반기", "11013": "1분기", "11014": "3분기"}.get(rc, rc)
            print(f"  {year} {rc_name}({rc}) {fs_div} - {cnt}개 항목")

        # 2) 매출액 raw 데이터 (모든 기간, sj_nm 포함)
        print(f"\n{'='*80}")
        print("매출액 관련 원시 데이터 (IS/CIS)")
        print(f"{'='*80}")

        for rev_name in REVENUE_NAMES + ["영업수익", "수익"]:
            stmt2 = (
                select(FinancialStatement)
                .where(
                    FinancialStatement.stock_code == stock_code,
                    FinancialStatement.account_nm.like(f"%{rev_name}%"),
                    FinancialStatement.sj_div.in_(["IS", "CIS"]),
                )
                .order_by(
                    FinancialStatement.bsns_year.desc(),
                    FinancialStatement.reprt_code,
                    FinancialStatement.fs_div,
                )
            )
            result2 = await db.execute(stmt2)
            rows = result2.scalars().all()
            if rows:
                print(f"\n  --- 계정명 패턴: '{rev_name}' ---")
                for r in rows:
                    rc_name = {"11011": "연간", "11012": "반기", "11013": "Q1", "11014": "Q3"}.get(r.reprt_code, r.reprt_code)
                    thstrm = f"{r.thstrm_amount:>20,}" if r.thstrm_amount is not None else f"{'None':>20}"
                    frmtrm = f"{r.frmtrm_amount:>20,}" if r.frmtrm_amount is not None else f"{'None':>20}"
                    print(
                        f"  {r.bsns_year} {rc_name:>4}({r.reprt_code}) {r.fs_div}"
                        f" | sj_nm={r.sj_nm!r:40s}"
                        f" | 당기={thstrm} | 전기={frmtrm}"
                        f" | account_nm={r.account_nm!r}"
                    )

        # 3) 누적 vs 개별 판별 시뮬레이션
        print(f"\n{'='*80}")
        print("누적/개별 판별 시뮬레이션")
        print(f"{'='*80}")

        years_to_check = set()
        for year, rc, fs_div, cnt in periods:
            years_to_check.add(year)

        for year in sorted(years_to_check, reverse=True):
            # 연간 매출
            annual_rev = await _get_revenue(db, stock_code, year, "11011")
            q3_rev = await _get_revenue(db, stock_code, year, "11014")
            h1_rev = await _get_revenue(db, stock_code, year, "11012")
            q1_rev = await _get_revenue(db, stock_code, year, "11013")

            def fmt(v):
                if v is None:
                    return "N/A"
                return f"{v/100_000_000:.1f}억"

            ratio = None
            if annual_rev and q3_rev and annual_rev > 0:
                ratio = q3_rev / annual_rev
            elif annual_rev and h1_rev and annual_rev > 0:
                ratio = h1_rev / annual_rev

            det = "누적" if (ratio and ratio > 0.5) else "개별" if ratio else "판별불가"

            print(f"\n  {year}년:")
            print(f"    Q1(11013): {fmt(q1_rev)}")
            print(f"    H1(11012): {fmt(h1_rev)}")
            print(f"    Q3(11014): {fmt(q3_rev)}")
            print(f"    연간(11011): {fmt(annual_rev)}")
            if ratio is not None:
                print(f"    비율: {ratio:.3f} → 판별={det}")
            else:
                print(f"    비율: 계산불가 → 판별={det}")

            # 올바른 분기 계산 (항상 누적 차감 방식)
            if q1_rev is not None:
                print(f"    [올바른 계산] Q1 = {fmt(q1_rev)}")
            if h1_rev is not None and q1_rev is not None:
                q2 = h1_rev - q1_rev
                print(f"    [올바른 계산] Q2 = H1-Q1 = {fmt(h1_rev)}-{fmt(q1_rev)} = {fmt(q2)}")
            if q3_rev is not None and h1_rev is not None:
                q3_ind = q3_rev - h1_rev
                print(f"    [올바른 계산] Q3 = 9M-H1 = {fmt(q3_rev)}-{fmt(h1_rev)} = {fmt(q3_ind)}")
            if annual_rev is not None and q3_rev is not None:
                q4 = annual_rev - q3_rev
                print(f"    [올바른 계산] Q4 = Annual-9M = {fmt(annual_rev)}-{fmt(q3_rev)} = {fmt(q4)}")

            # 현재 시스템이 개별로 판별했을 때의 결과
            if det == "개별":
                print(f"    [현재 버그] Q2 = H1 그대로 = {fmt(h1_rev)} ← 누적값 그대로 사용!")
                print(f"    [현재 버그] Q3 = 9M 그대로 = {fmt(q3_rev)} ← 누적값 그대로 사용!")
                if annual_rev is not None and q1_rev is not None and h1_rev is not None and q3_rev is not None:
                    q4_bug = annual_rev - q1_rev - h1_rev - q3_rev
                    print(f"    [현재 버그] Q4 = Annual-Q1-H1-9M = {fmt(q4_bug)} ← 이중차감!")


async def _get_revenue(db, stock_code, year, reprt_code):
    """특정 기간의 매출액(thstrm_amount) 조회. CFS 우선, 3개월 제외."""
    for fs_div in ["CFS", "OFS"]:
        stmt = (
            select(FinancialStatement.thstrm_amount, FinancialStatement.sj_nm)
            .where(and_(
                FinancialStatement.stock_code == stock_code,
                FinancialStatement.bsns_year == year,
                FinancialStatement.reprt_code == reprt_code,
                FinancialStatement.fs_div == fs_div,
                FinancialStatement.sj_div.in_(["IS", "CIS"]),
                FinancialStatement.account_nm.in_(REVENUE_NAMES),
            ))
            .order_by(FinancialStatement.ord)
        )
        result = await db.execute(stmt)
        rows = result.all()
        # 3개월 제외, 누적 우선
        for amount, sj_nm in rows:
            if "3개월" not in (sj_nm or ""):
                return amount
        # 3개월만 있으면 그것이라도
        if rows:
            return rows[0][0]
    return None


async def audit_all_stocks():
    """전체 종목 매출 데이터 품질 검사."""
    async with async_session_maker() as db:
        # 재무 데이터가 있는 종목 목록
        stmt = (
            select(FinancialStatement.stock_code)
            .group_by(FinancialStatement.stock_code)
        )
        result = await db.execute(stmt)
        stock_codes = [r[0] for r in result.all()]

        print(f"\n전체 {len(stock_codes)}개 종목 검사 시작...\n")

        issues = []
        for sc in stock_codes:
            problems = await _check_stock_quality(db, sc)
            if problems:
                issues.append((sc, problems))

        print(f"\n{'='*80}")
        print(f"전수조사 결과: {len(stock_codes)}종목 중 {len(issues)}종목 이상 발견")
        print(f"{'='*80}")
        for sc, probs in issues:
            for p in probs:
                print(f"  {sc}: {p}")


async def _check_stock_quality(db, stock_code) -> list[str]:
    """종목별 데이터 품질 검사."""
    problems = []

    # 1) OFS만 있고 CFS가 없는 경우
    stmt = (
        select(
            FinancialStatement.bsns_year,
            FinancialStatement.reprt_code,
            FinancialStatement.fs_div,
        )
        .where(FinancialStatement.stock_code == stock_code)
        .group_by(
            FinancialStatement.bsns_year,
            FinancialStatement.reprt_code,
            FinancialStatement.fs_div,
        )
    )
    result = await db.execute(stmt)
    rows = result.all()

    fs_map = {}
    for year, rc, fs_div in rows:
        key = (year, rc)
        if key not in fs_map:
            fs_map[key] = set()
        fs_map[key].add(fs_div)

    ofs_only_count = sum(1 for v in fs_map.values() if v == {"OFS"})
    if ofs_only_count > 0:
        problems.append(f"OFS만 존재 ({ofs_only_count}개 기간) - CFS 누락 가능성")

    # 2) 분기 데이터 정합성 (연간 ≈ Q1+Q2+Q3+Q4)
    years_with_annual = set()
    for (year, rc) in fs_map:
        if rc == "11011":
            years_with_annual.add(year)

    for year in sorted(years_with_annual, reverse=True)[:3]:
        annual_rev = await _get_revenue(db, stock_code, year, "11011")
        q1_rev = await _get_revenue(db, stock_code, year, "11013")
        h1_rev = await _get_revenue(db, stock_code, year, "11012")
        q3_rev = await _get_revenue(db, stock_code, year, "11014")

        if all(v is not None for v in [annual_rev, q1_rev, h1_rev, q3_rev]):
            # 올바른 분기합: Q1 + (H1-Q1) + (9M-H1) + (Annual-9M) = Annual (항상 일치)
            # 잘못된 분기합 (개별 판별 시): Q1 + H1 + 9M + (Annual-Q1-H1-9M)
            if annual_rev > 0:
                q3_ratio = q3_rev / annual_rev
                if q3_ratio <= 0.5:
                    # 시스템이 "개별"로 판별 → 잘못된 분기값 사용
                    wrong_q4 = annual_rev - q1_rev - h1_rev - q3_rev
                    if wrong_q4 < 0:
                        problems.append(
                            f"{year}년 누적오판별: Q3/Annual={q3_ratio:.2f}≤0.5 → "
                            f"Q4={wrong_q4/1e8:.0f}억(음수!), "
                            f"Annual={annual_rev/1e8:.0f}억"
                        )

    return problems


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--stock", default="950170", help="진단할 종목코드")
    parser.add_argument("--audit", action="store_true", help="전체 종목 전수조사")
    args = parser.parse_args()

    if args.audit:
        await audit_all_stocks()
    else:
        await diagnose_stock(args.stock)


if __name__ == "__main__":
    asyncio.run(main())
