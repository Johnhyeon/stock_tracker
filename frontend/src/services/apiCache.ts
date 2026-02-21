/**
 * 간단한 메모리 기반 API 캐시.
 * 동일 API를 짧은 시간 내 중복 호출하는 것을 방지합니다.
 */

interface CacheEntry<T> {
  data: T
  timestamp: number
}

const cache = new Map<string, CacheEntry<unknown>>()

const DEFAULT_TTL_MS = 60_000 // 1분

/**
 * 캐시 래퍼. TTL 내 동일 키 요청은 캐시에서 반환.
 *
 * @param key - 캐시 키 (보통 API URL + params)
 * @param fetcher - 실제 API 호출 함수
 * @param ttlMs - 캐시 유효 시간 (ms, 기본 1분)
 */
export async function cachedFetch<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttlMs: number = DEFAULT_TTL_MS,
): Promise<T> {
  const now = Date.now()
  const entry = cache.get(key)

  if (entry && now - entry.timestamp < ttlMs) {
    return entry.data as T
  }

  const data = await fetcher()
  cache.set(key, { data, timestamp: now })
  return data
}

/**
 * 특정 키의 캐시를 무효화합니다.
 */
export function invalidateCache(key: string): void {
  cache.delete(key)
}

/**
 * 패턴에 매칭되는 모든 캐시를 무효화합니다.
 */
export function invalidateCacheByPrefix(prefix: string): void {
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) {
      cache.delete(key)
    }
  }
}

/**
 * 모든 캐시를 비웁니다.
 */
export function clearCache(): void {
  cache.clear()
}

// 도메인별 캐시 무효화 헬퍼
export function invalidateDashboard(): void {
  invalidateCache('dashboard')
}

export function invalidateIdeas(): void {
  invalidateCache('dashboard')
}

export function invalidatePrices(): void {
  invalidateCacheByPrefix('ohlcv:')
}

export function invalidateEmerging(): void {
  invalidateCacheByPrefix('emerging:')
}

export function invalidateFlowRanking(): void {
  invalidateCacheByPrefix('flow-')
}
