"""시장 인텔리전스 서비스 - 통합 시그널 피드 생성."""

import logging
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.timezone import now_kst, today_kst

settings = get_settings()
from models import (
    CatalystEvent, ThemeChartPattern, ThemeSetup,
    YouTubeMention, TelegramIdea, StockInvestorFlow, Stock,
)
from services.cross_reference_service import get_convergence_signals

logger = logging.getLogger(__name__)


class MarketIntelService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_feed(self, limit: int = 50) -> dict:
        sources = [
            self._catalysts,
            self._flow_spikes,
            self._chart_patterns,
            self._emerging_themes,
            self._youtube_mentions,
            self._convergence_signals,
        ]
        if settings.telegram_feature_enabled:
            sources.append(self._telegram_ideas)

        feed = []
        for src in sources:
            try:
                items = await src()
                feed.extend(items)
            except Exception as e:
                logger.warning(f"인텔 소스 실패: {e}")

        # 시간순 정렬 (최신 먼저)
        # naive/aware datetime 혼재 방지: 모두 naive로 통일
        for item in feed:
            ts = item.get("timestamp")
            if ts and hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                item["timestamp"] = ts.replace(tzinfo=None)
        feed.sort(key=lambda x: x["timestamp"], reverse=True)
        feed = feed[:limit]

        # 요약 집계
        summary = defaultdict(int)
        for item in feed:
            summary[item["signal_type"]] += 1
            if item["severity"] == "critical":
                summary["critical_count"] += 1
            elif item["severity"] == "high":
                summary["high_count"] += 1

        total = len(feed)

        return {
            "feed": feed,
            "summary": {
                "catalyst": summary.get("catalyst", 0),
                "flow_spike": summary.get("flow_spike", 0),
                "chart_pattern": summary.get("chart_pattern", 0),
                "emerging_theme": summary.get("emerging_theme", 0),
                "youtube": summary.get("youtube", 0),
                "convergence": summary.get("convergence", 0),
                "telegram": summary.get("telegram", 0),
                "total": total,
                "critical_count": summary.get("critical_count", 0),
                "high_count": summary.get("high_count", 0),
            },
            "generated_at": now_kst().isoformat(),
        }

    async def _catalysts(self) -> list[dict]:
        since = today_kst() - timedelta(days=7)
        result = await self.db.execute(
            select(CatalystEvent)
            .where(and_(
                CatalystEvent.status == "active",
                CatalystEvent.event_date >= since,
            ))
            .order_by(desc(CatalystEvent.event_date))
            .limit(20)
        )
        events = result.scalars().all()

        items = []
        for e in events:
            severity = "medium"
            if e.flow_confirmed and abs(e.price_change_pct or 0) >= 5:
                severity = "high"
            if e.flow_confirmed and abs(e.price_change_pct or 0) >= 8:
                severity = "critical"

            items.append({
                "signal_type": "catalyst",
                "severity": severity,
                "stock_code": e.stock_code,
                "stock_name": e.stock_name,
                "title": e.title[:200],
                "description": f"{e.catalyst_type or '기타'} | 변동 {e.price_change_pct or 0:+.1f}% | 수급동반 {'O' if e.flow_confirmed else 'X'}",
                "timestamp": e.created_at,
                "metadata": {
                    "catalyst_type": e.catalyst_type,
                    "price_change_pct": e.price_change_pct,
                    "flow_confirmed": e.flow_confirmed,
                    "days_alive": e.days_alive,
                },
            })
        return items

    async def _flow_spikes(self) -> list[dict]:
        today = today_kst()
        recent_days = 2
        base_days = 20
        since_recent = today - timedelta(days=recent_days)
        since_base = today - timedelta(days=base_days)

        recent_q = (
            select(
                StockInvestorFlow.stock_code,
                func.sum(StockInvestorFlow.foreign_net_amount + StockInvestorFlow.institution_net_amount).label("recent_sum"),
            )
            .where(StockInvestorFlow.flow_date >= since_recent)
            .group_by(StockInvestorFlow.stock_code)
        )
        recent_result = await self.db.execute(recent_q)
        recent_map = {r.stock_code: float(r.recent_sum or 0) for r in recent_result}

        base_q = (
            select(
                StockInvestorFlow.stock_code,
                (func.sum(StockInvestorFlow.foreign_net_amount + StockInvestorFlow.institution_net_amount)
                 / func.count(func.distinct(StockInvestorFlow.flow_date))).label("daily_avg"),
            )
            .where(and_(
                StockInvestorFlow.flow_date >= since_base,
                StockInvestorFlow.flow_date < since_recent,
            ))
            .group_by(StockInvestorFlow.stock_code)
        )
        base_result = await self.db.execute(base_q)
        base_map = {r.stock_code: float(r.daily_avg or 0) for r in base_result}

        # 종목명 조회
        all_codes = set(recent_map.keys())
        name_map = {}
        if all_codes:
            name_result = await self.db.execute(
                select(Stock.code, Stock.name).where(Stock.code.in_(all_codes))
            )
            name_map = {r.code: r.name for r in name_result}

        items = []
        for code, recent_sum in recent_map.items():
            base_avg = base_map.get(code, 0)
            if base_avg > 0 and recent_sum > 300_000_000:
                ratio = (recent_sum / recent_days) / base_avg
                if ratio >= 2.0:
                    severity = "info"
                    if ratio >= 5.0:
                        severity = "high"
                    if ratio >= 8.0:
                        severity = "critical"
                    elif ratio >= 3.0:
                        severity = "medium"

                    items.append({
                        "signal_type": "flow_spike",
                        "severity": severity,
                        "stock_code": code,
                        "stock_name": name_map.get(code, code),
                        "title": f"수급 급증 x{ratio:.1f}",
                        "description": f"최근 2일 순매수 {recent_sum / 1e8:.0f}억 (평소 대비 {ratio:.1f}배)",
                        "timestamp": now_kst(),
                        "metadata": {
                            "spike_ratio": round(ratio, 1),
                            "recent_amount": round(recent_sum),
                        },
                    })

        items.sort(key=lambda x: x["metadata"]["spike_ratio"], reverse=True)
        return items[:15]

    async def _chart_patterns(self) -> list[dict]:
        since = today_kst() - timedelta(days=7)
        result = await self.db.execute(
            select(ThemeChartPattern)
            .where(and_(
                ThemeChartPattern.analysis_date >= since,
                ThemeChartPattern.is_active == True,
            ))
            .order_by(desc(ThemeChartPattern.confidence))
            .limit(15)
        )
        patterns = result.scalars().all()

        pattern_labels = {
            "range_bound": "횡보 박스권",
            "double_bottom": "쌍바닥",
            "triple_bottom": "삼중바닥",
            "converging": "수렴",
            "pre_breakout": "돌파 직전",
        }

        items = []
        for p in patterns:
            severity = "info"
            if p.pattern_type == "pre_breakout":
                severity = "high"
            elif p.pattern_type in ("double_bottom", "triple_bottom") and (p.confidence or 0) >= 70:
                severity = "medium"
            elif (p.confidence or 0) >= 80:
                severity = "medium"

            items.append({
                "signal_type": "chart_pattern",
                "severity": severity,
                "stock_code": p.stock_code,
                "stock_name": p.stock_name,
                "title": f"{pattern_labels.get(p.pattern_type, p.pattern_type)} 감지",
                "description": f"테마: {p.theme_name} | 신뢰도 {p.confidence}%",
                "timestamp": p.updated_at or p.created_at,
                "metadata": {
                    "pattern_type": p.pattern_type,
                    "confidence": p.confidence,
                    "theme_name": p.theme_name,
                },
            })
        return items

    async def _emerging_themes(self) -> list[dict]:
        result = await self.db.execute(
            select(ThemeSetup)
            .where(ThemeSetup.total_setup_score >= 30)
            .order_by(desc(ThemeSetup.total_setup_score))
            .limit(10)
        )
        themes = result.scalars().all()

        items = []
        for t in themes:
            severity = "info"
            if t.total_setup_score >= 70:
                severity = "high"
            elif t.total_setup_score >= 50:
                severity = "medium"

            top_stocks_str = ""
            if t.top_stocks:
                names = [s.get("name", "") for s in t.top_stocks[:3] if isinstance(s, dict)]
                top_stocks_str = ", ".join(names)

            items.append({
                "signal_type": "emerging_theme",
                "severity": severity,
                "stock_code": None,
                "stock_name": None,
                "title": f"테마 셋업: {t.theme_name}",
                "description": f"점수 {t.total_setup_score:.0f}/100 | 순위 #{t.rank or '-'}" + (f" | {top_stocks_str}" if top_stocks_str else ""),
                "timestamp": t.updated_at or t.created_at,
                "metadata": {
                    "theme_name": t.theme_name,
                    "setup_score": t.total_setup_score,
                    "rank": t.rank,
                },
            })
        return items

    async def _youtube_mentions(self) -> list[dict]:
        since = now_kst().replace(tzinfo=None) - timedelta(days=3)
        result = await self.db.execute(
            select(YouTubeMention)
            .where(YouTubeMention.published_at >= since)
            .order_by(desc(YouTubeMention.published_at))
            .limit(15)
        )
        mentions = result.scalars().all()

        items = []
        for m in mentions:
            tickers = m.mentioned_tickers or []
            if not tickers:
                continue

            items.append({
                "signal_type": "youtube",
                "severity": "info",
                "stock_code": tickers[0] if tickers else None,
                "stock_name": None,
                "title": m.video_title[:150],
                "description": f"{m.channel_name} | 종목: {', '.join(tickers[:5])} | 조회 {(m.view_count or 0):,}",
                "timestamp": m.published_at,
                "metadata": {
                    "channel_name": m.channel_name,
                    "video_id": m.video_id,
                    "tickers": tickers,
                    "view_count": m.view_count,
                },
            })
        return items

    async def _convergence_signals(self) -> list[dict]:
        signals = await get_convergence_signals(self.db, days=7, min_sources=2)

        items = []
        for sig in signals[:10]:
            src_count = sig.get("source_count", 0)
            severity = "info"
            if src_count >= 4:
                severity = "critical"
            elif src_count >= 3:
                severity = "high"
            elif src_count >= 2:
                severity = "medium"

            sources = sig.get("sources", [])
            items.append({
                "signal_type": "convergence",
                "severity": severity,
                "stock_code": sig.get("stock_code"),
                "stock_name": sig.get("stock_name"),
                "title": f"다중 소스 수렴 ({src_count}개 소스)",
                "description": f"소스: {', '.join(sources)} | 총 언급 {sig.get('total_mentions', 0)}건",
                "timestamp": now_kst(),
                "metadata": {
                    "source_count": src_count,
                    "sources": sources,
                    "total_mentions": sig.get("total_mentions", 0),
                },
            })
        return items

    async def _telegram_ideas(self) -> list[dict]:
        since = now_kst().replace(tzinfo=None) - timedelta(days=3)
        result = await self.db.execute(
            select(TelegramIdea)
            .where(and_(
                TelegramIdea.original_date >= since,
                TelegramIdea.stock_code.isnot(None),
            ))
            .order_by(desc(TelegramIdea.original_date))
            .limit(15)
        )
        ideas = result.scalars().all()

        items = []
        for idea in ideas:
            severity = "info"
            if idea.sentiment == "bullish" and (idea.sentiment_score or 0) >= 0.8:
                severity = "medium"

            items.append({
                "signal_type": "telegram",
                "severity": severity,
                "stock_code": idea.stock_code,
                "stock_name": idea.stock_name,
                "title": f"{idea.channel_name}: {idea.stock_name or idea.stock_code}",
                "description": idea.message_text[:200] if idea.message_text else "",
                "timestamp": idea.original_date,
                "metadata": {
                    "channel_name": idea.channel_name,
                    "sentiment": idea.sentiment,
                    "sentiment_score": idea.sentiment_score,
                },
            })
        return items
