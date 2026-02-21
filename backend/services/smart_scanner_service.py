"""Smart Scanner 서비스 - 4차원 복합 점수 엔진.

기존 PullbackService(차트) + CrossReferenceService(소셜) + 수급/뉴스 데이터를
결합하여 차트·내러티브·수급·소셜 4차원 교차검증 점수를 산출.
"""
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from core.config import get_settings
from core.timezone import now_kst, today_kst

settings = get_settings()

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from models import (
    StockInvestorFlow, ThemeNews, Disclosure, YouTubeMention,
    ExpertMention, TelegramIdea, ReportSentimentAnalysis, TelegramReport, Stock,
)
from schemas.smart_scanner import SmartSignalDimension, SmartScannerStock
from services.pullback_service import PullbackService
from services.cross_reference_service import get_trending_mentions
from services.theme_map_service import get_theme_map_service

logger = logging.getLogger(__name__)


def _grade(score: float, max_score: float) -> str:
    if max_score <= 0:
        return "D"
    pct = score / max_score * 100
    if pct >= 80:
        return "A"
    if pct >= 60:
        return "B"
    if pct >= 40:
        return "C"
    return "D"


def _composite_grade(score: float) -> str:
    if score >= 75:
        return "A"
    if score >= 55:
        return "B"
    if score >= 35:
        return "C"
    return "D"


class SmartScannerService:
    """4차원 복합 점수 스캐너."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._tms = get_theme_map_service()

    async def scan_all(
        self,
        min_score: float = 0.0,
        limit: int = 100,
        sort_by: str = "composite",
        exclude_expert: bool = False,
    ) -> list[SmartScannerStock]:
        """전체 종목 스캔 → 4차원 복합 점수 산출.

        Args:
            exclude_expert: True이면 전문가 멘션 점수를 제외하고 소셜 차원을
                           유튜브+텔레그램만으로 재산출. 전문가 없이도 종목
                           선별이 가능한지 검증용.
        """

        # 1) 차트 시그널 (PullbackService 재사용)
        pullback_svc = PullbackService(self.db)
        chart_signals = await pullback_svc.get_signals(min_score=0, limit=500)

        # 차트 시그널이 있는 종목 코드 수집
        chart_map: dict[str, dict] = {}
        for sig in chart_signals:
            code = sig.stock_code
            # 동일 종목 여러 시그널 중 최고점만 사용
            if code not in chart_map or sig.total_score > chart_map[code]["total_score"]:
                chart_map[code] = {
                    "total_score": sig.total_score,
                    "signal_type": sig.signal_type.value,
                    "stock_name": sig.stock_name,
                    "current_price": sig.current_price,
                    "themes": sig.themes,
                    "volume_ratio": sig.volume_ratio,
                    "ma20_distance_pct": sig.ma20_distance_pct,
                    "foreign_net_5d": sig.foreign_net_5d,
                    "institution_net_5d": sig.institution_net_5d,
                }

        if not chart_map:
            return []

        stock_codes = list(chart_map.keys())

        # 2) 소셜 데이터 (bulk)
        social_map = await self._get_bulk_social(stock_codes)

        # 3) 수급 데이터 (bulk)
        flow_map = await self._get_bulk_flow(stock_codes)

        # 4) 내러티브 데이터 (bulk)
        narrative_map = await self._get_bulk_narrative(stock_codes)

        # 5) 종목명 보강
        name_map = await self._get_stock_names(stock_codes)

        # 6) 4차원 점수 합산
        results: list[SmartScannerStock] = []
        for code in stock_codes:
            chart_data = chart_map[code]
            social_data = social_map.get(code, {})
            flow_data = flow_map.get(code, {})
            narr_data = narrative_map.get(code, {})

            stock_name = name_map.get(code) or chart_data.get("stock_name", "")

            # -- 차트 차원 (max 40) --
            chart_raw = chart_data["total_score"]  # 0-100
            chart_score = round(chart_raw * 0.4, 1)  # 0-40
            chart_dim = SmartSignalDimension(
                score=chart_score,
                max_score=40,
                grade=_grade(chart_score, 40),
                details={
                    "raw_score": chart_raw,
                    "signal_type": chart_data["signal_type"],
                },
            )

            # -- 내러티브 차원 (max 25) --
            news_7d = narr_data.get("news_count_7d", 0)
            disclosure_30d = narr_data.get("disclosure_count_30d", 0)
            sentiment_avg = narr_data.get("sentiment_avg", 0.0)
            theme_momentum = narr_data.get("theme_momentum", 0.0)

            # 뉴스 (0-10): 1건=2, 3건=6, 5건+=10
            news_score = min(10, news_7d * 2)
            # 공시 (0-5): 1건=2.5, 2건+=5
            disc_score = min(5, disclosure_30d * 2.5)
            # 감정분석 (0-5): avg_score -1~+1 → 0~5 (중립 2.5)
            sent_score = round(max(0, min(5, (sentiment_avg + 1) * 2.5)), 1) if narr_data.get("sentiment_count", 0) > 0 else 0
            # 테마 모멘텀 (0-5)
            theme_score = min(5, theme_momentum)

            narrative_score = round(news_score + disc_score + sent_score + theme_score, 1)
            narrative_dim = SmartSignalDimension(
                score=narrative_score,
                max_score=25,
                grade=_grade(narrative_score, 25),
                details={
                    "news": news_score,
                    "disclosure": disc_score,
                    "sentiment": sent_score,
                    "theme_momentum": theme_score,
                },
            )

            # -- 수급 차원 (max 20) --
            foreign_5d = flow_data.get("foreign_net_5d", chart_data.get("foreign_net_5d", 0))
            inst_5d = flow_data.get("institution_net_5d", chart_data.get("institution_net_5d", 0))
            consec_foreign = flow_data.get("consecutive_foreign_buy", 0)

            # 외국인+기관 순매수 방향/크기 (0-15)
            combined_net = foreign_5d + inst_5d
            if combined_net > 0:
                flow_direction_score = min(15, 5 + (combined_net / 100000) * 2)
            elif combined_net < 0:
                flow_direction_score = max(0, 3 - abs(combined_net) / 100000)
            else:
                flow_direction_score = 3
            flow_direction_score = round(min(15, flow_direction_score), 1)

            # 연속 매수일 (0-5)
            consec_score = min(5, consec_foreign * 1.0)

            flow_score = round(flow_direction_score + consec_score, 1)
            flow_dim = SmartSignalDimension(
                score=flow_score,
                max_score=20,
                grade=_grade(flow_score, 20),
                details={
                    "direction": flow_direction_score,
                    "consecutive": consec_score,
                    "foreign_net_5d": foreign_5d,
                    "institution_net_5d": inst_5d,
                },
            )

            # -- 소셜 차원 --
            # exclude_expert 모드: 전문가 점수 제외, max를 7로 축소 (yt4+tg3)
            expert_count = social_data.get("expert_count", 0)
            yt_count = social_data.get("youtube_count", 0)
            tg_count = social_data.get("telegram_count", 0)

            if exclude_expert:
                expert_score = 0.0
                social_max = 7.0  # 유튜브(4) + 텔레그램(3)
            else:
                # 전문가 언급 (0-8): 1건=2, 4건+=8
                expert_score = min(8, expert_count * 2)
                social_max = 15.0

            # 유튜브 (0-4): 1건=1.5, 3건+=4
            yt_score = min(4, yt_count * 1.5)
            # 텔레그램 (0-3): 1건=1, 3건+=3
            tg_score = min(3, tg_count * 1.0)

            social_score = round(expert_score + yt_score + tg_score, 1)
            social_dim = SmartSignalDimension(
                score=social_score,
                max_score=social_max,
                grade=_grade(social_score, social_max),
                details={
                    "expert": expert_score,
                    "youtube": yt_score,
                    "telegram": tg_score,
                    "exclude_expert": exclude_expert,
                },
            )

            # -- 복합 점수 --
            if exclude_expert:
                # 전문가 제외 시: 100점 만점으로 정규화 (비교 가능하도록)
                max_composite = 40 + 25 + 20 + social_max  # 92
                composite = round((chart_score + narrative_score + flow_score + social_score) / max_composite * 100, 1)
            else:
                # 기본: 단순 합산 (기존 동작 유지, max 100)
                composite = round(chart_score + narrative_score + flow_score + social_score, 1)

            # 정렬 차원 수 (50% 이상 득점 차원)
            aligned = sum(1 for dim in [chart_dim, narrative_dim, flow_dim, social_dim]
                         if dim.max_score > 0 and dim.score / dim.max_score >= 0.5)

            # 등락률 계산 (OHLCV에서 가져온 volume_ratio 등)
            price = chart_data.get("current_price", 0)

            result = SmartScannerStock(
                stock_code=code,
                stock_name=stock_name,
                themes=chart_data.get("themes", []),
                current_price=price,
                composite_score=composite,
                composite_grade=_composite_grade(composite),
                chart=chart_dim,
                narrative=narrative_dim,
                flow=flow_dim,
                social=social_dim,
                signal_type=chart_data["signal_type"],
                aligned_count=aligned,
                expert_mention_count=expert_count,
                youtube_count=yt_count,
                telegram_count=tg_count,
                news_count_7d=news_7d,
                disclosure_count_30d=disclosure_30d,
                foreign_net_5d=foreign_5d,
                institution_net_5d=inst_5d,
                consecutive_foreign_buy=consec_foreign,
                sentiment_avg=sentiment_avg,
                volume_ratio=chart_data.get("volume_ratio"),
                ma20_distance_pct=chart_data.get("ma20_distance_pct"),
            )
            results.append(result)

        # 정렬
        sort_key = {
            "composite": lambda s: s.composite_score,
            "chart": lambda s: s.chart.score,
            "narrative": lambda s: s.narrative.score,
            "flow": lambda s: s.flow.score,
            "social": lambda s: s.social.score,
            "aligned": lambda s: (s.aligned_count, s.composite_score),
        }.get(sort_by, lambda s: s.composite_score)

        results.sort(key=sort_key, reverse=True)

        # 필터
        if min_score > 0:
            results = [r for r in results if r.composite_score >= min_score]

        return results[:limit]

    async def get_stock_detail(self, stock_code: str) -> Optional[SmartScannerStock]:
        """단일 종목 4차원 상세 (scan_all 호출 없이 직접 분석)."""
        # 차트 시그널
        pullback_svc = PullbackService(self.db)
        chart_signals = await pullback_svc.get_by_stock_codes(
            [stock_code], min_score=0, limit=10
        )

        if not chart_signals:
            return None

        best_sig = max(chart_signals, key=lambda s: s.total_score)
        chart_data = {
            "total_score": best_sig.total_score,
            "signal_type": best_sig.signal_type.value,
            "stock_name": best_sig.stock_name,
            "current_price": best_sig.current_price,
            "themes": best_sig.themes,
            "volume_ratio": best_sig.volume_ratio,
            "ma20_distance_pct": best_sig.ma20_distance_pct,
            "foreign_net_5d": best_sig.foreign_net_5d,
            "institution_net_5d": best_sig.institution_net_5d,
        }

        codes = [stock_code]
        social_map = await self._get_bulk_social(codes)
        flow_map = await self._get_bulk_flow(codes)
        narrative_map = await self._get_bulk_narrative(codes)
        name_map = await self._get_stock_names(codes)

        # 점수 계산 (scan_all 내부와 동일 로직 재사용)
        social_data = social_map.get(stock_code, {})
        flow_data_item = flow_map.get(stock_code, {})
        narr_data = narrative_map.get(stock_code, {})
        stock_name = name_map.get(stock_code) or chart_data.get("stock_name", "")

        chart_raw = chart_data["total_score"]
        chart_score = round(chart_raw * 0.4, 1)
        chart_dim = SmartSignalDimension(
            score=chart_score, max_score=40, grade=_grade(chart_score, 40),
            details={"raw_score": chart_raw, "signal_type": chart_data["signal_type"]},
        )

        news_7d = narr_data.get("news_count_7d", 0)
        disclosure_30d = narr_data.get("disclosure_count_30d", 0)
        sentiment_avg = narr_data.get("sentiment_avg", 0.0)
        theme_momentum = narr_data.get("theme_momentum", 0.0)
        news_score = min(10, news_7d * 2)
        disc_score = min(5, disclosure_30d * 2.5)
        sent_score = round(max(0, min(5, (sentiment_avg + 1) * 2.5)), 1) if narr_data.get("sentiment_count", 0) > 0 else 0
        theme_score = min(5, theme_momentum)
        narrative_score = round(news_score + disc_score + sent_score + theme_score, 1)
        narrative_dim = SmartSignalDimension(
            score=narrative_score, max_score=25, grade=_grade(narrative_score, 25),
            details={"news": news_score, "disclosure": disc_score, "sentiment": sent_score, "theme_momentum": theme_score},
        )

        foreign_5d = flow_data_item.get("foreign_net_5d", chart_data.get("foreign_net_5d", 0))
        inst_5d = flow_data_item.get("institution_net_5d", chart_data.get("institution_net_5d", 0))
        consec_foreign = flow_data_item.get("consecutive_foreign_buy", 0)
        combined_net = foreign_5d + inst_5d
        if combined_net > 0:
            flow_direction_score = min(15, 5 + (combined_net / 100000) * 2)
        elif combined_net < 0:
            flow_direction_score = max(0, 3 - abs(combined_net) / 100000)
        else:
            flow_direction_score = 3
        flow_direction_score = round(min(15, flow_direction_score), 1)
        consec_score = min(5, consec_foreign * 1.0)
        flow_score = round(flow_direction_score + consec_score, 1)
        flow_dim = SmartSignalDimension(
            score=flow_score, max_score=20, grade=_grade(flow_score, 20),
            details={"direction": flow_direction_score, "consecutive": consec_score, "foreign_net_5d": foreign_5d, "institution_net_5d": inst_5d},
        )

        expert_count = social_data.get("expert_count", 0)
        yt_count = social_data.get("youtube_count", 0)
        tg_count = social_data.get("telegram_count", 0)
        expert_score_val = min(8, expert_count * 2)
        yt_score = min(4, yt_count * 1.5)
        tg_score = min(3, tg_count * 1.0)
        social_score = round(expert_score_val + yt_score + tg_score, 1)
        social_dim = SmartSignalDimension(
            score=social_score, max_score=15, grade=_grade(social_score, 15),
            details={"expert": expert_score_val, "youtube": yt_score, "telegram": tg_score, "exclude_expert": False},
        )

        composite = round(chart_score + narrative_score + flow_score + social_score, 1)
        aligned = sum(1 for dim in [chart_dim, narrative_dim, flow_dim, social_dim]
                      if dim.max_score > 0 and dim.score / dim.max_score >= 0.5)

        return SmartScannerStock(
            stock_code=stock_code, stock_name=stock_name,
            themes=chart_data.get("themes", []),
            current_price=chart_data.get("current_price", 0),
            composite_score=composite, composite_grade=_composite_grade(composite),
            chart=chart_dim, narrative=narrative_dim, flow=flow_dim, social=social_dim,
            signal_type=chart_data["signal_type"], aligned_count=aligned,
            expert_mention_count=expert_count, youtube_count=yt_count, telegram_count=tg_count,
            news_count_7d=news_7d, disclosure_count_30d=disclosure_30d,
            foreign_net_5d=foreign_5d, institution_net_5d=inst_5d,
            consecutive_foreign_buy=consec_foreign, sentiment_avg=sentiment_avg,
            volume_ratio=chart_data.get("volume_ratio"), ma20_distance_pct=chart_data.get("ma20_distance_pct"),
        )

    # ── Bulk 데이터 조회 ──

    async def _get_bulk_social(self, stock_codes: list[str]) -> dict[str, dict]:
        """소셜 데이터 bulk 조회 (YouTube, Expert, Telegram)."""
        since_date = today_kst() - timedelta(days=14)
        since_dt = now_kst().replace(tzinfo=None) - timedelta(days=14)

        # YouTube
        yt_stmt = (
            select(
                func.unnest(YouTubeMention.mentioned_tickers).label("code"),
                func.count(func.distinct(YouTubeMention.video_id)).label("cnt"),
            )
            .where(and_(
                YouTubeMention.published_at >= since_date,
                YouTubeMention.mentioned_tickers.overlap(stock_codes),
            ))
            .group_by("code")
        )
        yt_result = await self.db.execute(yt_stmt)
        yt_map = {r.code: r.cnt for r in yt_result}

        # Expert
        tr_map: dict[str, int] = {}
        if settings.expert_feature_enabled:
            tr_stmt = (
                select(
                    ExpertMention.stock_code,
                    func.count(ExpertMention.id).label("cnt"),
                )
                .where(and_(
                    ExpertMention.mention_date >= since_date,
                    ExpertMention.stock_code.in_(stock_codes),
                ))
                .group_by(ExpertMention.stock_code)
            )
            tr_result = await self.db.execute(tr_stmt)
            tr_map = {r.stock_code: int(r.cnt or 0) for r in tr_result}

        # Telegram
        tg_map: dict[str, int] = {}
        if settings.telegram_feature_enabled:
            tg_stmt = (
                select(
                    TelegramIdea.stock_code,
                    func.count(TelegramIdea.id).label("cnt"),
                )
                .where(and_(
                    TelegramIdea.original_date >= since_dt,
                    TelegramIdea.stock_code.in_(stock_codes),
                ))
                .group_by(TelegramIdea.stock_code)
            )
            tg_result = await self.db.execute(tg_stmt)
            tg_map = {r.stock_code: r.cnt for r in tg_result}

        result = {}
        for code in stock_codes:
            result[code] = {
                "youtube_count": yt_map.get(code, 0),
                "expert_count": tr_map.get(code, 0),
                "telegram_count": tg_map.get(code, 0),
            }
        return result

    async def _get_bulk_flow(self, stock_codes: list[str]) -> dict[str, dict]:
        """수급 데이터 bulk 조회."""
        since = today_kst() - timedelta(days=30)
        code_set = set(stock_codes)

        # 종목 수가 많으면 IN 절 없이 날짜만으로 조회
        if len(stock_codes) > 500:
            stmt = (
                select(StockInvestorFlow)
                .where(StockInvestorFlow.flow_date >= since)
                .order_by(StockInvestorFlow.stock_code, StockInvestorFlow.flow_date.desc())
            )
        else:
            stmt = (
                select(StockInvestorFlow)
                .where(and_(
                    StockInvestorFlow.stock_code.in_(stock_codes),
                    StockInvestorFlow.flow_date >= since,
                ))
                .order_by(StockInvestorFlow.stock_code, StockInvestorFlow.flow_date.desc())
            )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        grouped = defaultdict(list)
        for row in rows:
            if row.stock_code in code_set:
                grouped[row.stock_code].append(row)

        flow_map = {}
        for code, flows in grouped.items():
            recent_5 = flows[:5]
            foreign_sum = sum(f.foreign_net for f in recent_5)
            inst_sum = sum(f.institution_net for f in recent_5)

            # 연속 외국인 순매수일
            consec = 0
            for f in flows:
                if (f.foreign_net or 0) > 0:
                    consec += 1
                else:
                    break

            flow_map[code] = {
                "foreign_net_5d": foreign_sum,
                "institution_net_5d": inst_sum,
                "consecutive_foreign_buy": consec,
            }
        return flow_map

    async def _get_bulk_narrative(self, stock_codes: list[str]) -> dict[str, dict]:
        """내러티브 데이터 bulk 조회 (뉴스, 공시, 감정분석, 테마모멘텀)."""
        result = {}
        for code in stock_codes:
            result[code] = {
                "news_count_7d": 0,
                "disclosure_count_30d": 0,
                "sentiment_avg": 0.0,
                "sentiment_count": 0,
                "theme_momentum": 0.0,
            }

        # 뉴스: 종목 코드에 매핑된 테마를 통해 간접 조회
        themes_for_stocks = {}
        for code in stock_codes:
            themes = self._tms.get_themes_for_stock(code)
            if themes:
                themes_for_stocks[code] = themes

        if themes_for_stocks:
            all_themes = set()
            for ts in themes_for_stocks.values():
                all_themes.update(ts)

            since_7d = now_kst().replace(tzinfo=None) - timedelta(days=7)
            news_stmt = (
                select(
                    ThemeNews.theme_name,
                    func.count(ThemeNews.id).label("cnt"),
                )
                .where(and_(
                    ThemeNews.theme_name.in_(list(all_themes)),
                    ThemeNews.published_at >= since_7d,
                ))
                .group_by(ThemeNews.theme_name)
            )
            news_result = await self.db.execute(news_stmt)
            theme_news_count = {r.theme_name: r.cnt for r in news_result}

            for code, themes in themes_for_stocks.items():
                total_news = sum(theme_news_count.get(t, 0) for t in themes)
                result[code]["news_count_7d"] = total_news
                # 테마 모멘텀: 뉴스 많을수록 높음 (최대 5)
                result[code]["theme_momentum"] = min(5.0, total_news * 0.5)

        # 공시
        since_30d = today_kst() - timedelta(days=30)
        disc_stmt = (
            select(
                Disclosure.stock_code,
                func.count(Disclosure.id).label("cnt"),
            )
            .where(and_(
                Disclosure.stock_code.in_(stock_codes),
                Disclosure.rcept_dt >= since_30d.strftime("%Y%m%d"),
            ))
            .group_by(Disclosure.stock_code)
        )
        disc_result = await self.db.execute(disc_stmt)
        for r in disc_result:
            if r.stock_code in result:
                result[r.stock_code]["disclosure_count_30d"] = r.cnt

        # 감정분석
        since_14d = now_kst().replace(tzinfo=None) - timedelta(days=14)
        sent_stmt = (
            select(
                ReportSentimentAnalysis.stock_code,
                func.count(ReportSentimentAnalysis.id).label("cnt"),
                func.avg(ReportSentimentAnalysis.sentiment_score).label("avg_score"),
            )
            .join(TelegramReport)
            .where(and_(
                ReportSentimentAnalysis.stock_code.in_(stock_codes),
                TelegramReport.message_date >= since_14d,
            ))
            .group_by(ReportSentimentAnalysis.stock_code)
        )
        sent_result = await self.db.execute(sent_stmt)
        for r in sent_result:
            if r.stock_code in result:
                result[r.stock_code]["sentiment_avg"] = float(r.avg_score or 0)
                result[r.stock_code]["sentiment_count"] = r.cnt

        return result

    async def _get_stock_names(self, stock_codes: list[str]) -> dict[str, str]:
        """종목명 조회."""
        stmt = select(Stock.code, Stock.name).where(Stock.code.in_(stock_codes))
        res = await self.db.execute(stmt)
        return {r.code: r.name for r in res}
