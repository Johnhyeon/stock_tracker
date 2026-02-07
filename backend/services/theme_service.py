"""테마 순환매 분석 서비스."""
import logging
from datetime import datetime, date, timedelta
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import TraderMention
from services.theme_map_service import get_theme_map_service

logger = logging.getLogger(__name__)


class ThemeService:
    """테마 순환매 분석 서비스.

    analyze_theme_rotation과 get_theme_history만 제공.
    테마맵 조회는 ThemeMapService를 직접 사용하세요.
    """

    def __init__(self, db: Session):
        self.db = db
        self._tms = get_theme_map_service()

    def analyze_theme_rotation(
        self,
        youtube_data: list[dict],
        trader_data: list[dict],
        days: int = 7,
    ) -> dict:
        """테마 순환매 분석."""
        theme_scores = defaultdict(lambda: {
            "youtube_mentions": 0,
            "youtube_stocks": set(),
            "trader_mentions": 0,
            "trader_stocks": set(),
            "total_volume": 0,
            "avg_price_change": [],
            "stocks_detail": [],
        })

        for stock in youtube_data:
            stock_code = stock.get("stock_code")
            if not stock_code:
                continue

            themes = self._tms.get_themes_for_stock(stock_code)
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

        for stock in trader_data:
            stock_code = stock.get("stock_code")
            if not stock_code:
                continue

            themes = self._tms.get_themes_for_stock(stock_code)
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

        theme_results = []
        for theme_name, data in theme_scores.items():
            all_stocks = data["youtube_stocks"] | data["trader_stocks"]
            stock_count = len(all_stocks)

            if stock_count == 0:
                continue

            avg_change = (
                sum(data["avg_price_change"]) / len(data["avg_price_change"])
                if data["avg_price_change"]
                else 0
            )

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

            unique_stocks = {}
            for s in data["stocks_detail"]:
                code = s["code"]
                if code not in unique_stocks:
                    unique_stocks[code] = s
                else:
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
                "stocks": list(unique_stocks.values())[:10],
            })

        theme_results.sort(key=lambda x: x["total_score"], reverse=True)
        hot_themes = theme_results[:15]
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
            "tech": [], "bio": [], "energy": [], "defense": [],
            "finance": [], "consumer": [], "industrial": [], "other": [],
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

        return {k: v for k, v in categories.items() if v}

    def get_theme_history(
        self,
        theme_name: str,
        days: int = 30,
    ) -> list[dict]:
        """특정 테마의 히스토리 조회 (DB 기반)."""
        stocks = self._tms.get_stocks_in_theme(theme_name)
        stock_codes = [s["code"] for s in stocks]

        if not stock_codes:
            return []

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
