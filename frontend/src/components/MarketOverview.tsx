import { useState, useEffect, useCallback } from 'react'
import { dataApi } from '../services/api'
import type { MarketIndicesResponse } from '../services/api'
import { useMarketStatus } from '../hooks/useMarketStatus'
import { useRealtimePolling } from '../hooks/useRealtimePolling'

function IndexDisplay({ name, value, change, changeRate }: {
  name: string
  value: number
  change: number
  changeRate: number
}) {
  const isUp = change >= 0
  const color = isUp ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'
  const sign = isUp ? '+' : ''

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{name}</span>
      <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
        {value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>
      <span className={`text-xs font-medium ${color}`}>
        {sign}{change.toFixed(2)} ({sign}{changeRate.toFixed(2)}%)
      </span>
    </div>
  )
}

export default function MarketOverview() {
  const [indices, setIndices] = useState<MarketIndicesResponse | null>(null)
  const { isMarketOpen } = useMarketStatus()

  const fetchIndices = useCallback(async () => {
    try {
      const data = await dataApi.getMarketIndex()
      setIndices(data)
    } catch {
      // 조용히 실패 - 네트워크 문제 등
    }
  }, [])

  // 초기 로드
  useEffect(() => {
    fetchIndices()
  }, [fetchIndices])

  // 장중 60초 자동 갱신
  useRealtimePolling(fetchIndices, 60_000, { onlyMarketHours: true })

  // 데이터 없거나 값이 0이면 숨김 (모의투자 등)
  if (!indices || (indices.kospi.current_value === 0 && indices.kosdaq.current_value === 0)) return null

  return (
    <div className="flex items-center gap-4">
      <IndexDisplay
        name="KOSPI"
        value={indices.kospi.current_value}
        change={indices.kospi.change}
        changeRate={indices.kospi.change_rate}
      />
      <span className="text-gray-300 dark:text-gray-600">|</span>
      <IndexDisplay
        name="KOSDAQ"
        value={indices.kosdaq.current_value}
        change={indices.kosdaq.change}
        changeRate={indices.kosdaq.change_rate}
      />
      {isMarketOpen && (
        <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" title="장중" />
      )}
    </div>
  )
}
