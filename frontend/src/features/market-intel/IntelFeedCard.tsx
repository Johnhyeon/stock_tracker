import { Link } from 'react-router-dom'
import type { IntelFeedItem } from '../../types/market_intel'
import { WatchlistStar } from '../../components/WatchlistStar'

const severityConfig: Record<string, { border: string; bg: string; label: string; text: string }> = {
  critical: {
    border: 'border-l-red-500',
    bg: 'bg-red-50 dark:bg-red-900/20',
    label: 'CRITICAL',
    text: 'text-red-600 dark:text-red-400',
  },
  high: {
    border: 'border-l-orange-500',
    bg: 'bg-orange-50 dark:bg-orange-900/20',
    label: 'HIGH',
    text: 'text-orange-600 dark:text-orange-400',
  },
  medium: {
    border: 'border-l-yellow-500',
    bg: 'bg-white dark:bg-gray-800',
    label: 'MEDIUM',
    text: 'text-yellow-600 dark:text-yellow-400',
  },
  info: {
    border: 'border-l-gray-300 dark:border-l-gray-600',
    bg: 'bg-white dark:bg-gray-800',
    label: 'INFO',
    text: 'text-gray-400',
  },
}

const signalTypeConfig: Record<string, { icon: string; label: string; color: string }> = {
  catalyst: { icon: '⚡', label: '카탈리스트', color: 'text-purple-600 dark:text-purple-400' },
  flow_spike: { icon: '📊', label: '수급급증', color: 'text-blue-600 dark:text-blue-400' },
  chart_pattern: { icon: '📈', label: '차트패턴', color: 'text-green-600 dark:text-green-400' },
  emerging_theme: { icon: '🔥', label: '테마', color: 'text-orange-600 dark:text-orange-400' },
  youtube: { icon: '▶', label: 'YouTube', color: 'text-red-600 dark:text-red-400' },
  convergence: { icon: '🎯', label: '수렴', color: 'text-indigo-600 dark:text-indigo-400' },
  telegram: { icon: '💬', label: '텔레그램', color: 'text-sky-600 dark:text-sky-400' },
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 60) return `${minutes}분 전`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}시간 전`
  const days = Math.floor(hours / 24)
  return `${days}일 전`
}

interface IntelFeedCardProps {
  item: IntelFeedItem
}

export default function IntelFeedCard({ item }: IntelFeedCardProps) {
  const sev = severityConfig[item.severity] || severityConfig.info
  const sig = signalTypeConfig[item.signal_type] || signalTypeConfig.catalyst

  return (
    <div className={`border-l-4 ${sev.border} ${sev.bg} rounded-r-lg p-3 transition-all hover:shadow-sm`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          {/* 배지 + 제목 */}
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-bold ${sev.text} uppercase`}>{sev.label}</span>
            <span className={`text-xs ${sig.color}`}>
              {sig.icon} {sig.label}
            </span>
          </div>

          {/* 종목명 + 제목 */}
          <div className="flex items-center gap-1.5">
            {item.stock_code && (
              <>
                <WatchlistStar stockCode={item.stock_code!} stockName={item.stock_name || item.stock_code!} />
                <Link
                  to={`/stocks/${item.stock_code}`}
                  className="font-semibold text-sm text-gray-900 dark:text-gray-100 hover:text-blue-600 dark:hover:text-blue-400 flex-shrink-0"
                >
                  {item.stock_name || item.stock_code}
                </Link>
              </>
            )}
            <span className="text-sm text-gray-700 dark:text-gray-300 truncate">
              {item.stock_code ? '- ' : ''}{item.title}
            </span>
          </div>

          {/* 설명 */}
          {item.description && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">
              {item.description}
            </p>
          )}
        </div>

        {/* 시간 */}
        <div className="flex-shrink-0 text-xs text-gray-400">
          {timeAgo(item.timestamp)}
        </div>
      </div>
    </div>
  )
}
