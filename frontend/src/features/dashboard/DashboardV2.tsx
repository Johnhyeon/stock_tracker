import { useEffect, useState, useMemo, useCallback } from 'react'
import { Link } from 'react-router-dom'
import type { PortfolioDashboardData, PortfolioPosition } from '../../types/dashboard_v2'
import { dashboardV2Api } from '../../services/api'
import PortfolioSummaryBar from './PortfolioSummaryBar'
import PortfolioPnLChart from './PortfolioPnLChart'
import PositionCard from './PositionCard'
import { DashboardSkeleton } from '../../components/SkeletonLoader'
import { useRealtimePolling } from '../../hooks/useRealtimePolling'

type SortKey = 'return' | 'smart' | 'invested'

export default function DashboardV2() {
  const [data, setData] = useState<PortfolioDashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('return')
  const [watchingOpen, setWatchingOpen] = useState(false)

  useEffect(() => {
    loadDashboard()
  }, [])

  async function loadDashboard() {
    try {
      setLoading(true)
      const result = await dashboardV2Api.get()
      setData(result)
      setError(null)
    } catch (e: any) {
      setError(e.message || '대시보드 로드 실패')
    } finally {
      setLoading(false)
    }
  }

  const silentRefetch = useCallback(async () => {
    try {
      const result = await dashboardV2Api.get()
      setData(result)
    } catch { /* 조용히 실패 */ }
  }, [])

  useRealtimePolling(silentRefetch, 30_000, {
    onlyMarketHours: true,
    enabled: !!data,
  })

  // 활성 아이디어의 모든 포지션을 플랫하게 추출
  const activePositions = useMemo(() => {
    if (!data) return []
    const positions: PortfolioPosition[] = []
    for (const idea of data.active_ideas) {
      for (const pos of idea.positions) {
        positions.push(pos)
      }
    }
    return positions
  }, [data])

  // 정렬
  const sortedPositions = useMemo(() => {
    const sorted = [...activePositions]
    switch (sortKey) {
      case 'return':
        sorted.sort((a, b) => (b.unrealized_return_pct ?? -999) - (a.unrealized_return_pct ?? -999))
        break
      case 'smart':
        sorted.sort((a, b) => (b.smart_score?.composite_score ?? 0) - (a.smart_score?.composite_score ?? 0))
        break
      case 'invested':
        sorted.sort((a, b) => (b.invested ?? 0) - (a.invested ?? 0))
        break
    }
    return sorted
  }, [activePositions, sortKey])

  // 관심종목 포지션
  const watchingPositions = useMemo(() => {
    if (!data) return []
    const positions: PortfolioPosition[] = []
    for (const idea of data.watching_ideas) {
      for (const pos of idea.positions) {
        positions.push(pos)
      }
    }
    return positions
  }, [data])

  if (loading) return <DashboardSkeleton />
  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500 mb-4">{error}</p>
        <button onClick={loadDashboard} className="text-blue-500 hover:underline">다시 시도</button>
      </div>
    )
  }
  if (!data) return null

  return (
    <div className="space-y-4">
      {/* [1] 포트폴리오 요약 바 */}
      <PortfolioSummaryBar stats={data.stats} />

      {/* [2] 수익 추이 차트 */}
      <PortfolioPnLChart data={data.portfolio_trend} />

      {/* [3] 보유 포지션 그리드 */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            보유 포지션 ({sortedPositions.length})
          </h2>
          <div className="flex gap-1">
            {([
              { key: 'return' as SortKey, label: '수익률순' },
              { key: 'smart' as SortKey, label: 'SmartScore' },
              { key: 'invested' as SortKey, label: '투자금순' },
            ]).map(s => (
              <button
                key={s.key}
                onClick={() => setSortKey(s.key)}
                className={`px-2.5 py-1 text-xs rounded-full transition-colors ${
                  sortKey === s.key
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                    : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {sortedPositions.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            <p>활성 포지션이 없습니다.</p>
            <Link to="/ideas/create" className="text-blue-500 hover:underline text-sm mt-2 inline-block">
              아이디어 추가하기
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {sortedPositions.map(pos => (
              <PositionCard key={pos.id} position={pos} />
            ))}
          </div>
        )}
      </div>

      {/* [4] 관심 종목 (접이식) */}
      {watchingPositions.length > 0 && (
        <div>
          <button
            onClick={() => setWatchingOpen(!watchingOpen)}
            className="flex items-center gap-2 text-sm font-semibold text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
          >
            <svg
              className={`w-4 h-4 transition-transform ${watchingOpen ? 'rotate-90' : ''}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            관심 종목 ({watchingPositions.length})
          </button>

          {watchingOpen && (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 mt-3">
              {watchingPositions.map(pos => (
                <PositionCard key={pos.id} position={pos} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
