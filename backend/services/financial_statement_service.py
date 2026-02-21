"""재무제표 수집 및 조회 서비스."""
import logging
import re
from datetime import datetime
from typing import Optional

from sqlalchemy import select, and_, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.timezone import now_kst

from models.dart_corp_code import DartCorpCode
from models.financial_statement import FinancialStatement
from models.stock_ohlcv import StockOHLCV
from integrations.dart.client import get_dart_client
from schemas.financial_statement import (
    FinancialStatementItem,
    FinancialStatementResponse,
    FinancialRatios,
    AnnualFinancialData,
    FinancialSummaryResponse,
)

logger = logging.getLogger(__name__)

# 보고서 코드 매핑
REPRT_CODE_MAP = {
    "11011": "연간",
    "11012": "반기",
    "11013": "1분기",
    "11014": "3분기",
}

# 계정명 매칭 (DART 계정명이 회사마다 다름)
REVENUE_NAMES = ["매출액", "수익(매출액)", "영업수익", "매출"]
OPERATING_INCOME_NAMES = ["영업이익", "영업이익(손실)"]
NET_INCOME_NAMES = [
    "당기순이익", "당기순이익(손실)", "당기순이익(손실)의 귀속",
    "당기순손익",
    "반기순이익", "반기순이익(손실)",
    "반기순손익", "반기순손익(손실)",
    "분기순이익", "분기순이익(손실)",
    "분기순손익", "분기순손익(손실)",
]
TOTAL_ASSETS_NAMES = ["자산총계"]
TOTAL_LIABILITIES_NAMES = ["부채총계"]
TOTAL_EQUITY_NAMES = ["자본총계"]
CURRENT_ASSETS_NAMES = ["유동자산"]
CURRENT_LIABILITIES_NAMES = ["유동부채"]


def _parse_amount(value: str) -> Optional[int]:
    """DART 금액 문자열 파싱 (쉼표 제거, 빈값 None)."""
    if not value or value.strip() in ("", "-"):
        return None
    try:
        return int(value.replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _find_account_amount(
    accounts: list[dict],
    name_candidates: list[str],
    amount_key: str = "thstrm_amount",
    sj_divs: Optional[list[str]] = None,
) -> Optional[int]:
    """계정명 후보 리스트에서 매칭되는 금액 반환.

    sj_divs: 허용할 재무제표 구분 (BS, IS, CIS, CF, SCE).
    SCE의 '자본총계'와 BS의 '자본총계'가 다른 값이므로 반드시 구분해야 함.
    """
    for acc in accounts:
        if sj_divs and acc.get("sj_div") not in sj_divs:
            continue
        acc_nm = acc.get("account_nm", "")
        if acc_nm in name_candidates:
            val = acc.get(amount_key)
            if isinstance(val, int):
                return val
    return None


class FinancialStatementService:
    """재무제표 수집 및 조회 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.dart_client = get_dart_client()

    async def sync_corp_codes(self) -> int:
        """DART 고유번호 전체 다운로드 → DartCorpCode 테이블 upsert."""
        corp_list = await self.dart_client.download_corp_codes()
        if not corp_list:
            return 0

        count = 0
        batch_size = 500
        for i in range(0, len(corp_list), batch_size):
            batch = corp_list[i:i + batch_size]
            values = [
                {
                    "corp_code": c["corp_code"],
                    "corp_name": c["corp_name"],
                    "stock_code": c["stock_code"],
                    "modify_date": c["modify_date"],
                    "updated_at": now_kst().replace(tzinfo=None),
                }
                for c in batch
            ]
            stmt = pg_insert(DartCorpCode).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["corp_code"],
                set_={
                    "corp_name": stmt.excluded.corp_name,
                    "stock_code": stmt.excluded.stock_code,
                    "modify_date": stmt.excluded.modify_date,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            await self.db.execute(stmt)
            count += len(batch)

        await self.db.commit()
        logger.info(f"Synced {count} corp codes")
        return count

    async def get_corp_code(self, stock_code: str) -> Optional[str]:
        """종목코드로 DART 고유번호 조회. 테이블이 비어있으면 자동 동기화."""
        stmt = select(DartCorpCode.corp_code).where(
            DartCorpCode.stock_code == stock_code
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            # 테이블이 비어있는지 확인 후 자동 동기화
            count_result = await self.db.execute(
                select(func.count()).select_from(DartCorpCode)
            )
            total = count_result.scalar() or 0
            if total == 0:
                logger.info("dart_corp_codes 테이블이 비어있습니다. 자동 동기화 시작...")
                await self.sync_corp_codes()
                # 동기화 후 재조회
                result = await self.db.execute(stmt)
                row = result.scalar_one_or_none()

        return row

    async def collect_financial_statements(
        self, stock_code: str, years: int = 3
    ) -> dict:
        """특정 종목의 재무제표를 수집하여 DB에 저장."""
        corp_code = await self.get_corp_code(stock_code)
        if not corp_code:
            return {"collected_count": 0, "message": f"DART 고유번호를 찾을 수 없습니다: {stock_code}"}

        current_year = now_kst().year
        collected_count = 0
        years_collected = []

        # 현재 연도+직전 연도는 사업보고서 미제출일 수 있으므로 +2 여유분
        for year_offset in range(years + 2):
            bsns_year = str(current_year - year_offset)
            for reprt_code in ["11011", "11012", "11013", "11014"]:
                try:
                    items = await self._collect_single_report(
                        stock_code, corp_code, bsns_year, reprt_code
                    )
                    collected_count += items
                    if items > 0 and bsns_year not in years_collected:
                        years_collected.append(bsns_year)
                except Exception as e:
                    logger.warning(
                        f"Failed to collect {stock_code} {bsns_year} {reprt_code}: {e}"
                    )

        await self.db.commit()
        return {
            "collected_count": collected_count,
            "years_collected": years_collected,
            "message": f"{stock_code}: {collected_count}건 수집 완료",
        }

    async def _has_report_in_db(
        self, stock_code: str, bsns_year: str, reprt_code: str,
    ) -> Optional[str]:
        """DB에 해당 보고서 데이터가 이미 존재하는지 확인.

        Returns: 저장된 fs_div ('CFS'/'OFS') 또는 None.
        """
        stmt = (
            select(FinancialStatement.fs_div)
            .where(
                FinancialStatement.stock_code == stock_code,
                FinancialStatement.bsns_year == bsns_year,
                FinancialStatement.reprt_code == reprt_code,
            )
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _collect_single_report(
        self, stock_code: str, corp_code: str, bsns_year: str, reprt_code: str
    ) -> int:
        """단일 보고서 수집. CFS 우선, 없으면 OFS fallback."""
        existing_fs = await self._has_report_in_db(stock_code, bsns_year, reprt_code)
        if existing_fs == "CFS":
            return 0  # CFS 이미 있으면 스킵
        # OFS만 있으면 CFS 시도, 없으면 전체 수집

        for fs_div in ["CFS", "OFS"]:
            try:
                items = await self.dart_client.get_financial_statement(
                    corp_code=corp_code,
                    bsns_year=bsns_year,
                    reprt_code=reprt_code,
                    fs_div=fs_div,
                )
                if items:
                    # savepoint로 감싸서 실패 시 해당 보고서만 rollback
                    try:
                        async with self.db.begin_nested():
                            await self._save_items(stock_code, corp_code, bsns_year, reprt_code, fs_div, items)
                        return len(items)
                    except Exception as save_err:
                        logger.warning(f"Save failed for {stock_code} {bsns_year} {reprt_code} {fs_div}: {save_err}")
                        continue
            except Exception as e:
                logger.debug(f"No data for {fs_div}: {e}")
                continue
        return 0

    async def _save_items(
        self,
        stock_code: str,
        corp_code: str,
        bsns_year: str,
        reprt_code: str,
        fs_div: str,
        items: list[dict],
    ) -> None:
        """재무제표 항목들을 DB에 upsert."""
        for item in items:
            values = {
                "stock_code": stock_code,
                "corp_code": corp_code,
                "bsns_year": bsns_year,
                "reprt_code": reprt_code,
                "fs_div": fs_div,
                "sj_div": item.get("sj_div", ""),
                "sj_nm": item.get("sj_nm"),
                "account_id": item.get("account_id", ""),
                "account_nm": item.get("account_nm", ""),
                "account_detail": item.get("account_detail"),
                "thstrm_amount": _parse_amount(item.get("thstrm_amount", "")),
                "frmtrm_amount": _parse_amount(item.get("frmtrm_amount", "")),
                "bfefrmtrm_amount": _parse_amount(item.get("bfefrmtrm_amount", "")),
                "thstrm_nm": item.get("thstrm_nm"),
                "frmtrm_nm": item.get("frmtrm_nm"),
                "bfefrmtrm_nm": item.get("bfefrmtrm_nm"),
                "ord": int(item.get("ord", 0)) if item.get("ord") else None,
                "currency": item.get("currency", "KRW"),
                "collected_at": now_kst().replace(tzinfo=None),
            }

            stmt = pg_insert(FinancialStatement).values(values)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_fs_account",
                set_={
                    "sj_nm": stmt.excluded.sj_nm,
                    "account_nm": stmt.excluded.account_nm,
                    "account_detail": stmt.excluded.account_detail,
                    "thstrm_amount": stmt.excluded.thstrm_amount,
                    "frmtrm_amount": stmt.excluded.frmtrm_amount,
                    "bfefrmtrm_amount": stmt.excluded.bfefrmtrm_amount,
                    "thstrm_nm": stmt.excluded.thstrm_nm,
                    "frmtrm_nm": stmt.excluded.frmtrm_nm,
                    "bfefrmtrm_nm": stmt.excluded.bfefrmtrm_nm,
                    "ord": stmt.excluded.ord,
                    "currency": stmt.excluded.currency,
                    "collected_at": stmt.excluded.collected_at,
                },
            )
            await self.db.execute(stmt)

    async def get_earnings_dates(self, stock_code: str) -> list[dict]:
        """DB에 저장된 재무제표 기준으로 실적발표일 목록 반환.

        disclosures 테이블에 정기공시 데이터가 있으면 정확한 접수일(rcept_dt) 사용,
        없으면 표준 공시 마감일 기준으로 추정.
        """
        from models.disclosure import Disclosure

        # 1) financial_statements에서 (bsns_year, reprt_code) 조합 조회
        stmt = (
            select(
                FinancialStatement.bsns_year,
                FinancialStatement.reprt_code,
            )
            .where(FinancialStatement.stock_code == stock_code)
            .group_by(
                FinancialStatement.bsns_year,
                FinancialStatement.reprt_code,
            )
            .order_by(
                FinancialStatement.bsns_year.desc(),
                FinancialStatement.reprt_code,
            )
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        if not rows:
            return []

        # 2) 해당 종목의 정기공시에서 정확한 rcept_dt 가져오기
        disc_stmt = (
            select(Disclosure.report_nm, Disclosure.rcept_dt)
            .where(
                Disclosure.stock_code == stock_code,
                Disclosure.disclosure_type == "regular",
            )
            .order_by(Disclosure.rcept_dt.desc())
        )
        disc_result = await self.db.execute(disc_stmt)
        disc_rows = disc_result.all()

        # report_nm에서 키워드 매칭하여 rcept_dt 맵핑
        # "사업보고서 (2024.12)" → 연간, "분기보고서 (2024.09)" → Q3 등
        disc_date_map: dict[tuple[str, str], str] = {}
        for report_nm, rcept_dt in disc_rows:
            if not report_nm or not rcept_dt:
                continue
            # rcept_dt YYYYMMDD → YYYY-MM-DD
            dt_str = f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:8]}"
            period_match = re.search(r'\((\d{4})\.(\d{2})\)', report_nm)
            if not period_match:
                continue
            period_year = period_match.group(1)
            period_month = period_match.group(2)
            # 월 → reprt_code 매핑
            month_to_reprt = {"03": "11013", "06": "11012", "09": "11014", "12": "11011"}
            reprt = month_to_reprt.get(period_month)
            if reprt:
                disc_date_map[(period_year, reprt)] = dt_str

        # 3) 결과 생성
        reprt_label = {
            "11013": "Q1",
            "11012": "반기",
            "11014": "Q3",
            "11011": "연간",
        }
        # 표준 공시 마감일 (보고서코드 → 추정 공시일)
        reprt_std_date = {
            "11013": lambda y: f"{y}-05-15",
            "11012": lambda y: f"{y}-08-14",
            "11014": lambda y: f"{y}-11-14",
            "11011": lambda y: f"{int(y)+1}-03-31",
        }

        dates = []
        for bsns_year, reprt_code in rows:
            label = reprt_label.get(reprt_code)
            if not label:
                continue

            # 정확한 공시일이 있으면 사용, 없으면 추정
            date = disc_date_map.get((bsns_year, reprt_code))
            if not date:
                date_fn = reprt_std_date.get(reprt_code)
                if date_fn:
                    date = date_fn(bsns_year)
                else:
                    continue

            dates.append({"date": date, "label": f"{label} ({bsns_year})"})

        return dates

    async def get_financial_data(
        self,
        stock_code: str,
        bsns_year: Optional[str] = None,
        reprt_code: Optional[str] = None,
        fs_div: Optional[str] = None,
    ) -> list[dict]:
        """DB에서 재무제표 데이터 조회."""
        conditions = [FinancialStatement.stock_code == stock_code]
        if bsns_year:
            conditions.append(FinancialStatement.bsns_year == bsns_year)
        if reprt_code:
            conditions.append(FinancialStatement.reprt_code == reprt_code)
        if fs_div:
            conditions.append(FinancialStatement.fs_div == fs_div)

        stmt = (
            select(FinancialStatement)
            .where(and_(*conditions))
            .order_by(FinancialStatement.ord)
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "sj_div": r.sj_div,
                "sj_nm": r.sj_nm,
                "account_id": r.account_id,
                "account_nm": r.account_nm,
                "account_detail": r.account_detail,
                "thstrm_amount": r.thstrm_amount,
                "frmtrm_amount": r.frmtrm_amount,
                "bfefrmtrm_amount": r.bfefrmtrm_amount,
                "thstrm_nm": r.thstrm_nm,
                "frmtrm_nm": r.frmtrm_nm,
                "bfefrmtrm_nm": r.bfefrmtrm_nm,
                "ord": r.ord,
            }
            for r in rows
        ]

    def compute_ratios(
        self,
        accounts: list[dict],
        market_cap: Optional[int] = None,
    ) -> FinancialRatios:
        """재무비율 계산."""
        # 손익계산서(IS/CIS)에서 조회
        is_divs = ["IS", "CIS"]
        revenue = _find_account_amount(accounts, REVENUE_NAMES, sj_divs=is_divs)
        operating_income = _find_account_amount(accounts, OPERATING_INCOME_NAMES, sj_divs=is_divs)
        net_income = _find_account_amount(accounts, NET_INCOME_NAMES, sj_divs=is_divs)

        # 재무상태표(BS)에서 조회 - SCE의 동명 계정과 혼동 방지
        bs_divs = ["BS"]
        total_assets = _find_account_amount(accounts, TOTAL_ASSETS_NAMES, sj_divs=bs_divs)
        total_liabilities = _find_account_amount(accounts, TOTAL_LIABILITIES_NAMES, sj_divs=bs_divs)
        total_equity = _find_account_amount(accounts, TOTAL_EQUITY_NAMES, sj_divs=bs_divs)
        current_assets = _find_account_amount(accounts, CURRENT_ASSETS_NAMES, sj_divs=bs_divs)
        current_liabilities = _find_account_amount(accounts, CURRENT_LIABILITIES_NAMES, sj_divs=bs_divs)

        # 전기 매출 (성장률 계산용)
        prev_revenue = _find_account_amount(accounts, REVENUE_NAMES, "frmtrm_amount", sj_divs=is_divs)

        ratios = FinancialRatios()

        # PER = 시가총액 / 당기순이익
        if market_cap and net_income and net_income != 0:
            ratios.per = round(market_cap / net_income, 2)

        # PBR = 시가총액 / 자본총계
        if market_cap and total_equity and total_equity != 0:
            ratios.pbr = round(market_cap / total_equity, 2)

        # ROE = 당기순이익 / 자본총계 * 100
        if net_income is not None and total_equity and total_equity != 0:
            ratios.roe = round(net_income / total_equity * 100, 2)

        # ROA = 당기순이익 / 자산총계 * 100
        if net_income is not None and total_assets and total_assets != 0:
            ratios.roa = round(net_income / total_assets * 100, 2)

        # 영업이익률 = 영업이익 / 매출액 * 100
        if operating_income is not None and revenue and revenue != 0:
            ratios.operating_margin = round(operating_income / revenue * 100, 2)

        # 순이익률 = 당기순이익 / 매출액 * 100
        if net_income is not None and revenue and revenue != 0:
            ratios.net_margin = round(net_income / revenue * 100, 2)

        # 부채비율 = 부채총계 / 자본총계 * 100
        if total_liabilities is not None and total_equity and total_equity != 0:
            ratios.debt_ratio = round(total_liabilities / total_equity * 100, 2)

        # 유동비율 = 유동자산 / 유동부채 * 100
        if current_assets is not None and current_liabilities and current_liabilities != 0:
            ratios.current_ratio = round(current_assets / current_liabilities * 100, 2)

        # 매출성장률 = (당기매출 - 전기매출) / 전기매출 * 100
        if revenue is not None and prev_revenue and prev_revenue != 0:
            ratios.revenue_growth = round((revenue - prev_revenue) / abs(prev_revenue) * 100, 2)

        return ratios

    async def _get_market_cap(self, stock_code: str) -> Optional[int]:
        """시가총액 추정 (DB: stock_ohlcv 종가 × 주식수).

        주식수 = 순이익 / EPS (DART 기본주당이익)
        """
        # 1) 최신 종가
        latest_sub = (
            select(func.max(StockOHLCV.trade_date))
            .where(StockOHLCV.stock_code == stock_code)
            .scalar_subquery()
        )
        price_stmt = (
            select(StockOHLCV.close_price)
            .where(
                StockOHLCV.stock_code == stock_code,
                StockOHLCV.trade_date == latest_sub,
            )
        )
        price_result = await self.db.execute(price_stmt)
        close_row = price_result.scalar_one_or_none()
        if not close_row:
            return None

        # 2) 최신 연간 보고서에서 EPS + 순이익 추출
        eps_names = [
            "기본주당이익(손실)", "기본주당순이익", "기본주당순이익(손실)",
            "기본주당이익", "주당이익(손실)", "주당순이익",
        ]
        fs_stmt = (
            select(FinancialStatement)
            .where(
                FinancialStatement.stock_code == stock_code,
                FinancialStatement.reprt_code == "11011",
            )
            .order_by(FinancialStatement.bsns_year.desc())
        )
        fs_result = await self.db.execute(fs_stmt)
        fs_rows = fs_result.scalars().all()
        if not fs_rows:
            return None

        accounts = [
            {"sj_div": r.sj_div, "account_nm": r.account_nm, "thstrm_amount": r.thstrm_amount}
            for r in fs_rows
        ]
        eps = _find_account_amount(accounts, eps_names, sj_divs=["IS", "CIS"])
        ni = _find_account_amount(accounts, NET_INCOME_NAMES, sj_divs=["IS", "CIS"])

        if eps and eps != 0 and ni:
            shares = ni / eps
            return int(close_row * shares)
        return None

    async def get_financial_summary(self, stock_code: str) -> FinancialSummaryResponse:
        """3개년 재무 요약 + 비율."""
        corp_code = await self.get_corp_code(stock_code)

        # 전체 데이터 한 번에 조회 (연간 + 분기 모두)
        all_stmt = (
            select(FinancialStatement)
            .where(FinancialStatement.stock_code == stock_code)
            .order_by(FinancialStatement.bsns_year.desc(), FinancialStatement.ord)
        )
        all_result = await self.db.execute(all_stmt)
        all_rows = all_result.scalars().all()

        if not all_rows:
            return FinancialSummaryResponse(stock_code=stock_code, corp_code=corp_code)

        # 시가총액 조회 (PER/PBR 계산용)
        market_cap = await self._get_market_cap(stock_code)

        # 연간 데이터
        annual_rows = [r for r in all_rows if r.reprt_code == "11011"]
        annual_data = self._group_by_period(annual_rows, market_cap=market_cap)

        # 분기 데이터: 누적→개별 분기 변환
        quarterly_data = self._compute_quarterly_data(all_rows, max_quarters=8)

        # 최신 연간 데이터로 비율 계산
        latest_ratios = None
        if annual_data:
            latest = annual_data[0]
            if latest.ratios is None:
                latest_accounts = self._get_accounts_for_period(
                    annual_rows, latest.bsns_year, latest.reprt_code
                )
                # "3개월" IS 항목 제외 (연간 누적만 사용)
                latest_accounts = [
                    acc for acc in latest_accounts
                    if acc.get("sj_div") not in ("IS", "CIS") or "3개월" not in acc.get("sj_nm", "")
                ]
                latest.ratios = self.compute_ratios(latest_accounts, market_cap=market_cap)
            latest_ratios = latest.ratios

        return FinancialSummaryResponse(
            stock_code=stock_code,
            corp_code=corp_code,
            annual_data=annual_data,
            quarterly_data=quarterly_data,
            latest_ratios=latest_ratios,
            has_data=True,
        )

    def _compute_quarterly_data(
        self, all_rows: list, max_quarters: int = 8, market_cap: Optional[int] = None
    ) -> list[AnnualFinancialData]:
        """분기별 개별 실적 계산 (비12월 결산법인 지원).

        핵심 개선:
        1. thstrm_nm의 회계기수("제N기")로 회계연도 매칭 (bsns_year가 아닌 실제 FY)
        2. H1 >= Q1 비교로 누적/개별 확실히 판별
        3. 양 방식 시도 후 유효한(음수 없는) 결과 선택
        """
        is_divs = ["IS", "CIS"]
        bs_divs = ["BS"]

        # ── Step 1: 회계기수 파싱 ──
        fy_map: dict[tuple, int] = {}  # (bsns_year, reprt_code) → 회계기수
        for r in all_rows:
            key = (r.bsns_year, r.reprt_code)
            if key not in fy_map and r.thstrm_nm:
                m = re.search(r"제\s*(\d+)\s*기", r.thstrm_nm)
                if m:
                    fy_map[key] = int(m.group(1))

        # ── Step 2: CFS 우선 그룹화 ──
        periods_by_fs: dict[tuple, dict[str, list[dict]]] = {}
        for r in all_rows:
            key = (r.bsns_year, r.reprt_code)
            if key not in periods_by_fs:
                periods_by_fs[key] = {}
            if r.fs_div not in periods_by_fs[key]:
                periods_by_fs[key][r.fs_div] = []
            periods_by_fs[key][r.fs_div].append({
                "sj_div": r.sj_div,
                "sj_nm": r.sj_nm or "",
                "account_id": r.account_id,
                "account_nm": r.account_nm,
                "thstrm_amount": r.thstrm_amount,
                "frmtrm_amount": r.frmtrm_amount,
                "bfefrmtrm_amount": r.bfefrmtrm_amount,
            })

        periods: dict[tuple, list[dict]] = {}
        for key, fs_data in periods_by_fs.items():
            periods[key] = fs_data.get("CFS") or fs_data.get("OFS") or list(fs_data.values())[0]

        # ── Step 3: IS 3개월/누적 분리 + 회계기수별 그룹핑 ──
        # fy_num → {"annual": {...}, "q1": {...}, "h1": {...}, "q3": {...}}
        fy_groups: dict[int, dict[str, dict]] = {}
        ROLE_MAP = {"11011": "annual", "11013": "q1", "11012": "h1", "11014": "q3"}

        for (year, rc), accounts in periods.items():
            role = ROLE_MAP.get(rc)
            if not role:
                continue

            fy_num = fy_map.get((year, rc))
            if fy_num is None:
                # 회계기수 파싱 불가 → bsns_year 기반 fallback (12월 결산 가정)
                fy_num = int(year) * 100
                if rc != "11011":
                    fy_num += 1  # 분기와 연간을 같은 그룹에 넣기 위해

            three_month_is, cumulative_is, bs_other = [], [], []
            for acc in accounts:
                sj_nm = acc.get("sj_nm") or ""
                if acc["sj_div"] in ("IS", "CIS"):
                    if "3개월" in sj_nm:
                        three_month_is.append(acc)
                    else:
                        cumulative_is.append(acc)
                else:
                    bs_other.append(acc)

            if fy_num not in fy_groups:
                fy_groups[fy_num] = {}
            fy_groups[fy_num][role] = {
                "three_month": three_month_is,
                "cumulative": cumulative_is,
                "bs": bs_other,
                "bsns_year": year,
            }

        # ── Step 4: 헬퍼 ──
        def _extract_is(accounts: list[dict]) -> dict:
            return {
                "revenue": _find_account_amount(accounts, REVENUE_NAMES, sj_divs=is_divs),
                "operating_income": _find_account_amount(accounts, OPERATING_INCOME_NAMES, sj_divs=is_divs),
                "net_income": _find_account_amount(accounts, NET_INCOME_NAMES, sj_divs=is_divs),
            }

        def _extract_bs(accounts: list[dict]) -> dict:
            return {
                "total_assets": _find_account_amount(accounts, TOTAL_ASSETS_NAMES, sj_divs=bs_divs),
                "total_liabilities": _find_account_amount(accounts, TOTAL_LIABILITIES_NAMES, sj_divs=bs_divs),
                "total_equity": _find_account_amount(accounts, TOTAL_EQUITY_NAMES, sj_divs=bs_divs),
            }

        def _sub(a: Optional[int], b: Optional[int]) -> Optional[int]:
            if a is None or b is None:
                return None
            return a - b

        IS_KEYS = ("revenue", "operating_income", "net_income")

        def _all_non_negative(is_vals: dict) -> bool:
            """IS 값이 모두 None이 아니고 음수가 아닌지 확인."""
            rev = is_vals.get("revenue")
            if rev is not None and rev < 0:
                return False
            return True

        # ── Step 5: 누적/개별 글로벌 판별 ──
        # 모든 회계연도를 스캔하여 한 번에 결정 (회사별 일관된 방식)
        detected_is_cumulative: Optional[bool] = None

        for fy_num_check in sorted(fy_groups.keys()):
            fd_check = fy_groups[fy_num_check]
            if not any(r in fd_check for r in ("q1", "h1", "q3")):
                continue

            q1_r = (_extract_is(fd_check["q1"]["cumulative"])["revenue"]
                    if "q1" in fd_check else None)
            h1_r = (_extract_is(fd_check["h1"]["cumulative"])["revenue"]
                    if "h1" in fd_check else None)
            q3_r = (_extract_is(fd_check["q3"]["cumulative"])["revenue"]
                    if "q3" in fd_check else None)
            ann_r = (_extract_is(fd_check["annual"]["cumulative"])["revenue"]
                     if "annual" in fd_check else None)

            # Signal 1: Q3 < H1 → 누적이면 불가능 → 확정 개별
            if h1_r is not None and q3_r is not None and q3_r < h1_r:
                detected_is_cumulative = False
                break

            # Signal 2: 연간 대비 Q3 비율로 판별
            if ann_r and ann_r > 0 and q3_r and q3_r > 0:
                ratio = q3_r / ann_r
                if ratio > 0.6:  # 누적 Q3(9개월) ≈ 연간의 ~75%
                    detected_is_cumulative = True
                    break
                elif ratio < 0.45:  # 개별 분기 << 연간
                    detected_is_cumulative = False
                    break

            # Signal 3: Q1+H1+Q3 합계 대비 연간 비율
            if ann_r and ann_r > 0 and q1_r and h1_r and q3_r:
                sum_q = q1_r + h1_r + q3_r
                sum_ratio = sum_q / ann_r
                if 0.5 < sum_ratio < 1.0:  # 개별: 3분기 합 ≈ 연간의 ~75%
                    detected_is_cumulative = False
                    break
                elif sum_ratio > 1.3:  # 누적: Q1+(Q1+Q2)+(Q1+Q2+Q3) >> 연간
                    detected_is_cumulative = True
                    break

        if detected_is_cumulative is not None:
            logger.info(f"Financial cumulative detection (global): "
                        f"is_cumulative={detected_is_cumulative}")

        # ── Step 6: 회계기수별 분기 계산 ──
        result: list[AnnualFinancialData] = []

        for fy_num in sorted(fy_groups.keys(), reverse=True):
            fd = fy_groups[fy_num]
            if not any(r in fd for r in ("q1", "h1", "q3")):
                continue  # 분기 데이터 없는 연간만 있는 경우 건너뜀

            # 원시 IS 추출
            raw: dict[str, Optional[dict]] = {}
            for role in ("q1", "h1", "q3", "annual"):
                if role in fd:
                    raw[role] = _extract_is(fd[role]["cumulative"])
                else:
                    raw[role] = None

            # 글로벌 판별 결과 사용, 없으면 per-FY fallback
            q1_rev = raw.get("q1", {}).get("revenue") if raw.get("q1") else None
            h1_rev = raw.get("h1", {}).get("revenue") if raw.get("h1") else None
            q3_rev = raw.get("q3", {}).get("revenue") if raw.get("q3") else None

            if detected_is_cumulative is not None:
                is_cumulative = detected_is_cumulative
            else:
                # fallback: 기존 heuristic
                is_cumulative = True
                if q1_rev is not None and h1_rev is not None:
                    is_cumulative = h1_rev >= q1_rev
                elif h1_rev is not None and q3_rev is not None:
                    is_cumulative = q3_rev >= h1_rev

            logger.debug(f"Financial FY{fy_num}: cumulative={is_cumulative}, "
                         f"q1={q1_rev}, h1={h1_rev}, q3={q3_rev}")

            quarters: list[tuple[int, dict, str]] = []  # (q_num, vals, bsns_year)

            for q_num, role in [(1, "q1"), (2, "h1"), (3, "q3"), (4, "annual")]:
                if role not in fd:
                    continue
                period = fd[role]
                bs_vals = _extract_bs(period["bs"])
                year_label = period["bsns_year"]

                # 우선순위 1: [3개월] IS 항목
                if period["three_month"]:
                    is_vals = _extract_is(period["three_month"])
                # 우선순위 2: Q1 항상 개별
                elif q_num == 1:
                    is_vals = _extract_is(period["cumulative"])
                # 누적 데이터 → 차감
                elif is_cumulative:
                    prev_role = {"h1": "q1", "q3": "h1", "annual": "q3"}.get(role)
                    if prev_role and raw.get(prev_role):
                        cur_is = _extract_is(period["cumulative"])
                        prev_is = raw[prev_role]
                        is_vals = {k: _sub(cur_is[k], prev_is[k]) for k in IS_KEYS}
                    elif q_num < 4:
                        is_vals = _extract_is(period["cumulative"])
                    else:
                        continue
                # 개별 데이터
                else:
                    if q_num == 4:
                        # Q4 = Annual - Q1 - Q2 - Q3
                        annual_is = raw.get("annual")
                        if annual_is and all(raw.get(r) for r in ("q1", "h1", "q3")):
                            is_vals = {}
                            for k in IS_KEYS:
                                ann = annual_is[k]
                                parts = [raw["q1"][k], raw["h1"][k], raw["q3"][k]]
                                if ann is not None and all(p is not None for p in parts):
                                    is_vals[k] = ann - sum(parts)
                                else:
                                    is_vals[k] = None
                        else:
                            continue
                    else:
                        # Q2(h1), Q3(q3) - 개별 값 그대로
                        is_vals = _extract_is(period["cumulative"])

                # 음수 매출 검증 → 반대 방식 시도
                if not _all_non_negative(is_vals) and q_num in (2, 3):
                    logger.warning(f"FY{fy_num} Q{q_num}: negative revenue, trying opposite method")
                    if is_cumulative:
                        # 누적으로 판별했는데 음수 → 개별로 재시도
                        is_vals = _extract_is(period["cumulative"])
                    else:
                        # 개별로 판별했는데 음수 → 누적 차감 재시도
                        prev_role = {"h1": "q1", "q3": "h1"}.get(role)
                        if prev_role and raw.get(prev_role):
                            cur_is = _extract_is(period["cumulative"])
                            prev_is = raw[prev_role]
                            is_vals = {k: _sub(cur_is[k], prev_is[k]) for k in IS_KEYS}

                vals = {**is_vals, **bs_vals}
                quarters.append((q_num, vals, year_label))

            quarters.sort(key=lambda x: x[0], reverse=True)

            for q_num, data, year in quarters:
                result.append(AnnualFinancialData(
                    bsns_year=year,
                    reprt_code=f"Q{q_num}",
                    reprt_name=f"{q_num}Q",
                    revenue=data.get("revenue"),
                    operating_income=data.get("operating_income"),
                    net_income=data.get("net_income"),
                    total_assets=data.get("total_assets"),
                    total_liabilities=data.get("total_liabilities"),
                    total_equity=data.get("total_equity"),
                    ratios=None,
                ))

        return result[:max_quarters]

    def _group_by_period(
        self, rows: list, max_periods: int = 5, market_cap: Optional[int] = None
    ) -> list[AnnualFinancialData]:
        """DB 행들을 기간별로 그룹화. CFS(연결) 우선, OFS(개별) fallback."""
        # fs_div별로 분리 수집
        periods_by_fs: dict[tuple, dict[str, list[dict]]] = {}
        for r in rows:
            key = (r.bsns_year, r.reprt_code)
            if key not in periods_by_fs:
                periods_by_fs[key] = {}
            if r.fs_div not in periods_by_fs[key]:
                periods_by_fs[key][r.fs_div] = []
            periods_by_fs[key][r.fs_div].append({
                "sj_div": r.sj_div,
                "sj_nm": r.sj_nm or "",
                "account_id": r.account_id,
                "account_nm": r.account_nm,
                "thstrm_amount": r.thstrm_amount,
                "frmtrm_amount": r.frmtrm_amount,
                "bfefrmtrm_amount": r.bfefrmtrm_amount,
            })

        # CFS 우선, 없으면 OFS 사용
        periods: dict[tuple, list[dict]] = {}
        for key, fs_data in periods_by_fs.items():
            if "CFS" in fs_data:
                periods[key] = fs_data["CFS"]
            elif "OFS" in fs_data:
                periods[key] = fs_data["OFS"]
            else:
                periods[key] = list(fs_data.values())[0]

        result = []
        is_divs = ["IS", "CIS"]
        bs_divs = ["BS"]
        period_items = list(periods.items())[:max_periods]
        for idx, ((bsns_year, reprt_code), accounts) in enumerate(period_items):
            # IS에서 "3개월" 항목 제외 (연간은 누적=전체, 분기 보고서도 누적 사용)
            cumulative_accounts = [
                acc for acc in accounts
                if acc["sj_div"] not in ("IS", "CIS") or "3개월" not in acc.get("sj_nm", "")
            ]
            revenue = _find_account_amount(cumulative_accounts, REVENUE_NAMES, sj_divs=is_divs)
            operating_income = _find_account_amount(cumulative_accounts, OPERATING_INCOME_NAMES, sj_divs=is_divs)
            net_income = _find_account_amount(cumulative_accounts, NET_INCOME_NAMES, sj_divs=is_divs)
            total_assets = _find_account_amount(cumulative_accounts, TOTAL_ASSETS_NAMES, sj_divs=bs_divs)
            total_liabilities = _find_account_amount(cumulative_accounts, TOTAL_LIABILITIES_NAMES, sj_divs=bs_divs)
            total_equity = _find_account_amount(cumulative_accounts, TOTAL_EQUITY_NAMES, sj_divs=bs_divs)

            # 최신 기간에만 시가총액 기반 PER/PBR 계산
            mc = market_cap if idx == 0 else None
            ratios = self.compute_ratios(cumulative_accounts, market_cap=mc)
            ratios.bsns_year = bsns_year
            ratios.reprt_code = reprt_code

            result.append(AnnualFinancialData(
                bsns_year=bsns_year,
                reprt_code=reprt_code,
                reprt_name=REPRT_CODE_MAP.get(reprt_code, reprt_code),
                revenue=revenue,
                operating_income=operating_income,
                net_income=net_income,
                total_assets=total_assets,
                total_liabilities=total_liabilities,
                total_equity=total_equity,
                ratios=ratios,
            ))

        return result

    def _get_accounts_for_period(
        self, rows: list, bsns_year: str, reprt_code: str
    ) -> list[dict]:
        """특정 기간의 계정 리스트 추출."""
        return [
            {
                "sj_div": r.sj_div,
                "sj_nm": r.sj_nm or "",
                "account_id": r.account_id,
                "account_nm": r.account_nm,
                "thstrm_amount": r.thstrm_amount,
                "frmtrm_amount": r.frmtrm_amount,
                "bfefrmtrm_amount": r.bfefrmtrm_amount,
            }
            for r in rows
            if r.bsns_year == bsns_year and r.reprt_code == reprt_code
        ]

    async def get_last_collected_date(self, stock_code: str) -> Optional[datetime]:
        """종목의 가장 최근 수집일 조회."""
        stmt = (
            select(FinancialStatement.collected_at)
            .where(FinancialStatement.stock_code == stock_code)
            .order_by(FinancialStatement.collected_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
