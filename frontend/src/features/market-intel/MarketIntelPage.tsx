import { useEffect, useState, useMemo } from 'react'
import type { MarketIntelData } from '../../types/market_intel'
import { marketIntelApi } from '../../services/api'
import { useFeatureFlags } from '../../hooks/useFeatureFlags'
import IntelFeedCard from './IntelFeedCard'

type SignalFilter = 'all' | 'catalyst' | 'flow_spike' | 'chart_pattern' | 'emerging_theme' | 'youtube' | 'convergence' | 'telegram'
type SeverityFilter = 'all' | 'critical' | 'high'

const allFilterButtons: { key: SignalFilter; label: string }[] = [
  { key: 'all', label: '전체' },
  { key: 'catalyst', label: '카탈리스트' },
  { key: 'flow_spike', label: '수급' },
  { key: 'chart_pattern', label: '차트' },
  { key: 'emerging_theme', label: '테마' },
  { key: 'convergence', label: '수렴' },
  { key: 'youtube', label: 'YouTube' },
  { key: 'telegram', label: '텔레그램' },
]

export default function MarketIntelPage() {
  const features = useFeatureFlags()
  const [data, setData] = useState<MarketIntelData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [signalFilter, setSignalFilter] = useState<SignalFilter>('all')
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all')

  const filterButtons = useMemo(() => {
    if (features.telegram) return allFilterButtons
    return allFilterButtons.filter(f => f.key !== 'telegram')
  }, [features.telegram])

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    try {
      setLoading(true)
      const result = await marketIntelApi.getFeed(100)
      setData(result)
      setError(null)
    } catch (e: any) {
      setError(e.message || '시장 인텔리전스 로드 실패')
    } finally {
      setLoading(false)
    }
  }

  const filteredFeed = useMemo(() => {
    if (!data) return []
    let feed = data.feed

    if (signalFilter !== 'all') {
      feed = feed.filter(item => item.signal_type === signalFilter)
    }
    if (severityFilter !== 'all') {
      if (severityFilter === 'critical') {
        feed = feed.filter(item => item.severity === 'critical')
      } else if (severityFilter === 'high') {
        feed = feed.filter(item => item.severity === 'critical' || item.severity === 'high')
      }
    }

    return feed
  }, [data, signalFilter, severityFilter])

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded animate-pulse w-48" />
        <div className="h-12 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-20 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500 mb-4">{error}</p>
        <button onClick={loadData} className="text-blue-500 hover:underline">다시 시도</button>
      </div>
    )
  }

  if (!data) return null

  const { summary } = data

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">시장 인텔리전스</h1>

      {/* 요약 바 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-3">
        <div className="flex flex-wrap gap-3 text-xs">
          {[
            { label: '카탈리스트', count: summary.catalyst, color: 'text-purple-600 dark:text-purple-400' },
            { label: '수급급증', count: summary.flow_spike, color: 'text-blue-600 dark:text-blue-400' },
            { label: '차트패턴', count: summary.chart_pattern, color: 'text-green-600 dark:text-green-400' },
            { label: '테마', count: summary.emerging_theme, color: 'text-orange-600 dark:text-orange-400' },
            { label: '수렴', count: summary.convergence, color: 'text-indigo-600 dark:text-indigo-400' },
            { label: 'YouTube', count: summary.youtube, color: 'text-red-600 dark:text-red-400' },
            ...(features.telegram ? [{ label: '텔레그램', count: summary.telegram, color: 'text-sky-600 dark:text-sky-400' }] : []),
          ].map(s => (
            <span key={s.label} className={s.color}>
              <span className="font-bold">{s.count}</span> {s.label}
            </span>
          ))}
          <span className="ml-auto text-gray-500 dark:text-gray-400">
            총 {summary.total} |
            <span className="text-red-500 ml-1">Critical {summary.critical_count}</span> |
            <span className="text-orange-500 ml-1">High {summary.high_count}</span>
          </span>
        </div>
      </div>

      {/* 필터 */}
      <div className="flex flex-wrap gap-2">
        <div className="flex gap-1">
          {filterButtons.map(f => (
            <button
              key={f.key}
              onClick={() => setSignalFilter(f.key)}
              className={`px-2.5 py-1 text-xs rounded-full transition-colors ${
                signalFilter === f.key
                  ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                  : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="h-6 w-px bg-gray-200 dark:bg-gray-700 hidden sm:block" />
        <div className="flex gap-1">
          {([
            { key: 'all' as SeverityFilter, label: '전체' },
            { key: 'critical' as SeverityFilter, label: 'Critical' },
            { key: 'high' as SeverityFilter, label: 'High+' },
          ]).map(s => (
            <button
              key={s.key}
              onClick={() => setSeverityFilter(s.key)}
              className={`px-2.5 py-1 text-xs rounded-full transition-colors ${
                severityFilter === s.key
                  ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
                  : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* 피드 */}
      <div className="space-y-2">
        {filteredFeed.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400 text-sm">
            필터 조건에 맞는 시그널이 없습니다.
          </div>
        ) : (
          filteredFeed.map((item, idx) => (
            <IntelFeedCard key={`${item.signal_type}-${item.stock_code}-${idx}`} item={item} />
          ))
        )}
      </div>
    </div>
  )
}
