import { useState, useEffect } from 'react'
import { tradeApi } from '../../services/api'
import type { TradeAnalysisResponse, TradeType } from '../../types/trade'

const TRADE_TYPE_LABELS: Record<TradeType, string> = {
  BUY: '최초매수',
  ADD_BUY: '추가매수',
  SELL: '전량매도',
  PARTIAL_SELL: '부분매도',
}

const TRADE_TYPE_COLORS: Record<TradeType, string> = {
  BUY: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  ADD_BUY: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200',
  SELL: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  PARTIAL_SELL: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
}

export default function TradeAnalysis() {
  const [analysis, setAnalysis] = useState<TradeAnalysisResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadAnalysis()
  }, [])

  const loadAnalysis = async () => {
    try {
      setLoading(true)
      const data = await tradeApi.getAnalysis()
      setAnalysis(data)
    } catch (err) {
      setError('매매 분석 데이터를 불러오는데 실패했습니다.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('ko-KR').format(num)
  }

  const formatCurrency = (num: number) => {
    if (Math.abs(num) >= 100000000) {
      return `${(num / 100000000).toFixed(1)}억`
    } else if (Math.abs(num) >= 10000) {
      return `${(num / 10000).toFixed(0)}만`
    }
    return formatNumber(num)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg">
        {error}
      </div>
    )
  }

  if (!analysis) {
    return null
  }

  const { summary, monthly_stats, ticker_stats, recent_trades } = analysis

  return (
    <div className="space-y-6">
      {/* 요약 통계 카드 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <div className="text-sm text-gray-500 dark:text-gray-400">총 거래</div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white">
            {summary.total_trades}건
          </div>
          <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            매수 {summary.buy_count} / 매도 {summary.sell_count}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <div className="text-sm text-gray-500 dark:text-gray-400">총 실현손익</div>
          <div className={`text-2xl font-bold ${
            summary.total_realized_profit >= 0
              ? 'text-red-500'
              : 'text-blue-500'
          }`}>
            {summary.total_realized_profit >= 0 ? '+' : ''}{formatCurrency(summary.total_realized_profit)}원
          </div>
          <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            평균 {summary.avg_return_pct >= 0 ? '+' : ''}{summary.avg_return_pct.toFixed(1)}%
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <div className="text-sm text-gray-500 dark:text-gray-400">승률</div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white">
            {summary.win_rate.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            {summary.winning_trades}승 / {summary.losing_trades}패
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <div className="text-sm text-gray-500 dark:text-gray-400">거래 평균손익</div>
          <div className={`text-2xl font-bold ${
            summary.avg_profit_per_trade >= 0
              ? 'text-red-500'
              : 'text-blue-500'
          }`}>
            {summary.avg_profit_per_trade >= 0 ? '+' : ''}{formatCurrency(summary.avg_profit_per_trade)}원
          </div>
        </div>
      </div>

      {/* 월별 통계 */}
      {monthly_stats.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">월별 매매 통계</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400">월</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">거래수</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">매수/매도</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">실현손익</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">승률</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {monthly_stats.map((stat) => (
                  <tr key={stat.month} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-white font-medium">
                      {stat.month}
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600 dark:text-gray-300">
                      {stat.trade_count}건
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600 dark:text-gray-300">
                      {stat.buy_count} / {stat.sell_count}
                    </td>
                    <td className={`px-4 py-3 text-sm text-right font-medium ${
                      stat.realized_profit >= 0 ? 'text-red-500' : 'text-blue-500'
                    }`}>
                      {stat.realized_profit >= 0 ? '+' : ''}{formatCurrency(stat.realized_profit)}원
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600 dark:text-gray-300">
                      {stat.win_rate.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 종목별 통계 */}
      {ticker_stats.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">종목별 매매 통계</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400">종목</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">거래수</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">매수금액</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">매도금액</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">실현손익</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">평균수익률</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">승률</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {ticker_stats.map((stat) => (
                  <tr key={stat.ticker} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-white font-medium">
                      {stat.ticker}
                      {stat.stock_name && (
                        <span className="text-gray-500 dark:text-gray-400 ml-1 text-xs">
                          {stat.stock_name}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600 dark:text-gray-300">
                      {stat.trade_count}건
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600 dark:text-gray-300">
                      {formatCurrency(stat.total_buy_amount)}
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600 dark:text-gray-300">
                      {formatCurrency(stat.total_sell_amount)}
                    </td>
                    <td className={`px-4 py-3 text-sm text-right font-medium ${
                      stat.realized_profit >= 0 ? 'text-red-500' : 'text-blue-500'
                    }`}>
                      {stat.realized_profit >= 0 ? '+' : ''}{formatCurrency(stat.realized_profit)}원
                    </td>
                    <td className={`px-4 py-3 text-sm text-right ${
                      stat.avg_return_pct >= 0 ? 'text-red-500' : 'text-blue-500'
                    }`}>
                      {stat.avg_return_pct >= 0 ? '+' : ''}{stat.avg_return_pct.toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600 dark:text-gray-300">
                      {stat.win_rate.toFixed(1)}%
                      <span className="text-xs text-gray-400 ml-1">
                        ({stat.winning_trades}/{stat.winning_trades + stat.losing_trades})
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 최근 거래 내역 */}
      {recent_trades.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">최근 매매 내역</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400">날짜</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400">유형</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">가격</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">수량</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">금액</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">실현손익</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400">수익률</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {recent_trades.map((trade) => (
                  <tr key={trade.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-white">
                      {trade.trade_date}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${TRADE_TYPE_COLORS[trade.trade_type]}`}>
                        {TRADE_TYPE_LABELS[trade.trade_type]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600 dark:text-gray-300">
                      {formatNumber(trade.price)}원
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600 dark:text-gray-300">
                      {formatNumber(trade.quantity)}주
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600 dark:text-gray-300">
                      {formatCurrency(trade.total_amount)}
                    </td>
                    <td className={`px-4 py-3 text-sm text-right font-medium ${
                      trade.realized_profit === undefined || trade.realized_profit === null
                        ? 'text-gray-400'
                        : trade.realized_profit >= 0
                          ? 'text-red-500'
                          : 'text-blue-500'
                    }`}>
                      {trade.realized_profit !== undefined && trade.realized_profit !== null
                        ? `${trade.realized_profit >= 0 ? '+' : ''}${formatCurrency(trade.realized_profit)}원`
                        : '-'}
                    </td>
                    <td className={`px-4 py-3 text-sm text-right ${
                      trade.realized_return_pct === undefined || trade.realized_return_pct === null
                        ? 'text-gray-400'
                        : trade.realized_return_pct >= 0
                          ? 'text-red-500'
                          : 'text-blue-500'
                    }`}>
                      {trade.realized_return_pct !== undefined && trade.realized_return_pct !== null
                        ? `${trade.realized_return_pct >= 0 ? '+' : ''}${trade.realized_return_pct.toFixed(2)}%`
                        : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 데이터 없음 */}
      {summary.total_trades === 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-8 text-center">
          <div className="text-gray-400 dark:text-gray-500 text-lg">
            아직 매매 기록이 없습니다.
          </div>
          <div className="text-gray-500 dark:text-gray-400 text-sm mt-2">
            포지션에서 추가매수, 부분매도, 전량매도를 하면 자동으로 기록됩니다.
          </div>
        </div>
      )}
    </div>
  )
}
