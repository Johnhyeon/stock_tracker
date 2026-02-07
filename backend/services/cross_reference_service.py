"""종목 교차 참조 서비스.

하나의 종목코드로 모든 데이터 소스를 통합 조회.
"""
import asyncio
import logging
from datetime import date, timedelta, datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from models import (
    StockOHLCV, StockInvestorFlow, YouTubeMention, TraderMention,
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

        (
            stock_info, ohlcv, flow, youtube, trader,
            disclosures, ideas, sentiment, patterns,
        ) = await asyncio.gather(
            _query(self._get_stock_info, stock_code),
            _query(self._get_recent_ohlcv, stock_code),
            _query(self._get_flow_summary, stock_code),
            _query(self._get_youtube_mentions, stock_code),
            _query(self._get_trader_mentions, stock_code),
            _query(self._get_recent_disclosures, stock_code),
            _query(self._get_telegram_ideas, stock_code),
            _query(self._get_sentiment_summary, stock_code),
            _query(self._get_chart_patterns, stock_code),
        )

        return {
            "stock_code": stock_code,
            "stock_info": stock_info,
            "ohlcv": ohlcv,
            "investor_flow": flow,
            "youtube_mentions": youtube,
            "trader_mentions": trader,
            "disclosures": disclosures,
            "telegram_ideas": ideas,
            "sentiment": sentiment,
            "chart_patterns": patterns,
            "themes": themes,
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
        since = date.today() - timedelta(days=days + 10)
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
        since = date.today() - timedelta(days=days + 5)
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
        since = date.today() - timedelta(days=days)
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

    async def _get_trader_mentions(self, db: AsyncSession, stock_code: str, days: int = 14) -> dict:
        """트레이더 언급 요약."""
        since = date.today() - timedelta(days=days)
        stmt = (
            select(
                func.count(TraderMention.id),
            )
            .where(and_(
                TraderMention.stock_code == stock_code,
                TraderMention.mention_date >= since,
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
        since = date.today() - timedelta(days=30)
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
        since = datetime.utcnow() - timedelta(days=30)
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
        since = datetime.utcnow() - timedelta(days=days)
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


async def get_trending_mentions(db: AsyncSession, days: int = 7, limit: int = 20) -> list[dict]:
    """전체 소스 합산 인기 종목."""
    since_date = date.today() - timedelta(days=days)
    since_dt = datetime.utcnow() - timedelta(days=days)

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

    # 트레이더 언급
    tr_stmt = (
        select(
            TraderMention.stock_code,
            func.sum(TraderMention.mention_count).label("tr_count"),
        )
        .where(TraderMention.mention_date >= since_date)
        .group_by(TraderMention.stock_code)
    )
    tr_result = await db.execute(tr_stmt)
    tr_map = {r.stock_code: int(r.tr_count or 0) for r in tr_result}

    # 텔레그램 아이디어
    tg_stmt = (
        select(
            TelegramIdea.stock_code,
            func.count(TelegramIdea.id).label("tg_count"),
        )
        .where(TelegramIdea.message_date >= since_dt)
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
            "trader_count": tr,
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
