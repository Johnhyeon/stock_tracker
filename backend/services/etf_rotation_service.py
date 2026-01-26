"""ETF 순환매 분석 서비스."""
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from models import EtfOHLCV, StockOHLCV, StockInvestorFlow, InvestmentIdea
from models.theme_news import ThemeNews
from integrations.kis import KISClient

try:
    from pykrx import stock as pykrx_stock
    PYKRX_AVAILABLE = True
except ImportError:
    PYKRX_AVAILABLE = False

logger = logging.getLogger(__name__)

THEME_ETF_MAP_PATH = Path(__file__).parent.parent / "data" / "theme_etf_map.json"


@dataclass
class EtfPerformance:
    """ETF 성과 데이터."""
    etf_code: str
    etf_name: str
    theme: str
    is_primary: bool
    current_price: int
    change_1d: Optional[float]  # 1일 등락률
    change_5d: Optional[float]  # 5일 등락률
    change_20d: Optional[float]  # 20일 등락률
    change_60d: Optional[float]  # 60일 등락률
    trading_value: Optional[int]  # 최근 거래대금
    trading_value_avg_20d: Optional[int]  # 20일 평균 거래대금
    trading_value_ratio: Optional[float]  # 거래대금 비율 (현재/평균)
    volume: Optional[int]
    trade_date: Optional[str]


class EtfRotationService:
    """ETF 순환매 분석 서비스."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._theme_etf_map: dict = {}
        self._load_theme_etf_map()

    def _load_theme_etf_map(self):
        """테마-ETF 매핑 로드."""
        try:
            with open(THEME_ETF_MAP_PATH, "r", encoding="utf-8") as f:
                self._theme_etf_map = json.load(f)
            logger.info(f"Loaded {len(self._theme_etf_map)} theme-ETF mappings")
        except Exception as e:
            logger.error(f"Failed to load theme ETF map: {e}")

    async def _get_etf_price_at_date(
        self,
        etf_code: str,
        target_date: date,
    ) -> Optional[int]:
        """특정 날짜의 종가 조회."""
        stmt = (
            select(EtfOHLCV.close_price)
            .where(
                and_(
                    EtfOHLCV.etf_code == etf_code,
                    EtfOHLCV.trade_date <= target_date,
                )
            )
            .order_by(EtfOHLCV.trade_date.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        price = result.scalar()
        return price

    async def _get_trading_value_avg(
        self,
        etf_code: str,
        days: int = 20,
    ) -> Optional[int]:
        """최근 N일 평균 거래대금."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days + 10)  # 여유분

        stmt = (
            select(func.avg(EtfOHLCV.trading_value))
            .where(
                and_(
                    EtfOHLCV.etf_code == etf_code,
                    EtfOHLCV.trade_date >= start_date,
                    EtfOHLCV.trading_value.isnot(None),
                )
            )
        )
        result = await self.db.execute(stmt)
        avg = result.scalar()
        return int(avg) if avg else None

    async def _calculate_period_change(
        self,
        etf_code: str,
        current_price: int,
        days: int,
    ) -> Optional[float]:
        """N일 전 대비 등락률 계산."""
        target_date = date.today() - timedelta(days=days)
        past_price = await self._get_etf_price_at_date(etf_code, target_date)

        if past_price and past_price > 0:
            return round((current_price - past_price) / past_price * 100, 2)
        return None

    async def get_etf_heatmap_data(self) -> list[dict]:
        """히트맵용 ETF 데이터 조회.

        Returns:
            테마별 ETF 성과 리스트 (등락률순 정렬)
        """
        results = []

        for theme_name, theme_data in self._theme_etf_map.items():
            for etf in theme_data.get("etfs", []):
                etf_code = etf.get("code")
                if not etf_code:
                    continue

                # 최신 데이터 조회
                stmt = (
                    select(EtfOHLCV)
                    .where(EtfOHLCV.etf_code == etf_code)
                    .order_by(EtfOHLCV.trade_date.desc())
                    .limit(1)
                )
                result = await self.db.execute(stmt)
                latest = result.scalar_one_or_none()

                if not latest:
                    continue

                current_price = latest.close_price

                # 기간별 등락률 계산
                change_1d = latest.change_rate
                change_5d = await self._calculate_period_change(etf_code, current_price, 5)
                change_20d = await self._calculate_period_change(etf_code, current_price, 20)
                change_60d = await self._calculate_period_change(etf_code, current_price, 60)

                # 거래대금 분석
                trading_value_avg = await self._get_trading_value_avg(etf_code, 20)
                trading_value_ratio = None
                if trading_value_avg and trading_value_avg > 0 and latest.trading_value:
                    trading_value_ratio = round(latest.trading_value / trading_value_avg, 2)

                results.append({
                    "etf_code": etf_code,
                    "etf_name": latest.etf_name or etf.get("name", ""),
                    "theme": theme_name,
                    "is_primary": etf.get("is_primary", False),
                    "current_price": current_price,
                    "change_1d": change_1d,
                    "change_5d": change_5d,
                    "change_20d": change_20d,
                    "change_60d": change_60d,
                    "trading_value": latest.trading_value,
                    "trading_value_avg_20d": trading_value_avg,
                    "trading_value_ratio": trading_value_ratio,
                    "volume": latest.volume,
                    "trade_date": latest.trade_date.isoformat() if latest.trade_date else None,
                })

        # 5일 등락률 기준 정렬
        results.sort(key=lambda x: x.get("change_5d") or 0, reverse=True)

        return results

    async def get_theme_heatmap_data(self, period: str = "5d") -> list[dict]:
        """테마별 집계 히트맵 데이터.

        대표 ETF(is_primary=True) 기준으로 테마별 성과 집계.

        Args:
            period: 기준 기간 (1d, 5d, 20d, 60d)

        Returns:
            테마별 성과 리스트
        """
        period_map = {
            "1d": "change_1d",
            "5d": "change_5d",
            "20d": "change_20d",
            "60d": "change_60d",
        }
        change_field = period_map.get(period, "change_5d")

        etf_data = await self.get_etf_heatmap_data()

        # 대표 ETF만 필터링
        primary_etfs = [e for e in etf_data if e.get("is_primary")]

        # 테마별 집계
        theme_data = {}
        for etf in primary_etfs:
            theme = etf["theme"]
            if theme not in theme_data:
                theme_data[theme] = etf

        results = list(theme_data.values())

        # 선택된 기간 등락률 기준 정렬
        results.sort(key=lambda x: x.get(change_field) or 0, reverse=True)

        # 순위 부여
        for i, item in enumerate(results, 1):
            item["rank"] = i

        return results

    async def get_rotation_signals(self) -> list[dict]:
        """순환매 시그널 감지.

        Returns:
            순환매 시그널 리스트
        """
        signals = []
        etf_data = await self.get_etf_heatmap_data()

        # 대표 ETF만 분석
        primary_etfs = [e for e in etf_data if e.get("is_primary")]

        for etf in primary_etfs:
            signal_type = None
            signal_strength = 0
            reasons = []

            change_5d = etf.get("change_5d") or 0
            change_20d = etf.get("change_20d") or 0
            trading_ratio = etf.get("trading_value_ratio") or 1

            # 강세 전환 시그널
            if change_5d > 3 and trading_ratio > 1.5:
                signal_type = "STRONG_UP"
                signal_strength = min(100, int(change_5d * 10 + (trading_ratio - 1) * 20))
                reasons.append(f"5일 +{change_5d:.1f}%")
                reasons.append(f"거래대금 {trading_ratio:.1f}배")

            # 약세 전환 시그널
            elif change_5d < -3 and trading_ratio < 0.7:
                signal_type = "STRONG_DOWN"
                signal_strength = min(100, int(abs(change_5d) * 10))
                reasons.append(f"5일 {change_5d:.1f}%")
                reasons.append(f"거래량 감소")

            # 모멘텀 가속
            elif change_5d > 0 and change_20d > 0 and change_5d > change_20d / 4:
                signal_type = "MOMENTUM_UP"
                signal_strength = min(100, int(change_5d * 15))
                reasons.append(f"모멘텀 가속 중")

            # 반등 조짐
            elif change_5d > 2 and change_20d < -5:
                signal_type = "REVERSAL_UP"
                signal_strength = min(100, int(change_5d * 20))
                reasons.append(f"반등 시도 (20일 {change_20d:.1f}% → 5일 +{change_5d:.1f}%)")

            if signal_type:
                signals.append({
                    "theme": etf["theme"],
                    "etf_code": etf["etf_code"],
                    "etf_name": etf["etf_name"],
                    "signal_type": signal_type,
                    "signal_strength": signal_strength,
                    "change_5d": change_5d,
                    "change_20d": change_20d,
                    "trading_value_ratio": trading_ratio,
                    "reasons": reasons,
                })

        # 시그널 강도순 정렬
        signals.sort(key=lambda x: x["signal_strength"], reverse=True)

        return signals

    async def get_etf_chart_data(
        self,
        etf_code: str,
        days: int = 60,
    ) -> list[dict]:
        """ETF 차트 데이터 조회."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days + 10)

        stmt = (
            select(EtfOHLCV)
            .where(
                and_(
                    EtfOHLCV.etf_code == etf_code,
                    EtfOHLCV.trade_date >= start_date,
                )
            )
            .order_by(EtfOHLCV.trade_date)
            .limit(days)
        )

        result = await self.db.execute(stmt)
        records = result.scalars().all()

        return [r.to_dict() for r in records]

    async def get_theme_detail(self, theme_name: str) -> Optional[dict]:
        """테마 상세 정보 조회.

        Args:
            theme_name: 테마명

        Returns:
            테마 상세 정보 (ETF 정보, 차트, 연관 테마, 뉴스)
        """
        # 테마 존재 확인
        if theme_name not in self._theme_etf_map:
            return None

        theme_data = self._theme_etf_map[theme_name]
        etfs = theme_data.get("etfs", [])
        related_themes = theme_data.get("related_themes", [])

        if not etfs:
            return None

        # 대표 ETF 찾기
        primary_etf = next((e for e in etfs if e.get("is_primary")), etfs[0])
        etf_code = primary_etf.get("code")

        # ETF 성과 데이터 조회
        etf_data = await self.get_etf_heatmap_data()
        current_etf = next((e for e in etf_data if e["etf_code"] == etf_code), None)

        if not current_etf:
            return None

        # 60일 차트 데이터
        chart_data = await self.get_etf_chart_data(etf_code, 60)

        # 연관 테마 등락률 조회
        related_theme_data = []
        for related in related_themes:
            # 연관 테마가 theme_etf_map에 있으면 ETF 데이터 사용
            if related in self._theme_etf_map:
                related_etf_data = self._theme_etf_map[related]
                related_etfs = related_etf_data.get("etfs", [])
                if related_etfs:
                    primary = next((e for e in related_etfs if e.get("is_primary")), related_etfs[0])
                    related_perf = next((e for e in etf_data if e["etf_code"] == primary.get("code")), None)
                    if related_perf:
                        related_theme_data.append({
                            "name": related,
                            "etf_code": primary.get("code"),
                            "change_5d": related_perf.get("change_5d"),
                            "trading_value_ratio": related_perf.get("trading_value_ratio"),
                        })
            else:
                # ETF가 없는 연관 테마는 이름만 표시
                related_theme_data.append({
                    "name": related,
                    "etf_code": None,
                    "change_5d": None,
                    "trading_value_ratio": None,
                })

        # 테마 관련 뉴스 조회 (최근 7일)
        news_since = datetime.now() - timedelta(days=7)
        news_stmt = (
            select(ThemeNews)
            .where(
                and_(
                    ThemeNews.theme_name == theme_name,
                    ThemeNews.published_at >= news_since,
                )
            )
            .order_by(ThemeNews.published_at.desc())
            .limit(10)
        )
        news_result = await self.db.execute(news_stmt)
        news_list = news_result.scalars().all()

        news_data = [
            {
                "title": n.news_title,
                "source": n.news_source,
                "url": n.news_url,
                "published_at": n.published_at.isoformat() if n.published_at else None,
                "is_quality": n.is_quality,
            }
            for n in news_list
        ]

        # 모든 ETF 목록 (해당 테마)
        all_etfs_in_theme = []
        for etf in etfs:
            etf_perf = next((e for e in etf_data if e["etf_code"] == etf.get("code")), None)
            if etf_perf:
                all_etfs_in_theme.append(etf_perf)

        return {
            "theme": theme_name,
            "etf": {
                "code": current_etf["etf_code"],
                "name": current_etf["etf_name"],
                "current_price": current_etf["current_price"],
                "changes": {
                    "1d": current_etf.get("change_1d"),
                    "5d": current_etf.get("change_5d"),
                    "20d": current_etf.get("change_20d"),
                    "60d": current_etf.get("change_60d"),
                },
                "trading_value": current_etf.get("trading_value"),
                "trading_value_avg_20d": current_etf.get("trading_value_avg_20d"),
                "trading_value_ratio": current_etf.get("trading_value_ratio"),
                "trade_date": current_etf.get("trade_date"),
            },
            "all_etfs": all_etfs_in_theme,
            "chart": chart_data,
            "related_themes": related_theme_data,
            "news": news_data,
        }

    async def get_all_etf_compare(self, start_date: str = "2025-01-02") -> list[dict]:
        """전체 ETF 수익률 비교 데이터.

        모든 테마 대표 ETF의 수익률 추이를 시작일 기준으로 정규화합니다.

        Args:
            start_date: 시작일 (YYYY-MM-DD)

        Returns:
            ETF별 수익률 추이 리스트
        """
        from datetime import datetime as dt

        try:
            start = dt.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            start = date(2025, 1, 2)

        results = []

        for theme_name, theme_data in self._theme_etf_map.items():
            etfs = theme_data.get("etfs", [])
            if not etfs:
                continue

            # 대표 ETF 찾기
            primary_etf = next((e for e in etfs if e.get("is_primary")), etfs[0])
            etf_code = primary_etf.get("code")

            if not etf_code:
                continue

            # 시작일부터 데이터 조회
            stmt = (
                select(EtfOHLCV)
                .where(
                    and_(
                        EtfOHLCV.etf_code == etf_code,
                        EtfOHLCV.trade_date >= start,
                    )
                )
                .order_by(EtfOHLCV.trade_date)
            )

            result = await self.db.execute(stmt)
            records = result.scalars().all()

            if not records:
                continue

            # 시작가 기준 수익률 계산
            base_price = records[0].close_price
            if not base_price or base_price <= 0:
                continue

            data_points = []
            for r in records:
                pct_change = round((r.close_price - base_price) / base_price * 100, 2)
                data_points.append({
                    "date": r.trade_date.isoformat(),
                    "price": r.close_price,
                    "pct": pct_change,
                })

            # 최신 수익률
            latest_pct = data_points[-1]["pct"] if data_points else 0

            results.append({
                "theme": theme_name,
                "etf_code": etf_code,
                "etf_name": primary_etf.get("name", ""),
                "data": data_points,
                "latest_pct": latest_pct,
            })

        # 최신 수익률 기준 정렬
        results.sort(key=lambda x: x["latest_pct"], reverse=True)

        return results

    async def get_realtime_heatmap_data(self) -> dict:
        """실시간 ETF 히트맵 데이터 조회.

        KIS API를 통해 실시간 현재가를 조회하여 당일 등락률 히트맵 제공.

        Returns:
            {
                "themes": [...],  # 테마별 ETF 실시간 데이터
                "updated_at": "2026-01-26T10:30:00",
                "market_status": "open" | "closed"
            }
        """
        results = []
        errors = []

        try:
            kis_client = KISClient()
        except Exception as e:
            logger.error(f"KIS 클라이언트 초기화 실패: {e}")
            return {
                "themes": [],
                "updated_at": datetime.now().isoformat(),
                "market_status": "error",
                "error": str(e),
            }

        # 테마별 대표 ETF만 조회 (API 호출 수 제한)
        etf_codes_to_fetch = []
        etf_info_map = {}  # etf_code -> {theme, name, is_primary}

        for theme_name, theme_data in self._theme_etf_map.items():
            etfs = theme_data.get("etfs", [])
            if not etfs:
                continue

            # 대표 ETF만 조회
            primary_etf = next((e for e in etfs if e.get("is_primary")), etfs[0])
            etf_code = primary_etf.get("code")

            if etf_code:
                etf_codes_to_fetch.append(etf_code)
                etf_info_map[etf_code] = {
                    "theme": theme_name,
                    "name": primary_etf.get("name", ""),
                    "is_primary": True,
                }

        # 전일 종가 조회 (5일/20일 등락률 계산용)
        prev_prices = {}
        prices_5d = {}
        prices_20d = {}

        for etf_code in etf_codes_to_fetch:
            # 전일 종가
            stmt = (
                select(EtfOHLCV.close_price, EtfOHLCV.trade_date)
                .where(EtfOHLCV.etf_code == etf_code)
                .order_by(EtfOHLCV.trade_date.desc())
                .limit(21)
            )
            result = await self.db.execute(stmt)
            records = result.fetchall()

            if records:
                prev_prices[etf_code] = records[0][0]  # 가장 최근 종가
                if len(records) >= 5:
                    prices_5d[etf_code] = records[4][0]  # 5일 전 종가
                if len(records) >= 20:
                    prices_20d[etf_code] = records[19][0]  # 20일 전 종가

        # KIS API로 실시간 현재가 조회 (병렬 처리)
        async def fetch_price(etf_code: str) -> tuple[str, Optional[dict]]:
            try:
                price_data = await kis_client.get_current_price(etf_code)
                return (etf_code, price_data)
            except Exception as e:
                logger.warning(f"ETF {etf_code} 실시간 가격 조회 실패: {e}")
                return (etf_code, None)

        # 동시에 최대 5개씩 조회 (API 부하 방지)
        batch_size = 5
        price_results = {}

        for i in range(0, len(etf_codes_to_fetch), batch_size):
            batch = etf_codes_to_fetch[i:i + batch_size]
            tasks = [fetch_price(code) for code in batch]
            batch_results = await asyncio.gather(*tasks)

            for etf_code, price_data in batch_results:
                if price_data:
                    price_results[etf_code] = price_data
                else:
                    errors.append(etf_code)

            # 배치 간 딜레이 (API 제한 방지)
            if i + batch_size < len(etf_codes_to_fetch):
                await asyncio.sleep(0.1)

        # 결과 조합
        for etf_code, info in etf_info_map.items():
            price_data = price_results.get(etf_code)
            if not price_data:
                continue

            current_price = int(price_data.get("current_price", 0))
            prev_close = int(price_data.get("prev_close", 0))
            change_rate = float(price_data.get("change_rate", 0))

            # 5일/20일 등락률 계산
            change_5d = None
            change_20d = None

            if etf_code in prices_5d and prices_5d[etf_code] > 0:
                change_5d = round(
                    (current_price - prices_5d[etf_code]) / prices_5d[etf_code] * 100, 2
                )

            if etf_code in prices_20d and prices_20d[etf_code] > 0:
                change_20d = round(
                    (current_price - prices_20d[etf_code]) / prices_20d[etf_code] * 100, 2
                )

            results.append({
                "etf_code": etf_code,
                "etf_name": price_data.get("stock_name") or info["name"],
                "theme": info["theme"],
                "is_primary": info["is_primary"],
                "current_price": current_price,
                "prev_close": prev_close,
                "change_1d": change_rate,  # 전일 대비 등락률
                "change_5d": change_5d,
                "change_20d": change_20d,
                "volume": price_data.get("volume"),
                "high_price": int(price_data.get("high_price", 0)),
                "low_price": int(price_data.get("low_price", 0)),
                "open_price": int(price_data.get("open_price", 0)),
            })

        # 당일 등락률 기준 정렬
        results.sort(key=lambda x: x.get("change_1d") or 0, reverse=True)

        # 순위 부여
        for i, item in enumerate(results, 1):
            item["rank"] = i

        # 장 운영 시간 판단
        now = datetime.now()
        market_status = "closed"
        if now.weekday() < 5:  # 평일
            if 9 <= now.hour < 16:
                market_status = "open"
            elif now.hour == 15 and now.minute <= 30:
                market_status = "open"

        await kis_client.close()

        return {
            "themes": results,
            "updated_at": now.isoformat(),
            "market_status": market_status,
            "total_count": len(results),
            "error_count": len(errors),
        }

    async def get_etf_holdings(self, etf_code: str, limit: int = 15) -> list[dict]:
        """ETF 구성 종목 조회.

        pykrx를 사용하여 ETF 구성 종목을 조회하고,
        각 종목의 등락률, 수급, 아이디어 여부를 반환합니다.

        Args:
            etf_code: ETF 종목코드
            limit: 최대 종목 수

        Returns:
            구성 종목 리스트
        """
        if not PYKRX_AVAILABLE:
            logger.warning("pykrx가 설치되지 않아 ETF 구성 종목을 조회할 수 없습니다")
            return []

        try:
            # pykrx로 ETF 구성 종목 조회
            today = datetime.now().strftime('%Y%m%d')
            df = pykrx_stock.get_etf_portfolio_deposit_file(etf_code, today)

            if df.empty:
                return []

            # 내 아이디어 종목 코드 조회
            idea_stmt = select(InvestmentIdea.tickers)
            idea_result = await self.db.execute(idea_stmt)
            idea_tickers_raw = idea_result.scalars().all()

            # 아이디어에서 종목 코드 추출
            import re
            my_stock_codes = set()
            for tickers in idea_tickers_raw:
                if tickers:
                    for ticker in tickers:
                        match = re.search(r'\((\d{6})\)', ticker)
                        if match:
                            my_stock_codes.add(match.group(1))

            holdings = []

            for stock_code in list(df.index)[:limit]:
                try:
                    # 종목명 조회
                    stock_name = pykrx_stock.get_market_ticker_name(stock_code)
                    amount = float(df.loc[stock_code, '금액'])
                    weight = float(df.loc[stock_code, '비중']) if '비중' in df.columns else None

                    # 등락률 조회 (StockOHLCV에서)
                    change_1d = None
                    change_5d = None

                    ohlcv_stmt = (
                        select(StockOHLCV)
                        .where(StockOHLCV.stock_code == stock_code)
                        .order_by(StockOHLCV.trade_date.desc())
                        .limit(6)
                    )
                    ohlcv_result = await self.db.execute(ohlcv_stmt)
                    ohlcv_list = ohlcv_result.scalars().all()

                    if ohlcv_list:
                        latest = ohlcv_list[0]

                        # 1일 등락률 계산
                        if len(ohlcv_list) >= 2:
                            prev_price = ohlcv_list[1].close_price
                            if prev_price and prev_price > 0:
                                change_1d = round(
                                    (latest.close_price - prev_price) / prev_price * 100, 2
                                )

                        # 5일 전 대비 등락률
                        if len(ohlcv_list) >= 5:
                            past_price = ohlcv_list[-1].close_price
                            if past_price and past_price > 0:
                                change_5d = round(
                                    (latest.close_price - past_price) / past_price * 100, 2
                                )

                    # 수급 조회 (최근 5일 합계)
                    foreign_net = None
                    inst_net = None

                    flow_since = date.today() - timedelta(days=7)
                    flow_stmt = (
                        select(
                            func.sum(StockInvestorFlow.foreign_net_amount).label("foreign_net"),
                            func.sum(StockInvestorFlow.institution_net_amount).label("inst_net"),
                        )
                        .where(
                            and_(
                                StockInvestorFlow.stock_code == stock_code,
                                StockInvestorFlow.flow_date >= flow_since,
                            )
                        )
                    )
                    flow_result = await self.db.execute(flow_stmt)
                    flow_row = flow_result.one_or_none()

                    if flow_row:
                        foreign_net = flow_row.foreign_net
                        inst_net = flow_row.inst_net

                    # 내 아이디어 여부
                    in_my_ideas = stock_code in my_stock_codes

                    holdings.append({
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "amount": amount,
                        "weight": weight,
                        "change_1d": change_1d,
                        "change_5d": change_5d,
                        "foreign_net": foreign_net,
                        "inst_net": inst_net,
                        "in_my_ideas": in_my_ideas,
                    })

                except Exception as e:
                    logger.warning(f"종목 {stock_code} 조회 실패: {e}")
                    continue

            # 금액 기준 정렬 (비중)
            holdings.sort(key=lambda x: x.get("amount") or 0, reverse=True)

            return holdings

        except Exception as e:
            logger.error(f"ETF 구성 종목 조회 실패 ({etf_code}): {e}")
            return []
