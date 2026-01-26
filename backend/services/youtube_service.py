"""YouTube 서비스."""
import logging
import asyncio
from datetime import datetime, timedelta, date
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from models import YouTubeMention, TickerMentionStats, Stock, InvestmentIdea, IdeaStatus
from integrations.youtube import get_youtube_client, StockMentionAnalyzer
from integrations.kis import get_kis_client

logger = logging.getLogger(__name__)


class YouTubeService:
    """YouTube 서비스.

    YouTube 영상 수집 및 종목 언급 분석을 담당합니다.
    """

    def __init__(self, db: Session):
        self.db = db
        self.youtube_client = get_youtube_client()
        self.analyzer = StockMentionAnalyzer(db)

    def _get_idea_tickers(self) -> list[str]:
        """활성/관찰 중인 아이디어의 종목명 목록 조회."""
        ideas = self.db.query(InvestmentIdea).filter(
            InvestmentIdea.status.in_([IdeaStatus.ACTIVE, IdeaStatus.WATCHING])
        ).all()

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
            published_after = datetime.utcnow() - timedelta(hours=hours_back)

            # 아이디어에서 종목명 가져오기
            tickers = self._get_idea_tickers()
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

            # 종목 언급 분석
            analyzed_videos = self.analyzer.analyze_videos(videos)
            result["with_mentions"] = len(analyzed_videos)

            # DB에 저장
            for video in analyzed_videos:
                video_id = video.get("video_id")
                if not video_id:
                    continue

                # 중복 체크
                existing = self.db.query(YouTubeMention).filter(
                    YouTubeMention.video_id == video_id
                ).first()

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
                    published_at = datetime.utcnow()

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

                # 종목별 통계 업데이트
                await self._update_ticker_stats(
                    video.get("mentioned_tickers", []),
                    video.get("view_count", 0),
                )

            self.db.commit()
            logger.info(
                f"YouTube collection completed: {result['new']} new, "
                f"{result['with_mentions']} with mentions"
            )

        except Exception as e:
            logger.error(f"YouTube collection failed: {e}")
            self.db.rollback()
            raise

        return result

    async def _update_ticker_stats(
        self,
        tickers: list[str],
        view_count: int,
    ) -> None:
        """종목별 통계 업데이트."""
        today = date.today()

        for ticker in tickers:
            # 기존 통계 조회 또는 생성
            stats = self.db.query(TickerMentionStats).filter(
                TickerMentionStats.stock_code == ticker,
                TickerMentionStats.stat_date == today,
            ).first()

            if not stats:
                # 종목명 조회
                stock = self.db.query(Stock).filter(Stock.code == ticker).first()
                stats = TickerMentionStats(
                    stock_code=ticker,
                    stock_name=stock.name if stock else None,
                    stat_date=today,
                    youtube_mention_count=0,
                    youtube_total_views=0,
                )
                self.db.add(stats)
                self.db.flush()  # 중복 방지를 위해 즉시 DB에 반영

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

        cutoff = datetime.utcnow() - timedelta(days=days_back)
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
        cutoff = date.today() - timedelta(days=days_back)

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
        cutoff = date.today() - timedelta(days=days_back)

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
            published_after = datetime.utcnow() - timedelta(hours=hours_back)

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

            # 종목 언급 분석
            analyzed_videos = self.analyzer.analyze_videos(videos)
            result["with_mentions"] = len(analyzed_videos)

            # 발견된 종목 집계
            tickers_found = set()

            # DB에 저장
            for video in analyzed_videos:
                video_id = video.get("video_id")
                if not video_id:
                    continue

                mentioned_tickers = video.get("mentioned_tickers", [])
                tickers_found.update(mentioned_tickers)

                # 중복 체크
                existing = self.db.query(YouTubeMention).filter(
                    YouTubeMention.video_id == video_id
                ).first()

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
                    published_at = datetime.utcnow()

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

                # 종목별 통계 업데이트
                await self._update_ticker_stats(
                    mentioned_tickers,
                    video.get("view_count", 0),
                )

            self.db.commit()
            result["tickers_found"] = list(tickers_found)
            logger.info(
                f"Hot video collection completed: {result['new']} new, "
                f"{len(tickers_found)} tickers found"
            )

        except Exception as e:
            logger.error(f"Hot video collection failed: {e}")
            self.db.rollback()
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
        today = date.today()
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
        """KIS API로 주가/거래량 정보 조회."""
        import asyncio
        from integrations.kis.client import KISClient

        async def fetch_all():
            # 매번 새 클라이언트 생성하여 이벤트 루프 문제 방지
            kis_client = KISClient()
            try:
                return await kis_client.get_multiple_prices(stock_codes)
            finally:
                await kis_client.close()

        try:
            return asyncio.run(fetch_all())
        except Exception as e:
            logger.error(f"KIS API call failed: {e}")
            return {}

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
