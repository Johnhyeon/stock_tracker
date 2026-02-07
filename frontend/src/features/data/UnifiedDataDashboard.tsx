import { useEffect, useState, useCallback } from 'react'
import { Card } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import { dataStatusApi, type RefreshStatus } from '../../services/api'
import type {
  AllDataStatusResponse,
  DataCategory,
  DataStatusItemFull,
  DataStatus,
} from '../../types/data_status'
import {
  CATEGORY_META,
  STATUS_COLORS,
  STATUS_TEXT,
  STATUS_DOT_COLORS,
} from '../../types/data_status'

// 날짜 포맷팅 헬퍼
function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffMins < 1) return '방금 전'
  if (diffMins < 60) return `${diffMins}분 전`
  if (diffHours < 24) return `${diffHours}시간 전`
  if (diffDays < 7) return `${diffDays}일 전`

  return date.toLocaleDateString('ko-KR', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// 숫자 포맷팅 헬퍼
function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toLocaleString()
}

// 카테고리 아코디언 컴포넌트
interface CategorySectionProps {
  category: DataCategory
  items: DataStatusItemFull[]
  refreshing: boolean
  refreshStatus: RefreshStatus | null
  onRefreshCategory: (items: DataStatusItemFull[]) => void
  onRefreshSingle: (key: string) => void
}

function CategorySection({
  category,
  items,
  refreshing,
  refreshStatus,
  onRefreshCategory,
  onRefreshSingle,
}: CategorySectionProps) {
  const [isOpen, setIsOpen] = useState(true)
  const meta = CATEGORY_META[category]

  const staleCount = items.filter((item) => item.is_stale).length
  const refreshableItems = items.filter((item) => item.can_refresh)

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      {/* 카테고리 헤더 */}
      <div
        className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-3">
          <span className="text-xl">{meta.icon}</span>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100">
              {meta.name}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {items.length}개 항목
              {staleCount > 0 && (
                <span className="text-yellow-600 dark:text-yellow-400 ml-2">
                  ({staleCount}개 오래됨)
                </span>
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {refreshableItems.length > 0 && (
            <Button
              onClick={(e) => {
                e.stopPropagation()
                onRefreshCategory(refreshableItems)
              }}
              variant="secondary"
              size="sm"
              disabled={refreshing}
            >
              전체 새로고침
            </Button>
          )}
          <svg
            className={`w-5 h-5 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* 아이템 목록 */}
      {isOpen && (
        <div className="divide-y divide-gray-100 dark:divide-gray-700">
          {items.map((item) => (
            <DataStatusRow
              key={item.key}
              item={item}
              refreshing={refreshing}
              refreshStatus={refreshStatus}
              onRefresh={() => onRefreshSingle(item.key)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// 데이터 상태 행 컴포넌트
interface DataStatusRowProps {
  item: DataStatusItemFull
  refreshing: boolean
  refreshStatus: RefreshStatus | null
  onRefresh: () => void
}

function DataStatusRow({ item, refreshing, refreshStatus, onRefresh }: DataStatusRowProps) {
  const isItemRefreshing = refreshStatus?.progress?.[item.key] === 'running'
  const itemProgress = refreshStatus?.progress?.[item.key]

  return (
    <div className="flex items-center justify-between p-4 bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
      <div className="flex items-center gap-3 flex-1">
        {/* 상태 도트 */}
        <div className={`w-2.5 h-2.5 rounded-full ${STATUS_DOT_COLORS[item.status as DataStatus]}`} />

        {/* 데이터 정보 */}
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-900 dark:text-gray-100">
              {item.name}
            </span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[item.status as DataStatus]}`}
            >
              {STATUS_TEXT[item.status as DataStatus]}
            </span>
            {isItemRefreshing && (
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent" />
            )}
            {itemProgress === 'completed' && (
              <span className="text-xs text-green-600 dark:text-green-400">완료</span>
            )}
            {itemProgress === 'error' && (
              <span className="text-xs text-red-600 dark:text-red-400">오류</span>
            )}
          </div>
          <div className="flex gap-4 text-sm text-gray-500 dark:text-gray-400 mt-1">
            <span>레코드: {formatNumber(item.record_count)}</span>
            <span>업데이트: {formatDate(item.last_updated)}</span>
            <span className="text-gray-400 dark:text-gray-500">
              스케줄: {item.schedule.description}
            </span>
          </div>
        </div>
      </div>

      {/* 새로고침 버튼 */}
      {item.can_refresh && (
        <Button
          onClick={onRefresh}
          variant="secondary"
          size="sm"
          disabled={refreshing || isItemRefreshing}
        >
          {isItemRefreshing ? '진행 중...' : '새로고침'}
        </Button>
      )}
    </div>
  )
}

// 전체 상태 요약 컴포넌트
interface StatusSummaryProps {
  status: AllDataStatusResponse
}

function StatusSummary({ status }: StatusSummaryProps) {
  const allItems = [
    ...status.market,
    ...status.analysis,
    ...status.external,
    ...status.telegram,
  ]

  const okCount = allItems.filter((item) => item.status === 'ok').length
  const staleCount = allItems.filter((item) => item.status === 'stale').length
  const emptyCount = allItems.filter((item) => item.status === 'empty').length
  const errorCount = allItems.filter((item) => item.status === 'error').length

  const getOverallColor = () => {
    if (status.overall_status === 'ok') return 'text-green-600 dark:text-green-400'
    if (status.overall_status === 'needs_refresh') return 'text-yellow-600 dark:text-yellow-400'
    return 'text-red-600 dark:text-red-400'
  }

  const getOverallText = () => {
    if (status.overall_status === 'ok') return '모든 데이터가 최신입니다'
    if (status.overall_status === 'needs_refresh') return `${staleCount}개 데이터가 오래되었습니다`
    return `${emptyCount}개 데이터가 없습니다`
  }

  return (
    <div className="flex items-center justify-between">
      <div>
        <p className={`text-sm font-medium ${getOverallColor()}`}>
          {getOverallText()}
        </p>
        <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400 mt-1">
          <span className="text-green-600 dark:text-green-400">최신 {okCount}</span>
          <span className="text-yellow-600 dark:text-yellow-400">오래됨 {staleCount}</span>
          {emptyCount > 0 && (
            <span className="text-red-600 dark:text-red-400">없음 {emptyCount}</span>
          )}
          {errorCount > 0 && (
            <span className="text-gray-500">오류 {errorCount}</span>
          )}
        </div>
      </div>
      <p className="text-xs text-gray-400 dark:text-gray-500">
        확인: {formatDate(status.checked_at)}
      </p>
    </div>
  )
}

// 메인 컴포넌트
export default function UnifiedDataDashboard() {
  const [status, setStatus] = useState<AllDataStatusResponse | null>(null)
  const [refreshStatus, setRefreshStatus] = useState<RefreshStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const data = await dataStatusApi.getAllStatus()
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

      if (data.is_running) {
        setTimeout(fetchRefreshStatus, 2000)
      } else if (refreshing) {
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

  // 전체 새로고침
  const handleRefreshAll = async () => {
    if (!status) return

    try {
      setRefreshing(true)
      const allItems = [
        ...status.market,
        ...status.analysis,
        ...status.external,
        ...status.telegram,
      ]
      const refreshableKeys = allItems
        .filter((item) => item.can_refresh)
        .map((item) => item.key)

      await dataStatusApi.refresh(refreshableKeys)
      fetchRefreshStatus()
    } catch (e) {
      setError('새로고침 시작 실패')
      setRefreshing(false)
    }
  }

  // 카테고리별 새로고침
  const handleRefreshCategory = async (items: DataStatusItemFull[]) => {
    try {
      setRefreshing(true)
      const keys = items.filter((item) => item.can_refresh).map((item) => item.key)
      await dataStatusApi.refresh(keys)
      fetchRefreshStatus()
    } catch (e) {
      setError('새로고침 시작 실패')
      setRefreshing(false)
    }
  }

  // 단일 항목 새로고침
  const handleRefreshSingle = async (key: string) => {
    try {
      setRefreshing(true)
      await dataStatusApi.refresh([key])
      fetchRefreshStatus()
    } catch (e) {
      setError('새로고침 시작 실패')
      setRefreshing(false)
    }
  }

  if (loading) {
    return (
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">데이터 수집 현황</h2>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent" />
          <span className="ml-3 text-gray-500 dark:text-gray-400">로딩 중...</span>
        </div>
      </Card>
    )
  }

  if (error && !status) {
    return (
      <Card className="p-6">
        <h2 className="text-lg font-semibold mb-4">데이터 수집 현황</h2>
        <p className="text-red-500">{error}</p>
        <Button onClick={fetchStatus} variant="secondary" className="mt-2">
          다시 시도
        </Button>
      </Card>
    )
  }

  if (!status) return null

  const categories: { key: DataCategory; items: DataStatusItemFull[] }[] = [
    { key: 'market', items: status.market },
    { key: 'analysis', items: status.analysis },
    { key: 'external', items: status.external },
    { key: 'telegram', items: status.telegram },
  ]

  return (
    <Card className="p-6">
      {/* 헤더 */}
      <div className="flex justify-between items-start mb-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            데이터 수집 현황
          </h2>
          <StatusSummary status={status} />
        </div>
        <Button
          onClick={handleRefreshAll}
          variant="primary"
          disabled={refreshing}
        >
          {refreshing ? '새로고침 중...' : '전체 새로고침'}
        </Button>
      </div>

      {/* 진행 상태 바 */}
      {refreshStatus?.is_running && (
        <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
          <div className="flex items-center gap-2 mb-3">
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent" />
            <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
              새로고침 진행 중...
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 text-sm">
            {Object.entries(refreshStatus.progress).map(([key, state]) => (
              <div
                key={key}
                className="flex items-center justify-between px-2 py-1 bg-white dark:bg-gray-800 rounded"
              >
                <span className="text-gray-700 dark:text-gray-300 truncate">
                  {key}
                </span>
                <span
                  className={
                    state === 'completed'
                      ? 'text-green-600 dark:text-green-400'
                      : state === 'running'
                      ? 'text-blue-600 dark:text-blue-400'
                      : state === 'error'
                      ? 'text-red-600 dark:text-red-400'
                      : 'text-gray-400'
                  }
                >
                  {state === 'completed'
                    ? '완료'
                    : state === 'running'
                    ? '진행 중'
                    : state === 'error'
                    ? '오류'
                    : '대기'}
                </span>
              </div>
            ))}
          </div>
          {refreshStatus.errors.length > 0 && (
            <div className="mt-3 text-sm text-red-600 dark:text-red-400">
              <p className="font-medium">오류 발생:</p>
              <ul className="list-disc list-inside">
                {refreshStatus.errors.map((err, idx) => (
                  <li key={idx}>{err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 카테고리별 섹션 */}
      <div className="space-y-4">
        {categories.map(({ key, items }) => (
          <CategorySection
            key={key}
            category={key}
            items={items}
            refreshing={refreshing}
            refreshStatus={refreshStatus}
            onRefreshCategory={handleRefreshCategory}
            onRefreshSingle={handleRefreshSingle}
          />
        ))}
      </div>

      {/* 에러 표시 */}
      {error && (
        <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
          {error}
        </div>
      )}
    </Card>
  )
}
