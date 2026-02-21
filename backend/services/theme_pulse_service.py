"""테마 펄스 서비스 — 뉴스 기반 시장 테마 시각화."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from core.timezone import now_kst

from sqlalchemy import func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.stock_news import StockNews
from models.theme_setup import ThemeSetup
from services.theme_map_service import get_theme_map_service
from core.cache import api_cache

logger = logging.getLogger(__name__)


class ThemePulseService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.theme_map = get_theme_map_service()

    async def get_theme_pulse(self, days: int = 7, limit: int = 30) -> dict:
        """테마별 뉴스 집계 + 모멘텀 + 셋업점수."""
        cache_key = f"theme-pulse:{days}:{limit}"
        cached = api_cache.get(cache_key)
        if cached:
            return cached

        now = now_kst()
        now_naive = now.replace(tzinfo=None)
        since = now_naive - timedelta(days=days)
        prev_since = since - timedelta(days=days)

        # 이번 기간 뉴스
        stmt = select(StockNews).where(StockNews.published_at >= since)
        result = await self.db.execute(stmt)
        current_news = result.scalars().all()

        # 이전 기간 뉴스 (모멘텀 계산용)
        stmt_prev = select(StockNews).where(
            and_(StockNews.published_at >= prev_since, StockNews.published_at < since)
        )
        result_prev = await self.db.execute(stmt_prev)
        prev_news = result_prev.scalars().all()

        # 테마별 집계
        theme_data: dict[str, dict] = defaultdict(lambda: {
            "news_count": 0,
            "high_importance_count": 0,
            "catalyst_types": defaultdict(int),
            "stocks": defaultdict(int),
        })
        prev_theme_counts: dict[str, int] = defaultdict(int)

        for news in current_news:
            themes = self.theme_map.get_themes_for_stock(news.stock_code)
            for theme in themes:
                td = theme_data[theme]
                td["news_count"] += 1
                if news.importance in ("high", "critical"):
                    td["high_importance_count"] += 1
                if news.catalyst_type:
                    td["catalyst_types"][news.catalyst_type] += 1
                td["stocks"][news.stock_code] += 1

        for news in prev_news:
            themes = self.theme_map.get_themes_for_stock(news.stock_code)
            for theme in themes:
                prev_theme_counts[theme] += 1

        # ThemeSetup 최신 점수 조인
        setup_map = await self._get_latest_setups()

        # 결과 조립
        items = []
        for theme_name, td in theme_data.items():
            prev_count = prev_theme_counts.get(theme_name, 0)
            momentum = 0.0
            if prev_count > 0:
                momentum = round((td["news_count"] - prev_count) / prev_count * 100, 1)
            elif td["news_count"] > 0:
                momentum = 100.0

            # 상위 5개 종목
            sorted_stocks = sorted(td["stocks"].items(), key=lambda x: x[1], reverse=True)[:5]
            top_stocks = []
            all_themes = self.theme_map.get_all_themes()
            theme_stocks_map = {s.get("code"): s.get("name", "") for s in all_themes.get(theme_name, [])}
            for code, count in sorted_stocks:
                top_stocks.append({
                    "code": code,
                    "name": theme_stocks_map.get(code, code),
                    "news_count": count,
                })

            setup = setup_map.get(theme_name, {})

            items.append({
                "theme_name": theme_name,
                "news_count": td["news_count"],
                "high_importance_count": td["high_importance_count"],
                "momentum": momentum,
                "catalyst_types": dict(td["catalyst_types"]),
                "top_stocks": top_stocks,
                "setup_score": setup.get("total_setup_score", 0.0),
                "setup_rank": setup.get("rank"),
            })

        # 뉴스 수 기준 정렬 후 limit 적용
        items.sort(key=lambda x: x["news_count"], reverse=True)
        items = items[:limit]

        # 순위 부여
        for i, item in enumerate(items):
            item["rank"] = i + 1

        result_data = {
            "items": items,
            "total_themes": len(theme_data),
            "total_news": len(current_news),
            "period_days": days,
            "generated_at": now.isoformat(),
        }
        api_cache.set(cache_key, result_data, ttl=180)
        return result_data

    async def get_theme_timeline(self, days: int = 14, top_n: int = 8) -> dict:
        """상위 N개 테마의 일별 뉴스 수 시계열."""
        cache_key = f"theme-timeline:{days}:{top_n}"
        cached = api_cache.get(cache_key)
        if cached:
            return cached

        now = now_kst()
        now_naive = now.replace(tzinfo=None)
        since = now_naive - timedelta(days=days)

        stmt = select(StockNews).where(StockNews.published_at >= since)
        result = await self.db.execute(stmt)
        news_list = result.scalars().all()

        # 테마별 일별 집계
        theme_daily: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        theme_total: dict[str, int] = defaultdict(int)

        for news in news_list:
            date_str = news.published_at.strftime("%Y-%m-%d")
            themes = self.theme_map.get_themes_for_stock(news.stock_code)
            for theme in themes:
                theme_daily[theme][date_str] += 1
                theme_total[theme] += 1

        # 상위 N개 테마
        top_themes = sorted(theme_total.items(), key=lambda x: x[1], reverse=True)[:top_n]
        top_theme_names = [t[0] for t in top_themes]

        # 날짜 리스트 생성
        dates = []
        for i in range(days):
            d = (now_naive - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            dates.append(d)

        themes_data = []
        for theme_name in top_theme_names:
            daily = theme_daily[theme_name]
            data = [{"date": d, "count": daily.get(d, 0)} for d in dates]
            themes_data.append({
                "name": theme_name,
                "data": data,
            })

        result_data = {
            "dates": dates,
            "themes": themes_data,
            "generated_at": now.isoformat(),
        }
        api_cache.set(cache_key, result_data, ttl=180)
        return result_data

    async def get_catalyst_distribution(self, days: int = 7) -> dict:
        """전체 뉴스의 catalyst_type 비율 + importance 분포."""
        cache_key = f"theme-catalyst-dist:{days}"
        cached = api_cache.get(cache_key)
        if cached:
            return cached

        now = now_kst()
        now_naive = now.replace(tzinfo=None)
        since = now_naive - timedelta(days=days)

        # catalyst_type 집계
        stmt_cat = (
            select(StockNews.catalyst_type, func.count(StockNews.id))
            .where(and_(StockNews.published_at >= since, StockNews.catalyst_type.isnot(None)))
            .group_by(StockNews.catalyst_type)
        )
        result_cat = await self.db.execute(stmt_cat)
        catalyst_counts = result_cat.all()

        total_cat = sum(c for _, c in catalyst_counts)
        catalyst_distribution = [
            {
                "type": ctype or "unknown",
                "count": count,
                "ratio": round(count / total_cat * 100, 1) if total_cat > 0 else 0,
            }
            for ctype, count in catalyst_counts
        ]
        catalyst_distribution.sort(key=lambda x: x["count"], reverse=True)

        # importance 집계
        stmt_imp = (
            select(StockNews.importance, func.count(StockNews.id))
            .where(and_(StockNews.published_at >= since, StockNews.importance.isnot(None)))
            .group_by(StockNews.importance)
        )
        result_imp = await self.db.execute(stmt_imp)
        importance_counts = result_imp.all()

        total_imp = sum(c for _, c in importance_counts)
        importance_distribution = [
            {
                "level": level or "unknown",
                "count": count,
                "ratio": round(count / total_imp * 100, 1) if total_imp > 0 else 0,
            }
            for level, count in importance_counts
        ]

        result_data = {
            "catalyst_distribution": catalyst_distribution,
            "importance_distribution": importance_distribution,
            "total_news": total_cat,
            "period_days": days,
            "generated_at": now.isoformat(),
        }
        api_cache.set(cache_key, result_data, ttl=180)
        return result_data

    async def _get_latest_setups(self) -> dict[str, dict]:
        """ThemeSetup 최신 날짜의 점수 맵 반환."""
        # 최신 날짜 조회
        stmt_date = select(func.max(ThemeSetup.setup_date))
        result_date = await self.db.execute(stmt_date)
        latest_date = result_date.scalar()
        if not latest_date:
            return {}

        stmt = select(ThemeSetup).where(ThemeSetup.setup_date == latest_date)
        result = await self.db.execute(stmt)
        setups = result.scalars().all()

        return {
            s.theme_name: {
                "total_setup_score": s.total_setup_score,
                "rank": s.rank,
            }
            for s in setups
        }
