import { Link } from 'react-router-dom'
import type { PortfolioPosition } from '../../types/dashboard_v2'
import MiniSparkline from './MiniSparkline'
import SmartScoreBadge from './SmartScoreBadge'
import { WatchlistStar } from '../../components/WatchlistStar'

function formatMoney(n: number | undefined | null): string {
  if (n == null) return '-'
  return n.toLocaleString('ko-KR')
}

function getReturnColor(pct: number | undefined | null): string {
  if (pct == null) return 'bg-gray-200 dark:bg-gray-700'
  if (pct > 0) return 'bg-red-500'
  if (pct < 0) return 'bg-blue-500'
  return 'bg-gray-400'
}

function getReturnTextColor(pct: number | undefined | null): string {
  if (pct == null) return 'text-gray-500'
  if (pct > 0) return 'text-red-500 dark:text-red-400'
  if (pct < 0) return 'text-blue-500 dark:text-blue-400'
  return 'text-gray-500'
}

function getBarHeight(pct: number | undefined | null): string {
  if (pct == null) return 'h-0'
  const absPct = Math.min(Math.abs(pct), 30)
  const ratio = absPct / 30
  return `${Math.max(ratio * 100, 5)}%`
}

interface PositionCardProps {
  position: PortfolioPosition
}

export default function PositionCard({ position }: PositionCardProps) {
  const {
    stock_code, stock_name, ticker,
    entry_price, quantity, days_held,
    current_price, unrealized_profit, unrealized_return_pct,
    smart_score, price_trend_7d,
  } = position
  return (
    <div className="relative flex bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden hover:shadow-md transition-shadow">
      {/* 좌측 컬러바 */}
      <div
        className={`w-1.5 flex-shrink-0 ${getReturnColor(unrealized_return_pct)}`}
        style={{ opacity: unrealized_return_pct != null ? Math.min(0.4 + Math.abs(unrealized_return_pct) / 30, 1) : 0.3 }}
      />

      <div className="flex-1 p-3 min-w-0">
        {/* 상단: 종목명 + SmartScore */}
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2 min-w-0">
            {stock_code && (
              <WatchlistStar stockCode={stock_code} stockName={stock_name || ticker} />
            )}
            <Link
              to={stock_code ? `/stocks/${stock_code}` : '#'}
              className="font-semibold text-sm text-gray-900 dark:text-gray-100 hover:text-blue-600 dark:hover:text-blue-400 truncate"
            >
              {stock_name || ticker}
            </Link>
            <span className="text-xs text-gray-400 flex-shrink-0">{stock_code}</span>
          </div>
          {smart_score && (
            <SmartScoreBadge score={smart_score} />
          )}
        </div>

        {/* 현재가 + 수익률 */}
        <div className="flex items-baseline gap-3 mb-2">
          <span className="text-lg font-bold text-gray-900 dark:text-gray-100">
            {formatMoney(current_price)}
            <span className="text-xs text-gray-400 ml-0.5">원</span>
          </span>
          <span className={`text-sm font-semibold ${getReturnTextColor(unrealized_return_pct)}`}>
            {unrealized_return_pct != null ? (unrealized_return_pct > 0 ? '+' : '') + unrealized_return_pct.toFixed(1) + '%' : '-'}
          </span>
          <span className={`text-xs ${getReturnTextColor(unrealized_return_pct)}`}>
            {unrealized_profit != null ? (unrealized_profit > 0 ? '+' : '') + formatMoney(unrealized_profit) : ''}
          </span>
        </div>

        {/* 수익률 프로그레스 바 */}
        {unrealized_return_pct != null && (
          <div className="w-full h-1 bg-gray-100 dark:bg-gray-700 rounded-full mb-2 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${unrealized_return_pct >= 0 ? 'bg-red-400' : 'bg-blue-400'}`}
              style={{ width: getBarHeight(unrealized_return_pct) }}
            />
          </div>
        )}

        {/* 하단: 매수정보 + 스파크라인 + 4차원 그리드 */}
        <div className="flex items-center justify-between">
          <div className="text-xs text-gray-500 dark:text-gray-400">
            <span>매수 {formatMoney(entry_price)} x {quantity}주</span>
            <span className="ml-2">보유 {days_held}일</span>
          </div>
          <div className="flex items-center gap-2">
            <MiniSparkline data={price_trend_7d} width={60} height={20} />
            {smart_score && <SmartScoreBadge score={smart_score} compact />}
          </div>
        </div>
      </div>
    </div>
  )
}
