"""RSS 피드 파서 클라이언트."""
import logging
import re
import ssl
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
import asyncio
from concurrent.futures import ThreadPoolExecutor

import feedparser
import httpx

logger = logging.getLogger(__name__)

# SSL 레거시 재협상이 필요한 서버용 (연합뉴스 등)
_LEGACY_SSL_CTX: Optional[ssl.SSLContext] = None


def _get_legacy_ssl_ctx() -> ssl.SSLContext:
    """레거시 SSL 서버 호환 SSLContext 반환."""
    global _LEGACY_SSL_CTX
    if _LEGACY_SSL_CTX is None:
        ctx = ssl.create_default_context()
        ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        _LEGACY_SSL_CTX = ctx
    return _LEGACY_SSL_CTX


def _sanitize_xml(text: str) -> str:
    """XML에서 허용되지 않는 제어 문자 제거."""
    # XML 1.0 허용: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD]
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

# 기본 RSS 피드 소스
DEFAULT_RSS_FEEDS = {
    "mk": "https://www.mk.co.kr/rss/30000001/",  # 매경 증권
    "hankyung": "https://rss.hankyung.com/feed/stock.xml",  # 한경
    "edaily": "https://www.edaily.co.kr/rss/economy.xml",  # 이데일리
    "yna_economy": "https://www.yonhapnews.co.kr/RSS/economy.xml",  # 연합뉴스 경제
}


@dataclass
class RSSFeedItem:
    """RSS 피드 아이템."""
    title: str
    link: str
    description: str
    pub_date: Optional[datetime]
    source: str  # 피드 소스명 (mk, hankyung 등)


class RSSClient:
    """RSS 피드 파서 클라이언트."""

    def __init__(self, feeds: Optional[dict[str, str]] = None, timeout: float = 15.0):
        """
        Args:
            feeds: 피드 딕셔너리 {이름: URL}. None이면 기본 피드 사용.
            timeout: HTTP 요청 타임아웃
        """
        self.feeds = feeds or DEFAULT_RSS_FEEDS
        self.timeout = timeout
        self._executor = ThreadPoolExecutor(max_workers=4)

    def _parse_feed_sync(self, url: str) -> feedparser.FeedParserDict:
        """동기적으로 피드 파싱.

        httpx로 본문을 먼저 받아 제어 문자를 정리한 뒤 feedparser로 파싱.
        SSL 레거시 서버도 처리.
        """
        try:
            # 먼저 일반 SSL로 시도, 실패하면 레거시 SSL로 재시도
            try:
                resp = httpx.get(url, timeout=self.timeout, follow_redirects=True)
            except (httpx.ConnectError, Exception) as ssl_err:
                if "SSL" in str(ssl_err) or "legacy" in str(ssl_err).lower():
                    resp = httpx.get(
                        url, timeout=self.timeout, follow_redirects=True,
                        verify=_get_legacy_ssl_ctx(),
                    )
                else:
                    raise

            resp.raise_for_status()
            raw = resp.text
            cleaned = _sanitize_xml(raw)
            return feedparser.parse(cleaned)
        except Exception as e:
            logger.warning(f"RSS httpx 다운로드 실패 ({url}): {e}, feedparser 직접 시도")
            return feedparser.parse(url)

    def _parse_date(self, entry: dict) -> Optional[datetime]:
        """피드 엔트리에서 날짜 파싱."""
        # feedparser가 파싱한 구조화된 시간
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6])
            except Exception:
                pass

        if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            try:
                return datetime(*entry.updated_parsed[:6])
            except Exception:
                pass

        return None

    async def fetch_feed(self, source_name: str, url: str) -> list[RSSFeedItem]:
        """단일 RSS 피드 가져오기.

        Args:
            source_name: 소스 이름
            url: RSS 피드 URL

        Returns:
            피드 아이템 리스트
        """
        loop = asyncio.get_running_loop()

        try:
            # feedparser를 별도 스레드에서 실행
            feed = await loop.run_in_executor(
                self._executor,
                self._parse_feed_sync,
                url
            )
        except Exception as e:
            logger.error(f"RSS 피드 가져오기 실패 ({source_name}): {e}")
            return []

        if feed.bozo and not feed.entries:
            logger.warning(f"RSS 피드 파싱 오류 ({source_name}): {feed.bozo_exception}")
            return []

        items = []
        for entry in feed.entries:
            pub_date = self._parse_date(entry)

            items.append(RSSFeedItem(
                title=entry.get('title', '').strip(),
                link=entry.get('link', ''),
                description=entry.get('summary', entry.get('description', '')).strip(),
                pub_date=pub_date,
                source=source_name,
            ))

        logger.debug(f"RSS 피드 수집 완료: {source_name} - {len(items)}건")
        return items

    async def fetch_all_feeds(self) -> dict[str, list[RSSFeedItem]]:
        """모든 RSS 피드 동시에 가져오기.

        Returns:
            {소스명: [피드아이템, ...]} 딕셔너리
        """
        tasks = [
            self.fetch_feed(name, url)
            for name, url in self.feeds.items()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        feed_items = {}
        for (name, _), result in zip(self.feeds.items(), results):
            if isinstance(result, Exception):
                logger.error(f"피드 수집 예외 ({name}): {result}")
                feed_items[name] = []
            else:
                feed_items[name] = result

        total_items = sum(len(items) for items in feed_items.values())
        logger.info(f"RSS 피드 전체 수집 완료: {len(feed_items)}개 소스, 총 {total_items}건")

        return feed_items

    async def fetch_all_items(self) -> list[RSSFeedItem]:
        """모든 피드에서 아이템을 가져와 하나의 리스트로 반환."""
        feed_items = await self.fetch_all_feeds()
        all_items = []
        for items in feed_items.values():
            all_items.extend(items)
        return all_items

    def close(self):
        """리소스 정리."""
        self._executor.shutdown(wait=False)
