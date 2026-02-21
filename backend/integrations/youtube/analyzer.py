"""YouTube 영상 종목 언급 분석."""
import re
import logging
from typing import Optional

from sqlalchemy import select

from models import Stock

logger = logging.getLogger(__name__)


class StockMentionAnalyzer:
    """영상에서 종목 언급을 추출하는 분석기.

    제목과 설명에서 종목명/종목코드를 찾아 매칭합니다.
    """

    def __init__(self):
        self._stock_cache: Optional[dict[str, str]] = None  # name -> code
        self._stock_codes: Optional[set[str]] = None  # code set

    async def load_stock_cache_async(self, db) -> None:
        """비동기로 종목 캐시 로딩."""
        result = await db.execute(select(Stock))
        stocks = result.scalars().all()
        self._stock_cache = {}
        self._stock_codes = set()
        for stock in stocks:
            self._stock_cache[stock.name] = stock.code
            self._stock_codes.add(stock.code)
            # 종목명에서 "보통주", "우선주" 등 제거한 버전도 추가
            clean_name = re.sub(r'(보통주|우선주|1우B|2우B|우B)$', '', stock.name).strip()
            if clean_name != stock.name:
                self._stock_cache[clean_name] = stock.code

    @property
    def stock_map(self) -> dict[str, str]:
        """종목명 -> 종목코드 매핑 캐시."""
        if self._stock_cache is None:
            raise RuntimeError("Stock cache not loaded. Call load_stock_cache_async() first.")
        return self._stock_cache

    @property
    def stock_codes(self) -> set[str]:
        """종목코드 세트 캐시."""
        if self._stock_codes is None:
            raise RuntimeError("Stock cache not loaded. Call load_stock_cache_async() first.")
        return self._stock_codes

    def extract_mentions(
        self,
        title: str,
        description: Optional[str] = None,
    ) -> tuple[list[str], str]:
        """영상에서 종목 언급 추출.

        Args:
            title: 영상 제목
            description: 영상 설명

        Returns:
            (종목코드 리스트, 언급 맥락 텍스트)
        """
        text = f"{title} {description or ''}"
        mentioned_codes = set()
        contexts = []

        # 1. 종목코드 패턴 매칭 (6자리 숫자)
        code_pattern = r'\b(\d{6})\b'
        for match in re.finditer(code_pattern, text):
            code = match.group(1)
            # 캐시된 코드 세트로 확인 (DB 조회 제거)
            if code in self.stock_codes:
                mentioned_codes.add(code)
                # 주변 맥락 추출
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 20)
                contexts.append(text[start:end].strip())

        # 2. 종목명 매칭
        # 긴 이름부터 매칭하여 부분 매칭 방지
        sorted_names = sorted(self.stock_map.keys(), key=len, reverse=True)
        for name in sorted_names:
            if name in text and len(name) >= 2:  # 최소 2글자
                code = self.stock_map[name]
                if code not in mentioned_codes:
                    mentioned_codes.add(code)
                    # 주변 맥락 추출
                    idx = text.find(name)
                    start = max(0, idx - 20)
                    end = min(len(text), idx + len(name) + 20)
                    contexts.append(text[start:end].strip())

        # 맥락 텍스트 합치기 (중복 제거)
        unique_contexts = list(dict.fromkeys(contexts))
        context_text = " | ".join(unique_contexts[:5])  # 최대 5개

        return list(mentioned_codes), context_text

    def analyze_video(self, video: dict) -> dict:
        """영상 분석 결과 반환.

        Args:
            video: 영상 정보 dict

        Returns:
            {
                "video_id": "...",
                "mentioned_tickers": ["005930", "000660"],
                "ticker_context": "삼성전자 실적 발표...",
                ...
            }
        """
        title = video.get("title", "")
        description = video.get("description", "")

        tickers, context = self.extract_mentions(title, description)

        return {
            **video,
            "mentioned_tickers": tickers,
            "ticker_context": context,
        }

    def analyze_videos(self, videos: list[dict]) -> list[dict]:
        """여러 영상 일괄 분석.

        Args:
            videos: 영상 목록

        Returns:
            분석 결과가 추가된 영상 목록 (종목 언급이 있는 것만)
        """
        results = []
        for video in videos:
            analyzed = self.analyze_video(video)
            # 종목 언급이 있는 영상만 포함
            if analyzed.get("mentioned_tickers"):
                results.append(analyzed)
        return results
