import { useEffect, useState } from 'react'
import { useDataStore } from '../../store/useDataStore'
import { disclosureApi } from '../../services/api'
import { Card } from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import type { DisclosureImportance } from '../../types/data'

export default function DisclosureList() {
  const { disclosures, disclosuresLoading, fetchDisclosures } = useDataStore()
  const [filter, setFilter] = useState<{
    unreadOnly: boolean
    myIdeasOnly: boolean
    importance?: DisclosureImportance
  }>({ unreadOnly: false, myIdeasOnly: true }) // 기본값: 내 아이디어만

  useEffect(() => {
    fetchDisclosures({
      unread_only: filter.unreadOnly,
      my_ideas_only: filter.myIdeasOnly,
      importance: filter.importance,
    })
  }, [fetchDisclosures, filter])

  const handleMarkAsRead = async (id: string) => {
    await disclosureApi.markAsRead(id)
    fetchDisclosures({
      unread_only: filter.unreadOnly,
      my_ideas_only: filter.myIdeasOnly,
      importance: filter.importance,
    })
  }

  const handleMarkAllAsRead = async () => {
    await disclosureApi.markAllAsRead()
    fetchDisclosures({
      unread_only: filter.unreadOnly,
      my_ideas_only: filter.myIdeasOnly,
      importance: filter.importance,
    })
  }

  const handleCollect = async () => {
    await disclosureApi.collect({})
    fetchDisclosures({
      unread_only: filter.unreadOnly,
      my_ideas_only: filter.myIdeasOnly,
      importance: filter.importance,
    })
  }

  const getImportanceBadge = (importance: DisclosureImportance) => {
    const variants: Record<DisclosureImportance, 'danger' | 'warning' | 'default'> = {
      high: 'danger',
      medium: 'warning',
      low: 'default',
    }
    const labels: Record<DisclosureImportance, string> = {
      high: '중요',
      medium: '보통',
      low: '낮음',
    }
    return <Badge variant={variants[importance]}>{labels[importance]}</Badge>
  }

  const formatDate = (dateStr: string) => {
    if (!dateStr || dateStr.length !== 8) return dateStr
    return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">공시 목록</h1>
        <div className="flex gap-2">
          <Button onClick={handleCollect} variant="secondary">
            공시 수집
          </Button>
          <Button onClick={handleMarkAllAsRead} variant="secondary">
            모두 읽음
          </Button>
        </div>
      </div>

      {/* 필터 */}
      <div className="flex gap-4 flex-wrap">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={filter.myIdeasOnly}
            onChange={(e) => setFilter({ ...filter, myIdeasOnly: e.target.checked })}
            className="rounded text-primary-600"
          />
          <span className="text-sm font-medium">내 아이디어만</span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={filter.unreadOnly}
            onChange={(e) => setFilter({ ...filter, unreadOnly: e.target.checked })}
            className="rounded"
          />
          <span className="text-sm">읽지 않은 것만</span>
        </label>
        <select
          value={filter.importance || ''}
          onChange={(e) =>
            setFilter({
              ...filter,
              importance: e.target.value as DisclosureImportance | undefined,
            })
          }
          className="text-sm border rounded px-2 py-1"
        >
          <option value="">전체 중요도</option>
          <option value="high">중요</option>
          <option value="medium">보통</option>
          <option value="low">낮음</option>
        </select>
      </div>

      {/* 공시 목록 */}
      {disclosuresLoading ? (
        <p className="text-gray-500">로딩 중...</p>
      ) : disclosures.length === 0 ? (
        <Card className="p-6">
          <p className="text-gray-500 text-center py-8">공시가 없습니다.</p>
        </Card>
      ) : (
        <div className="space-y-2">
          {disclosures.map((disclosure) => (
            <Card
              key={disclosure.id}
              className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${
                !disclosure.is_read ? 'border-l-4 border-l-blue-500' : ''
              }`}
              onClick={() => {
                if (disclosure.url) {
                  window.open(disclosure.url, '_blank')
                }
                if (!disclosure.is_read) {
                  handleMarkAsRead(disclosure.id)
                }
              }}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    {getImportanceBadge(disclosure.importance)}
                    <span className="font-medium">{disclosure.corp_name}</span>
                    {disclosure.stock_code && (
                      <span className="text-sm text-gray-500">({disclosure.stock_code})</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-700">{disclosure.report_nm}</p>
                  {disclosure.summary && (
                    <p className="text-xs text-gray-500 mt-1">{disclosure.summary}</p>
                  )}
                </div>
                <div className="text-right text-sm text-gray-500">
                  <p>{formatDate(disclosure.rcept_dt)}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
