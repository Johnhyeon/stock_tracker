"""테마 뉴스 수집 서비스."""
import json
import logging
import re
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, Integer
from sqlalchemy.dialects.postgresql import insert

from models import ThemeNews, ThemeNewsStats, YouTubeMention, TraderMention
from integrations.naver_search import NaverSearchClient
from integrations.rss import RSSClient, RSSFeedItem
from core.config import get_settings

logger = logging.getLogger(__name__)

THEME_MAP_PATH = Path(__file__).parent.parent / "data" / "theme_map.json"

# 제외할 패턴 (영양가 없는 시황 뉴스)
EXCLUDE_PATTERNS = [
    r'\d+(\.\d+)?%\s*(상승|하락)',  # N% 상승/하락
    r'상승\s*마감',
    r'하락\s*마감',
    r'신고가',
    r'신저가',
    r'52주\s*(최고|최저)',
    r'장중\s*(최고|최저)',
    r'급등\s*마감',
    r'급락\s*마감',
    r'보합\s*마감',
    r'\[마감시황\]',  # 마감시황 뉴스
    r'마감시황',
    r'오늘의\s*운세',  # 운세
    r'띠별\s*운세',
    r'증시\s*마감',
    r'장\s*마감',
    r'종가\s*마감',
    r'코스피\s*마감',
    r'코스닥\s*마감',
    r'\[글로벌\s*마켓',  # 글로벌 시황
    r'글로벌\s*마켓\s*리포트',
    r'\[뉴욕마켓',  # 해외시황
    r'뉴욕마켓워치',
    r'뉴욕증시',
    r'\[머니무브',  # 재테크/자산배분
    r'채권금리',
    r'환율\s*동향',
    r'외환시장',
    r'역대\s*최고\s*종가',
    r'사상\s*최고',
]

# 양질의 뉴스 키워드 (가중치 부여)
QUALITY_KEYWORDS = [
    '정책', '발표', '계약', '수주', '투자',
    '인수', '합병', 'M&A', '협약', '협력',
    '승인', '허가', '출시', '개발', '신규',
    '확대', '증설', '착공', '준공', '수출',
    '법안', '규제', '지원', '보조금', '세제',
]


class NewsCollectorService:
    """테마 관련 뉴스 수집 및 분석 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self._theme_map: dict[str, list[dict]] = {}
        self._theme_keywords: dict[str, list[str]] = {}
        self._naver_client: Optional[NaverSearchClient] = None
        self._rss_client: Optional[RSSClient] = None
        self._load_theme_map()

    def _load_theme_map(self):
        """테마 맵 로드 및 검색 키워드 생성."""
        try:
            with open(THEME_MAP_PATH, "r", encoding="utf-8") as f:
                self._theme_map = json.load(f)

            # 테마별 검색 키워드 생성
            for theme_name, stocks in self._theme_map.items():
                keywords = [theme_name]  # 테마명 자체
                # 테마명에서 괄호 안의 영문명 추출
                if "(" in theme_name and ")" in theme_name:
                    match = re.search(r'\(([^)]+)\)', theme_name)
                    if match:
                        keywords.append(match.group(1))
                # 대표 종목명 추가 (상위 3개)
                for stock in stocks[:3]:
                    if stock.get("name"):
                        keywords.append(stock["name"])
                self._theme_keywords[theme_name] = keywords

            logger.info(f"Loaded {len(self._theme_map)} themes for news collection")
        except Exception as e:
            logger.error(f"Failed to load theme map: {e}")

    def _get_naver_client(self) -> Optional[NaverSearchClient]:
        """네이버 검색 API 클라이언트 반환."""
        if self._naver_client is None:
            if self.settings.naver_client_id and self.settings.naver_client_secret:
                self._naver_client = NaverSearchClient(
                    client_id=self.settings.naver_client_id,
                    client_secret=self.settings.naver_client_secret,
                )
            else:
                logger.warning("네이버 API 키가 설정되지 않았습니다")
        return self._naver_client

    def _get_rss_client(self) -> RSSClient:
        """RSS 클라이언트 반환."""
        if self._rss_client is None:
            self._rss_client = RSSClient()
        return self._rss_client

    async def _get_mentioned_stock_codes(self, days: int = 7) -> set[str]:
        """최근 언급된 종목 코드 조회 (YouTube + Trader)."""
        start_date = date.today() - timedelta(days=days)
        mentioned_codes = set()

        # YouTube 언급 종목
        youtube_stmt = (
            select(YouTubeMention.mentioned_tickers)
            .where(YouTubeMention.published_at >= start_date)
        )
        youtube_result = await self.db.execute(youtube_stmt)
        for row in youtube_result.scalars().all():
            if row:
                mentioned_codes.update(row)

        # Trader 언급 종목
        trader_stmt = (
            select(func.distinct(TraderMention.stock_code))
            .where(TraderMention.mention_date >= start_date)
        )
        trader_result = await self.db.execute(trader_stmt)
        for code in trader_result.scalars().all():
            if code:
                mentioned_codes.add(code)

        logger.info(f"뉴스 수집: 최근 {days}일 언급된 종목 {len(mentioned_codes)}개")
        return mentioned_codes

    def _get_themes_for_stocks(self, stock_codes: set[str]) -> set[str]:
        """종목 코드들이 속한 테마 목록 반환."""
        themes = set()
        for theme_name, stocks in self._theme_map.items():
            theme_codes = {s.get("code") for s in stocks if s.get("code")}
            if theme_codes & stock_codes:  # 교집합이 있으면
                themes.add(theme_name)
        return themes

    async def collect_news_from_naver(
        self,
        theme_names: Optional[list[str]] = None,
        max_per_theme: int = 30,
    ) -> int:
        """네이버 검색 API로 테마 뉴스 수집.

        Args:
            theme_names: 수집할 테마 목록 (None이면 전체)
            max_per_theme: 테마당 최대 수집 건수

        Returns:
            저장된 뉴스 건수
        """
        client = self._get_naver_client()
        if not client:
            logger.warning("네이버 클라이언트 없이 뉴스 수집 스킵")
            return 0

        themes = theme_names or list(self._theme_map.keys())
        saved_count = 0

        for theme_name in themes:
            keywords = self._theme_keywords.get(theme_name, [theme_name])
            search_query = keywords[0]  # 메인 키워드 (테마명)로 검색

            try:
                items = await client.search_news(
                    query=f"{search_query} 주식",  # "테마명 주식"으로 검색
                    display=max_per_theme,
                    sort="date",
                )

                for item in items:
                    # 키워드 매칭 확인
                    matched_keyword = self._find_matching_keyword(
                        keywords,
                        f"{item.title} {item.description}",
                    )

                    if matched_keyword:
                        saved = await self._save_news(
                            theme_name=theme_name,
                            matched_keyword=matched_keyword,
                            title=item.title,
                            url=item.original_link or item.link,
                            source="naver",
                            published_at=item.pub_date,
                            description=item.description,
                            collection_source="naver_api",
                        )
                        if saved:
                            saved_count += 1

            except Exception as e:
                logger.error(f"네이버 뉴스 수집 실패 (theme={theme_name}): {e}")
                continue

        logger.info(f"네이버 뉴스 수집 완료: {saved_count}건 저장")
        return saved_count

    async def collect_news_from_rss(
        self,
        target_themes: Optional[set[str]] = None,
    ) -> int:
        """RSS 피드에서 테마 뉴스 수집.

        Args:
            target_themes: 수집할 테마 목록 (None이면 전체)

        Returns:
            저장된 뉴스 건수
        """
        rss_client = self._get_rss_client()
        all_items = await rss_client.fetch_all_items()

        saved_count = 0

        # 대상 테마의 키워드만 사용
        if target_themes:
            theme_keywords = {
                name: kws for name, kws in self._theme_keywords.items()
                if name in target_themes
            }
        else:
            theme_keywords = self._theme_keywords

        for item in all_items:
            # 대상 테마의 키워드와 매칭 시도
            text = f"{item.title} {item.description}"

            for theme_name, keywords in theme_keywords.items():
                matched_keyword = self._find_matching_keyword(keywords, text)

                if matched_keyword:
                    saved = await self._save_news(
                        theme_name=theme_name,
                        matched_keyword=matched_keyword,
                        title=item.title,
                        url=item.link,
                        source=item.source,
                        published_at=item.pub_date or datetime.utcnow(),
                        description=item.description,
                        collection_source="rss",
                    )
                    if saved:
                        saved_count += 1

        logger.info(f"RSS 뉴스 수집 완료: {saved_count}건 저장 (대상 테마: {len(theme_keywords)}개)")
        return saved_count

    def _find_matching_keyword(
        self,
        keywords: list[str],
        text: str,
    ) -> Optional[str]:
        """텍스트에서 매칭되는 키워드 찾기 (정확한 단어 매칭)."""
        for keyword in keywords:
            # 정확한 단어 매칭 (단어 경계 사용)
            # 키워드 앞뒤로 단어가 아닌 문자 또는 문자열 시작/끝이어야 함
            pattern = r'(?<![가-힣a-zA-Z0-9])' + re.escape(keyword) + r'(?![가-힣a-zA-Z0-9])'
            if re.search(pattern, text, re.IGNORECASE):
                return keyword

        return None

    def _should_exclude_news(self, title: str) -> bool:
        """제외해야 할 뉴스인지 확인 (영양가 없는 시황 뉴스)."""
        for pattern in EXCLUDE_PATTERNS:
            if re.search(pattern, title):
                return True
        return False

    def _is_quality_news(self, title: str, description: str = "") -> bool:
        """양질의 뉴스인지 확인 (정책, 계약 등 키워드 포함)."""
        text = f"{title} {description}".lower()
        for keyword in QUALITY_KEYWORDS:
            if keyword.lower() in text:
                return True
        return False

    async def _save_news(
        self,
        theme_name: str,
        matched_keyword: str,
        title: str,
        url: str,
        source: str,
        published_at: datetime,
        description: str,
        collection_source: str,
    ) -> bool:
        """뉴스 저장 (중복 체크, 필터링 적용).

        Returns:
            저장 성공 여부
        """
        try:
            # 영양가 없는 뉴스 필터링
            if self._should_exclude_news(title):
                logger.debug(f"뉴스 제외 (시황): {title[:50]}")
                return False

            # 양질의 뉴스 여부 체크
            is_quality = self._is_quality_news(title, description or "")

            # timezone aware datetime을 naive로 변환 (UTC)
            if published_at.tzinfo is not None:
                published_at = published_at.replace(tzinfo=None)

            # Upsert 사용 (URL 중복 시 무시)
            stmt = insert(ThemeNews).values(
                theme_name=theme_name,
                matched_keyword=matched_keyword,
                news_title=title[:500],
                news_url=url[:1000],
                news_source=source[:100] if source else None,
                published_at=published_at,
                description=description[:2000] if description else None,
                collection_source=collection_source,
                is_quality=is_quality,
            ).on_conflict_do_nothing(index_elements=['news_url'])

            result = await self.db.execute(stmt)
            await self.db.commit()

            return result.rowcount > 0
        except Exception as e:
            logger.error(f"뉴스 저장 실패: {e}")
            await self.db.rollback()
            return False

    async def collect_all(
        self,
        theme_names: Optional[list[str]] = None,
    ) -> dict:
        """모든 소스에서 뉴스 수집 (언급된 종목 테마만).

        Returns:
            수집 결과 요약
        """
        # 언급된 종목의 테마만 수집
        mentioned_codes = await self._get_mentioned_stock_codes(days=7)

        if not mentioned_codes:
            logger.warning("언급된 종목이 없어 뉴스 수집 스킵")
            return {
                "naver_count": 0,
                "rss_count": 0,
                "total_count": 0,
                "mentioned_stocks": 0,
                "target_themes": 0,
                "collected_at": datetime.utcnow().isoformat(),
            }

        target_themes = self._get_themes_for_stocks(mentioned_codes)
        logger.info(f"뉴스 수집 대상 테마: {len(target_themes)}개 (전체 {len(self._theme_map)}개 중)")

        # theme_names가 지정되면 교집합 사용
        if theme_names:
            target_themes = target_themes & set(theme_names)

        naver_count = await self.collect_news_from_naver(list(target_themes))
        rss_count = await self.collect_news_from_rss(target_themes)

        # 통계 갱신
        await self.update_stats()

        return {
            "naver_count": naver_count,
            "rss_count": rss_count,
            "total_count": naver_count + rss_count,
            "mentioned_stocks": len(mentioned_codes),
            "target_themes": len(target_themes),
            "collected_at": datetime.utcnow().isoformat(),
        }

    async def update_stats(self, target_date: Optional[date] = None):
        """테마별 일별 통계 갱신.

        Args:
            target_date: 갱신할 날짜 (None이면 오늘)
        """
        stat_date = target_date or date.today()

        # 테마별 집계
        stmt = (
            select(
                ThemeNews.theme_name,
                func.count(ThemeNews.id).label("mention_count"),
                func.count(func.distinct(ThemeNews.news_source)).label("unique_sources"),
            )
            .where(
                func.date(ThemeNews.published_at) == stat_date
            )
            .group_by(ThemeNews.theme_name)
        )

        result = await self.db.execute(stmt)
        rows = result.fetchall()

        for row in rows:
            theme_name, mention_count, unique_sources = row

            # 상위 키워드 집계
            keyword_stmt = (
                select(
                    ThemeNews.matched_keyword,
                    func.count(ThemeNews.id).label("cnt"),
                )
                .where(
                    and_(
                        ThemeNews.theme_name == theme_name,
                        func.date(ThemeNews.published_at) == stat_date,
                    )
                )
                .group_by(ThemeNews.matched_keyword)
                .order_by(func.count(ThemeNews.id).desc())
                .limit(5)
            )
            keyword_result = await self.db.execute(keyword_stmt)
            top_keywords = [
                {"keyword": kw, "count": cnt}
                for kw, cnt in keyword_result.fetchall()
            ]

            # WoW 변화율 계산
            last_week = stat_date - timedelta(days=7)
            wow_stmt = (
                select(func.count(ThemeNews.id))
                .where(
                    and_(
                        ThemeNews.theme_name == theme_name,
                        func.date(ThemeNews.published_at) == last_week,
                    )
                )
            )
            wow_result = await self.db.execute(wow_stmt)
            last_week_count = wow_result.scalar() or 0

            wow_change = None
            if last_week_count > 0:
                wow_change = int((mention_count - last_week_count) / last_week_count * 100)

            # Upsert
            upsert_stmt = insert(ThemeNewsStats).values(
                theme_name=theme_name,
                stat_date=stat_date,
                mention_count=mention_count,
                unique_sources=unique_sources,
                top_keywords=top_keywords,
                wow_change_pct=wow_change,
            ).on_conflict_do_update(
                index_elements=['theme_name', 'stat_date'],
                set_={
                    'mention_count': mention_count,
                    'unique_sources': unique_sources,
                    'top_keywords': top_keywords,
                    'wow_change_pct': wow_change,
                    'updated_at': datetime.utcnow(),
                }
            )

            await self.db.execute(upsert_stmt)

        await self.db.commit()
        logger.info(f"테마 뉴스 통계 갱신 완료: {len(rows)}개 테마, {stat_date}")

    async def get_theme_news_trend(
        self,
        theme_name: str,
        days: int = 14,
    ) -> list[dict]:
        """테마별 뉴스 추이 조회.

        Args:
            theme_name: 테마명
            days: 조회 기간

        Returns:
            일별 뉴스 통계 리스트
        """
        start_date = date.today() - timedelta(days=days)

        stmt = (
            select(ThemeNewsStats)
            .where(
                and_(
                    ThemeNewsStats.theme_name == theme_name,
                    ThemeNewsStats.stat_date >= start_date,
                )
            )
            .order_by(ThemeNewsStats.stat_date)
        )

        result = await self.db.execute(stmt)
        stats = result.scalars().all()

        return [
            {
                "date": stat.stat_date.isoformat(),
                "mention_count": stat.mention_count,
                "unique_sources": stat.unique_sources,
                "top_keywords": stat.top_keywords,
                "wow_change_pct": stat.wow_change_pct,
            }
            for stat in stats
        ]

    async def get_recent_news(
        self,
        theme_name: str,
        limit: int = 10,
    ) -> list[dict]:
        """테마별 최근 뉴스 조회."""
        stmt = (
            select(ThemeNews)
            .where(ThemeNews.theme_name == theme_name)
            .order_by(ThemeNews.published_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        news = result.scalars().all()

        return [
            {
                "title": n.news_title,
                "url": n.news_url,
                "source": n.news_source,
                "published_at": n.published_at.isoformat(),
                "keyword": n.matched_keyword,
            }
            for n in news
        ]

    async def get_news_momentum(
        self,
        theme_name: str,
        days: int = 7,
    ) -> dict:
        """테마의 뉴스 모멘텀 점수 계산.

        ThemeNews 테이블에서 직접 집계합니다.
        양질의 뉴스(정책, 계약 등)에 가중치 부여.

        Returns:
            {
                "score": 0-30,
                "7d_count": int,
                "quality_count": int,
                "wow_change": int,
                "source_diversity": int,
            }
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 최근 7일 뉴스 수, 양질 뉴스 수, 출처 다양성
        stmt = (
            select(
                func.count(ThemeNews.id).label("total_count"),
                func.sum(func.cast(ThemeNews.is_quality, Integer)).label("quality_count"),
                func.count(func.distinct(ThemeNews.news_source)).label("unique_sources"),
            )
            .where(
                and_(
                    ThemeNews.theme_name == theme_name,
                    ThemeNews.published_at >= start_date,
                    ThemeNews.published_at <= end_date,
                )
            )
        )

        result = await self.db.execute(stmt)
        row = result.fetchone()

        total_count = row.total_count or 0
        quality_count = row.quality_count or 0
        unique_sources = row.unique_sources or 0

        # 전주 대비 변화
        prev_start = start_date - timedelta(days=7)
        prev_stmt = (
            select(func.count(ThemeNews.id))
            .where(
                and_(
                    ThemeNews.theme_name == theme_name,
                    ThemeNews.published_at >= prev_start,
                    ThemeNews.published_at < start_date,
                )
            )
        )
        prev_result = await self.db.execute(prev_stmt)
        prev_count = prev_result.scalar() or 0

        wow_change = 0
        if prev_count > 0:
            wow_change = int((total_count - prev_count) / prev_count * 100)

        # 점수 계산 (30점 만점)
        # 뉴스 수 (0-12점): 최대 30건 기준
        count_score = min(float(total_count) / 30 * 12, 12)
        # 양질 뉴스 보너스 (0-8점): 양질 뉴스 10건당 만점
        quality_score = min(float(quality_count) / 10 * 8, 8)
        # WoW 변화 (0-5점): 100% 증가 기준
        change_score = min(max(wow_change, 0) / 100 * 5, 5)
        # 출처 다양성 (0-5점): 5개 소스 기준
        diversity_score = min(float(unique_sources) / 5 * 5, 5)

        total_score = count_score + quality_score + change_score + diversity_score

        return {
            "score": round(total_score, 1),
            "7d_count": int(total_count),
            "quality_count": int(quality_count),
            "wow_change": wow_change,
            "source_diversity": int(unique_sources),
        }

    async def close(self):
        """리소스 정리."""
        if self._naver_client:
            await self._naver_client.close()
        if self._rss_client:
            self._rss_client.close()
