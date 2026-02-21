import type { PortfolioStats } from '../../types/dashboard_v2'

function formatMoney(n: number | undefined | null): string {
  if (n == null) return '-'
  return n.toLocaleString('ko-KR')
}

interface PortfolioSummaryBarProps {
  stats: PortfolioStats
}

export default function PortfolioSummaryBar({ stats }: PortfolioSummaryBarProps) {
  const profitColor = (stats.total_unrealized_profit ?? 0) >= 0
    ? 'text-red-500 dark:text-red-400'
    : 'text-blue-500 dark:text-blue-400'

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
        {/* 투자금 */}
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">투자금</div>
          <div className="text-lg font-bold text-gray-900 dark:text-gray-100">
            {formatMoney(stats.total_invested)}
          </div>
        </div>

        {/* 평가금 */}
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">평가금</div>
          <div className="text-lg font-bold text-gray-900 dark:text-gray-100">
            {stats.total_eval != null ? formatMoney(stats.total_eval) : '-'}
          </div>
        </div>

        {/* 손익 */}
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">손익</div>
          <div className={`text-lg font-bold ${profitColor}`}>
            {stats.total_unrealized_profit != null
              ? `${stats.total_unrealized_profit >= 0 ? '+' : ''}${formatMoney(stats.total_unrealized_profit)}`
              : '-'}
            {stats.total_return_pct != null && (
              <span className="text-sm ml-1">
                ({stats.total_return_pct >= 0 ? '+' : ''}{stats.total_return_pct.toFixed(1)}%)
              </span>
            )}
          </div>
        </div>

        {/* 구분선 */}
        <div className="h-8 w-px bg-gray-200 dark:bg-gray-700 hidden sm:block" />

        {/* 아이디어 현황 */}
        <div className="flex gap-4">
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400">활성</div>
            <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{stats.active_ideas}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400">관심</div>
            <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{stats.watching_ideas}</div>
          </div>
        </div>

        {/* Best / Worst */}
        {stats.best_performer && (
          <>
            <div className="h-8 w-px bg-gray-200 dark:bg-gray-700 hidden sm:block" />
            <div className="flex gap-4">
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Best</div>
                <div className="text-sm font-semibold text-red-500 dark:text-red-400">
                  {stats.best_performer.stock_name}
                  <span className="ml-1">+{stats.best_performer.return_pct.toFixed(1)}%</span>
                </div>
              </div>
              {stats.worst_performer && (
                <div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">Worst</div>
                  <div className="text-sm font-semibold text-blue-500 dark:text-blue-400">
                    {stats.worst_performer.stock_name}
                    <span className="ml-1">{stats.worst_performer.return_pct.toFixed(1)}%</span>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
