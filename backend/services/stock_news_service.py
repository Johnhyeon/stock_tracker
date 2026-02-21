"""종목별 뉴스 수집 서비스."""
import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from sqlalchemy.dialects.postgresql import insert

from core.timezone import now_kst
from models.stock_news import StockNews
from integrations.naver_search import NaverSearchClient
from core.config import get_settings
from services.news_collector_service import EXCLUDE_PATTERNS, QUALITY_KEYWORDS

logger = logging.getLogger(__name__)


class StockNewsService:
    """종목별 뉴스 수집 및 분석 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self._naver_client: Optional[NaverSearchClient] = None

    def _get_naver_client(self) -> Optional[NaverSearchClient]:
        if self._naver_client is None:
            if self.settings.naver_client_id and self.settings.naver_client_secret:
                self._naver_client = NaverSearchClient(
                    client_id=self.settings.naver_client_id,
                    client_secret=self.settings.naver_client_secret,
                )
            else:
                logger.warning("네이버 API 키가 설정되지 않았습니다")
        return self._naver_client

    def _should_exclude(self, title: str) -> bool:
        for pattern in EXCLUDE_PATTERNS:
            if re.search(pattern, title):
                return True
        return False

    def _is_quality(self, title: str, description: str = "") -> bool:
        text = f"{title} {description}".lower()
        for keyword in QUALITY_KEYWORDS:
            if keyword.lower() in text:
                return True
        return False

    async def collect_for_stocks(
        self,
        stock_codes: list[str],
        stock_names_map: dict[str, str],
        max_per_stock: int = 20,
    ) -> int:
        """네이버 API로 종목별 뉴스 검색 및 저장.

        Args:
            stock_codes: 수집 대상 종목 코드 리스트
            stock_names_map: {종목코드: 종목명} 매핑
            max_per_stock: 종목당 최대 수집 건수

        Returns:
            저장된 뉴스 건수
        """
        client = self._get_naver_client()
        if not client:
            return 0

        saved_count = 0

        for code in stock_codes:
            name = stock_names_map.get(code, "")
            if not name:
                continue

            try:
                items = await client.search_news(
                    query=f"{name} 주식",
                    display=max_per_stock,
                    sort="date",
                )

                for item in items:
                    if self._should_exclude(item.title):
                        continue

                    is_quality = self._is_quality(item.title, item.description)

                    published_at = item.pub_date
                    if published_at.tzinfo is not None:
                        published_at = published_at.replace(tzinfo=None)

                    url = item.original_link or item.link
                    stmt = insert(StockNews).values(
                        stock_code=code,
                        stock_name=name,
                        title=item.title[:500],
                        url=url[:1000],
                        source=self._extract_source(url),
                        published_at=published_at,
                        description=(item.description[:2000] if item.description else None),
                        is_quality=is_quality,
                        collection_source="naver_api",
                    ).on_conflict_do_nothing(index_elements=["url"])

                    result = await self.db.execute(stmt)
                    if result.rowcount > 0:
                        saved_count += 1

                await self.db.commit()

            except Exception as e:
                logger.error(f"종목 뉴스 수집 실패 ({code} {name}): {e}")
                await self.db.rollback()
                continue

        logger.info(f"종목별 뉴스 수집 완료: {len(stock_codes)}종목, {saved_count}건 저장")
        return saved_count

    def _extract_source(self, url: str) -> str:
        """URL에서 언론사명 추출."""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            source_map = {
                "mk.co.kr": "매일경제",
                "hankyung.com": "한국경제",
                "edaily.co.kr": "이데일리",
                "mt.co.kr": "머니투데이",
                "sedaily.com": "서울경제",
                "biz.chosun.com": "조선비즈",
                "news.heraldcorp.com": "헤럴드경제",
                "newsis.com": "뉴시스",
                "yna.co.kr": "연합뉴스",
                "fnnews.com": "파이낸셜뉴스",
                "infostock.co.kr": "인포스탁",
                "thebell.co.kr": "더벨",
            }
            for key, name in source_map.items():
                if key in domain:
                    return name
            return domain
        except Exception:
            return "unknown"

    async def classify_catalysts(self, limit: int = 50) -> int:
        """미분류 뉴스를 Gemini로 일괄 분류.

        Returns:
            분류된 뉴스 건수
        """
        from integrations.gemini.client import get_gemini_client

        gemini = get_gemini_client()
        if not gemini.is_configured:
            logger.warning("Gemini API 미설정, 뉴스 분류 스킵")
            return 0

        # 미분류 뉴스 조회
        stmt = (
            select(StockNews)
            .where(StockNews.catalyst_type.is_(None))
            .order_by(desc(StockNews.published_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        news_list = result.scalars().all()

        if not news_list:
            return 0

        classified = 0

        # 10건씩 배치
        for i in range(0, len(news_list), 10):
            batch = news_list[i:i + 10]
            items = [
                {
                    "title": n.title,
                    "description": (n.description or "")[:200],
                    "stock_name": n.stock_name or "",
                }
                for n in batch
            ]

            try:
                results = await gemini.classify_news_catalysts(items)
                if results:
                    for j, r in enumerate(results):
                        if j < len(batch):
                            batch[j].catalyst_type = r.get("catalyst_type", "other")
                            batch[j].importance = r.get("importance", "low")
                            classified += 1
                    await self.db.commit()
            except Exception as e:
                logger.error(f"뉴스 분류 실패 (batch {i}): {e}")
                await self.db.rollback()

        logger.info(f"뉴스 분류 완료: {classified}/{len(news_list)}건")
        return classified

    async def get_stock_news(
        self,
        stock_code: str,
        days: int = 7,
        limit: int = 20,
    ) -> list[dict]:
        """종목별 최근 뉴스 조회."""
        since = now_kst().replace(tzinfo=None) - timedelta(days=days)
        stmt = (
            select(StockNews)
            .where(
                and_(
                    StockNews.stock_code == stock_code,
                    StockNews.published_at >= since,
                )
            )
            .order_by(desc(StockNews.published_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        news = result.scalars().all()

        return [
            {
                "id": str(n.id),
                "title": n.title,
                "url": n.url,
                "source": n.source,
                "published_at": n.published_at.isoformat(),
                "catalyst_type": n.catalyst_type,
                "importance": n.importance,
                "is_quality": n.is_quality,
            }
            for n in news
        ]

    async def get_catalyst_summary(
        self,
        stock_code: str,
        days: int = 14,
    ) -> dict:
        """종목별 재료 요약 (type별 건수, 최근 주요 뉴스)."""
        since = now_kst().replace(tzinfo=None) - timedelta(days=days)

        # 유형별 건수
        type_stmt = (
            select(
                StockNews.catalyst_type,
                func.count(StockNews.id).label("count"),
            )
            .where(
                and_(
                    StockNews.stock_code == stock_code,
                    StockNews.published_at >= since,
                    StockNews.catalyst_type.isnot(None),
                )
            )
            .group_by(StockNews.catalyst_type)
        )
        type_result = await self.db.execute(type_stmt)
        type_counts = {row[0]: row[1] for row in type_result.fetchall()}

        # 최근 주요(high importance) 뉴스
        important_stmt = (
            select(StockNews)
            .where(
                and_(
                    StockNews.stock_code == stock_code,
                    StockNews.published_at >= since,
                    StockNews.importance == "high",
                )
            )
            .order_by(desc(StockNews.published_at))
            .limit(5)
        )
        important_result = await self.db.execute(important_stmt)
        important_news = important_result.scalars().all()

        # 전체 건수
        total_stmt = (
            select(func.count(StockNews.id))
            .where(
                and_(
                    StockNews.stock_code == stock_code,
                    StockNews.published_at >= since,
                )
            )
        )
        total_result = await self.db.execute(total_stmt)
        total_count = total_result.scalar() or 0

        return {
            "stock_code": stock_code,
            "days": days,
            "total_count": total_count,
            "type_counts": type_counts,
            "important_news": [
                {
                    "title": n.title,
                    "url": n.url,
                    "catalyst_type": n.catalyst_type,
                    "published_at": n.published_at.isoformat(),
                }
                for n in important_news
            ],
        }

    async def get_hot_stocks_by_news(self, limit: int = 30, days: int = 3) -> list[dict]:
        """뉴스가 많은 종목 순위."""
        since = now_kst().replace(tzinfo=None) - timedelta(days=days)

        from sqlalchemy import case, Integer
        stmt = (
            select(
                StockNews.stock_code,
                StockNews.stock_name,
                func.count(StockNews.id).label("news_count"),
                func.sum(case((StockNews.is_quality == True, 1), else_=0)).label("quality_count"),
            )
            .where(StockNews.published_at >= since)
            .group_by(StockNews.stock_code, StockNews.stock_name)
            .order_by(desc("news_count"))
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = result.fetchall()

        return [
            {
                "stock_code": row.stock_code,
                "stock_name": row.stock_name,
                "news_count": row.news_count,
                "quality_count": row.quality_count or 0,
            }
            for row in rows
        ]

    async def close(self):
        if self._naver_client:
            await self._naver_client.close()
