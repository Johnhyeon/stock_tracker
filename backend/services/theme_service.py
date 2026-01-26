"""테마 순환매 분석 서비스."""
import json
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from models import TraderMention, Stock

logger = logging.getLogger(__name__)

THEME_MAP_PATH = Path(__file__).parent.parent / "data" / "theme_map.json"


class ThemeService:
    """테마 순환매 분석 서비스."""

    def __init__(self, db: Session):
        self.db = db
        self._theme_map: dict[str, list[dict]] = {}
        self._stock_to_themes: dict[str, list[str]] = {}
        self._load_theme_map()

    def _load_theme_map(self):
        """테마 맵 로드 및 역매핑 생성."""
        try:
            with open(THEME_MAP_PATH, "r", encoding="utf-8") as f:
                self._theme_map = json.load(f)

            # 종목코드 -> 테마 역매핑 생성
            for theme_name, stocks in self._theme_map.items():
                for stock in stocks:
                    code = stock.get("code")
                    if code:
                        if code not in self._stock_to_themes:
                            self._stock_to_themes[code] = []
                        self._stock_to_themes[code].append(theme_name)

            logger.info(
                f"Loaded {len(self._theme_map)} themes, "
                f"{len(self._stock_to_themes)} stock mappings"
            )
        except Exception as e:
            logger.error(f"Failed to load theme map: {e}")

    def get_themes_for_stock(self, stock_code: str) -> list[str]:
        """종목이 속한 테마 목록 반환."""
        return self._stock_to_themes.get(stock_code, [])

    def get_stocks_in_theme(self, theme_name: str) -> list[dict]:
        """테마에 속한 종목 목록 반환."""
        return self._theme_map.get(theme_name, [])

    def analyze_theme_rotation(
        self,
        youtube_data: list[dict],
        trader_data: list[dict],
        days: int = 7,
    ) -> dict:
        """테마 순환매 분석.

        Args:
            youtube_data: YouTube 언급 데이터
            trader_data: 트레이더 언급 데이터
            days: 분석 기간

        Returns:
            {
                "hot_themes": [...],  # 현재 핫한 테마
                "theme_details": {...},  # 테마별 상세 정보
                "rotation_flow": [...],  # 순환매 흐름
                "summary": {...},  # 요약 통계
            }
        """
        # 테마별 점수 집계
        theme_scores = defaultdict(lambda: {
            "youtube_mentions": 0,
            "youtube_stocks": set(),
            "trader_mentions": 0,
            "trader_stocks": set(),
            "total_volume": 0,
            "avg_price_change": [],
            "stocks_detail": [],
        })

        # YouTube 데이터에서 테마 매핑
        for stock in youtube_data:
            stock_code = stock.get("stock_code")
            if not stock_code:
                continue

            themes = self.get_themes_for_stock(stock_code)
            mentions = stock.get("recent_mentions", 0)
            volume = stock.get("volume") or 0
            price_change = stock.get("price_change_rate") or 0

            for theme in themes:
                theme_scores[theme]["youtube_mentions"] += mentions
                theme_scores[theme]["youtube_stocks"].add(stock_code)
                theme_scores[theme]["total_volume"] += volume
                theme_scores[theme]["avg_price_change"].append(price_change)
                theme_scores[theme]["stocks_detail"].append({
                    "code": stock_code,
                    "name": stock.get("stock_name"),
                    "source": "youtube",
                    "mentions": mentions,
                    "price_change": price_change,
                    "volume": volume,
                })

        # 트레이더 데이터에서 테마 매핑
        for stock in trader_data:
            stock_code = stock.get("stock_code")
            if not stock_code:
                continue

            themes = self.get_themes_for_stock(stock_code)
            mentions = stock.get("mention_count", 0)
            volume = stock.get("volume") or 0
            price_change = stock.get("price_change_rate") or 0

            for theme in themes:
                theme_scores[theme]["trader_mentions"] += mentions
                theme_scores[theme]["trader_stocks"].add(stock_code)
                if stock_code not in theme_scores[theme]["youtube_stocks"]:
                    theme_scores[theme]["total_volume"] += volume
                    theme_scores[theme]["avg_price_change"].append(price_change)
                theme_scores[theme]["stocks_detail"].append({
                    "code": stock_code,
                    "name": stock.get("stock_name"),
                    "source": "trader",
                    "mentions": mentions,
                    "price_change": price_change,
                    "volume": volume,
                })

        # 테마 점수 계산 및 정렬
        theme_results = []
        for theme_name, data in theme_scores.items():
            # 유니크 종목 수
            all_stocks = data["youtube_stocks"] | data["trader_stocks"]
            stock_count = len(all_stocks)

            if stock_count == 0:
                continue

            # 평균 주가 변동률
            avg_change = (
                sum(data["avg_price_change"]) / len(data["avg_price_change"])
                if data["avg_price_change"]
                else 0
            )

            # 종합 점수 계산
            # 언급 점수 (40%) + 종목 수 (20%) + 주가 상승률 (25%) + 거래량 (15%)
            mention_score = min(
                (data["youtube_mentions"] + data["trader_mentions"] * 2) / 50 * 40,
                40
            )
            stock_score = min(stock_count / 5 * 20, 20)
            price_score = max(min(avg_change / 5 * 25, 25), 0)
            volume_score = min(
                (data["total_volume"] / 10_000_000) * 15,
                15
            ) if data["total_volume"] > 0 else 0

            total_score = mention_score + stock_score + price_score + volume_score

            # 중복 제거된 종목 상세
            unique_stocks = {}
            for s in data["stocks_detail"]:
                code = s["code"]
                if code not in unique_stocks:
                    unique_stocks[code] = s
                else:
                    # 같은 종목이면 source 합치기
                    existing = unique_stocks[code]
                    if existing["source"] != s["source"]:
                        existing["source"] = "both"
                    existing["mentions"] = max(existing["mentions"], s["mentions"])

            theme_results.append({
                "theme_name": theme_name,
                "total_score": round(total_score, 1),
                "stock_count": stock_count,
                "youtube_mentions": data["youtube_mentions"],
                "trader_mentions": data["trader_mentions"],
                "avg_price_change": round(avg_change, 2),
                "total_volume": data["total_volume"],
                "stocks": list(unique_stocks.values())[:10],  # 상위 10개만
            })

        # 점수 순 정렬
        theme_results.sort(key=lambda x: x["total_score"], reverse=True)

        # 상위 테마 추출
        hot_themes = theme_results[:15]

        # 테마 카테고리 분류
        categories = self._categorize_themes(hot_themes)

        return {
            "hot_themes": hot_themes,
            "theme_count": len(theme_results),
            "categories": categories,
            "analyzed_at": datetime.now().isoformat(),
            "summary": {
                "total_themes_detected": len(theme_results),
                "top_theme": hot_themes[0]["theme_name"] if hot_themes else None,
                "avg_theme_score": round(
                    sum(t["total_score"] for t in theme_results) / len(theme_results),
                    1
                ) if theme_results else 0,
            }
        }

    def _categorize_themes(self, themes: list[dict]) -> dict[str, list[dict]]:
        """테마를 카테고리로 분류."""
        categories = {
            "tech": [],  # IT/반도체/AI
            "bio": [],   # 바이오/제약
            "energy": [],  # 에너지/2차전지
            "defense": [],  # 방산/우주
            "finance": [],  # 금융/부동산
            "consumer": [],  # 소비재/유통
            "industrial": [],  # 산업재/건설
            "other": [],  # 기타
        }

        category_keywords = {
            "tech": ["반도체", "AI", "IT", "소프트웨어", "클라우드", "데이터", "로봇",
                    "자율주행", "스마트", "메타버스", "AR", "VR", "5G", "6G", "통신"],
            "bio": ["바이오", "제약", "헬스케어", "의료", "치료", "mRNA", "줄기세포",
                   "진단", "백신", "신약", "암", "치매", "당뇨"],
            "energy": ["에너지", "2차전지", "배터리", "태양광", "풍력", "수소",
                      "원자력", "핵융합", "전기차", "리튬", "니켈"],
            "defense": ["방산", "우주", "항공", "드론", "미사일", "국방", "위성"],
            "finance": ["금융", "은행", "증권", "보험", "부동산", "리츠", "핀테크"],
            "consumer": ["소비", "유통", "면세", "화장품", "엔터", "게임", "여행",
                        "음식", "의류", "패션"],
            "industrial": ["건설", "조선", "철강", "화학", "기계", "자동차", "물류"],
        }

        for theme in themes:
            theme_name = theme["theme_name"]
            categorized = False

            for category, keywords in category_keywords.items():
                if any(kw in theme_name for kw in keywords):
                    categories[category].append(theme)
                    categorized = True
                    break

            if not categorized:
                categories["other"].append(theme)

        # 빈 카테고리 제거
        return {k: v for k, v in categories.items() if v}

    def get_theme_history(
        self,
        theme_name: str,
        days: int = 30,
    ) -> list[dict]:
        """특정 테마의 히스토리 조회 (DB 기반)."""
        stocks = self.get_stocks_in_theme(theme_name)
        stock_codes = [s["code"] for s in stocks]

        if not stock_codes:
            return []

        # 최근 N일 동안의 언급 이력 조회
        start_date = date.today() - timedelta(days=days)

        mentions = (
            self.db.query(
                TraderMention.mentioned_date,
                func.count(TraderMention.id).label("mention_count"),
                func.sum(TraderMention.mention_count).label("total_mentions"),
            )
            .filter(
                TraderMention.stock_code.in_(stock_codes),
                TraderMention.mentioned_date >= start_date,
            )
            .group_by(TraderMention.mentioned_date)
            .order_by(TraderMention.mentioned_date)
            .all()
        )

        return [
            {
                "date": m.mentioned_date.isoformat(),
                "stock_count": m.mention_count,
                "total_mentions": m.total_mentions,
            }
            for m in mentions
        ]

    def get_all_themes(self) -> list[dict]:
        """전체 테마 목록 반환."""
        return [
            {
                "name": name,
                "stock_count": len(stocks),
            }
            for name, stocks in self._theme_map.items()
        ]

    def search_themes(self, query: str) -> list[dict]:
        """테마 검색."""
        query = query.lower()
        results = []

        for name, stocks in self._theme_map.items():
            if query in name.lower():
                results.append({
                    "name": name,
                    "stock_count": len(stocks),
                    "stocks": stocks[:5],  # 상위 5개만
                })

        return results[:20]  # 최대 20개
