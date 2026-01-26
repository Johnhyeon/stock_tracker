"""네이버 검색 API 클라이언트."""
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
import html

from integrations.base_client import BaseAPIClient

logger = logging.getLogger(__name__)


@dataclass
class NaverNewsItem:
    """네이버 뉴스 검색 결과 아이템."""
    title: str
    link: str
    description: str
    pub_date: datetime
    original_link: str


class NaverSearchClient(BaseAPIClient):
    """네이버 검색 API 클라이언트.

    API 문서: https://developers.naver.com/docs/serviceapi/search/news/news.md
    하루 25,000건 무료.
    """

    def __init__(self, client_id: str, client_secret: str):
        super().__init__(
            base_url="https://openapi.naver.com",
            rate_limit=10.0,  # 초당 10회 제한
            timeout=10.0,
        )
        self.client_id = client_id
        self.client_secret = client_secret

    def get_headers(self) -> dict[str, str]:
        return {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }

    def _clean_html(self, text: str) -> str:
        """HTML 태그와 엔티티 제거."""
        import re
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', text)
        # HTML 엔티티 디코드
        text = html.unescape(text)
        return text.strip()

    def _parse_pub_date(self, date_str: str) -> Optional[datetime]:
        """네이버 API 날짜 형식 파싱.

        예: "Tue, 21 Jan 2025 10:30:00 +0900"
        """
        try:
            # RFC 2822 형식
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except Exception as e:
            logger.warning(f"날짜 파싱 실패: {date_str} - {e}")
            return None

    async def search_news(
        self,
        query: str,
        display: int = 100,
        start: int = 1,
        sort: str = "date",
    ) -> list[NaverNewsItem]:
        """뉴스 검색.

        Args:
            query: 검색어
            display: 결과 개수 (최대 100)
            start: 시작 위치 (1-1000)
            sort: 정렬 (sim: 정확도, date: 날짜순)

        Returns:
            뉴스 아이템 리스트
        """
        params = {
            "query": query,
            "display": min(display, 100),
            "start": start,
            "sort": sort,
        }

        try:
            data = await self.get("/v1/search/news.json", params=params)
        except Exception as e:
            logger.error(f"네이버 뉴스 검색 실패 (query={query}): {e}")
            return []

        items = []
        for item in data.get("items", []):
            pub_date = self._parse_pub_date(item.get("pubDate", ""))
            if pub_date is None:
                continue

            items.append(NaverNewsItem(
                title=self._clean_html(item.get("title", "")),
                link=item.get("link", ""),
                description=self._clean_html(item.get("description", "")),
                pub_date=pub_date,
                original_link=item.get("originallink", item.get("link", "")),
            ))

        logger.debug(f"네이버 뉴스 검색 완료: query={query}, 결과={len(items)}건")
        return items

    async def search_news_by_keywords(
        self,
        keywords: list[str],
        max_per_keyword: int = 50,
    ) -> dict[str, list[NaverNewsItem]]:
        """여러 키워드로 뉴스 검색.

        Args:
            keywords: 검색 키워드 목록
            max_per_keyword: 키워드당 최대 결과 수

        Returns:
            {키워드: [뉴스아이템, ...]} 딕셔너리
        """
        results = {}
        for keyword in keywords:
            items = await self.search_news(keyword, display=max_per_keyword)
            results[keyword] = items
        return results
