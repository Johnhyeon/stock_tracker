import { useEffect } from 'react'
import { useDataStore } from '../../store/useDataStore'
import { Card } from '../../components/ui/Card'
import SchedulerStatus from './SchedulerStatus'
import APIHealthCheck from './APIHealthCheck'
import UnifiedDataDashboard from './UnifiedDataDashboard'

export default function DataMonitor() {
  const {
    disclosureStats,
    trendingTickers,
    fetchDisclosureStats,
    fetchTrendingTickers,
    disclosuresLoading,
    trendingLoading,
  } = useDataStore()

  useEffect(() => {
    fetchDisclosureStats()
    fetchTrendingTickers(7)
  }, [fetchDisclosureStats, fetchTrendingTickers])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-t-text-primary">데이터 모니터링</h1>

      {/* 통합 데이터 수집 현황 (새로고침 기능 포함) */}
      <UnifiedDataDashboard />

      {/* API 연결 상태 */}
      <APIHealthCheck />

      {/* 스케줄러 상태 */}
      <SchedulerStatus />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 공시 통계 */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">공시 현황</h2>
          {disclosuresLoading ? (
            <p className="text-gray-500">로딩 중...</p>
          ) : disclosureStats ? (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span>전체 공시</span>
                <span className="font-medium">{disclosureStats.total}건</span>
              </div>
              <div className="flex justify-between">
                <span>읽지 않은 공시</span>
                <span className="font-medium text-red-600">{disclosureStats.unread}건</span>
              </div>
              <div className="border-t pt-3 mt-3">
                <p className="text-sm text-gray-500 mb-2">중요도별</p>
                <div className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-red-600">높음</span>
                    <span>{disclosureStats.by_importance.high || 0}건</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-yellow-600">보통</span>
                    <span>{disclosureStats.by_importance.medium || 0}건</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">낮음</span>
                    <span>{disclosureStats.by_importance.low || 0}건</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">데이터 없음</p>
          )}
        </Card>

        {/* YouTube 트렌딩 */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4">YouTube 트렌딩 종목 (7일)</h2>
          {trendingLoading ? (
            <p className="text-gray-500">로딩 중...</p>
          ) : trendingTickers.length > 0 ? (
            <div className="space-y-2">
              {trendingTickers.slice(0, 10).map((ticker, index) => (
                <div key={ticker.stock_code} className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-500 w-5">{index + 1}</span>
                    <span className="font-medium">{ticker.stock_name || ticker.stock_code}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-sm text-blue-600">{ticker.mention_count}회 언급</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500">데이터 없음</p>
          )}
        </Card>
      </div>
    </div>
  )
}
