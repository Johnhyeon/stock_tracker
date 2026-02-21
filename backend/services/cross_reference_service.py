"""종목 교차 참조 서비스.

하나의 종목코드로 모든 데이터 소스를 통합 조회.
"""
import asyncio
import logging
from datetime import date, timedelta, datetime
from typing import Optional

from core.config import get_settings
from core.timezone import now_kst, today_kst

settings = get_settings()

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from models import (
    StockOHLCV, StockInvestorFlow, YouTubeMention, ExpertMention,
    Disclosure, TelegramIdea, ReportSentimentAnalysis, ThemeChartPattern,
    TelegramReport, Stock,
)
from core.database import async_session_maker
from services.theme_map_service import get_theme_map_service

logger = logging.getLogger(__name__)


class CrossReferenceService:
    """종목 교차 참조 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._tms = get_theme_map_service()

    async def get_stock_profile(self, stock_code: str) -> dict:
        """종목의 전체 프로필 데이터 통합 조회 (병렬)."""
        themes = self._tms.get_themes_for_stock(stock_code)

        # 각 쿼리를 별도 세션으로 병렬 실행
        async def _query(coro_func, *args):
            async with async_session_maker() as session:
                return await coro_func(session, *args)

        async def _empty_list():
            return []

        async def _empty_expert():
            return {"mention_count": 0, "total_mentions": 0, "period_days": 14}

        (
            stock_info, ohlcv, flow, youtube, expert,
            disclosures, ideas, sentiment, patterns,
            financial_summary,
        ) = await asyncio.gather(
            _query(self._get_stock_info, stock_code),
            _query(self._get_recent_ohlcv, stock_code),
            _query(self._get_flow_summary, stock_code),
            _query(self._get_youtube_mentions, stock_code),
            _query(self._get_expert_mentions, stock_code) if settings.expert_feature_enabled else _empty_expert(),
            _query(self._get_recent_disclosures, stock_code),
            _query(self._get_telegram_ideas, stock_code) if settings.telegram_feature_enabled else _empty_list(),
            _query(self._get_sentiment_summary, stock_code),
            _query(self._get_chart_patterns, stock_code),
            _query(self._get_financial_summary, stock_code),
        )

        return {
            "stock_code": stock_code,
            "stock_info": stock_info,
            "ohlcv": ohlcv,
            "investor_flow": flow,
            "youtube_mentions": youtube,
            "expert_mentions": expert,
            "disclosures": disclosures,
            "telegram_ideas": ideas,
            "sentiment": sentiment,
            "chart_patterns": patterns,
            "themes": themes,
            "financial_summary": financial_summary,
        }

    async def _get_stock_info(self, db: AsyncSession, stock_code: str) -> Optional[dict]:
        """종목 기본 정보."""
        stmt = select(Stock).where(Stock.code == stock_code)
        result = await db.execute(stmt)
        stock = result.scalar_one_or_none()
        if not stock:
            return None
        return {
            "code": stock.code,
            "name": stock.name,
            "market": stock.market,
        }

    async def _get_recent_ohlcv(self, db: AsyncSession, stock_code: str, days: int = 5) -> dict:
        """최근 OHLCV 데이터 요약."""
        since = today_kst() - timedelta(days=days + 10)
        stmt = (
            select(StockOHLCV)
            .where(and_(
                StockOHLCV.stock_code == stock_code,
                StockOHLCV.trade_date >= since,
            ))
            .order_by(StockOHLCV.trade_date.desc())
            .limit(days)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return {"has_data": False}

        latest = rows[0]
        prev = rows[1] if len(rows) > 1 else None
        change_rate = 0
        if prev and prev.close_price > 0:
            change_rate = ((latest.close_price - prev.close_price) / prev.close_price) * 100

        return {
            "has_data": True,
            "latest_price": latest.close_price,
            "change_rate": round(change_rate, 2),
            "volume": latest.volume,
            "trade_date": latest.trade_date.isoformat(),
            "data_count": len(rows),
        }

    async def _get_flow_summary(self, db: AsyncSession, stock_code: str, days: int = 10) -> dict:
        """투자자 수급 요약."""
        since = today_kst() - timedelta(days=days + 5)
        stmt = (
            select(StockInvestorFlow)
            .where(and_(
                StockInvestorFlow.stock_code == stock_code,
                StockInvestorFlow.flow_date >= since,
            ))
            .order_by(StockInvestorFlow.flow_date.desc())
            .limit(days)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return {"has_data": False}

        foreign_net = sum(r.foreign_net or 0 for r in rows)
        inst_net = sum(r.institution_net or 0 for r in rows)

        # 연속 매수일 계산 (외국인)
        consecutive_foreign = 0
        for r in rows:
            if (r.foreign_net or 0) > 0:
                consecutive_foreign += 1
            else:
                break

        return {
            "has_data": True,
            "days": len(rows),
            "foreign_net_total": foreign_net,
            "institution_net_total": inst_net,
            "consecutive_foreign_buy": consecutive_foreign,
            "latest_date": rows[0].flow_date.isoformat(),
        }

    async def _get_youtube_mentions(self, db: AsyncSession, stock_code: str, days: int = 14) -> dict:
        """유튜브 언급 요약."""
        since = today_kst() - timedelta(days=days)
        stmt = (
            select(func.count(func.distinct(YouTubeMention.video_id)))
            .where(and_(
                YouTubeMention.mentioned_tickers.overlap([stock_code]),
                YouTubeMention.published_at >= since,
            ))
        )
        result = await db.execute(stmt)
        count = result.scalar() or 0

        return {
            "video_count": count,
            "period_days": days,
            "is_trending": count >= 3,
        }

    async def _get_expert_mentions(self, db: AsyncSession, stock_code: str, days: int = 14) -> dict:
        """전문가 언급 요약."""
        since = today_kst() - timedelta(days=days)
        stmt = (
            select(
                func.count(ExpertMention.id),
            )
            .where(and_(
                ExpertMention.stock_code == stock_code,
                ExpertMention.mention_date >= since,
            ))
        )
        result = await db.execute(stmt)
        count = result.scalar() or 0

        return {
            "mention_count": count,
            "total_mentions": count,
            "period_days": days,
        }

    async def _get_recent_disclosures(self, db: AsyncSession, stock_code: str, limit: int = 5) -> list[dict]:
        """최근 공시."""
        since = today_kst() - timedelta(days=30)
        stmt = (
            select(Disclosure)
            .where(and_(
                Disclosure.stock_code == stock_code,
                Disclosure.rcept_dt >= since.isoformat().replace('-', ''),
            ))
            .order_by(Disclosure.rcept_dt.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "title": r.report_nm,
                "date": r.rcept_dt if r.rcept_dt else None,
                "type": r.disclosure_type,
            }
            for r in rows
        ]

    async def _get_telegram_ideas(self, db: AsyncSession, stock_code: str, limit: int = 5) -> list[dict]:
        """텔레그램 아이디어."""
        since = now_kst().replace(tzinfo=None) - timedelta(days=30)
        stmt = (
            select(TelegramIdea)
            .where(and_(
                TelegramIdea.stock_code == stock_code,
                TelegramIdea.original_date >= since,
            ))
            .order_by(TelegramIdea.original_date.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "message_text": r.message_text[:200] if r.message_text else "",
                "author": r.channel_name,
                "date": r.original_date.isoformat() if r.original_date else None,
                "source_type": str(r.source_type) if r.source_type else None,
            }
            for r in rows
        ]

    async def _get_sentiment_summary(self, db: AsyncSession, stock_code: str, days: int = 14) -> dict:
        """감정분석 요약."""
        since = now_kst().replace(tzinfo=None) - timedelta(days=days)
        stmt = (
            select(
                func.count(ReportSentimentAnalysis.id),
                func.avg(ReportSentimentAnalysis.sentiment_score),
            )
            .join(TelegramReport)
            .where(and_(
                ReportSentimentAnalysis.stock_code == stock_code,
                TelegramReport.message_date >= since,
            ))
        )
        result = await db.execute(stmt)
        row = result.one()

        return {
            "analysis_count": row[0] or 0,
            "avg_score": round(float(row[1] or 0), 3),
            "period_days": days,
        }

    async def _get_chart_patterns(self, db: AsyncSession, stock_code: str) -> list[dict]:
        """차트 패턴."""
        stmt = (
            select(ThemeChartPattern)
            .where(and_(
                ThemeChartPattern.stock_code == stock_code,
                ThemeChartPattern.is_active == True,
            ))
            .order_by(ThemeChartPattern.analysis_date.desc())
            .limit(3)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "pattern_type": str(r.pattern_type) if r.pattern_type else None,
                "confidence": r.confidence,
                "analysis_date": r.analysis_date.isoformat() if r.analysis_date else None,
            }
            for r in rows
        ]

    async def _get_financial_summary(self, db: AsyncSession, stock_code: str) -> dict:
        """재무제표 요약 (최신 보고서 기준 + 연간 추세).

        - 최신 보고서(분기 포함)의 thstrm/frmtrm으로 전년 동기 YoY 비교
        - 최근 3개년 연간 실적 추세
        """
        from models.financial_statement import FinancialStatement as FS
        from services.financial_statement_service import (
            _find_account_amount,
            REVENUE_NAMES, OPERATING_INCOME_NAMES, NET_INCOME_NAMES,
            TOTAL_EQUITY_NAMES, TOTAL_ASSETS_NAMES, TOTAL_LIABILITIES_NAMES,
            CURRENT_ASSETS_NAMES, CURRENT_LIABILITIES_NAMES,
        )

        # 모든 보고서 조회 (분기+연간)
        stmt = (
            select(FS)
            .where(FS.stock_code == stock_code)
            .order_by(FS.bsns_year.desc(), FS.ord)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return {"has_data": False}

        is_divs = ["IS", "CIS"]
        bs_divs = ["BS"]
        REPRT_LABELS = {
            "11011": "연간", "11014": "3분기(누적)",
            "11012": "반기", "11013": "1분기",
        }
        # 동일 연도 내 최신순: 연간 > 3분기 > 반기 > 1분기
        REPRT_ORDER = {"11011": 0, "11014": 1, "11012": 2, "11013": 3}

        def _safe_ratio(num, den, mult=100):
            if num is not None and den and den != 0:
                return round(num / den * mult, 2)
            return None

        def _growth(cur, prev):
            if cur is not None and prev and prev != 0:
                return round((cur - prev) / abs(prev) * 100, 2)
            return None

        # (year, reprt_code)별 그룹화, CFS 우선
        periods_by_fs: dict[tuple, dict[str, list[dict]]] = {}
        for r in rows:
            key = (r.bsns_year, r.reprt_code)
            if key not in periods_by_fs:
                periods_by_fs[key] = {}
            fs = r.fs_div or "OFS"
            if fs not in periods_by_fs[key]:
                periods_by_fs[key][fs] = []
            periods_by_fs[key][fs].append({
                "sj_div": r.sj_div,
                "sj_nm": r.sj_nm or "",
                "account_nm": r.account_nm,
                "thstrm_amount": r.thstrm_amount,
                "frmtrm_amount": r.frmtrm_amount,
                "bfefrmtrm_amount": r.bfefrmtrm_amount,
            })

        periods: dict[tuple, list[dict]] = {}
        for key, fs_data in periods_by_fs.items():
            periods[key] = fs_data.get("CFS") or fs_data.get("OFS") or list(fs_data.values())[0]

        # 최신순 정렬
        sorted_keys = sorted(
            periods.keys(),
            key=lambda k: (-int(k[0]), REPRT_ORDER.get(k[1], 9))
        )
        if not sorted_keys:
            return {"has_data": False}

        # --- 가장 최신 보고서 기준 ---
        latest_key = sorted_keys[0]
        latest_accounts = periods[latest_key]
        latest_year, latest_reprt = latest_key
        latest_label = f"{latest_year}년 {REPRT_LABELS.get(latest_reprt, latest_reprt)}"

        # IS에서 "3개월" 항목 제외 (누적 기준 사용)
        cum_accounts = [
            acc for acc in latest_accounts
            if acc["sj_div"] not in ("IS", "CIS") or "3개월" not in acc.get("sj_nm", "")
        ]

        # 당기
        revenue = _find_account_amount(cum_accounts, REVENUE_NAMES, sj_divs=is_divs)
        operating_income = _find_account_amount(cum_accounts, OPERATING_INCOME_NAMES, sj_divs=is_divs)
        net_income = _find_account_amount(cum_accounts, NET_INCOME_NAMES, sj_divs=is_divs)
        total_assets = _find_account_amount(cum_accounts, TOTAL_ASSETS_NAMES, sj_divs=bs_divs)
        total_liabilities = _find_account_amount(cum_accounts, TOTAL_LIABILITIES_NAMES, sj_divs=bs_divs)
        total_equity = _find_account_amount(cum_accounts, TOTAL_EQUITY_NAMES, sj_divs=bs_divs)
        current_assets = _find_account_amount(cum_accounts, CURRENT_ASSETS_NAMES, sj_divs=bs_divs)
        current_liabilities = _find_account_amount(cum_accounts, CURRENT_LIABILITIES_NAMES, sj_divs=bs_divs)

        # 전년 동기 (frmtrm_amount) → 같은 보고서 내 동일 기준이라 비교 가능
        prev_revenue = _find_account_amount(cum_accounts, REVENUE_NAMES, "frmtrm_amount", sj_divs=is_divs)
        prev_oi = _find_account_amount(cum_accounts, OPERATING_INCOME_NAMES, "frmtrm_amount", sj_divs=is_divs)
        prev_ni = _find_account_amount(cum_accounts, NET_INCOME_NAMES, "frmtrm_amount", sj_divs=is_divs)

        # 비율
        roe = _safe_ratio(net_income, total_equity)
        roa = _safe_ratio(net_income, total_assets)
        op_margin = _safe_ratio(operating_income, revenue)
        net_margin = _safe_ratio(net_income, revenue)
        debt_ratio = _safe_ratio(total_liabilities, total_equity)
        current_ratio = _safe_ratio(current_assets, current_liabilities)

        # YoY 성장률 (전년 동기 대비)
        revenue_growth = _growth(revenue, prev_revenue)
        oi_growth = _growth(operating_income, prev_oi)
        ni_growth = _growth(net_income, prev_ni)

        # 마진 추세
        prev_op_margin = _safe_ratio(prev_oi, prev_revenue)
        margin_trend = "stable"
        if op_margin is not None and prev_op_margin is not None:
            diff = op_margin - prev_op_margin
            if diff > 2:
                margin_trend = "improving"
            elif diff < -2:
                margin_trend = "deteriorating"

        is_profitable = net_income is not None and net_income > 0
        is_growing = revenue_growth is not None and revenue_growth > 0

        # --- 연간 추세 (최근 3년) ---
        annual_trend = []
        annual_keys = [k for k in sorted_keys if k[1] == "11011"][:3]
        for key in annual_keys:
            accs = periods[key]
            cum_accs = [
                a for a in accs
                if a["sj_div"] not in ("IS", "CIS") or "3개월" not in a.get("sj_nm", "")
            ]
            a_rev = _find_account_amount(cum_accs, REVENUE_NAMES, sj_divs=is_divs)
            a_oi = _find_account_amount(cum_accs, OPERATING_INCOME_NAMES, sj_divs=is_divs)
            a_ni = _find_account_amount(cum_accs, NET_INCOME_NAMES, sj_divs=is_divs)
            annual_trend.append({
                "year": key[0],
                "revenue": a_rev,
                "operating_income": a_oi,
                "net_income": a_ni,
            })

        return {
            "has_data": True,
            "latest_period": latest_label,
            "bsns_year": latest_year,
            "reprt_code": latest_reprt,
            "revenue": revenue,
            "operating_income": operating_income,
            "net_income": net_income,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "total_equity": total_equity,
            # 비율
            "roe": roe,
            "roa": roa,
            "operating_margin": op_margin,
            "net_margin": net_margin,
            "debt_ratio": debt_ratio,
            "current_ratio": current_ratio,
            # 전년 동기 대비 YoY 성장률
            "revenue_growth_yoy": revenue_growth,
            "oi_growth_yoy": oi_growth,
            "ni_growth_yoy": ni_growth,
            # 판단 플래그
            "margin_trend": margin_trend,
            "is_profitable": is_profitable,
            "is_growing": is_growing,
            # 연간 추세
            "annual_trend": annual_trend,
        }


async def get_trending_mentions(db: AsyncSession, days: int = 7, limit: int = 20) -> list[dict]:
    """전체 소스 합산 인기 종목."""
    since_date = today_kst() - timedelta(days=days)
    since_dt = now_kst().replace(tzinfo=None) - timedelta(days=days)

    # YouTube 언급
    yt_stmt = (
        select(
            func.unnest(YouTubeMention.mentioned_tickers).label("code"),
            func.count(func.distinct(YouTubeMention.video_id)).label("yt_count"),
        )
        .where(YouTubeMention.published_at >= since_date)
        .group_by("code")
    )
    yt_result = await db.execute(yt_stmt)
    yt_map = {r.code: r.yt_count for r in yt_result}

    # 전문가 언급
    tr_map: dict[str, int] = {}
    if settings.expert_feature_enabled:
        tr_stmt = (
            select(
                ExpertMention.stock_code,
                func.count(ExpertMention.id).label("tr_count"),
            )
            .where(ExpertMention.mention_date >= since_date)
            .group_by(ExpertMention.stock_code)
        )
        tr_result = await db.execute(tr_stmt)
        tr_map = {r.stock_code: int(r.tr_count or 0) for r in tr_result}

    # 텔레그램 아이디어
    tg_map: dict[str, int] = {}
    if settings.telegram_feature_enabled:
        tg_stmt = (
            select(
                TelegramIdea.stock_code,
                func.count(TelegramIdea.id).label("tg_count"),
            )
            .where(TelegramIdea.original_date >= since_dt)
            .group_by(TelegramIdea.stock_code)
        )
        tg_result = await db.execute(tg_stmt)
        tg_map = {r.stock_code: r.tg_count for r in tg_result}

    # 합산
    all_codes = set(yt_map.keys()) | set(tr_map.keys()) | set(tg_map.keys())
    scored = []
    for code in all_codes:
        if not code:
            continue
        yt = yt_map.get(code, 0)
        tr = tr_map.get(code, 0)
        tg = tg_map.get(code, 0)
        sources = sum(1 for x in [yt, tr, tg] if x > 0)
        total = yt + tr + tg
        scored.append({
            "stock_code": code,
            "youtube_count": yt,
            "expert_count": tr,
            "telegram_count": tg,
            "total_mentions": total,
            "source_count": sources,
        })

    scored.sort(key=lambda x: x["total_mentions"], reverse=True)

    # 종목명 조회
    codes = [s["stock_code"] for s in scored[:limit]]
    name_stmt = select(Stock.code, Stock.name).where(Stock.code.in_(codes))
    name_result = await db.execute(name_stmt)
    name_map = {r.code: r.name for r in name_result}

    for s in scored[:limit]:
        s["stock_name"] = name_map.get(s["stock_code"], "")

    return scored[:limit]


async def get_convergence_signals(db: AsyncSession, days: int = 7, min_sources: int = 2) -> list[dict]:
    """2개 이상 소스에서 동시 언급된 종목 (교차 시그널)."""
    all_mentions = await get_trending_mentions(db, days=days, limit=100)
    convergence = [m for m in all_mentions if m["source_count"] >= min_sources]
    convergence.sort(key=lambda x: (x["source_count"], x["total_mentions"]), reverse=True)
    return convergence[:30]
