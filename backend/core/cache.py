"""서버 사이드 인메모리 TTL 캐시.

자주 호출되는 API 엔드포인트에 캐시를 적용합니다.
- 대시보드: 30초 TTL (자주 폴링하지만 데이터가 빈번히 변하지 않음)
- 분석 시그널: 60초 TTL (분석 결과는 비교적 안정적)
- 수급 랭킹: 이미 flow_ranking.py에서 자체 TTL 캐시 사용 (5분)

사용법:
    from core.cache import api_cache

    # 캐시 조회/저장
    cached = api_cache.get("dashboard")
    if cached:
        return cached
    result = expensive_computation()
    api_cache.set("dashboard", result, ttl=30)
    return result

    # 캐시 무효화
    api_cache.invalidate("dashboard")
"""
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class APICache:
    """간단한 키-값 TTL 캐시."""

    def __init__(self):
        self._store: dict[str, tuple[float, float, Any]] = {}  # key -> (expire_at, ttl, value)

    def get(self, key: str) -> Optional[Any]:
        """캐시에서 값을 조회합니다. 만료되었으면 None 반환."""
        if key in self._store:
            expire_at, _, value = self._store[key]
            if time.time() < expire_at:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 60) -> None:
        """캐시에 값을 저장합니다.

        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: 만료 시간(초). 기본 60초
        """
        self._store[key] = (time.time() + ttl, ttl, value)

    def invalidate(self, key: str) -> bool:
        """특정 키의 캐시를 무효화합니다."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    def invalidate_prefix(self, prefix: str) -> int:
        """특정 접두사로 시작하는 모든 캐시를 무효화합니다."""
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for key in keys_to_delete:
            del self._store[key]
        return len(keys_to_delete)

    def clear(self) -> None:
        """모든 캐시를 초기화합니다."""
        self._store.clear()

    def stats(self) -> dict:
        """캐시 통계를 반환합니다."""
        now = time.time()
        total = len(self._store)
        active = sum(1 for expire_at, _, _ in self._store.values() if now < expire_at)
        return {
            "total_keys": total,
            "active_keys": active,
            "expired_keys": total - active,
        }


# 싱글톤 인스턴스
api_cache = APICache()
