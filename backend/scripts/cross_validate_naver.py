# -*- coding: utf-8 -*-
"""네이버 증권 재무 데이터와 DART DB 교차 검증 스크립트.

네이버 증권(FnGuide 기반) 연결재무제표 매출액과
우리 DB(DART 기반) 데이터를 비교하여 불일치를 찾아냅니다.

사용법:
    python scripts/cross_validate_naver.py --stock 950170
    python scripts/cross_validate_naver.py --audit
    python scripts/cross_validate_naver.py --audit --limit 50
    python scripts/cross_validate_naver.py --recollect 950170
"""
import asyncio
import sys
import os
import io
import re
import argparse
import logging

# Windows 콘솔 UTF-8 출력
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import select, and_, func
from core.database import async_session_maker
from models.financial_statement import FinancialStatement

logger = logging.getLogger(__name__)

REVENUE_NAMES = ["매출액", "수익(매출액)", "영업수익", "매출"]


async def fetch_naver_financial(stock_code: str) -> dict:
    """네이버 증권 메인 페이지에서 재무 요약 데이터 파싱.

    Returns:
        {
            "annual": {"2024.12": 3086, ...},   # 억원
            "quarterly": {"2024.09": 732, ...},  # 억원
            "fs_type": "CFS" or "OFS",
            "error": None or str,
        }
    """
    result = {"annual": {}, "quarterly": {}, "fs_type": "CFS", "error": None}

    url = f'https://finance.naver.com/item/main.naver?code={stock_code}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            text = resp.text

        if len(text) < 1000:
            result["error"] = "페이지 로드 실패"
            return result

        # cop_analysis 섹션 찾기
        idx = text.find('cop_analysis')
        if idx < 0:
            result["error"] = "재무분석 섹션 없음"
            return result

        section = text[idx:idx + 20000]

        # IFRS 유형 확인
        if "IFRS개별" in section or "GAAP개별" in section:
            result["fs_type"] = "OFS"

        # 연도 헤더 파싱
        th_years = re.findall(
            r'<th[^>]*>\s*(\d{4}\.\d{2})\s*(?:<em>.*?</em>)?\s*</th>',
            section,
        )
        if not th_years:
            result["error"] = "연도 헤더 없음"
            return result

        # 추정치(E) 연도 식별 - 여러 패턴 대응
        estimate_years = set()
        for m in re.finditer(r'(\d{4}\.\d{2})\s*<em>\&#40;E\&#41;</em>', section):
            estimate_years.add(m.group(1))
        for m in re.finditer(r'(\d{4}\.\d{2})\s*<em>\(E\)</em>', section):
            estimate_years.add(m.group(1))
        result["estimate_years"] = estimate_years

        # 연간(앞 4개) vs 분기(뒤 6개) 분리
        # 일반적으로 연간 3~4개 + 분기 5~6개
        # 첫 추정치(E) 위치 또는 4번째까지를 연간으로 간주
        annual_end = min(4, len(th_years))
        for i, y in enumerate(th_years[:5]):
            if y in estimate_years:
                annual_end = i + 1  # E 포함
                break

        annual_years = th_years[:annual_end]
        quarterly_years = th_years[annual_end:]

        # 매출액 행 파싱 (tbody 첫 번째 tr)
        thead_end = section.find('</thead>')
        if thead_end < 0:
            result["error"] = "thead 없음"
            return result

        after_thead = section[thead_end:]

        # 매출액 행의 td 값들 추출
        revenue_row = re.search(
            r'매출액.*?</th>(.*?)</tr>',
            after_thead, re.DOTALL,
        )
        if not revenue_row:
            # 영업수익 등 대안 시도
            for alt in ["영업수익", "수익"]:
                revenue_row = re.search(
                    rf'{alt}.*?</th>(.*?)</tr>',
                    after_thead, re.DOTALL,
                )
                if revenue_row:
                    break

        if not revenue_row:
            result["error"] = "매출액 행 없음"
            return result

        row_html = revenue_row.group(1)
        # td 값 추출 (whitespace 제거, comma 제거)
        td_values = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
        clean_values = []
        for td in td_values:
            v = re.sub(r'<[^>]+>', '', td).strip()
            v = v.replace(',', '').replace('&nbsp;', '').replace('\n', '').replace('\t', '')
            clean_values.append(v)

        # 연도에 매핑 (인덱스 기반 - 중복 연도 대응)
        for i, year_str in enumerate(annual_years):
            if i < len(clean_values) and clean_values[i]:
                try:
                    result["annual"][year_str] = int(clean_values[i])
                except ValueError:
                    pass

        offset = len(annual_years)
        for j, year_str in enumerate(quarterly_years):
            idx = offset + j
            if idx < len(clean_values) and clean_values[idx]:
                try:
                    result["quarterly"][year_str] = int(clean_values[idx])
                except ValueError:
                    pass

        return result

    except httpx.HTTPStatusError as e:
        result["error"] = f"HTTP {e.response.status_code}"
        return result
    except Exception as e:
        result["error"] = str(e)
        return result


async def get_db_annual_revenue(stock_code: str) -> dict:
    """DB에서 연간 매출액 + fs_div 조회.

    Returns:
        {bsns_year: {"revenue": int(원), "fs_div": "CFS"/"OFS"}}
    """
    result = {}
    async with async_session_maker() as db:
        stmt = (
            select(
                FinancialStatement.bsns_year,
                FinancialStatement.fs_div,
                FinancialStatement.thstrm_amount,
                FinancialStatement.account_nm,
                FinancialStatement.sj_nm,
            )
            .where(and_(
                FinancialStatement.stock_code == stock_code,
                FinancialStatement.reprt_code == "11011",
                FinancialStatement.account_nm.in_(REVENUE_NAMES),
                FinancialStatement.sj_div.in_(["IS", "CIS"]),
            ))
            .order_by(
                FinancialStatement.bsns_year.desc(),
                FinancialStatement.fs_div,
                FinancialStatement.ord,
            )
        )
        rows = (await db.execute(stmt)).all()

        for year, fs_div, amount, acc_nm, sj_nm in rows:
            if "3개월" in (sj_nm or ""):
                continue
            if year not in result:
                result[year] = {"revenue": amount, "fs_div": fs_div}
            elif result[year]["fs_div"] == "OFS" and fs_div == "CFS":
                result[year] = {"revenue": amount, "fs_div": fs_div}

    return result


async def get_settlement_month(stock_code: str) -> str:
    """결산월 추정. DB의 thstrm_nm 또는 네이버 연도 패턴에서 추출."""
    async with async_session_maker() as db:
        stmt = (
            select(FinancialStatement.bsns_year)
            .where(and_(
                FinancialStatement.stock_code == stock_code,
                FinancialStatement.reprt_code == "11011",
            ))
            .order_by(FinancialStatement.bsns_year.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


def _match_years(naver_year_str: str, db_data: dict) -> tuple:
    """네이버 연도(2025.02)와 DB bsns_year 매칭.

    DART bsns_year는 결산연도 기준. 비12월 결산사도 결산연도 사용.
    예: JTC FY ending Feb 2025 → bsns_year "2025"

    Returns: (db_year, db_entry) or (None, None)
    """
    parts = naver_year_str.split(".")
    naver_year = int(parts[0])

    # 같은 연도 우선, 전년도 fallback
    candidates = [str(naver_year), str(naver_year - 1)]

    for c in candidates:
        if c in db_data:
            return c, db_data[c]

    return None, None


async def cross_validate_stock(stock_code: str, verbose: bool = True) -> list[str]:
    """단일 종목 네이버 교차 검증."""
    issues = []

    naver = await fetch_naver_financial(stock_code)
    if naver.get("error"):
        if verbose:
            print(f"  [{stock_code}] 네이버 오류: {naver['error']}")
        return [f"네이버 조회 실패: {naver['error']}"]

    db_data = await get_db_annual_revenue(stock_code)

    if verbose:
        print(f"\n{'='*80}")
        print(f"종목: {stock_code} | 네이버: {naver['fs_type']}")
        print(f"{'='*80}")
        print(f"  네이버 연간: {naver['annual']}")
        print(f"  네이버 분기: {naver['quarterly']}")
        db_summary = {y: f"{d['revenue']/1e8:.0f}억({d['fs_div']})" for y, d in db_data.items()}
        print(f"  DB 연간:    {db_summary}")
        print()
        print(f"  {'네이버연도':>10} | {'네이버(억)':>12} | {'DB(억)':>12} | {'DB기준':>6} | {'차이':>8} | 판정")
        print(f"  {'-'*10}-+-{'-'*12}-+-{'-'*12}-+-{'-'*6}-+-{'-'*8}-+------")

    estimate_years = naver.get("estimate_years", set())

    for naver_year_str in sorted(naver["annual"].keys(), reverse=True):
        naver_rev = naver["annual"][naver_year_str]
        is_estimate = naver_year_str in estimate_years
        db_year, db_entry = _match_years(naver_year_str, db_data)

        db_rev = None
        db_fs = "N/A"
        diff_pct = None
        verdict = ""

        if db_entry and db_entry["revenue"] is not None:
            db_rev = db_entry["revenue"] / 1e8
            db_fs = db_entry["fs_div"]

            if naver_rev and naver_rev != 0:
                diff_pct = abs(db_rev - naver_rev) / naver_rev * 100

                if diff_pct < 5:
                    verdict = "OK"
                elif is_estimate and diff_pct < 30:
                    verdict = "추정치"
                elif diff_pct < 20:
                    verdict = "주의"
                    issues.append(
                        f"{naver_year_str} 매출 차이 {diff_pct:.1f}%: "
                        f"네이버={naver_rev}억 vs DB={db_rev:.0f}억({db_fs})"
                    )
                else:
                    verdict = "불일치!"
                    issues.append(
                        f"{naver_year_str} 매출 대폭 불일치 {diff_pct:.0f}%: "
                        f"네이버={naver_rev}억 vs DB={db_rev:.0f}억({db_fs})"
                    )
                    if naver["fs_type"] == "CFS" and db_fs == "OFS":
                        issues.append(
                            f"  -> 원인: 네이버=CFS(연결), DB=OFS(개별). CFS 재수집 필요"
                        )
        else:
            naver_year = int(naver_year_str.split(".")[0])
            if db_data and naver_year < min(int(y) for y in db_data.keys()):
                verdict = "범위밖"
            else:
                verdict = "DB없음"
                if naver_rev:
                    issues.append(f"{naver_year_str} DB 데이터 없음 (네이버={naver_rev}억)")

        if verbose:
            est_mark = "(E)" if is_estimate else ""
            n_str = f"{naver_rev:>10,}억" if naver_rev else f"{'N/A':>12}"
            d_str = f"{db_rev:>10,.0f}억" if db_rev is not None else f"{'N/A':>12}"
            diff_str = f"{diff_pct:>7.1f}%" if diff_pct is not None else f"{'N/A':>8}"
            print(f"  {naver_year_str:>10}{est_mark:>3} | {n_str} | {d_str} | {db_fs:>6} | {diff_str} | {verdict}")

    return issues


async def audit_all(limit: int = 0, threshold_pct: float = 20.0):
    """전체 종목 교차 검증."""
    async with async_session_maker() as db:
        stmt = (
            select(FinancialStatement.stock_code)
            .group_by(FinancialStatement.stock_code)
        )
        result = await db.execute(stmt)
        stock_codes = sorted([r[0] for r in result.all()])

    if limit > 0:
        stock_codes = stock_codes[:limit]

    total = len(stock_codes)
    print(f"\n전체 {total}개 종목 네이버 교차 검증 시작...\n")

    ok_count = 0
    error_count = 0
    all_issues = []

    for i, sc in enumerate(stock_codes):
        if (i + 1) % 20 == 0 or i == 0:
            print(f"  진행: {i+1}/{total} ({(i+1)/total*100:.0f}%) ...")

        try:
            issues = await cross_validate_stock(sc, verbose=False)
            if not issues:
                ok_count += 1
            elif any("조회 실패" in iss for iss in issues):
                error_count += 1
            else:
                all_issues.append((sc, issues))
        except Exception as e:
            error_count += 1
            logger.debug(f"{sc} 오류: {e}")

        await asyncio.sleep(0.3)  # Rate limit

    mismatch_count = len(all_issues)
    print(f"\n{'='*80}")
    print(f"교차 검증 결과 요약")
    print(f"{'='*80}")
    print(f"  검사: {total}종목")
    print(f"  일치(차이<5%): {ok_count}종목")
    print(f"  불일치: {mismatch_count}종목")
    print(f"  조회실패: {error_count}종목")

    if all_issues:
        # CFS/OFS 원인과 기타 분리
        cfs_issues = []
        other_issues = []
        for sc, issues in all_issues:
            if any("CFS 재수집" in iss for iss in issues):
                cfs_issues.append((sc, issues))
            else:
                other_issues.append((sc, issues))

        if cfs_issues:
            print(f"\n  [CFS/OFS 불일치] {len(cfs_issues)}종목 (CFS 재수집 필요):")
            for sc, issues in cfs_issues:
                for iss in issues:
                    print(f"    {sc}: {iss}")

        if other_issues:
            print(f"\n  [기타 불일치] {len(other_issues)}종목:")
            for sc, issues in other_issues:
                for iss in issues:
                    print(f"    {sc}: {iss}")


async def recollect_cfs(stock_code: str):
    """특정 종목의 OFS → CFS 재수집."""
    from sqlalchemy import delete as sql_delete
    from services.financial_statement_service import FinancialStatementService

    async with async_session_maker() as db:
        # 현재 상태
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
        )
        result = await db.execute(stmt)
        periods = result.all()

        ofs_only = []
        has_cfs = set()
        for y, rc, fs, cnt in periods:
            if fs == "CFS":
                has_cfs.add((y, rc))
            elif fs == "OFS":
                ofs_only.append((y, rc))

        to_retry = [(y, rc) for y, rc in ofs_only if (y, rc) not in has_cfs]

        if not to_retry:
            print(f"  {stock_code}: 모든 기간에 CFS 존재 또는 재수집 대상 없음")
            return 0

        print(f"  {stock_code}: {len(to_retry)}개 기간 OFS 삭제 후 CFS 재수집")

        for year, rc in to_retry:
            del_stmt = sql_delete(FinancialStatement).where(and_(
                FinancialStatement.stock_code == stock_code,
                FinancialStatement.bsns_year == year,
                FinancialStatement.reprt_code == rc,
                FinancialStatement.fs_div == "OFS",
            ))
            await db.execute(del_stmt)

        await db.commit()

        # 재수집
        svc = FinancialStatementService(db)
        result = await svc.collect_financial_data(stock_code, years=5)
        print(f"  {stock_code}: 재수집 완료 - {result}")
        return 1


async def main():
    parser = argparse.ArgumentParser(description="네이버 증권 교차 검증")
    parser.add_argument("--stock", help="검증할 종목코드")
    parser.add_argument("--audit", action="store_true", help="전체 종목 검증")
    parser.add_argument("--limit", type=int, default=0, help="최대 종목 수")
    parser.add_argument("--recollect", help="CFS 재수집할 종목코드")
    args = parser.parse_args()

    if args.recollect:
        await recollect_cfs(args.recollect)
    elif args.audit:
        await audit_all(limit=args.limit)
    elif args.stock:
        await cross_validate_stock(args.stock)
    else:
        await cross_validate_stock("950170")


if __name__ == "__main__":
    asyncio.run(main())
