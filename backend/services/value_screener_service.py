"""재무 저평가 종목 스크리너 서비스.

외부 API 호출 없이 DB에 축적된 데이터만 사용:
- 재무제표: financial_statements 테이블 (DART 수집)
- 종가: stock_ohlcv 테이블 (KIS 일봉 수집)
- PER = 종가 / EPS (DART 기본주당이익)
- PBR = 시가총액 / 자본총계 (시가총액 = 종가 × 주식수, 주식수 = 순이익/EPS)
"""
import logging
import math
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.timezone import now_kst
from models.financial_statement import FinancialStatement
from models.stock import Stock
from models.stock_ohlcv import StockOHLCV
from models.company_profile import CompanyProfile
from services.financial_statement_service import (
    FinancialStatementService,
    REVENUE_NAMES,
    OPERATING_INCOME_NAMES,
    NET_INCOME_NAMES,
    TOTAL_ASSETS_NAMES,
    TOTAL_LIABILITIES_NAMES,
    TOTAL_EQUITY_NAMES,
    CURRENT_ASSETS_NAMES,
    CURRENT_LIABILITIES_NAMES,
    _find_account_amount,
)
from schemas.value_screener import (
    ValueMetrics,
    ValueScreenerSummary,
    ValueScreenerResponse,
)

# DART EPS 계정명 후보
EPS_NAMES = [
    "기본주당이익(손실)", "기본주당순이익", "기본주당순이익(손실)",
    "기본주당이익", "주당이익(손실)", "주당순이익",
]

logger = logging.getLogger(__name__)


def _score_per(per: Optional[float]) -> int:
    """PER 점수 (20점 만점)."""
    if per is None:
        return 0
    if per <= 0:
        return 0  # 적자
    if per <= 8:
        return 20
    if per <= 12:
        return 15
    if per <= 20:
        return 10
    return 5


def _score_pbr(pbr: Optional[float]) -> int:
    """PBR 점수 (15점 만점)."""
    if pbr is None:
        return 0
    if pbr < 0.5:
        return 15
    if pbr < 0.8:
        return 12
    if pbr < 1.0:
        return 9
    if pbr < 1.5:
        return 5
    return 0


def _score_roe(roe: Optional[float]) -> int:
    """ROE 점수 (20점 만점)."""
    if roe is None:
        return 0
    if roe < 0:
        return 0
    if roe >= 20:
        return 20
    if roe >= 15:
        return 16
    if roe >= 10:
        return 12
    if roe >= 5:
        return 8
    return 3


def _score_operating_margin(margin: Optional[float]) -> int:
    """영업이익률 점수 (15점 만점)."""
    if margin is None:
        return 0
    if margin <= 0:
        return 0
    if margin >= 20:
        return 15
    if margin >= 10:
        return 12
    if margin >= 5:
        return 8
    return 4


def _score_revenue_growth(growth: Optional[float]) -> int:
    """매출성장률 점수 (15점 만점)."""
    if growth is None:
        return 0
    if growth < 0:
        return 0
    if growth >= 30:
        return 15
    if growth >= 15:
        return 12
    if growth >= 5:
        return 8
    return 4


def _score_debt_ratio(ratio: Optional[float]) -> int:
    """부채비율 점수 (10점 만점)."""
    if ratio is None:
        return 0
    if ratio < 50:
        return 10
    if ratio < 100:
        return 8
    if ratio < 150:
        return 5
    if ratio < 200:
        return 2
    return 0


def _score_current_ratio(ratio: Optional[float]) -> int:
    """유동비율 점수 (5점 만점)."""
    if ratio is None:
        return 0
    if ratio >= 200:
        return 5
    if ratio >= 150:
        return 4
    if ratio >= 100:
        return 2
    return 0


def _grade(total: int) -> str:
    """등급 판정."""
    if total >= 75:
        return "A"
    if total >= 55:
        return "B"
    if total >= 35:
        return "C"
    return "D"


def _build_comment(
    per: Optional[float],
    pbr: Optional[float],
    roe: Optional[float],
    operating_margin: Optional[float],
    revenue_growth: Optional[float],
    debt_ratio: Optional[float],
    per_s: int,
    pbr_s: int,
    roe_s: int,
    margin_s: int,
    growth_s: int,
    debt_s: int,
) -> str:
    """점수 기반 저평가 이유 코멘트 생성."""
    strengths: list[str] = []
    cautions: list[str] = []

    # PER
    if per_s >= 15 and per is not None:
        strengths.append(f"PER {per:.1f}배로 저평가")
    elif per_s == 0 and per is not None and per <= 0:
        cautions.append("적자 상태")

    # PBR
    if pbr_s >= 12 and pbr is not None:
        strengths.append(f"PBR {pbr:.2f}배로 자산 대비 할인")

    # ROE
    if roe_s >= 16 and roe is not None:
        strengths.append(f"ROE {roe:.1f}%로 높은 자본효율")
    elif roe_s >= 12 and roe is not None:
        strengths.append(f"ROE {roe:.1f}% 양호")

    # 영업이익률
    if margin_s >= 12 and operating_margin is not None:
        strengths.append(f"영업이익률 {operating_margin:.1f}%로 수익성 우수")

    # 매출 성장
    if growth_s >= 12 and revenue_growth is not None:
        strengths.append(f"매출 {revenue_growth:+.1f}% 성장")
    elif revenue_growth is not None and revenue_growth < 0:
        cautions.append(f"매출 {revenue_growth:.1f}% 역성장")

    # 부채
    if debt_s >= 8 and debt_ratio is not None:
        strengths.append(f"부채비율 {debt_ratio:.0f}%로 재무 안정")
    elif debt_ratio is not None and debt_ratio >= 200:
        cautions.append(f"부채비율 {debt_ratio:.0f}% 높음")

    parts: list[str] = []
    if strengths:
        parts.append(", ".join(strengths[:3]))
    if cautions:
        parts.append("주의: " + ", ".join(cautions[:2]))

    return ". ".join(parts) if parts else "데이터 부족"


# ── 적정가치 산출 ──
_REQUIRED_RETURN = 10.0  # 기대수익률 10%


def _estimate_fair_value(
    eps: Optional[int],
    bps: Optional[float],
    roe: Optional[float],
    revenue_growth: Optional[float],
) -> Optional[tuple[int, str]]:
    """3가지 모델로 적정가치 추정.

    1) S-RIM: BPS + (ROE-r)/r × BPS × W  (W=0.8 지속률)
    2) Graham Number: sqrt(22.5 × EPS × BPS)
    3) 목표PER: EPS × 적정PER (성장률 연동)

    Returns: (fair_value, method_label) or None
    """
    estimates: list[tuple[float, str]] = []

    # 1) S-RIM (초과이익 모델)
    if bps and bps > 0 and roe is not None:
        r = _REQUIRED_RETURN
        w = 0.8  # 초과이익 지속률
        srim = bps * (1 + (roe - r) / r * w)
        if srim > 0:
            estimates.append((srim, "S-RIM"))

    # 2) Graham Number
    if eps and eps > 0 and bps and bps > 0:
        graham = math.sqrt(22.5 * eps * bps)
        if graham > 0:
            estimates.append((graham, "Graham"))

    # 3) 목표 PER (성장률 기반)
    if eps and eps > 0:
        if revenue_growth is not None and revenue_growth > 20:
            target_per = 15
        elif revenue_growth is not None and revenue_growth > 10:
            target_per = 12
        else:
            target_per = 10
        estimates.append((eps * target_per, f"PER{target_per}x"))

    if not estimates:
        return None

    # 중앙값 (극단값 배제)
    estimates.sort(key=lambda x: x[0])
    mid_idx = len(estimates) // 2
    fair = estimates[mid_idx][0]
    labels = [e[1] for e in estimates]

    return int(fair), "/".join(labels)


class ValueScreenerService:
    """재무 저평가 스크리너."""

    # 보고서 우선순위: 연간 > 3분기 > 반기 (같은 연도 내)
    # Q1(11013)은 3개월뿐이라 연환산 왜곡이 커서 제외
    _REPRT_PRIORITY = ["11011", "11014", "11012"]
    # IS 연환산 배수: 누적 기간 → 12개월
    _ANNUALIZE_FACTOR = {
        "11014": 4 / 3,  # 9개월 → 12개월
        "11012": 2,      # 6개월 → 12개월
        "11011": 1,      # 이미 연간
    }
    _REPRT_LABEL = {
        "11014": "3분기",
        "11012": "반기",
        "11011": "사업보고서",
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.fs_service = FinancialStatementService(db)

    async def _load_all_reports(self) -> list:
        """반기/3분기/연간 보고서 전체 벌크 조회."""
        stmt = (
            select(FinancialStatement)
            .where(
                FinancialStatement.reprt_code.in_(self._REPRT_PRIORITY),
            )
            .order_by(
                FinancialStatement.stock_code,
                FinancialStatement.bsns_year.desc(),
                FinancialStatement.ord,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    def _pick_best_report(
        self,
        reports: dict[tuple[str, str], dict[str, list[dict]]],
    ) -> Optional[tuple[str, str, list[dict]]]:
        """종목의 보고서 중 가장 최신 것을 선택.

        Returns: (bsns_year, reprt_code, accounts) or None
        """
        # (year, reprt_code) 키를 최신순으로 정렬
        # 정렬 기준: 연도 내림차순, 같은 연도면 reprt_priority 순
        priority_map = {rc: i for i, rc in enumerate(self._REPRT_PRIORITY)}
        sorted_keys = sorted(
            reports.keys(),
            key=lambda k: (-int(k[0]), priority_map.get(k[1], 99)),
        )
        for year, rc in sorted_keys:
            fs_data = reports[(year, rc)]
            accounts = fs_data.get("CFS") or fs_data.get("OFS")
            if not accounts:
                accounts = list(fs_data.values())[0] if fs_data else None
            if accounts:
                return year, rc, accounts
        return None

    def _annualize_accounts(
        self, accounts: list[dict], reprt_code: str,
    ) -> list[dict]:
        """IS 항목을 연환산. BS 항목은 그대로."""
        factor = self._ANNUALIZE_FACTOR.get(reprt_code, 1)
        if factor == 1:
            return accounts

        result = []
        for acc in accounts:
            if acc["sj_div"] in ("IS", "CIS"):
                acc = dict(acc)  # copy
                if acc.get("thstrm_amount") is not None:
                    acc["thstrm_amount"] = int(acc["thstrm_amount"] * factor)
                if acc.get("frmtrm_amount") is not None:
                    acc["frmtrm_amount"] = int(acc["frmtrm_amount"] * factor)
            result.append(acc)
        return result

    async def scan(
        self,
        min_score: int = 0,
        limit: int = 100,
        sort_by: str = "total",
    ) -> ValueScreenerResponse:
        """전체 종목 재무 스크리닝 (최신 보고서 우선 + 연환산)."""
        # 1) 벌크 조회
        rows = await self._load_all_reports()
        if not rows:
            return ValueScreenerResponse(generated_at=now_kst().isoformat())

        # 2) 종목별 → (year, reprt_code) → fs_div → accounts 그룹핑
        by_stock: dict[str, dict[tuple[str, str], dict[str, list[dict]]]] = {}
        for r in rows:
            sc = r.stock_code
            key = (r.bsns_year, r.reprt_code)
            if sc not in by_stock:
                by_stock[sc] = {}
            if key not in by_stock[sc]:
                by_stock[sc][key] = {}
            if r.fs_div not in by_stock[sc][key]:
                by_stock[sc][key][r.fs_div] = []
            by_stock[sc][key][r.fs_div].append({
                "sj_div": r.sj_div,
                "sj_nm": r.sj_nm or "",
                "account_id": r.account_id,
                "account_nm": r.account_nm,
                "thstrm_amount": r.thstrm_amount,
                "frmtrm_amount": r.frmtrm_amount,
                "bfefrmtrm_amount": r.bfefrmtrm_amount,
            })

        # 3) 종목별 최적 보고서 선택
        chosen: dict[str, tuple[str, str, list[dict]]] = {}
        for sc, reports in by_stock.items():
            pick = self._pick_best_report(reports)
            if pick:
                chosen[sc] = pick

        stock_codes = list(chosen.keys())
        if not stock_codes:
            return ValueScreenerResponse(generated_at=now_kst().isoformat())

        # 4) 종목명 + 업종 일괄 조회
        name_stmt = select(Stock.code, Stock.name).where(Stock.code.in_(stock_codes))
        name_result = await self.db.execute(name_stmt)
        name_map = {r.code: r.name for r in name_result}

        sector_map: dict[str, str] = {}
        try:
            sector_stmt = select(
                CompanyProfile.stock_code, CompanyProfile.industry_name
            ).where(CompanyProfile.stock_code.in_(stock_codes))
            sector_result = await self.db.execute(sector_stmt)
            sector_map = {
                r.stock_code: r.industry_name
                for r in sector_result
                if r.industry_name
            }
        except Exception:
            pass

        # 5) 최신 종가 DB 조회 (stock_ohlcv — 외부 API 호출 없음)
        latest_date_sub = (
            select(
                StockOHLCV.stock_code,
                func.max(StockOHLCV.trade_date).label("max_date"),
            )
            .where(StockOHLCV.stock_code.in_(stock_codes))
            .group_by(StockOHLCV.stock_code)
            .subquery()
        )
        price_stmt = (
            select(StockOHLCV.stock_code, StockOHLCV.close_price)
            .join(
                latest_date_sub,
                and_(
                    StockOHLCV.stock_code == latest_date_sub.c.stock_code,
                    StockOHLCV.trade_date == latest_date_sub.c.max_date,
                ),
            )
        )
        price_result = await self.db.execute(price_stmt)
        close_prices: dict[str, int] = {
            r.stock_code: r.close_price for r in price_result
        }

        # 6) 비율 계산 + 스코어링
        metrics_list: list[ValueMetrics] = []
        for stock_code, (bsns_year, reprt_code, accounts) in chosen.items():
            # IS에서 "3개월" 항목 제외 (누적 데이터만 사용)
            filtered = [
                acc for acc in accounts
                if acc["sj_div"] not in ("IS", "CIS") or "3개월" not in acc.get("sj_nm", "")
            ]

            # 분기/반기는 IS 연환산
            filtered = self._annualize_accounts(filtered, reprt_code)

            # 시가총액 = 종가 × 주식수 (주식수 = 순이익 / EPS)
            mc: Optional[int] = None
            close = close_prices.get(stock_code)
            if close:
                eps = _find_account_amount(filtered, EPS_NAMES, sj_divs=["IS", "CIS"])
                ni = _find_account_amount(filtered, NET_INCOME_NAMES, sj_divs=["IS", "CIS"])
                if eps and eps != 0 and ni:
                    shares = ni / eps
                    mc = int(close * shares)

            ratios = self.fs_service.compute_ratios(filtered, market_cap=mc)

            per_s = _score_per(ratios.per)
            pbr_s = _score_pbr(ratios.pbr)
            roe_s = _score_roe(ratios.roe)
            margin_s = _score_operating_margin(ratios.operating_margin)
            growth_s = _score_revenue_growth(ratios.revenue_growth)
            debt_s = _score_debt_ratio(ratios.debt_ratio)
            current_s = _score_current_ratio(ratios.current_ratio)
            safety_s = debt_s + current_s

            total = per_s + pbr_s + roe_s + margin_s + growth_s + safety_s

            if total < min_score:
                continue

            comment = _build_comment(
                ratios.per, ratios.pbr, ratios.roe,
                ratios.operating_margin, ratios.revenue_growth,
                ratios.debt_ratio,
                per_s, pbr_s, roe_s, margin_s, growth_s, debt_s,
            )

            label = self._REPRT_LABEL.get(reprt_code, reprt_code)

            # 적정가치 산출 (BPS = 자본총계 / 주식수)
            fair_value: Optional[int] = None
            upside_pct: Optional[float] = None
            val_method: Optional[str] = None
            eps_val = _find_account_amount(filtered, EPS_NAMES, sj_divs=["IS", "CIS"])
            ni_val = _find_account_amount(filtered, NET_INCOME_NAMES, sj_divs=["IS", "CIS"])
            eq_val = _find_account_amount(filtered, TOTAL_EQUITY_NAMES, sj_divs=["BS"])
            bps: Optional[float] = None
            if eps_val and eps_val != 0 and ni_val and eq_val:
                bps = eq_val * eps_val / ni_val  # 자본총계 × EPS / 순이익 = 자본총계 / 주식수

            fv_result = _estimate_fair_value(
                eps=eps_val, bps=bps,
                roe=ratios.roe, revenue_growth=ratios.revenue_growth,
            )
            if fv_result:
                fair_value, val_method = fv_result
                if close and fair_value:
                    upside_pct = round((fair_value - close) / close * 100, 1)

            metrics_list.append(ValueMetrics(
                stock_code=stock_code,
                stock_name=name_map.get(stock_code, stock_code),
                sector=sector_map.get(stock_code),
                current_price=close,
                per=ratios.per,
                pbr=ratios.pbr,
                roe=ratios.roe,
                roa=ratios.roa,
                operating_margin=ratios.operating_margin,
                net_margin=ratios.net_margin,
                debt_ratio=ratios.debt_ratio,
                current_ratio=ratios.current_ratio,
                revenue_growth=ratios.revenue_growth,
                per_score=per_s,
                pbr_score=pbr_s,
                roe_score=roe_s,
                margin_score=margin_s,
                growth_score=growth_s,
                safety_score=safety_s,
                total_score=total,
                grade=_grade(total),
                comment=comment,
                fair_value=fair_value,
                upside_pct=upside_pct,
                valuation_method=val_method,
                bsns_year=bsns_year,
                reprt_code=f"{label}({reprt_code})",
            ))

        # 7) 정렬
        sort_keys = {
            "total": lambda m: m.total_score,
            "per": lambda m: m.per if m.per and m.per > 0 else 9999,
            "pbr": lambda m: m.pbr if m.pbr is not None else 9999,
            "roe": lambda m: m.roe if m.roe is not None else -9999,
            "growth": lambda m: m.revenue_growth if m.revenue_growth is not None else -9999,
            "upside": lambda m: m.upside_pct if m.upside_pct is not None else -9999,
        }
        key_fn = sort_keys.get(sort_by, sort_keys["total"])
        reverse = sort_by not in ("per", "pbr")
        metrics_list.sort(key=key_fn, reverse=reverse)
        metrics_list = metrics_list[:limit]

        # 8) 요약
        grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
        per_vals, pbr_vals, roe_vals = [], [], []
        for m in metrics_list:
            grade_counts[m.grade] = grade_counts.get(m.grade, 0) + 1
            if m.per is not None and m.per > 0:
                per_vals.append(m.per)
            if m.pbr is not None:
                pbr_vals.append(m.pbr)
            if m.roe is not None:
                roe_vals.append(m.roe)

        summary = ValueScreenerSummary(
            grade_counts=grade_counts,
            avg_per=round(sum(per_vals) / len(per_vals), 2) if per_vals else None,
            avg_pbr=round(sum(pbr_vals) / len(pbr_vals), 2) if pbr_vals else None,
            avg_roe=round(sum(roe_vals) / len(roe_vals), 2) if roe_vals else None,
            total_screened=len(metrics_list),
        )

        return ValueScreenerResponse(
            stocks=metrics_list,
            summary=summary,
            generated_at=now_kst().isoformat(),
        )

    async def get_stock_detail(self, stock_code: str) -> Optional[ValueMetrics]:
        """단일 종목 상세 재무 스코어."""
        result = await self.scan(min_score=0, limit=9999, sort_by="total")
        for m in result.stocks:
            if m.stock_code == stock_code:
                return m
        return None
