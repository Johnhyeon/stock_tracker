import { useEffect, useState, useCallback } from 'react'
import { Card } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import { dataStatusApi, type DataStatusResponse, type RefreshStatus } from '../../services/api'

const STATUS_LABELS: Record<string, string> = {
  investor_flow: '투자자 수급',
  ohlcv: 'OHLCV (일봉)',
  chart_patterns: '차트 패턴',
  theme_setups: '테마 셋업',
}

const STATUS_COLORS: Record<string, string> = {
  ok: 'bg-green-100 text-green-700',
  stale: 'bg-yellow-100 text-yellow-700',
  empty: 'bg-red-100 text-red-700',
  error: 'bg-gray-100 text-gray-500',
  unknown: 'bg-gray-100 text-gray-400',
}

const STATUS_TEXT: Record<string, string> = {
  ok: '최신',
  stale: '오래됨',
  empty: '데이터 없음',
  error: '오류',
  unknown: '확인 중',
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffHours < 1) return '방금 전'
  if (diffHours < 24) return `${diffHours}시간 전`
  if (diffDays < 7) return `${diffDays}일 전`

  return date.toLocaleDateString('ko-KR', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toString()
}

export default function DataStatusPanel() {
  const [status, setStatus] = useState<DataStatusResponse | null>(null)
  const [refreshStatus, setRefreshStatus] = useState<RefreshStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const data = await dataStatusApi.getStatus()
      setStatus(data)
      setError(null)
    } catch (e) {
      setError('상태 조회 실패')
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchRefreshStatus = useCallback(async () => {
    try {
      const data = await dataStatusApi.getRefreshStatus()
      setRefreshStatus(data)

      // 진행 중이면 계속 폴링
      if (data.is_running) {
        setTimeout(fetchRefreshStatus, 2000)
      } else if (refreshing) {
        // 완료되면 상태 새로고침
        setRefreshing(false)
        fetchStatus()
      }
    } catch (e) {
      console.error(e)
    }
  }, [refreshing, fetchStatus])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  const handleRefreshAll = async () => {
    try {
      setRefreshing(true)
      await dataStatusApi.refresh([])
      fetchRefreshStatus()
    } catch (e) {
      setError('새로고침 시작 실패')
      setRefreshing(false)
    }
  }

  const handleRefreshSingle = async (target: string) => {
    try {
      setRefreshing(true)
      await dataStatusApi.refresh([target])
      fetchRefreshStatus()
    } catch (e) {
      setError('새로고침 시작 실패')
      setRefreshing(false)
    }
  }

  if (loading) {
    return (
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">데이터 상태</h2>
        <p className="text-gray-500">로딩 중...</p>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">데이터 상태</h2>
        <p className="text-red-500">{error}</p>
        <Button onClick={fetchStatus} variant="secondary" className="mt-2">
          다시 시도
        </Button>
      </Card>
    )
  }

  const dataItems = status
    ? [
        { key: 'investor_flow', ...status.investor_flow },
        { key: 'ohlcv', ...status.ohlcv },
        { key: 'chart_patterns', ...status.chart_patterns },
        { key: 'theme_setups', ...status.theme_setups },
      ]
    : []

  const staleCount = dataItems.filter((item) => item.is_stale).length
  const emptyCount = dataItems.filter((item) => item.status === 'empty').length

  return (
    <Card className="p-6">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="text-lg font-semibold">데이터 상태</h2>
          {status && (
            <p className="text-sm text-gray-500">
              {status.overall_status === 'ok' && '모든 데이터가 최신입니다'}
              {status.overall_status === 'needs_refresh' &&
                `${staleCount}개 데이터가 오래되었습니다`}
              {status.overall_status === 'critical' &&
                `${emptyCount}개 데이터가 없습니다`}
            </p>
          )}
        </div>
        <Button
          onClick={handleRefreshAll}
          variant="primary"
          disabled={refreshing}
        >
          {refreshing ? '새로고침 중...' : '전체 새로고침'}
        </Button>
      </div>

      {/* 진행 상태 */}
      {refreshStatus?.is_running && (
        <div className="mb-4 p-3 bg-blue-50 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent" />
            <span className="text-sm font-medium text-blue-700">
              새로고침 진행 중...
            </span>
          </div>
          <div className="space-y-1 text-sm">
            {Object.entries(refreshStatus.progress).map(([key, state]) => (
              <div key={key} className="flex justify-between">
                <span>{STATUS_LABELS[key] || key}</span>
                <span
                  className={
                    state === 'completed'
                      ? 'text-green-600'
                      : state === 'running'
                      ? 'text-blue-600'
                      : state === 'error'
                      ? 'text-red-600'
                      : 'text-gray-400'
                  }
                >
                  {state === 'completed'
                    ? '완료'
                    : state === 'running'
                    ? '진행 중...'
                    : state === 'error'
                    ? '오류'
                    : '대기'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 데이터 항목 목록 */}
      <div className="space-y-3">
        {dataItems.map((item) => (
          <div
            key={item.key}
            className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
          >
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{item.name}</span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    STATUS_COLORS[item.status]
                  }`}
                >
                  {STATUS_TEXT[item.status]}
                </span>
              </div>
              <div className="flex gap-4 text-sm text-gray-500 mt-1">
                <span>레코드: {formatNumber(item.record_count)}</span>
                <span>업데이트: {formatDate(item.last_updated)}</span>
              </div>
            </div>
            <Button
              onClick={() => handleRefreshSingle(item.key)}
              variant="secondary"
              size="sm"
              disabled={refreshing}
            >
              새로고침
            </Button>
          </div>
        ))}
      </div>

      {/* 마지막 확인 시간 */}
      {status && (
        <p className="text-xs text-gray-400 mt-4 text-right">
          확인 시간: {formatDate(status.checked_at)}
        </p>
      )}
    </Card>
  )
}
