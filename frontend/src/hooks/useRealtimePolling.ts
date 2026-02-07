import { useEffect, useRef, useCallback } from 'react'
import { isMarketOpen } from './useMarketStatus'

interface PollingOptions {
  /** 장중에만 폴링할지 여부 (기본 true) */
  onlyMarketHours?: boolean
  /** 폴링 활성화 여부 (기본 true) */
  enabled?: boolean
}

/**
 * 장중에만 자동 폴링하는 재사용 가능 훅.
 *
 * @param fetchFn - 데이터 fetch 함수
 * @param intervalMs - 폴링 간격 (ms)
 * @param options - 옵션
 */
export function useRealtimePolling(
  fetchFn: () => void | Promise<void>,
  intervalMs: number,
  options: PollingOptions = {},
): void {
  const { onlyMarketHours = true, enabled = true } = options
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const fetchRef = useRef(fetchFn)

  // fetchFn이 바뀔 때 ref 갱신 (interval 재설정 방지)
  useEffect(() => {
    fetchRef.current = fetchFn
  }, [fetchFn])

  const tick = useCallback(() => {
    if (onlyMarketHours && !isMarketOpen()) return
    fetchRef.current()
  }, [onlyMarketHours])

  useEffect(() => {
    if (!enabled) return

    intervalRef.current = setInterval(tick, intervalMs)
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [tick, intervalMs, enabled])
}
