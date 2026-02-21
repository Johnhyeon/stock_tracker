"""주식 가격 조회 서비스."""
import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import httpx

from integrations.kis import get_kis_client, KISClient
from core.timezone import now_kst

logger = logging.getLogger(__name__)


class PriceCache:
    """간단한 메모리 캐시."""

    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[datetime, dict]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[dict]:
        async with self._lock:
            if key in self._cache:
                timestamp, data = self._cache[key]
                if now_kst() - timestamp < timedelta(seconds=self.ttl):
                    return data
                del self._cache[key]
            return None

    async def set(self, key: str, value: dict) -> None:
        async with self._lock:
            self._cache[key] = (now_kst(), value)

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()


class PriceService:
    """주식 가격 조회 서비스.

    KIS API를 통해 가격 정보를 조회하고 캐싱합니다.
    """

    # Yahoo Finance 심볼 매핑
    US_INDEX_SYMBOLS = {
        "sp500": {"symbol": "^GSPC", "name": "S&P 500"},
        "nasdaq": {"symbol": "^IXIC", "name": "NASDAQ"},
        "dow": {"symbol": "^DJI", "name": "DOW"},
    }

    def __init__(self, kis_client: Optional[KISClient] = None):
        self.kis_client = kis_client or get_kis_client()
        self._price_cache = PriceCache(ttl_seconds=60)  # 현재가 1분 캐시
        self._ohlcv_cache = PriceCache(ttl_seconds=300)  # OHLCV 5분 캐시
        self._index_cache = PriceCache(ttl_seconds=120)  # 시장 지수 2분 캐시
        self._us_index_cache = PriceCache(ttl_seconds=300)  # 미국 지수 5분 캐시

    async def get_current_price(
        self,
        stock_code: str,
        use_cache: bool = True,
    ) -> dict:
        """종목 현재가 조회.

        Args:
            stock_code: 종목코드
            use_cache: 캐시 사용 여부

        Returns:
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "current_price": Decimal("72000"),
                "change": Decimal("-500"),
                "change_rate": Decimal("-0.69"),
                "volume": 12345678,
                "high_price": Decimal("72500"),
                "low_price": Decimal("71000"),
                "open_price": Decimal("72100"),
                "prev_close": Decimal("72500"),
                "updated_at": "2024-01-15T14:30:00",
            }
        """
        cache_key = f"price:{stock_code}"

        if use_cache:
            cached = await self._price_cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for {stock_code}")
                return cached

        try:
            data = await self.kis_client.get_current_price(stock_code)
            data["updated_at"] = now_kst().isoformat()
            await self._price_cache.set(cache_key, data)
            return data
        except Exception as e:
            logger.error(f"Failed to fetch price for {stock_code}: {e}")
            raise

    async def get_multiple_prices(
        self,
        stock_codes: list[str],
        use_cache: bool = True,
    ) -> dict[str, dict]:
        """여러 종목 현재가 일괄 조회.

        Args:
            stock_codes: 종목코드 리스트
            use_cache: 캐시 사용 여부

        Returns:
            {"005930": {...}, "000660": {...}, ...}
        """
        results = {}
        codes_to_fetch = []

        if use_cache:
            for code in stock_codes:
                cached = await self._price_cache.get(f"price:{code}")
                if cached:
                    results[code] = cached
                else:
                    codes_to_fetch.append(code)
        else:
            codes_to_fetch = stock_codes

        if codes_to_fetch:
            fetched = await self.kis_client.get_multiple_prices(codes_to_fetch)
            for code, data in fetched.items():
                data["updated_at"] = now_kst().isoformat()
                await self._price_cache.set(f"price:{code}", data)
                results[code] = data

        return results

    async def get_ohlcv(
        self,
        stock_code: str,
        period: str = "D",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_cache: bool = True,
    ) -> list[dict]:
        """일봉/주봉/월봉 시세 조회.

        Args:
            stock_code: 종목코드
            period: D(일), W(주), M(월)
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            use_cache: 캐시 사용 여부

        Returns:
            [{"date": "20240115", "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...}, ...]
        """
        cache_key = f"ohlcv:{stock_code}:{period}:{start_date}:{end_date}"

        if use_cache:
            cached = await self._ohlcv_cache.get(cache_key)
            if cached:
                return cached

        try:
            data = await self.kis_client.get_daily_ohlcv(
                stock_code=stock_code,
                start_date=start_date,
                end_date=end_date,
                period=period,
            )
            await self._ohlcv_cache.set(cache_key, data)
            return data
        except Exception as e:
            logger.error(f"Failed to fetch OHLCV for {stock_code}: {e}")
            raise

    async def _fetch_us_index(self, key: str) -> Optional[dict]:
        """Yahoo Finance에서 미국 지수 1건 조회."""
        info = self.US_INDEX_SYMBOLS[key]
        symbol = info["symbol"]
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        params = {"range": "1d", "interval": "1d"}
        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            meta = data["chart"]["result"][0]["meta"]
            current = Decimal(str(meta["regularMarketPrice"]))
            prev_close = Decimal(str(meta["chartPreviousClose"]))
            change = current - prev_close
            change_rate = (change / prev_close * 100) if prev_close else Decimal("0")

            return {
                "index_code": key,
                "index_name": info["name"],
                "current_value": current,
                "change": change,
                "change_rate": change_rate.quantize(Decimal("0.01")),
                "volume": 0,
                "trading_value": 0,
            }
        except Exception as e:
            logger.warning(f"US index fetch failed ({key}): {e}")
            return None

    async def get_us_market_indices(self) -> dict[str, dict]:
        """미국 3대 지수 조회 (S&P 500, NASDAQ, DOW)."""
        cache_key = "us_market_indices"
        cached = await self._us_index_cache.get(cache_key)
        if cached:
            return cached

        results = await asyncio.gather(
            self._fetch_us_index("sp500"),
            self._fetch_us_index("nasdaq"),
            self._fetch_us_index("dow"),
        )

        us_indices = {}
        for key, data in zip(self.US_INDEX_SYMBOLS.keys(), results):
            if data:
                us_indices[key] = data

        if us_indices:
            await self._us_index_cache.set(cache_key, us_indices)

        return us_indices

    async def get_market_indices(self) -> dict:
        """코스피/코스닥 + 미국 3대 지수 조회.

        Returns:
            {
                "kospi": {...},
                "kosdaq": {...},
                "sp500": {...},
                "nasdaq": {...},
                "dow": {...},
                "updated_at": "...",
            }
        """
        cache_key = "market_indices"
        cached = await self._index_cache.get(cache_key)
        if cached:
            return cached

        try:
            # 한국 지수 + 미국 지수 병렬 조회
            (kospi, kosdaq), us_indices = await asyncio.gather(
                asyncio.gather(
                    self.kis_client.get_market_index("0001"),
                    self.kis_client.get_market_index("1001"),
                ),
                self.get_us_market_indices(),
            )
            result = {
                "kospi": kospi,
                "kosdaq": kosdaq,
                **us_indices,
                "updated_at": now_kst().isoformat(),
            }
            await self._index_cache.set(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Failed to fetch market indices: {e}")
            raise

    async def clear_cache(self) -> None:
        """캐시 초기화."""
        await self._price_cache.clear()
        await self._ohlcv_cache.clear()
        await self._index_cache.clear()


# 싱글톤 인스턴스
_price_service: Optional[PriceService] = None


def get_price_service() -> PriceService:
    """가격 서비스 싱글톤 반환."""
    global _price_service
    if _price_service is None:
        _price_service = PriceService()
    return _price_service
