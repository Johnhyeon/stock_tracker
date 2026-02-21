"""테마 셋업 종합 점수 서비스."""
import json
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, desc, delete
from sqlalchemy.dialects.postgresql import insert

from models import ThemeSetup, ThemeChartPattern, ThemeNewsStats, YouTubeMention, ExpertMention, StockOHLCV
from services.news_collector_service import NewsCollectorService
from services.chart_pattern_service import ChartPatternService
from services.price_service import get_price_service
from services.investor_flow_service import InvestorFlowService
from core.config import get_settings
from core.timezone import now_kst, today_kst

_settings = get_settings()

logger = logging.getLogger(__name__)

THEME_MAP_PATH = Path(__file__).parent.parent / "data" / "theme_map.json"


class ThemeSetupService:
    """테마 셋업 종합 점수 계산 서비스.

    뉴스 모멘텀, 차트 패턴, 기존 언급 데이터를 종합하여
    "자리를 만들고 있는" 테마를 감지합니다.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._theme_map: dict[str, list[dict]] = {}
        self._stock_to_themes: dict[str, list[str]] = {}
        self._load_theme_map()

    def _load_theme_map(self):
        """테마 맵 로드."""
        try:
            with open(THEME_MAP_PATH, "r", encoding="utf-8") as f:
                self._theme_map = json.load(f)

            # 종목코드 -> 테마 역매핑
            for theme_name, stocks in self._theme_map.items():
                for stock in stocks:
                    code = stock.get("code")
                    if code:
                        if code not in self._stock_to_themes:
                            self._stock_to_themes[code] = []
                        self._stock_to_themes[code].append(theme_name)

            logger.info(f"Loaded {len(self._theme_map)} themes for setup analysis")
        except Exception as e:
            logger.error(f"Failed to load theme map: {e}")

    async def _get_news_momentum_score(
        self,
        theme_name: str,
    ) -> dict:
        """뉴스 모멘텀 점수 계산 (25점 만점)."""
        news_service = NewsCollectorService(self.db)
        momentum = await news_service.get_news_momentum(theme_name)

        # 30점 만점 -> 25점 만점으로 스케일링
        scaled_score = momentum["score"] * (25 / 30)

        return {
            "score": round(scaled_score, 1),
            "7d_count": momentum["7d_count"],
            "wow_change": momentum["wow_change"],
            "source_diversity": momentum["source_diversity"],
        }

    async def _get_chart_pattern_score(
        self,
        theme_name: str,
    ) -> dict:
        """차트 패턴 점수 계산 (30점 만점)."""
        chart_service = ChartPatternService(self.db)
        pattern_data = await chart_service.get_pattern_score(theme_name)

        # 35점 만점 -> 30점 만점으로 스케일링
        scaled_score = pattern_data["score"] * (30 / 35)

        return {
            "score": round(scaled_score, 1),
            "pattern_ratio": pattern_data["pattern_ratio"],
            "avg_confidence": pattern_data["avg_confidence"],
            "patterns": pattern_data["patterns"],
            "pattern_count": pattern_data.get("pattern_count", 0),
            "total_stocks": pattern_data.get("total_stocks", 0),
        }

    async def _get_mention_score(
        self,
        theme_name: str,
    ) -> dict:
        """기존 언급 점수 계산 (20점 만점).

        YouTube와 전문가 언급 데이터 기반.
        """
        stocks = self._theme_map.get(theme_name, [])
        stock_codes = [s["code"] for s in stocks if s.get("code")]

        if not stock_codes:
            return {"score": 0, "youtube_count": 0, "expert_count": 0}

        # 최근 7일 기준
        start_date = today_kst() - timedelta(days=7)

        # YouTube 언급 수
        youtube_stmt = (
            select(func.count(func.distinct(YouTubeMention.video_id)))
            .where(
                and_(
                    YouTubeMention.mentioned_tickers.overlap(stock_codes),
                    YouTubeMention.published_at >= start_date,
                )
            )
        )
        youtube_result = await self.db.execute(youtube_stmt)
        youtube_count = youtube_result.scalar() or 0

        # 전문가 언급 수 (ExpertMention 행 수)
        expert_count = 0
        if _settings.expert_feature_enabled:
            expert_stmt = (
                select(func.count(ExpertMention.id))
                .where(
                    and_(
                        ExpertMention.stock_code.in_(stock_codes),
                        ExpertMention.mention_date >= start_date,
                    )
                )
            )
            expert_result = await self.db.execute(expert_stmt)
            expert_count = expert_result.scalar() or 0

        # 점수 계산 (20점 만점)
        # YouTube (0-12점): 5개 영상 이상이면 만점
        youtube_score = min(youtube_count / 5 * 12, 12)
        # 전문가 (0-8점): 10회 이상이면 만점
        expert_score = min(expert_count / 10 * 8, 8)

        total_score = youtube_score + expert_score

        return {
            "score": round(total_score, 1),
            "youtube_count": youtube_count,
            "expert_count": int(expert_count) if expert_count else 0,
        }

    def _is_market_closed_day(self) -> bool:
        """주말 또는 장 마감 후인지 확인."""
        now = now_kst()
        # 주말 체크 (토요일=5, 일요일=6)
        if now.weekday() >= 5:
            return True
        # 장 시작 전 (09:00 이전) 또는 장 마감 후 (15:30 이후)
        market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        if now < market_open or now > market_close:
            return True
        return False

    async def _get_price_from_db(
        self,
        stock_codes: list[str],
    ) -> dict[str, dict]:
        """DB에서 가장 최근 거래일의 가격 데이터 조회."""
        results = {}

        # 가장 최근 거래일 찾기 (stock_ohlcv 테이블)
        latest_date_stmt = (
            select(func.max(StockOHLCV.trade_date))
            .where(StockOHLCV.stock_code.in_(stock_codes))
        )
        latest_result = await self.db.execute(latest_date_stmt)
        latest_date = latest_result.scalar()

        if not latest_date:
            return results

        # 최근 2일 데이터 조회 (등락률 계산용)
        prev_date_stmt = (
            select(func.max(StockOHLCV.trade_date))
            .where(
                and_(
                    StockOHLCV.stock_code.in_(stock_codes),
                    StockOHLCV.trade_date < latest_date,
                )
            )
        )
        prev_result = await self.db.execute(prev_date_stmt)
        prev_date = prev_result.scalar()

        # 최근 거래일 데이터
        stmt = (
            select(StockOHLCV)
            .where(
                and_(
                    StockOHLCV.stock_code.in_(stock_codes),
                    StockOHLCV.trade_date == latest_date,
                )
            )
        )
        result = await self.db.execute(stmt)
        latest_records = {r.stock_code: r for r in result.scalars().all()}

        # 전일 데이터 (등락률 계산용)
        prev_records = {}
        if prev_date:
            prev_stmt = (
                select(StockOHLCV)
                .where(
                    and_(
                        StockOHLCV.stock_code.in_(stock_codes),
                        StockOHLCV.trade_date == prev_date,
                    )
                )
            )
            prev_result = await self.db.execute(prev_stmt)
            prev_records = {r.stock_code: r for r in prev_result.scalars().all()}

        # 등락률 계산
        for code, latest in latest_records.items():
            prev = prev_records.get(code)
            if prev and prev.close_price > 0:
                change = latest.close_price - prev.close_price
                change_rate = (change / prev.close_price) * 100
            else:
                change = 0
                change_rate = 0

            results[code] = {
                "stock_code": code,
                "current_price": latest.close_price,
                "change": change,
                "change_rate": change_rate,
                "volume": latest.volume,
                "high_price": latest.high_price,
                "low_price": latest.low_price,
                "open_price": latest.open_price,
                "prev_close": prev.close_price if prev else latest.close_price,
                "trade_date": latest_date.isoformat(),
            }

        return results

    async def _get_price_action_score(
        self,
        theme_name: str,
    ) -> dict:
        """가격 액션 점수 계산 (10점 만점).

        7일 평균 등락률 + 거래량 변화.
        주말/공휴일에는 DB의 최근 거래일 데이터 사용.
        """
        stocks = self._theme_map.get(theme_name, [])
        if not stocks:
            return {"score": 0, "avg_change": 0, "volume_change": 0}

        stock_codes = [s["code"] for s in stocks[:10] if s.get("code")]  # 상위 10개만
        prices = {}

        # 주말/장외 시간에는 DB 데이터 사용
        if self._is_market_closed_day():
            try:
                prices = await self._get_price_from_db(stock_codes)
            except Exception as e:
                logger.warning(f"DB 가격 조회 실패 ({theme_name}): {e}")
        else:
            # 평일 장중에는 KIS API 사용, 실패 시 DB fallback
            price_service = get_price_service()
            try:
                prices = await price_service.get_multiple_prices(stock_codes)
            except Exception as e:
                logger.warning(f"KIS API 가격 조회 실패 ({theme_name}): {e}, DB fallback")
                try:
                    prices = await self._get_price_from_db(stock_codes)
                except Exception as e2:
                    logger.warning(f"DB 가격 조회도 실패 ({theme_name}): {e2}")
                    return {"score": 0, "avg_change": 0, "volume_change": 0}

        if not prices:
            return {"score": 0, "avg_change": 0, "volume_change": 0}

        # 평균 등락률 계산
        changes = []
        for code, data in prices.items():
            change_rate = data.get("change_rate")
            if change_rate is not None:
                changes.append(float(change_rate))

        avg_change = sum(changes) / len(changes) if changes else 0

        # 점수 계산 (10점 만점)
        # 등락률: -5% ~ +5% 범위에서 선형 매핑
        price_score = max(0, min(10, (avg_change + 5) / 10 * 10))

        return {
            "score": round(price_score, 1),
            "avg_change": round(avg_change, 2),
            "volume_change": 0,  # 추후 구현
        }

    async def _get_investor_flow_score(
        self,
        theme_name: str,
    ) -> dict:
        """투자자 수급 점수 계산 (15점 만점).

        외국인/기관 순매수 데이터 기반.
        """
        stocks = self._theme_map.get(theme_name, [])
        stock_codes = [s["code"] for s in stocks if s.get("code")]

        if not stock_codes:
            return {
                "score": 0,
                "foreign_net_sum": 0,
                "institution_net_sum": 0,
                "positive_foreign": 0,
                "positive_institution": 0,
                "total_stocks": 0,
                "avg_flow_score": 0,
            }

        flow_service = InvestorFlowService(self.db)
        flow_data = await flow_service.calculate_theme_flow_score(stock_codes, days=5)

        return flow_data

    async def calculate_setup_score(
        self,
        theme_name: str,
    ) -> dict:
        """테마의 종합 셋업 점수 계산.

        Returns:
            {
                "theme_name": str,
                "total_score": float,
                "news_momentum_score": float,
                "chart_pattern_score": float,
                "mention_score": float,
                "price_action_score": float,
                "investor_flow_score": float,
                "score_breakdown": dict,
            }
        """
        # 각 점수 계산
        news_data = await self._get_news_momentum_score(theme_name)
        chart_data = await self._get_chart_pattern_score(theme_name)
        mention_data = await self._get_mention_score(theme_name)
        price_data = await self._get_price_action_score(theme_name)
        flow_data = await self._get_investor_flow_score(theme_name)

        # 종합 점수 (100점 만점)
        total_score = (
            news_data["score"] +      # 25점
            chart_data["score"] +     # 30점
            mention_data["score"] +   # 20점
            price_data["score"] +     # 10점
            flow_data["score"]        # 15점
        )

        return {
            "theme_name": theme_name,
            "total_score": round(total_score, 1),
            "news_momentum_score": news_data["score"],
            "chart_pattern_score": chart_data["score"],
            "mention_score": mention_data["score"],
            "price_action_score": price_data["score"],
            "investor_flow_score": flow_data["score"],
            "score_breakdown": {
                "news": news_data,
                "chart": chart_data,
                "mention": mention_data,
                "price": price_data,
                "flow": flow_data,
            },
        }

    async def calculate_all_setups(self) -> dict:
        """모든 테마의 셋업 점수 계산 및 저장.

        Returns:
            {"calculated_count": N, "emerging_count": M, "timestamp": str}
        """
        setup_date = today_kst()
        results = []

        for theme_name in self._theme_map.keys():
            try:
                score_data = await self.calculate_setup_score(theme_name)
                results.append(score_data)
            except Exception as e:
                logger.warning(f"셋업 점수 계산 실패 ({theme_name}): {e}")
                continue

        # 점수순 정렬 및 순위 부여
        results.sort(key=lambda x: x["total_score"], reverse=True)

        for rank, data in enumerate(results, 1):
            data["rank"] = rank

        # 상위 패턴 종목 조회 및 저장
        for data in results:
            theme_name = data["theme_name"]

            # 상위 패턴 종목
            top_stocks = await self._get_top_pattern_stocks(theme_name)

            # 이머징 여부 (상위 20% 또는 점수 50 이상)
            is_emerging = 1 if (data["rank"] <= len(results) * 0.2 or data["total_score"] >= 50) else 0

            stmt = insert(ThemeSetup).values(
                theme_name=theme_name,
                setup_date=setup_date,
                rank=data["rank"],
                news_momentum_score=data["news_momentum_score"],
                chart_pattern_score=data["chart_pattern_score"],
                mention_score=data["mention_score"],
                price_action_score=data["price_action_score"],
                investor_flow_score=data["investor_flow_score"],
                total_setup_score=data["total_score"],
                score_breakdown=data["score_breakdown"],
                top_stocks=top_stocks,
                total_stocks_in_theme=len(self._theme_map.get(theme_name, [])),
                stocks_with_pattern=data["score_breakdown"]["chart"].get("pattern_count", 0),
                is_emerging=is_emerging,
            ).on_conflict_do_update(
                index_elements=['theme_name', 'setup_date'],
                set_={
                    'rank': data["rank"],
                    'news_momentum_score': data["news_momentum_score"],
                    'chart_pattern_score': data["chart_pattern_score"],
                    'mention_score': data["mention_score"],
                    'price_action_score': data["price_action_score"],
                    'investor_flow_score': data["investor_flow_score"],
                    'total_setup_score': data["total_score"],
                    'score_breakdown': data["score_breakdown"],
                    'top_stocks': top_stocks,
                    'total_stocks_in_theme': len(self._theme_map.get(theme_name, [])),
                    'stocks_with_pattern': data["score_breakdown"]["chart"].get("pattern_count", 0),
                    'is_emerging': is_emerging,
                    'updated_at': now_kst().replace(tzinfo=None),
                }
            )

            await self.db.execute(stmt)

        await self.db.commit()

        emerging_count = sum(1 for d in results if d["rank"] <= len(results) * 0.2 or d["total_score"] >= 50)

        logger.info(f"셋업 점수 계산 완료: {len(results)}개 테마, {emerging_count}개 이머징")

        return {
            "calculated_count": len(results),
            "emerging_count": emerging_count,
            "timestamp": now_kst().isoformat(),
        }

    async def _get_top_pattern_stocks(
        self,
        theme_name: str,
        limit: int = 5,
    ) -> list[dict]:
        """테마의 상위 패턴 종목 조회."""
        stmt = (
            select(ThemeChartPattern)
            .where(
                and_(
                    ThemeChartPattern.theme_name == theme_name,
                    ThemeChartPattern.analysis_date == today_kst(),
                    ThemeChartPattern.is_active == True,
                )
            )
            .order_by(ThemeChartPattern.confidence.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        patterns = result.scalars().all()

        return [
            {
                "code": p.stock_code,
                "name": p.stock_name,
                "pattern": p.pattern_type,
                "confidence": p.confidence,
            }
            for p in patterns
        ]

    def _generate_score_explanation(
        self,
        setup: "ThemeSetup",
    ) -> str:
        """점수가 왜 이렇게 나왔는지 한글 설명 생성."""
        breakdown = setup.score_breakdown or {}
        explanations = []

        # 1. 뉴스 모멘텀 설명
        news = breakdown.get("news", {})
        news_score = setup.news_momentum_score
        if news_score >= 20:
            explanations.append(f"뉴스 활발 (7일 {news.get('7d_count', 0)}건, 주간 +{news.get('wow_change', 0):.0f}%)")
        elif news_score >= 10:
            explanations.append(f"뉴스 보통 (7일 {news.get('7d_count', 0)}건)")
        elif news.get('7d_count', 0) == 0:
            explanations.append("뉴스 없음")

        # 2. 차트 패턴 설명
        chart = breakdown.get("chart", {})
        chart_score = setup.chart_pattern_score
        pattern_count = chart.get("pattern_count", 0)
        total_stocks = chart.get("total_stocks", 0)
        avg_confidence = chart.get("avg_confidence", 0)
        patterns = chart.get("patterns", [])

        if chart_score >= 20:
            pattern_str = ", ".join(self._pattern_to_korean(p) for p in patterns[:2])
            explanations.append(f"패턴 강함 ({pattern_count}/{total_stocks}개 종목, {pattern_str})")
        elif chart_score >= 10:
            explanations.append(f"패턴 감지 ({pattern_count}개 종목, 신뢰도 {avg_confidence:.0f}%)")
        elif pattern_count == 0:
            explanations.append("패턴 미감지")

        # 3. 언급 설명
        mention = breakdown.get("mention", {})
        mention_score = setup.mention_score
        youtube_count = mention.get("youtube_count", 0)
        expert_count = mention.get("expert_count", 0)

        if mention_score >= 15:
            explanations.append(f"언급 많음 (유튜브 {youtube_count}건, 전문가 {expert_count}건)")
        elif mention_score >= 5:
            if youtube_count > 0 and expert_count > 0:
                explanations.append(f"언급 있음 (유튜브 {youtube_count}, 전문가 {expert_count})")
            elif youtube_count > 0:
                explanations.append(f"유튜브 언급 {youtube_count}건")
            elif expert_count > 0:
                explanations.append(f"전문가 언급 {expert_count}건")

        # 4. 수급 설명
        flow = breakdown.get("flow", {})
        flow_score = setup.investor_flow_score
        foreign_net = flow.get("foreign_net_sum", 0)
        inst_net = flow.get("institution_net_sum", 0)
        positive_foreign = flow.get("positive_foreign", 0)
        positive_inst = flow.get("positive_institution", 0)
        flow_total = flow.get("total_stocks", 0)

        if flow_score >= 10:
            parts = []
            if foreign_net > 0:
                parts.append(f"외인 순매수 {positive_foreign}/{flow_total}")
            if inst_net > 0:
                parts.append(f"기관 순매수 {positive_inst}/{flow_total}")
            if parts:
                explanations.append("수급 양호 (" + ", ".join(parts) + ")")
        elif flow_score >= 5:
            explanations.append("수급 보통")
        elif flow_score < 3 and flow_total > 0:
            explanations.append("수급 약함")

        # 5. 가격 설명
        price = breakdown.get("price", {})
        price_score = setup.price_action_score
        avg_change = price.get("avg_change", 0)

        if price_score >= 7:
            explanations.append(f"주가 상승세 (+{avg_change:.1f}%)")
        elif price_score <= 3 and avg_change < 0:
            explanations.append(f"주가 하락세 ({avg_change:.1f}%)")

        # 최종 설명 조합
        if not explanations:
            return "데이터 부족"

        return " / ".join(explanations)

    def _pattern_to_korean(self, pattern: str) -> str:
        """패턴 타입을 한글로 변환."""
        mapping = {
            "range_bound": "박스권",
            "double_bottom": "쌍바닥",
            "triple_bottom": "삼중바닥",
            "converging": "수렴",
            "pre_breakout": "돌파직전",
        }
        return mapping.get(pattern, pattern)

    async def get_emerging_themes(
        self,
        limit: int = 20,
        min_score: float = 30.0,
    ) -> list[dict]:
        """자리 잡는 테마 목록 조회.

        Args:
            limit: 최대 조회 개수
            min_score: 최소 점수

        Returns:
            테마 셋업 리스트
        """
        stmt = (
            select(ThemeSetup)
            .where(
                and_(
                    ThemeSetup.setup_date == today_kst(),
                    ThemeSetup.total_setup_score >= min_score,
                )
            )
            .order_by(ThemeSetup.total_setup_score.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        setups = result.scalars().all()

        return [
            {
                "theme_name": s.theme_name,
                "rank": s.rank,
                "total_score": s.total_setup_score,
                "news_momentum_score": s.news_momentum_score,
                "chart_pattern_score": s.chart_pattern_score,
                "mention_score": s.mention_score,
                "price_action_score": s.price_action_score,
                "investor_flow_score": s.investor_flow_score,
                "top_stocks": s.top_stocks,
                "stocks_with_pattern": s.stocks_with_pattern,
                "total_stocks": s.total_stocks_in_theme,
                "is_emerging": s.is_emerging,
                "score_breakdown": s.score_breakdown,
                "explanation": self._generate_score_explanation(s),
            }
            for s in setups
        ]

    async def get_theme_setup_detail(
        self,
        theme_name: str,
    ) -> Optional[dict]:
        """테마 셋업 상세 정보."""
        stmt = (
            select(ThemeSetup)
            .where(
                and_(
                    ThemeSetup.theme_name == theme_name,
                    ThemeSetup.setup_date == today_kst(),
                )
            )
        )

        result = await self.db.execute(stmt)
        setup = result.scalar_one_or_none()

        if not setup:
            return None

        # 히스토리 데이터 (최근 14일)
        history_stmt = (
            select(ThemeSetup)
            .where(
                and_(
                    ThemeSetup.theme_name == theme_name,
                    ThemeSetup.setup_date >= today_kst() - timedelta(days=14),
                )
            )
            .order_by(ThemeSetup.setup_date)
        )

        history_result = await self.db.execute(history_stmt)
        history = history_result.scalars().all()

        return {
            "theme_name": setup.theme_name,
            "rank": setup.rank,
            "total_score": setup.total_setup_score,
            "news_momentum_score": setup.news_momentum_score,
            "chart_pattern_score": setup.chart_pattern_score,
            "mention_score": setup.mention_score,
            "price_action_score": setup.price_action_score,
            "investor_flow_score": setup.investor_flow_score,
            "score_breakdown": setup.score_breakdown,
            "top_stocks": setup.top_stocks,
            "stocks_with_pattern": setup.stocks_with_pattern,
            "total_stocks": setup.total_stocks_in_theme,
            "is_emerging": setup.is_emerging,
            "setup_date": setup.setup_date.isoformat(),
            "history": [
                {
                    "date": h.setup_date.isoformat(),
                    "score": h.total_setup_score,
                    "rank": h.rank,
                }
                for h in history
            ],
        }

    async def get_setup_history(
        self,
        theme_name: str,
        days: int = 30,
    ) -> list[dict]:
        """테마 셋업 히스토리 조회."""
        start_date = today_kst() - timedelta(days=days)

        stmt = (
            select(ThemeSetup)
            .where(
                and_(
                    ThemeSetup.theme_name == theme_name,
                    ThemeSetup.setup_date >= start_date,
                )
            )
            .order_by(ThemeSetup.setup_date)
        )

        result = await self.db.execute(stmt)
        setups = result.scalars().all()

        return [
            {
                "date": s.setup_date.isoformat(),
                "total_score": s.total_setup_score,
                "news_score": s.news_momentum_score,
                "chart_score": s.chart_pattern_score,
                "mention_score": s.mention_score,
                "price_score": s.price_action_score,
                "flow_score": s.investor_flow_score,
                "rank": s.rank,
            }
            for s in setups
        ]

    async def get_rank_trend(
        self,
        days: int = 14,
        top_n: int = 10,
    ) -> dict:
        """상위 테마들의 순위 추이 조회.

        Args:
            days: 조회 기간 (일)
            top_n: 조회할 테마 수 (최근 기준 상위 N개)

        Returns:
            {
                "dates": ["2026-01-22", "2026-01-23", ...],
                "themes": [
                    {
                        "name": "테마명",
                        "data": [
                            {"date": "2026-01-22", "rank": 1, "score": 75.5},
                            ...
                        ]
                    },
                    ...
                ]
            }
        """
        start_date = today_kst() - timedelta(days=days)

        # 1. 가장 최근 날짜의 상위 N개 테마 조회
        latest_date_stmt = select(func.max(ThemeSetup.setup_date))
        latest_date_result = await self.db.execute(latest_date_stmt)
        latest_date = latest_date_result.scalar()

        if not latest_date:
            return {"dates": [], "themes": []}

        top_themes_stmt = (
            select(ThemeSetup.theme_name)
            .where(ThemeSetup.setup_date == latest_date)
            .order_by(ThemeSetup.rank)
            .limit(top_n)
        )
        top_themes_result = await self.db.execute(top_themes_stmt)
        top_theme_names = [row[0] for row in top_themes_result]

        if not top_theme_names:
            return {"dates": [], "themes": []}

        # 2. 해당 테마들의 전체 기간 데이터 조회
        stmt = (
            select(ThemeSetup)
            .where(
                and_(
                    ThemeSetup.theme_name.in_(top_theme_names),
                    ThemeSetup.setup_date >= start_date,
                )
            )
            .order_by(ThemeSetup.setup_date, ThemeSetup.rank)
        )
        result = await self.db.execute(stmt)
        setups = result.scalars().all()

        # 3. 날짜 목록 생성
        dates_set = set()
        for s in setups:
            dates_set.add(s.setup_date)
        dates = sorted(dates_set)

        # 4. 테마별 데이터 정리
        theme_data = {name: {} for name in top_theme_names}
        for s in setups:
            theme_data[s.theme_name][s.setup_date] = {
                "date": s.setup_date.isoformat(),
                "rank": s.rank,
                "score": round(s.total_setup_score, 1),
            }

        # 5. 결과 포맷팅
        themes = []
        for name in top_theme_names:
            data = []
            for d in dates:
                if d in theme_data[name]:
                    data.append(theme_data[name][d])
                else:
                    data.append({"date": d.isoformat(), "rank": None, "score": None})
            themes.append({
                "name": name,
                "data": data,
            })

        return {
            "dates": [d.isoformat() for d in dates],
            "themes": themes,
        }
