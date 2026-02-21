"""YouTube 클라이언트 (yt-dlp 기반).

API 할당량 제한 없이 YouTube 데이터를 수집합니다.
"""
import logging
import random
from typing import Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import yt_dlp

from core.timezone import now_kst

logger = logging.getLogger(__name__)


class YouTubeClient:
    """yt-dlp 기반 YouTube 클라이언트.

    지원 기능:
    - 키워드 검색 (섹터별, 시간별, 분석유형별, 뉴스별)
    - 인기 채널 크롤링
    - 영상 상세 정보 조회
    """

    # ========== 1. 섹터별 키워드 ==========
    SECTOR_KEYWORDS = [
        # 핫 섹터
        "반도체 주식", "반도체 관련주",
        "2차전지 주식", "배터리 관련주",
        "AI 주식", "AI 관련주", "인공지능 주식",
        "로봇 주식", "로봇 관련주",
        "바이오 주식", "제약 관련주",
        "방산 주식", "방위산업 관련주",
        "조선 주식", "조선 관련주",
        "원전 주식", "원자력 관련주",
        # 전통 섹터
        "자동차 주식", "전기차 관련주",
        "금융주", "은행주",
        "건설주", "부동산 관련주",
        "화학주", "정유주",
        "철강주", "소재주",
        # 성장 섹터
        "게임주", "엔터주",
        "플랫폼 주식", "IT 주식",
        "헬스케어 주식", "의료기기 주식",
        "친환경 주식", "태양광 관련주",
        "우주항공 주식", "드론 관련주",
    ]

    # ========== 2. 시간/트렌드 키워드 ==========
    TIME_KEYWORDS = [
        # 일간
        "오늘 급등주", "오늘 주식",
        "내일 급등주", "내일 주식 전망",
        "장 마감 분석", "장 마감 후 주식",
        "장 시작 전 주식", "프리마켓 분석",
        # 주간
        "이번주 급등주", "이번주 주식",
        "주간 증시 전망", "주간 주식 리뷰",
        # 월간/분기
        "월간 주식 전망", "분기 실적 주식",
        # 트렌드
        "핫한 주식", "뜨는 주식",
        "지금 사야할 주식", "놓치면 안되는 주식",
        "숨은 급등주", "저평가 주식",
    ]

    # ========== 3. 분석 유형 키워드 ==========
    ANALYSIS_KEYWORDS = [
        # 기술적 분석
        "주식 차트 분석", "기술적 분석",
        "캔들 분석", "이동평균선",
        "볼린저밴드", "RSI 분석",
        "지지선 저항선", "추세선 분석",
        # 수급 분석
        "수급 분석", "거래량 분석",
        "외국인 매수", "외국인 순매수",
        "기관 매수", "기관 순매수",
        "개인 매수", "개인투자자",
        # 가치 분석
        "저PER 주식", "저PBR 주식",
        "고배당주", "배당주 추천",
        "실적 좋은 주식", "흑자 전환 주식",
        # 특수 상황
        "공매도 주식", "공매도 잔고",
        "신고가 주식", "52주 신고가",
        "거래량 급증", "이상 급등",
        "상한가", "하한가",
    ]

    # ========== 4. 뉴스/이슈 키워드 ==========
    NEWS_KEYWORDS = [
        # 경제 뉴스
        "주식 뉴스", "증시 뉴스",
        "경제 이슈 주식", "금융 뉴스",
        # 정책/금리
        "금리 인상 주식", "금리 인하 수혜주",
        "정부 정책 주식", "규제 완화 주식",
        # 글로벌
        "미국 증시 영향", "나스닥 관련주",
        "중국 관련주", "환율 영향 주식",
        "유가 관련주", "원자재 관련주",
        # 이벤트
        "실적 발표 주식", "어닝 시즌",
        "IPO 주식", "신규 상장",
        "인수합병 주식", "M&A 관련주",
        "자사주 매입", "액면분할",
    ]

    # ========== 5. 일반 키워드 (기존) ==========
    GENERAL_KEYWORDS = [
        "주식 추천", "종목 추천",
        "급등주", "급등주 추천",
        "종목 분석", "주식 분석",
        "주식 전망", "증시 전망",
        "오늘의 주식", "주식 리뷰",
        "주식 투자", "주식 공부",
        "주도주", "대장주",
        "테마주", "소외주",
        "가치주", "성장주",
        "단타 종목", "스윙 종목",
    ]

    # ========== 6. 인기 주식 유튜브 채널 ==========
    # 채널 핸들 또는 이름으로 검색 (채널 ID보다 찾기 쉬움)
    POPULAR_CHANNELS = [
        # 대형 채널
        ("삼프로TV", "@3proTV"),
        ("슈카월드", "@syukaworld"),
        ("신사임당", "@sdandmt"),
        ("김작가TV", "@kimwritertv"),
        ("월급쟁이부자들", "@wealthyemployees"),
        # 주식 전문 채널
        ("염승환의 시그널", "@signaleom"),
        ("주코노미TV", "@juconomy"),
        ("이효석아카데미", "@hyoseok"),
        ("박곰희TV", "@parkgomhee"),
        ("주식하는 좀비", "@stockzombie"),
        # 증권사/기관
        ("한국경제TV", "@wowtv"),
        ("이데일리", "@edaily_tv"),
        ("머니투데이", "@maboroshi"),
        ("매일경제TV", "@maboroshi"),
        ("토스증권", "@toss_invest"),
        # 분석 채널
        ("차트의정석", "@chartmaster"),
        ("미주부", "@mijubu"),
        ("소수몽키", "@sosumonkey"),
        ("내일은 주식왕", "@stockking"),
        ("주린이탈출기", "@julini_escape"),
    ]

    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'ignoreerrors': True,
        }

    def _get_video_info(self, video_id: str) -> Optional[dict]:
        """영상 상세 정보 조회."""
        opts = {
            **self.ydl_opts,
            'extract_flat': False,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(
                    f'https://www.youtube.com/watch?v={video_id}',
                    download=False
                )
                if info:
                    return self._parse_video_info(info)
        except Exception as e:
            logger.debug(f"Failed to get video info for {video_id}: {e}")
        return None

    def _parse_video_info(self, info: dict) -> dict:
        """yt-dlp 결과를 표준 형식으로 변환."""
        # 업로드 날짜 파싱
        upload_date = info.get('upload_date', '')
        if upload_date:
            try:
                published_at = datetime.strptime(upload_date, '%Y%m%d').isoformat() + 'Z'
            except:
                published_at = now_kst().isoformat()
        else:
            published_at = now_kst().isoformat()

        # 썸네일 URL
        thumbnails = info.get('thumbnails', [])
        thumbnail_url = None
        if thumbnails:
            for t in reversed(thumbnails):
                if t.get('url'):
                    thumbnail_url = t['url']
                    break

        return {
            'video_id': info.get('id', ''),
            'title': info.get('title', ''),
            'description': info.get('description', '') or '',
            'channel_id': info.get('channel_id', ''),
            'channel_title': info.get('channel', '') or info.get('uploader', ''),
            'published_at': published_at,
            'view_count': info.get('view_count', 0) or 0,
            'like_count': info.get('like_count', 0) or 0,
            'comment_count': info.get('comment_count', 0) or 0,
            'duration': self._format_duration(info.get('duration', 0)),
            'thumbnail_url': thumbnail_url,
        }

    def _format_duration(self, seconds: Optional[int]) -> str:
        """초를 ISO 8601 duration으로 변환."""
        if not seconds:
            return 'PT0S'
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f'PT{hours}H{minutes}M{secs}S'
        elif minutes:
            return f'PT{minutes}M{secs}S'
        return f'PT{secs}S'

    async def search_videos(
        self,
        query: str,
        max_results: int = 10,
        published_after: Optional[datetime] = None,
    ) -> list[dict]:
        """키워드로 영상 검색."""
        videos = []

        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                result = ydl.extract_info(
                    f'ytsearch{max_results * 2}:{query}',
                    download=False
                )

                entries = result.get('entries', []) if result else []
                video_ids = [e.get('id') for e in entries if e and e.get('id')]

                with ThreadPoolExecutor(max_workers=5) as executor:
                    video_infos = list(executor.map(self._get_video_info, video_ids[:max_results]))

                for info in video_infos:
                    if info:
                        if published_after:
                            try:
                                video_date = datetime.fromisoformat(
                                    info['published_at'].replace('Z', '+00:00')
                                ).replace(tzinfo=None)
                                if video_date < published_after:
                                    continue
                            except:
                                pass
                        videos.append(info)

                        if len(videos) >= max_results:
                            break

        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")

        return videos

    async def search_channel_videos(
        self,
        channel_handle: str,
        max_results: int = 10,
        published_after: Optional[datetime] = None,
    ) -> list[dict]:
        """채널 핸들로 최근 영상 검색."""
        videos = []

        opts = {
            **self.ydl_opts,
            'playlistend': max_results * 2,
        }

        try:
            # @handle 형식 또는 채널명으로 검색
            url = f'https://www.youtube.com/{channel_handle}/videos'
            with yt_dlp.YoutubeDL(opts) as ydl:
                result = ydl.extract_info(url, download=False)

                if result and result.get('entries'):
                    video_ids = [
                        e.get('id') for e in result['entries']
                        if e and e.get('id')
                    ][:max_results]

                    with ThreadPoolExecutor(max_workers=5) as executor:
                        video_infos = list(executor.map(self._get_video_info, video_ids))

                    for info in video_infos:
                        if info:
                            if published_after:
                                try:
                                    video_date = datetime.fromisoformat(
                                        info['published_at'].replace('Z', '+00:00')
                                    ).replace(tzinfo=None)
                                    if video_date < published_after:
                                        continue
                                except:
                                    pass
                            videos.append(info)

        except Exception as e:
            logger.debug(f"Failed to get channel videos for {channel_handle}: {e}")

        return videos

    def get_all_keywords(self, sample_per_category: Optional[int] = None) -> list[str]:
        """모든 카테고리의 키워드 반환.

        Args:
            sample_per_category: 각 카테고리에서 샘플링할 개수 (None이면 전체)
        """
        categories = [
            self.SECTOR_KEYWORDS,
            self.TIME_KEYWORDS,
            self.ANALYSIS_KEYWORDS,
            self.NEWS_KEYWORDS,
            self.GENERAL_KEYWORDS,
        ]

        all_keywords = []
        for category in categories:
            if sample_per_category and len(category) > sample_per_category:
                all_keywords.extend(random.sample(category, sample_per_category))
            else:
                all_keywords.extend(category)

        return all_keywords

    async def search_stock_videos(
        self,
        max_results_per_keyword: int = 5,
        published_after: Optional[datetime] = None,
        include_channels: bool = True,
        sample_keywords: Optional[int] = None,
    ) -> list[dict]:
        """종합 주식 영상 검색 (키워드 + 채널).

        Args:
            max_results_per_keyword: 키워드/채널당 최대 결과 수
            published_after: 이 시점 이후 영상만
            include_channels: 인기 채널 수집 포함 여부
            sample_keywords: 각 카테고리에서 샘플링할 키워드 수 (None이면 전체)

        Returns:
            영상 목록 (중복 제거됨)
        """
        all_videos = []
        seen_video_ids = set()

        # 1. 키워드 기반 검색
        keywords = self.get_all_keywords(sample_per_category=sample_keywords)
        logger.info(f"Searching with {len(keywords)} keywords...")

        for i, keyword in enumerate(keywords):
            try:
                videos = await self.search_videos(
                    query=keyword,
                    max_results=max_results_per_keyword,
                    published_after=published_after,
                )
                new_count = 0
                for v in videos:
                    vid = v.get('video_id')
                    if vid and vid not in seen_video_ids:
                        seen_video_ids.add(vid)
                        all_videos.append(v)
                        new_count += 1

                if new_count > 0:
                    logger.info(f"[{i+1}/{len(keywords)}] '{keyword}': +{new_count} videos")
            except Exception as e:
                logger.error(f"Failed to search for '{keyword}': {e}")

        # 2. 인기 채널 크롤링
        if include_channels:
            logger.info(f"Crawling {len(self.POPULAR_CHANNELS)} popular channels...")

            for name, handle in self.POPULAR_CHANNELS:
                try:
                    videos = await self.search_channel_videos(
                        channel_handle=handle,
                        max_results=max_results_per_keyword,
                        published_after=published_after,
                    )
                    new_count = 0
                    for v in videos:
                        vid = v.get('video_id')
                        if vid and vid not in seen_video_ids:
                            seen_video_ids.add(vid)
                            all_videos.append(v)
                            new_count += 1

                    if new_count > 0:
                        logger.info(f"Channel '{name}': +{new_count} videos")
                except Exception as e:
                    logger.debug(f"Failed to crawl channel '{name}': {e}")

        logger.info(f"Total collected: {len(all_videos)} unique videos")
        return all_videos

    async def search_by_tickers(
        self,
        tickers: list[str],
        max_results_per_ticker: int = 5,
        published_after: Optional[datetime] = None,
    ) -> list[dict]:
        """여러 종목명으로 검색."""
        all_videos = []
        seen_video_ids = set()

        for ticker in tickers:
            try:
                query = f"{ticker} 주식"
                videos = await self.search_videos(
                    query=query,
                    max_results=max_results_per_ticker,
                    published_after=published_after,
                )
                for v in videos:
                    vid = v.get('video_id')
                    if vid and vid not in seen_video_ids:
                        seen_video_ids.add(vid)
                        all_videos.append(v)

                logger.info(f"Searched '{ticker}': {len(videos)} videos")
            except Exception as e:
                logger.error(f"Failed to search for '{ticker}': {e}")

        return all_videos

    async def get_video_details(self, video_ids: list[str]) -> list[dict]:
        """영상 상세 정보 일괄 조회."""
        videos = []

        with ThreadPoolExecutor(max_workers=5) as executor:
            video_infos = list(executor.map(self._get_video_info, video_ids))

        for info in video_infos:
            if info:
                videos.append(info)

        return videos

    async def get_channel_videos(
        self,
        channel_id: str,
        max_results: int = 20,
        published_after: Optional[datetime] = None,
    ) -> list[dict]:
        """채널의 최근 영상 목록 조회."""
        videos = []

        opts = {
            **self.ydl_opts,
            'playlistend': max_results * 2,
        }

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                result = ydl.extract_info(
                    f'https://www.youtube.com/channel/{channel_id}/videos',
                    download=False
                )

                if result and result.get('entries'):
                    video_ids = [
                        e.get('id') for e in result['entries']
                        if e and e.get('id')
                    ][:max_results]

                    with ThreadPoolExecutor(max_workers=5) as executor:
                        video_infos = list(executor.map(self._get_video_info, video_ids))

                    for info in video_infos:
                        if info:
                            if published_after:
                                try:
                                    video_date = datetime.fromisoformat(
                                        info['published_at'].replace('Z', '+00:00')
                                    ).replace(tzinfo=None)
                                    if video_date < published_after:
                                        continue
                                except:
                                    pass
                            videos.append(info)

        except Exception as e:
            logger.error(f"Failed to get channel videos for {channel_id}: {e}")

        return videos

    async def get_videos_from_channels(
        self,
        max_results_per_channel: int = 10,
        published_after: Optional[datetime] = None,
    ) -> list[dict]:
        """설정된 모든 채널에서 영상 수집."""
        return await self.search_stock_videos(
            max_results_per_keyword=max_results_per_channel,
            published_after=published_after,
        )

    # ========== 빠른 수집 모드 ==========
    async def quick_collect(
        self,
        published_after: Optional[datetime] = None,
    ) -> list[dict]:
        """빠른 수집 (샘플링된 키워드 + 주요 채널만).

        각 카테고리에서 5개씩 샘플링하여 빠르게 수집합니다.
        """
        return await self.search_stock_videos(
            max_results_per_keyword=3,
            published_after=published_after,
            include_channels=True,
            sample_keywords=5,  # 각 카테고리에서 5개씩만
        )

    async def full_collect(
        self,
        published_after: Optional[datetime] = None,
    ) -> list[dict]:
        """전체 수집 (모든 키워드 + 모든 채널).

        모든 키워드와 채널에서 최대한 수집합니다.
        시간이 오래 걸릴 수 있습니다.
        """
        return await self.search_stock_videos(
            max_results_per_keyword=5,
            published_after=published_after,
            include_channels=True,
            sample_keywords=None,  # 전체 키워드
        )


# 싱글톤 인스턴스
_youtube_client: Optional[YouTubeClient] = None


def get_youtube_client() -> YouTubeClient:
    """YouTube 클라이언트 싱글톤 반환."""
    global _youtube_client
    if _youtube_client is None:
        _youtube_client = YouTubeClient()
    return _youtube_client
