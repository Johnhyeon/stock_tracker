"""KIS (한국투자증권) API 클라이언트."""
import logging
from datetime import datetime
from typing import Optional
from decimal import Decimal

from integrations.base_client import BaseAPIClient
from integrations.kis.auth import get_token_manager, KISTokenManager
from core.config import get_settings

logger = logging.getLogger(__name__)


class KISClient(BaseAPIClient):
    """KIS Open API 클라이언트.

    지원 기능:
    - 주식 현재가 조회
    - 일봉/주봉/월봉 시세 조회
    """

    def __init__(self, token_manager: Optional[KISTokenManager] = None):
        settings = get_settings()
        super().__init__(
            base_url=settings.kis_base_url,
            rate_limit=10.0,  # 초당 10회 제한
            timeout=30.0,
        )
        self.settings = settings
        self.token_manager = token_manager or get_token_manager()

    def get_headers(self) -> dict[str, str]:
        """기본 헤더 (토큰 없이)."""
        return {
            "Content-Type": "application/json; charset=utf-8",
            "appkey": self.settings.kis_app_key or "",
            "appsecret": self.settings.kis_app_secret or "",
        }

    async def _get_auth_headers(self) -> dict[str, str]:
        """인증 포함 헤더."""
        token = await self.token_manager.get_access_token()
        headers = self.get_headers()
        headers["authorization"] = f"Bearer {token}"
        return headers

    async def get_current_price(self, stock_code: str) -> dict:
        """주식 현재가 조회.

        Args:
            stock_code: 종목코드 (6자리)

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
                "market_cap": 430000000000000,  # 시가총액
            }
        """
        headers = await self._get_auth_headers()
        headers["tr_id"] = "FHKST01010100"  # 주식현재가 시세

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # 주식
            "FID_INPUT_ISCD": stock_code,
        }

        data = await self.get(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            params=params,
            headers=headers,
        )

        output = data.get("output", {})
        return {
            "stock_code": stock_code,
            "stock_name": output.get("hts_kor_isnm", ""),
            "current_price": Decimal(output.get("stck_prpr", "0")),
            "change": Decimal(output.get("prdy_vrss", "0")),
            "change_rate": Decimal(output.get("prdy_ctrt", "0")),
            "volume": int(output.get("acml_vol", "0")),
            "high_price": Decimal(output.get("stck_hgpr", "0")),
            "low_price": Decimal(output.get("stck_lwpr", "0")),
            "open_price": Decimal(output.get("stck_oprc", "0")),
            "prev_close": Decimal(output.get("stck_sdpr", "0")),
            "market_cap": int(output.get("hts_avls", "0")) * 100000000,  # 억 단위
        }

    async def get_daily_ohlcv(
        self,
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "D",  # D: 일, W: 주, M: 월
        adjusted: bool = True,
    ) -> list[dict]:
        """일봉/주봉/월봉 시세 조회.

        Args:
            stock_code: 종목코드
            start_date: 시작일 (YYYYMMDD), 기본값 100일 전
            end_date: 종료일 (YYYYMMDD), 기본값 오늘
            period: D(일봉), W(주봉), M(월봉)
            adjusted: 수정주가 여부

        Returns:
            [
                {
                    "date": "20240115",
                    "open": Decimal("72000"),
                    "high": Decimal("73000"),
                    "low": Decimal("71500"),
                    "close": Decimal("72500"),
                    "volume": 12345678,
                    "change": Decimal("500"),
                    "change_rate": Decimal("0.69"),
                },
                ...
            ]
        """
        from datetime import timedelta

        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start = datetime.strptime(end_date, "%Y%m%d") - timedelta(days=100)
            start_date = start.strftime("%Y%m%d")

        # 요청 기간 계산 (영업일 기준 약 250일 = 1년)
        start_dt = datetime.strptime(start_date, "%Y%m%d")
        end_dt = datetime.strptime(end_date, "%Y%m%d")
        total_days = (end_dt - start_dt).days

        # KIS API는 한 번에 약 100개 데이터만 반환
        # 100일 이상 요청 시 여러 번 호출해서 병합
        all_results = []

        if total_days <= 100:
            # 단일 호출
            result = await self._fetch_ohlcv_chunk(stock_code, start_date, end_date, period, adjusted)
            all_results.extend(result)
        else:
            # 여러 번 호출 (100일씩 나누어)
            current_end = end_dt
            while current_end > start_dt:
                chunk_start = current_end - timedelta(days=100)
                if chunk_start < start_dt:
                    chunk_start = start_dt

                result = await self._fetch_ohlcv_chunk(
                    stock_code,
                    chunk_start.strftime("%Y%m%d"),
                    current_end.strftime("%Y%m%d"),
                    period,
                    adjusted
                )
                all_results.extend(result)

                # 다음 구간으로 이동 (중복 방지를 위해 하루 빼기)
                current_end = chunk_start - timedelta(days=1)

        # 중복 제거 및 정렬
        seen_dates = set()
        unique_results = []
        for item in all_results:
            if item["date"] not in seen_dates:
                seen_dates.add(item["date"])
                unique_results.append(item)

        unique_results.sort(key=lambda x: x["date"])
        return unique_results

    async def _fetch_ohlcv_chunk(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        period: str = "D",
        adjusted: bool = True,
    ) -> list[dict]:
        """OHLCV 데이터 단일 청크 조회 (내부용)."""
        headers = await self._get_auth_headers()
        headers["tr_id"] = "FHKST03010100"

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": period,
            "FID_ORG_ADJ_PRC": "0" if adjusted else "1",
        }

        data = await self.get(
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            params=params,
            headers=headers,
        )

        output_list = data.get("output2", [])
        result = []

        for item in output_list:
            if not item.get("stck_bsop_date"):
                continue
            result.append({
                "date": item.get("stck_bsop_date", ""),
                "open": Decimal(item.get("stck_oprc", "0")),
                "high": Decimal(item.get("stck_hgpr", "0")),
                "low": Decimal(item.get("stck_lwpr", "0")),
                "close": Decimal(item.get("stck_clpr", "0")),
                "volume": int(item.get("acml_vol", "0")),
                "change": Decimal(item.get("prdy_vrss", "0")),
                "change_rate": Decimal(item.get("prdy_ctrt", "0")),
            })

        return result

    async def get_multiple_prices(
        self,
        stock_codes: list[str],
        max_concurrent: int = 5,
        delay_between: float = 0.1,
        batch_size: int = 10,
    ) -> dict[str, dict]:
        """여러 종목 현재가 일괄 조회 (배치 병렬 처리).

        Args:
            stock_codes: 종목코드 리스트
            max_concurrent: 배치 내 최대 동시 요청 수
            delay_between: 요청 간 딜레이 (초)
            batch_size: 배치당 종목 수

        Returns:
            {"005930": {...}, "000660": {...}, ...}
        """
        import asyncio

        results = {}

        async def fetch_single(code: str) -> tuple[str, Optional[dict]]:
            try:
                price = await self.get_current_price(code)
                return code, price
            except Exception as e:
                logger.warning(f"Failed to fetch price for {code}: {e}")
                return code, None

        # 배치 단위로 처리
        for i in range(0, len(stock_codes), batch_size):
            batch = stock_codes[i:i + batch_size]

            # 배치 내에서 병렬 처리 (세마포어로 동시성 제한)
            semaphore = asyncio.Semaphore(max_concurrent)

            async def fetch_with_semaphore(code: str):
                async with semaphore:
                    await asyncio.sleep(delay_between)
                    return await fetch_single(code)

            batch_results = await asyncio.gather(*[fetch_with_semaphore(c) for c in batch])

            for code, data in batch_results:
                if data is not None:
                    results[code] = data

            # 배치 간 짧은 휴식 (rate limit 여유)
            if i + batch_size < len(stock_codes):
                await asyncio.sleep(0.2)

        return results

    async def get_investor_trading(self, stock_code: str, days: int = 30) -> list[dict]:
        """종목별 투자자별 매매동향 조회 (여러 일치).

        Args:
            stock_code: 종목코드 (6자리)
            days: 조회할 일수 (최대 30일)

        Returns:
            일별 수급 데이터 리스트
            [
                {
                    "stock_code": "005930",
                    "date": "2026-01-22",
                    "foreign_net": 1333121,
                    "institution_net": 136101,
                    "individual_net": -2905871,
                },
                ...
            ]
        """
        headers = await self._get_auth_headers()
        headers["tr_id"] = "FHKST01010900"  # 주식현재가 투자자

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # 주식
            "FID_INPUT_ISCD": stock_code,
        }

        data = await self.get(
            "/uapi/domestic-stock/v1/quotations/inquire-investor",
            params=params,
            headers=headers,
        )

        output_list = data.get("output", [])

        if not output_list:
            return []

        results = []
        for item in output_list[:days]:
            # 빈 데이터는 스킵 (수량 또는 금액 중 하나라도 있으면 포함)
            has_qty = item.get("frgn_ntby_qty") or item.get("orgn_ntby_qty") or item.get("prsn_ntby_qty")
            has_amount = item.get("frgn_ntby_tr_pbmn") or item.get("orgn_ntby_tr_pbmn") or item.get("prsn_ntby_tr_pbmn")
            if not (has_qty or has_amount):
                continue

            date_str = item.get("stck_bsop_date", "")
            if not date_str:
                continue

            # YYYYMMDD -> YYYY-MM-DD
            date_formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

            results.append({
                "stock_code": stock_code,
                "date": date_formatted,
                "foreign_net": int(item.get("frgn_ntby_qty", "0") or "0"),
                "institution_net": int(item.get("orgn_ntby_qty", "0") or "0"),
                "individual_net": int(item.get("prsn_ntby_qty", "0") or "0"),
                # 순매수금액 (단위: 백만원 -> 원으로 변환)
                "foreign_net_amount": int(item.get("frgn_ntby_tr_pbmn", "0") or "0") * 1000000,
                "institution_net_amount": int(item.get("orgn_ntby_tr_pbmn", "0") or "0") * 1000000,
                "individual_net_amount": int(item.get("prsn_ntby_tr_pbmn", "0") or "0") * 1000000,
            })

        return results

    async def get_multiple_investor_trading(
        self,
        stock_codes: list[str],
        days: int = 30,
        max_concurrent: int = 5,
        delay_between: float = 0.1,
        batch_size: int = 10,
        progress_callback: Optional[callable] = None,
    ) -> dict[str, list[dict]]:
        """여러 종목 투자자별 매매동향 일괄 조회 (배치 병렬 처리).

        Args:
            stock_codes: 종목코드 리스트
            days: 조회할 일수 (최대 30일)
            max_concurrent: 배치 내 최대 동시 요청 수
            delay_between: 요청 간 딜레이 (초)
            batch_size: 배치당 종목 수
            progress_callback: 진행률 콜백 (current, total) -> None

        Returns:
            {"005930": [{일별데이터}, ...], "000660": [...], ...}
        """
        import asyncio

        results = {}
        total = len(stock_codes)
        processed = 0

        async def fetch_single(code: str) -> tuple[str, Optional[list]]:
            try:
                data = await self.get_investor_trading(code, days)
                return code, data
            except Exception as e:
                logger.warning(f"Failed to fetch investor data for {code}: {e}")
                return code, None

        # 배치 단위로 처리
        for i in range(0, len(stock_codes), batch_size):
            batch = stock_codes[i:i + batch_size]

            # 배치 내에서 병렬 처리
            semaphore = asyncio.Semaphore(max_concurrent)

            async def fetch_with_semaphore(code: str):
                async with semaphore:
                    await asyncio.sleep(delay_between)
                    return await fetch_single(code)

            batch_results = await asyncio.gather(*[fetch_with_semaphore(c) for c in batch])

            for code, data in batch_results:
                if data is not None:
                    results[code] = data

            processed += len(batch)

            # 진행률 콜백
            if progress_callback:
                try:
                    progress_callback(processed, total)
                except Exception:
                    pass

            # 배치 간 짧은 휴식
            if i + batch_size < len(stock_codes):
                await asyncio.sleep(0.2)

        return results


# 싱글톤 클라이언트
_kis_client: Optional[KISClient] = None


def get_kis_client() -> KISClient:
    """KIS 클라이언트 싱글톤 반환."""
    global _kis_client
    if _kis_client is None:
        _kis_client = KISClient()
    return _kis_client
