import { useState, useEffect } from 'react'

/**
 * KST 기준 평일 09:00~15:30 장 상태 체크
 */
export function isMarketOpen(): boolean {
  const now = new Date()
  // KST = UTC+9
  const kst = new Date(now.getTime() + (9 * 60 + now.getTimezoneOffset()) * 60000)
  const day = kst.getDay()
  if (day === 0 || day === 6) return false // 주말
  const hhmm = kst.getHours() * 100 + kst.getMinutes()
  return hhmm >= 900 && hhmm <= 1530
}

interface MarketStatus {
  isMarketOpen: boolean
  marketStatusText: string
}

/**
 * 1분마다 장 상태를 갱신하는 훅
 */
export function useMarketStatus(): MarketStatus {
  const [status, setStatus] = useState<MarketStatus>(() => ({
    isMarketOpen: isMarketOpen(),
    marketStatusText: isMarketOpen() ? '장중' : '장마감',
  }))

  useEffect(() => {
    const update = () => {
      const open = isMarketOpen()
      setStatus({
        isMarketOpen: open,
        marketStatusText: open ? '장중' : '장마감',
      })
    }

    const interval = setInterval(update, 60_000)
    return () => clearInterval(interval)
  }, [])

  return status
}
