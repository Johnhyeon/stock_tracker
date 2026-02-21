"""YouTube 서비스."""
import logging
import asyncio
import statistics
from datetime import datetime, timedelta, date
from typing import Optional, Union
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, func, asc, select

from core.timezone import now_kst, today_kst
from models import YouTubeMention, TickerMentionStats, Stock, InvestmentIdea, IdeaStatus
from models.stock_ohlcv import StockOHLCV
from integrations.youtube import get_youtube_client, StockMentionAnalyzer
logger = logging.getLogger(__name__)


class YouTubeService:
    """YouTube 서비스.

    YouTube 영상 수집 및 종목 언급 분석을 담당합니다.
    """

    def __init__(self, db: Union[Session, AsyncSession]):
        self.db = db
        self.youtube_client = get_youtube_client()
        self.analyzer = StockMentionAnalyzer()

    async def _get_idea_tickers(self) -> list[str]:
        """활성/관찰 중인 아이디어의 종목명 목록 조회 (비동기)."""
        stmt = select(InvestmentIdea).where(
            InvestmentIdea.status.in_([IdeaStatus.ACTIVE, IdeaStatus.WATCHING])
        )
        result = await self.db.execute(stmt)
        ideas = result.scalars().all()

        tickers = set()
        for idea in ideas:
            if idea.tickers:
                for ticker in idea.tickers:
                    tickers.add(ticker)
        return list(tickers)

    async def collect_videos(
        self,
        hours_back: int = 24,
    ) -> dict:
        """아이디어 종목명으로 YouTube 영상 검색 및 수집.

        Args:
            hours_back: 몇 시간 전부터 수집할지

        Returns:
            {"collected": N, "new": M, "with_mentions": K, "tickers_searched": [...]}
        """
        result = {"collected": 0, "new": 0, "with_mentions": 0, "tickers_searched": []}

        try:
            published_after = now_kst().replace(tzinfo=None) - timedelta(hours=hours_back)

            # 아이디어에서 종목명 가져오기 (비동기)
            tickers = await self._get_idea_tickers()
            result["tickers_searched"] = tickers

            if not tickers:
                logger.warning("No tickers found in active/watching ideas")
                return result

            # 종목명으로 YouTube 검색
            videos = await self.youtube_client.search_by_tickers(
                tickers=tickers,
                max_results_per_ticker=5,
                published_after=published_after,
            )
            result["collected"] = len(videos)

            # 비동기로 종목 캐시 로딩 후 분석
            await self.analyzer.load_stock_cache_async(self.db)
            analyzed_videos = self.analyzer.analyze_videos(videos)
            result["with_mentions"] = len(analyzed_videos)

            # DB에 저장 (비동기)
            for video in analyzed_videos:
                video_id = video.get("video_id")
                if not video_id:
                    continue

                # 중복 체크 (비동기)
                stmt = select(YouTubeMention).where(YouTubeMention.video_id == video_id)
                existing = (await self.db.execute(stmt)).scalars().first()

                if existing:
                    # 통계 업데이트
                    existing.view_count = video.get("view_count", existing.view_count)
                    existing.like_count = video.get("like_count", existing.like_count)
                    existing.comment_count = video.get("comment_count", existing.comment_count)
                    continue

                # 새 영상 저장
                published_at_str = video.get("published_at", "")
                try:
                    published_at = datetime.fromisoformat(
                        published_at_str.replace("Z", "+00:00")
                    )
                except:
                    published_at = now_kst().replace(tzinfo=None)

                mention = YouTubeMention(
                    video_id=video_id,
                    video_title=video.get("title", "")[:500],
                    channel_id=video.get("channel_id", ""),
                    channel_name=video.get("channel_title"),
                    published_at=published_at,
                    view_count=video.get("view_count"),
                    like_count=video.get("like_count"),
                    comment_count=video.get("comment_count"),
                    duration=video.get("duration"),
                    mentioned_tickers=video.get("mentioned_tickers", []),
                    ticker_context=video.get("ticker_context"),
                    thumbnail_url=video.get("thumbnail_url"),
                )
                self.db.add(mention)
                result["new"] += 1

                # 종목별 통계 업데이트 (비동기)
                await self._update_ticker_stats(
                    video.get("mentioned_tickers", []),
                    video.get("view_count", 0),
                )

            await self.db.commit()
            logger.info(
                f"YouTube collection completed: {result['new']} new, "
                f"{result['with_mentions']} with mentions"
            )

        except Exception as e:
            logger.error(f"YouTube collection failed: {e}")
            await self.db.rollback()
            raise

        return result

    async def _update_ticker_stats(
        self,
        tickers: list[str],
        view_count: int,
    ) -> None:
        """종목별 통계 업데이트 (비동기)."""
        today = today_kst()

        for ticker in tickers:
            # 기존 통계 조회 또는 생성 (비동기)
            stmt = select(TickerMentionStats).where(
                TickerMentionStats.stock_code == ticker,
                TickerMentionStats.stat_date == today,
            )
            stats = (await self.db.execute(stmt)).scalars().first()

            if not stats:
                # 종목명 조회 (비동기)
                stock_stmt = select(Stock).where(Stock.code == ticker)
                stock = (await self.db.execute(stock_stmt)).scalars().first()
                stats = TickerMentionStats(
                    stock_code=ticker,
                    stock_name=stock.name if stock else None,
                    stat_date=today,
                    youtube_mention_count=0,
                    youtube_total_views=0,
                )
                self.db.add(stats)
                await self.db.flush()  # 중복 방지를 위해 즉시 DB에 반영

            # None 처리
            if stats.youtube_mention_count is None:
                stats.youtube_mention_count = 0
            if stats.youtube_total_views is None:
                stats.youtube_total_views = 0

            stats.youtube_mention_count += 1
            stats.youtube_total_views += (view_count or 0)

    def get_mentions(
        self,
        stock_code: Optional[str] = None,
        channel_id: Optional[str] = None,
        days_back: int = 7,
        skip: int = 0,
        limit: int = 50,
    ) -> list[YouTubeMention]:
        """YouTube 언급 목록 조회.

        Args:
            stock_code: 종목코드 필터
            channel_id: 채널 ID 필터
            days_back: 며칠 전까지
            skip: 건너뛸 개수
            limit: 조회 개수

        Returns:
            YouTubeMention 목록
        """
        query = self.db.query(YouTubeMention)

        if stock_code:
            query = query.filter(
                YouTubeMention.mentioned_tickers.contains([stock_code])
            )
        if channel_id:
            query = query.filter(YouTubeMention.channel_id == channel_id)

        cutoff = now_kst().replace(tzinfo=None) - timedelta(days=days_back)
        query = query.filter(YouTubeMention.published_at >= cutoff)

        return (
            query
            .order_by(desc(YouTubeMention.published_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_mention(self, mention_id: UUID) -> Optional[YouTubeMention]:
        """YouTube 언급 상세 조회."""
        return self.db.query(YouTubeMention).filter(
            YouTubeMention.id == mention_id
        ).first()

    def get_trending_tickers(
        self,
        days_back: int = 7,
        limit: int = 20,
    ) -> list[dict]:
        """트렌딩 종목 조회 (언급 횟수 기준).

        Args:
            days_back: 며칠간의 데이터
            limit: 상위 몇 개

        Returns:
            [
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "mention_count": 15,
                    "total_views": 1234567,
                },
                ...
            ]
        """
        cutoff = today_kst() - timedelta(days=days_back)

        results = (
            self.db.query(
                TickerMentionStats.stock_code,
                TickerMentionStats.stock_name,
                func.sum(TickerMentionStats.youtube_mention_count).label("mention_count"),
                func.sum(TickerMentionStats.youtube_total_views).label("total_views"),
            )
            .filter(TickerMentionStats.stat_date >= cutoff)
            .group_by(TickerMentionStats.stock_code, TickerMentionStats.stock_name)
            .order_by(desc("mention_count"))
            .limit(limit)
            .all()
        )

        return [
            {
                "stock_code": r.stock_code,
                "stock_name": r.stock_name,
                "mention_count": r.mention_count,
                "total_views": r.total_views,
            }
            for r in results
        ]

    def get_ticker_mention_history(
        self,
        stock_code: str,
        days_back: int = 30,
    ) -> list[dict]:
        """종목별 일간 언급 추이.

        Args:
            stock_code: 종목코드
            days_back: 며칠간의 데이터

        Returns:
            [{"date": "2024-01-15", "mention_count": 5, "total_views": 12345}, ...]
        """
        cutoff = today_kst() - timedelta(days=days_back)

        results = (
            self.db.query(TickerMentionStats)
            .filter(
                TickerMentionStats.stock_code == stock_code,
                TickerMentionStats.stat_date >= cutoff,
            )
            .order_by(TickerMentionStats.stat_date)
            .all()
        )

        return [
            {
                "date": r.stat_date.isoformat(),
                "mention_count": r.youtube_mention_count,
                "total_views": r.youtube_total_views,
            }
            for r in results
        ]

    async def collect_hot_videos(
        self,
        hours_back: int = 24,
        mode: str = "normal",  # "quick", "normal", "full"
    ) -> dict:
        """주식 관련 인기 영상 수집 (핫 종목 발굴용).

        Args:
            hours_back: 몇 시간 전부터 수집할지
            mode: 수집 모드
                - "quick": 빠른 수집 (카테고리당 5개 키워드, 채널 포함)
                - "normal": 일반 수집 (전체 키워드, 채널 포함)
                - "full": 전체 수집 (전체 키워드, 채널 포함, 더 많은 결과)

        Returns:
            {"collected": N, "new": M, "with_mentions": K, "tickers_found": [...], "mode": str}
        """
        result = {"collected": 0, "new": 0, "with_mentions": 0, "tickers_found": [], "mode": mode}

        try:
            published_after = now_kst().replace(tzinfo=None) - timedelta(hours=hours_back)

            # 모드별 설정
            if mode == "quick":
                videos = await self.youtube_client.quick_collect(
                    published_after=published_after,
                )
            elif mode == "full":
                videos = await self.youtube_client.full_collect(
                    published_after=published_after,
                )
            else:  # normal
                videos = await self.youtube_client.search_stock_videos(
                    max_results_per_keyword=5,
                    published_after=published_after,
                    include_channels=True,
                    sample_keywords=10,  # 카테고리당 10개
                )
            result["collected"] = len(videos)

            # 비동기로 종목 캐시 로딩 후 분석
            await self.analyzer.load_stock_cache_async(self.db)
            analyzed_videos = self.analyzer.analyze_videos(videos)
            result["with_mentions"] = len(analyzed_videos)

            # 발견된 종목 집계
            tickers_found = set()

            # DB에 저장 (비동기)
            for video in analyzed_videos:
                video_id = video.get("video_id")
                if not video_id:
                    continue

                mentioned_tickers = video.get("mentioned_tickers", [])
                tickers_found.update(mentioned_tickers)

                # 중복 체크 (비동기)
                stmt = select(YouTubeMention).where(YouTubeMention.video_id == video_id)
                existing = (await self.db.execute(stmt)).scalars().first()

                if existing:
                    existing.view_count = video.get("view_count", existing.view_count)
                    existing.like_count = video.get("like_count", existing.like_count)
                    existing.comment_count = video.get("comment_count", existing.comment_count)
                    continue

                # 새 영상 저장
                published_at_str = video.get("published_at", "")
                try:
                    published_at = datetime.fromisoformat(
                        published_at_str.replace("Z", "+00:00")
                    )
                except:
                    published_at = now_kst().replace(tzinfo=None)

                mention = YouTubeMention(
                    video_id=video_id,
                    video_title=video.get("title", "")[:500],
                    channel_id=video.get("channel_id", ""),
                    channel_name=video.get("channel_title"),
                    published_at=published_at,
                    view_count=video.get("view_count"),
                    like_count=video.get("like_count"),
                    comment_count=video.get("comment_count"),
                    duration=video.get("duration"),
                    mentioned_tickers=mentioned_tickers,
                    ticker_context=video.get("ticker_context"),
                    thumbnail_url=video.get("thumbnail_url"),
                )
                self.db.add(mention)
                result["new"] += 1

                # 종목별 통계 업데이트 (비동기)
                await self._update_ticker_stats(
                    mentioned_tickers,
                    video.get("view_count", 0),
                )

            await self.db.commit()
            result["tickers_found"] = list(tickers_found)
            logger.info(
                f"Hot video collection completed: {result['new']} new, "
                f"{len(tickers_found)} tickers found"
            )

        except Exception as e:
            logger.error(f"Hot video collection failed: {e}")
            await self.db.rollback()
            raise

        return result

    def get_rising_tickers(
        self,
        days_back: int = 7,
        limit: int = 20,
        include_price: bool = True,
    ) -> list[dict]:
        """급상승 종목 조회 (언급 증가율 + 주가/거래량 가중치).

        Args:
            days_back: 분석 기간
            limit: 상위 몇 개
            include_price: KIS API로 주가/거래량 정보 포함 여부

        Returns:
            [
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "recent_mentions": 15,
                    "prev_mentions": 5,
                    "growth_rate": 200.0,
                    "total_views": 1234567,
                    "current_price": 72000,
                    "price_change_rate": 2.5,
                    "volume": 12345678,
                    "volume_ratio": 1.5,
                    "weighted_score": 85.5,
                },
                ...
            ]
        """
        today = today_kst()
        half_period = days_back // 2

        # 최근 기간 (예: 최근 3일)
        recent_start = today - timedelta(days=half_period)
        # 이전 기간 (예: 4~7일 전)
        prev_start = today - timedelta(days=days_back)
        prev_end = recent_start - timedelta(days=1)

        # 최근 기간 통계
        recent_stats = dict(
            self.db.query(
                TickerMentionStats.stock_code,
                func.sum(TickerMentionStats.youtube_mention_count).label("mentions"),
            )
            .filter(TickerMentionStats.stat_date >= recent_start)
            .group_by(TickerMentionStats.stock_code)
            .all()
        )

        # 이전 기간 통계
        prev_stats = dict(
            self.db.query(
                TickerMentionStats.stock_code,
                func.sum(TickerMentionStats.youtube_mention_count).label("mentions"),
            )
            .filter(
                TickerMentionStats.stat_date >= prev_start,
                TickerMentionStats.stat_date <= prev_end,
            )
            .group_by(TickerMentionStats.stock_code)
            .all()
        )

        # 증가율 계산
        rising_tickers = []
        all_codes = set(recent_stats.keys()) | set(prev_stats.keys())

        for code in all_codes:
            recent = recent_stats.get(code, 0)
            prev = prev_stats.get(code, 0)

            # 최근에 언급이 있어야 함
            if recent == 0:
                continue

            # 증가율 계산 (이전이 0이면 신규 등장으로 취급)
            if prev == 0:
                growth_rate = 100.0 if recent > 0 else 0.0
                is_new = True
            else:
                growth_rate = ((recent - prev) / prev) * 100
                is_new = False

            # 종목명 조회
            stock = self.db.query(Stock).filter(Stock.code == code).first()

            # 총 조회수
            total_views = (
                self.db.query(func.sum(TickerMentionStats.youtube_total_views))
                .filter(
                    TickerMentionStats.stock_code == code,
                    TickerMentionStats.stat_date >= prev_start,
                )
                .scalar() or 0
            )

            rising_tickers.append({
                "stock_code": code,
                "stock_name": stock.name if stock else None,
                "recent_mentions": recent,
                "prev_mentions": prev,
                "growth_rate": round(growth_rate, 1),
                "total_views": total_views,
                "is_new": is_new,
                # KIS 데이터는 나중에 채워짐
                "current_price": None,
                "price_change": None,
                "price_change_rate": None,
                "volume": None,
                "volume_ratio": None,
                "weighted_score": None,
            })

        # 1차 정렬: 언급 증가율 기준
        rising_tickers.sort(
            key=lambda x: (x["is_new"], x["growth_rate"], x["recent_mentions"]),
            reverse=True
        )

        # 상위 limit개만 KIS API 조회 (API 호출 최소화)
        top_tickers = rising_tickers[:limit]

        # KIS API로 주가/거래량 정보 추가
        if include_price and top_tickers:
            try:
                price_data = self._fetch_kis_prices([t["stock_code"] for t in top_tickers])
                top_tickers = self._enrich_with_price_data(top_tickers, price_data)
                # 가중치 점수로 재정렬
                top_tickers.sort(key=lambda x: x.get("weighted_score") or 0, reverse=True)
            except Exception as e:
                logger.warning(f"Failed to fetch KIS price data: {e}")

        return top_tickers

    def _fetch_kis_prices(self, stock_codes: list[str]) -> dict[str, dict]:
        """DB(stock_ohlcv)에서 최신 종가/거래량 조회."""
        if not stock_codes:
            return {}

        result = {}
        for code in stock_codes:
            rows = (
                self.db.query(StockOHLCV)
                .filter(StockOHLCV.stock_code == code)
                .order_by(StockOHLCV.trade_date.desc())
                .limit(2)
                .all()
            )
            if not rows:
                continue
            latest = rows[0]
            prev_close = rows[1].close_price if len(rows) >= 2 else latest.close_price
            change = latest.close_price - prev_close
            change_rate = round(change / prev_close * 100, 2) if prev_close else 0.0
            result[code] = {
                "current_price": latest.close_price,
                "change": change,
                "change_rate": change_rate,
                "volume": latest.volume,
                "prev_close": prev_close,
            }
        return result

    def _enrich_with_price_data(
        self,
        tickers: list[dict],
        price_data: dict[str, dict],
    ) -> list[dict]:
        """종목 데이터에 주가/거래량 정보 및 가중치 추가."""
        for ticker in tickers:
            code = ticker["stock_code"]
            price_info = price_data.get(code)

            if price_info:
                ticker["current_price"] = int(price_info.get("current_price", 0))
                ticker["price_change"] = int(price_info.get("change", 0))
                ticker["price_change_rate"] = float(price_info.get("change_rate", 0))
                ticker["volume"] = price_info.get("volume", 0)

                # 거래량 비율 계산 (평균 거래량 대비) - 추후 개선 가능
                # 현재는 단순히 거래량 표시만
                ticker["volume_ratio"] = None

            # 가중치 점수 계산 (총점 + 상세 breakdown)
            weighted_score, score_breakdown = self._calculate_weighted_score(ticker)
            ticker["weighted_score"] = weighted_score
            ticker["score_breakdown"] = score_breakdown

        return tickers

    def _calculate_weighted_score(self, ticker: dict) -> tuple[float, dict]:
        """종합 가중치 점수 계산 (Emerging Signal Score).

        가중치 구성 (100점 만점):
        - 언급 증가율 (25점): YouTube 언급 증가율 (기준 상향)
        - 절대 언급량 (15점): 최근 언급 횟수 (증가율만으로 부족한 부분 보완)
        - 조회수 가중치 (10점): 영향력 있는 채널 언급 반영
        - 주가 모멘텀 (20점): 상승/하락 모두 반영 (언급↑ + 하락 = 매수 기회)
        - 거래량 급등 (20점): 거래량 로그 스케일
        - 신규 등장 보너스 (10점): 새로 발견된 종목

        Returns:
            (총점, 상세 breakdown dict)
        """
        import math
        breakdown = {}

        # 1. 언급 증가율 (25점 만점)
        # 기준 상향: 500% 이상이면 만점 (1회→6회 수준)
        growth_rate = ticker.get("growth_rate", 0)
        if growth_rate > 0:
            mention_growth_score = min(growth_rate / 500 * 25, 25)
        else:
            mention_growth_score = 0
        breakdown["mention_growth"] = round(mention_growth_score, 1)

        # 2. 절대 언급량 (15점 만점)
        # 최근 언급 횟수 기준 (10회 이상이면 만점)
        recent_mentions = ticker.get("recent_mentions", 0)
        mention_volume_score = min(recent_mentions / 10 * 15, 15)
        breakdown["mention_volume"] = round(mention_volume_score, 1)

        # 3. 조회수 가중치 (10점 만점)
        # 총 조회수 기준 (100만 이상이면 만점, 로그 스케일)
        total_views = ticker.get("total_views", 0) or 0
        if total_views > 0:
            # log10(1,000,000) = 6
            view_score = min(math.log10(total_views + 1) / 6 * 10, 10)
        else:
            view_score = 0
        breakdown["view_weight"] = round(view_score, 1)

        # 4. 주가 모멘텀 (20점 만점)
        # 상승: 직접 반영 (10% 상승 = 20점)
        # 하락: 언급 급증 + 하락 = 역발상 매수 기회로 가점
        price_change_rate = ticker.get("price_change_rate") or 0
        is_contrarian = False
        if price_change_rate > 0:
            # 상승 중: 10% 상승이면 만점
            price_score = min(price_change_rate / 10 * 20, 20)
        elif price_change_rate < 0:
            # 하락 중: 언급 증가율이 높을수록 역발상 매수 시그널
            # 예: 언급 +300%, 주가 -5% → 매수 기회 시그널
            if growth_rate > 100:  # 언급 100% 이상 증가시에만 역발상 점수
                is_contrarian = True
                # 하락폭 5% 이상 + 언급 급증 = 최대 15점
                contrarian_score = min(abs(price_change_rate) / 5 * 10, 10)
                # 언급 증가율에 따른 추가 점수 (최대 5점)
                contrarian_score += min(growth_rate / 300 * 5, 5)
                price_score = contrarian_score
            else:
                # 언급 증가 없이 하락만 = 0점
                price_score = 0
        else:
            price_score = 0
        breakdown["price_momentum"] = round(price_score, 1)
        breakdown["is_contrarian"] = is_contrarian

        # 5. 거래량 급등 (20점 만점)
        # 로그 스케일 (1000만주 이상이면 만점)
        volume = ticker.get("volume") or 0
        if volume > 0:
            # log10(10,000,000) = 7
            volume_score = min(math.log10(volume + 1) / 7 * 20, 20)
        else:
            volume_score = 0
        breakdown["volume_score"] = round(volume_score, 1)

        # 6. 신규 등장 보너스 (10점)
        new_bonus = 10 if ticker.get("is_new") else 0
        breakdown["new_bonus"] = new_bonus

        # 총점 계산
        total_score = (
            mention_growth_score +
            mention_volume_score +
            view_score +
            price_score +
            volume_score +
            new_bonus
        )

        return round(total_score, 1), breakdown

    # ===== 미디어 타임라인 =====

    def get_stock_timeline(
        self,
        stock_code: str,
        days_back: int = 90,
    ) -> dict:
        """종목별 미디어 타임라인 (가격 + 언급 결합).

        Args:
            stock_code: 종목코드
            days_back: 분석 기간 (일)

        Returns:
            {daily, videos, summary}
        """
        cutoff = today_kst() - timedelta(days=days_back)

        # 종목명 조회
        stock = self.db.query(Stock).filter(Stock.code == stock_code).first()
        stock_name = stock.name if stock else None

        # 1. TickerMentionStats에서 일별 언급 데이터
        mention_rows = (
            self.db.query(TickerMentionStats)
            .filter(
                TickerMentionStats.stock_code == stock_code,
                TickerMentionStats.stat_date >= cutoff,
            )
            .order_by(TickerMentionStats.stat_date)
            .all()
        )
        mention_by_date = {
            r.stat_date: {
                "mention_count": r.youtube_mention_count or 0,
                "total_views": r.youtube_total_views or 0,
            }
            for r in mention_rows
        }

        # 2. StockOHLCV에서 일별 종가
        ohlcv_rows = (
            self.db.query(StockOHLCV)
            .filter(
                StockOHLCV.stock_code == stock_code,
                StockOHLCV.trade_date >= cutoff,
            )
            .order_by(StockOHLCV.trade_date)
            .all()
        )
        price_by_date = {r.trade_date: int(r.close_price) for r in ohlcv_rows}

        # 3. 날짜 병합 — 주말 가격은 직전 거래일 종가로 이월(forward-fill)
        all_dates = sorted(set(mention_by_date.keys()) | set(price_by_date.keys()))
        daily = []
        last_known_price = None
        for d in all_dates:
            m = mention_by_date.get(d, {"mention_count": 0, "total_views": 0})
            price = price_by_date.get(d)
            if price is not None:
                last_known_price = price
            daily.append({
                "date": d.isoformat(),
                "close_price": price if price is not None else last_known_price,
                "mention_count": m["mention_count"],
                "total_views": m["total_views"],
            })

        # 4. 관련 영상 목록
        cutoff_dt = datetime.combine(cutoff, datetime.min.time())
        video_rows = (
            self.db.query(YouTubeMention)
            .filter(
                YouTubeMention.mentioned_tickers.contains([stock_code]),
                YouTubeMention.published_at >= cutoff_dt,
            )
            .order_by(desc(YouTubeMention.published_at))
            .limit(30)
            .all()
        )
        videos = [
            {
                "video_id": v.video_id,
                "video_title": v.video_title,
                "channel_name": v.channel_name,
                "published_at": v.published_at.isoformat() if v.published_at else "",
                "view_count": v.view_count,
                "thumbnail_url": v.thumbnail_url,
            }
            for v in video_rows
        ]

        # 5. 요약 통계
        total_mentions = sum(d["mention_count"] for d in daily)
        mention_days_count = sum(1 for d in daily if d["mention_count"] > 0)
        avg_daily = total_mentions / max(mention_days_count, 1)

        # 첫 언급일 가격, 최신 가격
        first_mention_date = None
        for d in all_dates:
            m = mention_by_date.get(d)
            if m and m["mention_count"] > 0:
                first_mention_date = d
                break

        # forward-fill된 daily에서 가격 조회 (주말도 직전 거래일 가격 적용됨)
        daily_by_date = {d["date"]: d["close_price"] for d in daily}
        price_at_first = daily_by_date.get(first_mention_date.isoformat()) if first_mention_date else None
        price_now = daily[-1]["close_price"] if daily else None

        price_change_pct = None
        if price_at_first and price_now and price_at_first > 0:
            price_change_pct = round((price_now - price_at_first) / price_at_first * 100, 2)

        summary = {
            "total_mentions": total_mentions,
            "mention_days": mention_days_count,
            "avg_daily": round(avg_daily, 2),
            "price_at_first_mention": price_at_first,
            "price_now": price_now,
            "price_change_pct": price_change_pct,
        }

        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "daily": daily,
            "videos": videos,
            "summary": summary,
        }

    # ===== 언급 백테스트 =====

    def get_mention_backtest(
        self,
        days_back: int = 90,
        min_mentions: int = 3,
        holding_days_str: str = "3,7,14",
    ) -> dict:
        """유튜브 언급 후 수익률 백테스트.

        Args:
            days_back: 분석 기간
            min_mentions: 최소 언급 횟수 임계값
            holding_days_str: 보유 기간 (콤마 구분)

        Returns:
            {params, total_signals, holding_stats, items, summary}
        """
        holding_days = [int(x.strip()) for x in holding_days_str.split(",") if x.strip()]
        cutoff = today_kst() - timedelta(days=days_back)

        # 1. 임계값 이상 언급된 (stock_code, stat_date) 추출
        signal_rows = (
            self.db.query(
                TickerMentionStats.stock_code,
                TickerMentionStats.stock_name,
                TickerMentionStats.stat_date,
                TickerMentionStats.youtube_mention_count,
            )
            .filter(
                TickerMentionStats.stat_date >= cutoff,
                TickerMentionStats.youtube_mention_count >= min_mentions,
            )
            .order_by(TickerMentionStats.stat_date)
            .all()
        )

        # 2. 종목별 첫 신호일 그룹화
        first_signals: dict[str, dict] = {}
        for row in signal_rows:
            code = row.stock_code
            if code not in first_signals:
                first_signals[code] = {
                    "stock_code": code,
                    "stock_name": row.stock_name,
                    "signal_date": row.stat_date,
                    "mention_count": row.youtube_mention_count or 0,
                }

        # 3. 각 신호에 대해 OHLCV 기반 수익률 계산
        max_holding = max(holding_days) if holding_days else 30
        items = []

        for code, sig in first_signals.items():
            signal_date = sig["signal_date"]

            # entry_price: 신호일 또는 직전 거래일 종가
            entry_row = (
                self.db.query(StockOHLCV)
                .filter(
                    StockOHLCV.stock_code == code,
                    StockOHLCV.trade_date <= signal_date,
                )
                .order_by(desc(StockOHLCV.trade_date))
                .first()
            )
            if not entry_row:
                continue

            entry_price = int(entry_row.close_price)
            if entry_price <= 0:
                continue

            # 보유기간별 exit_price 계산
            returns = {}
            for hd in holding_days:
                target_date = signal_date + timedelta(days=hd)
                exit_row = (
                    self.db.query(StockOHLCV)
                    .filter(
                        StockOHLCV.stock_code == code,
                        StockOHLCV.trade_date >= target_date,
                    )
                    .order_by(asc(StockOHLCV.trade_date))
                    .first()
                )
                if exit_row:
                    exit_price = int(exit_row.close_price)
                    ret = round((exit_price - entry_price) / entry_price * 100, 2)
                    returns[f"{hd}d"] = ret
                else:
                    returns[f"{hd}d"] = None

            items.append({
                "stock_code": code,
                "stock_name": sig["stock_name"],
                "signal_date": signal_date.isoformat(),
                "mention_count": sig["mention_count"],
                "entry_price": entry_price,
                "returns": returns,
            })

        # 4. 보유기간별 통계
        holding_stats = {}
        for hd in holding_days:
            key = f"{hd}d"
            rets = [it["returns"][key] for it in items if it["returns"].get(key) is not None]
            if rets:
                holding_stats[key] = {
                    "sample_count": len(rets),
                    "avg_return": round(sum(rets) / len(rets), 2),
                    "median": round(statistics.median(rets), 2),
                    "win_rate": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
                    "max_return": round(max(rets), 2),
                    "max_loss": round(min(rets), 2),
                }
            else:
                holding_stats[key] = {
                    "sample_count": 0,
                    "avg_return": 0,
                    "median": 0,
                    "win_rate": 0,
                    "max_return": 0,
                    "max_loss": 0,
                }

        # 5. 전체 요약
        all_first_returns = [
            it["returns"].get(f"{holding_days[0]}d")
            for it in items
            if it["returns"].get(f"{holding_days[0]}d") is not None
        ] if holding_days else []

        # 최고/최악 종목 찾기
        best_stock = None
        worst_stock = None
        if items and holding_days:
            first_key = f"{holding_days[0]}d"
            valid_items = [it for it in items if it["returns"].get(first_key) is not None]
            if valid_items:
                best_item = max(valid_items, key=lambda x: x["returns"][first_key])
                worst_item = min(valid_items, key=lambda x: x["returns"][first_key])
                best_stock = f"{best_item['stock_name'] or best_item['stock_code']} ({best_item['returns'][first_key]}%)"
                worst_stock = f"{worst_item['stock_name'] or worst_item['stock_code']} ({worst_item['returns'][first_key]}%)"

        summary = {
            "avg_return": round(sum(all_first_returns) / len(all_first_returns), 2) if all_first_returns else 0,
            "win_rate": round(sum(1 for r in all_first_returns if r > 0) / len(all_first_returns) * 100, 1) if all_first_returns else 0,
            "best_stock": best_stock,
            "worst_stock": worst_stock,
        }

        # 수익률순 정렬 (첫 보유기간 기준)
        if holding_days:
            first_key = f"{holding_days[0]}d"
            items.sort(key=lambda x: x["returns"].get(first_key) or -999, reverse=True)

        return {
            "params": {
                "days_back": days_back,
                "min_mentions": min_mentions,
                "holding_days": holding_days,
            },
            "total_signals": len(items),
            "holding_stats": holding_stats,
            "items": items,
            "summary": summary,
        }

    # ===== 과열 경고 =====

    def get_overheat_stocks(
        self,
        recent_days: int = 3,
        baseline_days: int = 30,
    ) -> dict:
        """유튜브 과열 경고 시스템.

        Args:
            recent_days: 최근 기간 (일)
            baseline_days: 기준 기간 (일)

        Returns:
            {items, summary}
        """
        today = today_kst()
        recent_start = today - timedelta(days=recent_days)
        baseline_start = today - timedelta(days=baseline_days)
        baseline_end = recent_start - timedelta(days=1)

        # 1. 최근 N일 종목별 총 언급 수
        recent_rows = (
            self.db.query(
                TickerMentionStats.stock_code,
                TickerMentionStats.stock_name,
                func.sum(TickerMentionStats.youtube_mention_count).label("recent_sum"),
            )
            .filter(
                TickerMentionStats.stat_date >= recent_start,
            )
            .group_by(TickerMentionStats.stock_code, TickerMentionStats.stock_name)
            .having(func.sum(TickerMentionStats.youtube_mention_count) > 0)
            .all()
        )

        # 2. 과거 baseline 기간 일평균
        baseline_rows = (
            self.db.query(
                TickerMentionStats.stock_code,
                func.sum(TickerMentionStats.youtube_mention_count).label("baseline_sum"),
                func.count(TickerMentionStats.id).label("baseline_days_count"),
            )
            .filter(
                TickerMentionStats.stat_date >= baseline_start,
                TickerMentionStats.stat_date <= baseline_end,
            )
            .group_by(TickerMentionStats.stock_code)
            .all()
        )
        baseline_map = {}
        for row in baseline_rows:
            days_count = max(row.baseline_days_count or 1, 1)
            baseline_map[row.stock_code] = (row.baseline_sum or 0) / days_count

        # 3. 전체 기간 총 언급 수
        total_mention_rows = dict(
            self.db.query(
                TickerMentionStats.stock_code,
                func.sum(TickerMentionStats.youtube_mention_count).label("total"),
            )
            .filter(TickerMentionStats.stat_date >= baseline_start)
            .group_by(TickerMentionStats.stock_code)
            .all()
        )

        # 4. 최근 영상 수 (종목별)
        cutoff_dt = datetime.combine(recent_start, datetime.min.time())
        # 빠른 조회를 위해 한번에 가져옴
        recent_videos = (
            self.db.query(YouTubeMention)
            .filter(YouTubeMention.published_at >= cutoff_dt)
            .all()
        )
        video_count_map: dict[str, int] = {}
        for v in recent_videos:
            for ticker in (v.mentioned_tickers or []):
                video_count_map[ticker] = video_count_map.get(ticker, 0) + 1

        # 5. 주가 변화 계산
        items = []
        for row in recent_rows:
            code = row.stock_code
            recent_sum = row.recent_sum or 0
            baseline_avg = baseline_map.get(code, 0)

            # overheat_ratio 계산
            if baseline_avg > 0:
                overheat_ratio = round(recent_sum / (baseline_avg * recent_days), 2)
            else:
                # baseline이 0이면 신규 등장 → ratio를 recent_sum 자체로
                overheat_ratio = float(recent_sum) if recent_sum > 0 else 0

            if overheat_ratio < 1.5 and baseline_avg > 0:
                continue  # 평소 수준이면 스킵

            # 주가 변화
            price_change_pct = None
            ohlcv_recent = (
                self.db.query(StockOHLCV)
                .filter(
                    StockOHLCV.stock_code == code,
                    StockOHLCV.trade_date >= recent_start,
                )
                .order_by(asc(StockOHLCV.trade_date))
                .first()
            )
            ohlcv_latest = (
                self.db.query(StockOHLCV)
                .filter(StockOHLCV.stock_code == code)
                .order_by(desc(StockOHLCV.trade_date))
                .first()
            )
            if ohlcv_recent and ohlcv_latest and ohlcv_recent.close_price > 0:
                price_change_pct = round(
                    (int(ohlcv_latest.close_price) - int(ohlcv_recent.close_price))
                    / int(ohlcv_recent.close_price) * 100, 2
                )

            # 상태 분류
            if overheat_ratio >= 5:
                status = "FRENZY"
            elif overheat_ratio >= 3 and (price_change_pct is None or price_change_pct > 0):
                status = "OVERHEAT"
            elif overheat_ratio >= 2 and price_change_pct is not None and price_change_pct < -3:
                status = "CONTRARIAN"
            elif baseline_avg > 0 and overheat_ratio < 1:
                status = "COOLING"
            else:
                status = "NORMAL"

            items.append({
                "stock_code": code,
                "stock_name": row.stock_name,
                "status": status,
                "recent_mentions": recent_sum,
                "baseline_avg_daily": round(baseline_avg, 2),
                "overheat_ratio": overheat_ratio,
                "price_change_pct": price_change_pct,
                "mention_count_total": total_mention_rows.get(code, 0),
                "recent_videos_count": video_count_map.get(code, 0),
            })

        # 6. overheat_ratio 내림차순 정렬
        items.sort(key=lambda x: x["overheat_ratio"], reverse=True)

        # 7. 요약
        status_counts = {"OVERHEAT": 0, "FRENZY": 0, "CONTRARIAN": 0, "COOLING": 0}
        for it in items:
            if it["status"] in status_counts:
                status_counts[it["status"]] += 1

        summary = {
            "total": len(items),
            "overheat_count": status_counts["OVERHEAT"],
            "frenzy_count": status_counts["FRENZY"],
            "contrarian_count": status_counts["CONTRARIAN"],
            "cooling_count": status_counts["COOLING"],
        }

        return {
            "items": items,
            "summary": summary,
        }
