"""Base HTTP client with retry and rate limiting support."""
import asyncio
import logging
from typing import Any, Optional
from abc import ABC, abstractmethod

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter.

    asyncio.Lock으로 요청 직렬화 + 최소 간격 보장.
    gather()로 병렬 호출해도 초당 제한을 정확히 지킵니다.
    """

    def __init__(self, calls_per_second: float = 5.0):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self._lock: Optional[asyncio.Lock] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._last_call_time: float = 0.0

    def _get_lock(self) -> asyncio.Lock:
        """현재 이벤트 루프에 맞는 Lock 반환."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._lock is None or self._loop is not current_loop:
            self._lock = asyncio.Lock()
            self._loop = current_loop
            self._last_call_time = 0.0

        return self._lock

    async def acquire(self):
        lock = self._get_lock()
        async with lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            wait_time = self.min_interval - (now - self._last_call_time)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_call_time = asyncio.get_running_loop().time()


class BaseAPIClient(ABC):
    """Base class for API clients with retry and rate limiting."""

    def __init__(
        self,
        base_url: str,
        rate_limit: float = 5.0,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.rate_limiter = RateLimiter(rate_limit)
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    def get_headers(self) -> dict[str, str]:
        """Return headers for API requests. Override in subclasses."""
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with retry and rate limiting."""
        await self.rate_limiter.acquire()

        request_headers = self.get_headers()
        if headers:
            request_headers.update(headers)

        try:
            response = await self.client.request(
                method=method,
                url=path,
                params=params,
                json=json_data,
                headers=request_headers,
            )

            # 초당 거래건수 초과 (EGW00201) → 잠시 대기 후 재시도
            if response.status_code == 500:
                try:
                    body = response.json()
                    if body.get("msg_cd") == "EGW00201":
                        logger.warning(f"Rate limit hit for {method} {path}, backing off 1s")
                        await asyncio.sleep(1.0)
                        # 재시도
                        await self.rate_limiter.acquire()
                        response = await self.client.request(
                            method=method,
                            url=path,
                            params=params,
                            json=json_data,
                            headers=request_headers,
                        )
                except (ValueError, KeyError):
                    pass

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error {e.response.status_code} for {method} {path}: {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error for {method} {path}: {e}")
            raise

    async def get(
        self,
        path: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> dict[str, Any]:
        return await self._request("GET", path, params=params, headers=headers)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def _request_binary(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> bytes:
        """Make an HTTP request that returns binary data (e.g. ZIP files)."""
        await self.rate_limiter.acquire()

        request_headers = self.get_headers()
        if headers:
            request_headers.update(headers)

        try:
            response = await self.client.request(
                method=method,
                url=path,
                params=params,
                headers=request_headers,
            )
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error {e.response.status_code} for {method} {path}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error for {method} {path}: {e}")
            raise

    async def post(
        self,
        path: str,
        json_data: Optional[dict] = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST", path, params=params, json_data=json_data, headers=headers
        )
