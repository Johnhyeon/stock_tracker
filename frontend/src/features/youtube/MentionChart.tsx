import { useEffect, useState } from 'react'
import { youtubeApi } from '../../services/api'
import type { TickerMentionHistory } from '../../types/data'

interface MentionChartProps {
  stockCode: string
  daysBack?: number
}

export default function MentionChart({ stockCode, daysBack = 30 }: MentionChartProps) {
  const [history, setHistory] = useState<TickerMentionHistory[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchHistory = async () => {
      setLoading(true)
      try {
        const data = await youtubeApi.getHistory(stockCode, daysBack)
        setHistory(data)
      } catch (err) {
        console.error('Failed to fetch mention history:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchHistory()
  }, [stockCode, daysBack])

  if (loading) {
    return <p className="text-gray-500 text-center py-8">로딩 중...</p>
  }

  if (history.length === 0) {
    return <p className="text-gray-500 text-center py-8">데이터가 없습니다.</p>
  }

  // 간단한 바 차트 렌더링
  const maxMentions = Math.max(...history.map((h) => h.mention_count), 1)

  return (
    <div className="space-y-4">
      {/* 요약 통계 */}
      <div className="grid grid-cols-3 gap-4 text-center">
        <div>
          <p className="text-2xl font-bold text-blue-600">
            {history.reduce((sum, h) => sum + h.mention_count, 0)}
          </p>
          <p className="text-sm text-gray-500">총 언급 횟수</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-green-600">
            {formatViews(history.reduce((sum, h) => sum + h.total_views, 0))}
          </p>
          <p className="text-sm text-gray-500">총 조회수</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-purple-600">{history.length}</p>
          <p className="text-sm text-gray-500">활성 일수</p>
        </div>
      </div>

      {/* 바 차트 */}
      <div className="mt-6">
        <p className="text-sm text-gray-500 mb-2">일별 언급 횟수</p>
        <div className="flex items-end gap-1 h-32">
          {history.map((item) => (
            <div
              key={item.date}
              className="flex-1 flex flex-col items-center"
              title={`${item.date}: ${item.mention_count}회 언급`}
            >
              <div
                className="w-full bg-blue-500 rounded-t"
                style={{
                  height: `${(item.mention_count / maxMentions) * 100}%`,
                  minHeight: item.mention_count > 0 ? '4px' : '0',
                }}
              />
            </div>
          ))}
        </div>
        <div className="flex justify-between text-xs text-gray-400 mt-1">
          <span>{formatDate(history[0]?.date)}</span>
          <span>{formatDate(history[history.length - 1]?.date)}</span>
        </div>
      </div>

      {/* 상세 데이터 테이블 */}
      <div className="mt-4 max-h-48 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="text-gray-500 sticky top-0 bg-white">
            <tr>
              <th className="text-left py-1">날짜</th>
              <th className="text-right py-1">언급</th>
              <th className="text-right py-1">조회수</th>
            </tr>
          </thead>
          <tbody>
            {[...history].reverse().map((item) => (
              <tr key={item.date} className="border-t">
                <td className="py-1">{item.date}</td>
                <td className="text-right py-1">{item.mention_count}회</td>
                <td className="text-right py-1 text-gray-500">{formatViews(item.total_views)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function formatViews(views: number): string {
  if (views >= 1000000) return `${(views / 1000000).toFixed(1)}M`
  if (views >= 1000) return `${(views / 1000).toFixed(1)}K`
  return views.toString()
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
}
