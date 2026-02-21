import { useState, useEffect, useMemo, lazy, Suspense } from 'react'
import { tradeApi, positionApi, dashboardV2Api, analysisApi } from '../../services/api'
import type { TradeAnalysisResponse, RiskMetrics, TickerTradeStats, TradeHabitsResponse } from '../../services/api'
import type { PortfolioDashboardData, PortfolioPosition } from '../../types/dashboard_v2'
import type { Trade } from '../../types/trade'
import { TradeAnalysisSkeleton } from '../../components/SkeletonLoader'
import TradeChartModal from './TradeChartModal'

const ChartAnalysisTab = lazy(() => import('./ChartAnalysisTab'))
const TradeReviewTab = lazy(() => import('./TradeReviewTab'))

type TradeType = 'BUY' | 'ADD_BUY' | 'SELL' | 'PARTIAL_SELL'

const TRADE_TYPE_LABELS: Record<TradeType, string> = {
  BUY: '매수',
  ADD_BUY: '추매',
  SELL: '매도',
  PARTIAL_SELL: '부분매도',
}

const TRADE_TYPE_COLORS: Record<TradeType, string> = {
  BUY: 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300',
  ADD_BUY: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/50 dark:text-cyan-300',
  SELL: 'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300',
  PARTIAL_SELL: 'bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-300',
}

type PeriodPreset = '1M' | '3M' | '6M' | '1Y' | 'ALL'

export default function TradeAnalysis() {
  const [analysis, setAnalysis] = useState<TradeAnalysisResponse | null>(null)
  const [dashboardV2, setDashboardV2] = useState<PortfolioDashboardData | null>(null)
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 기간 선택
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>('ALL')

  // 차트 모달
  const [chartModal, setChartModal] = useState<{ stockCode: string; stockName: string } | null>(null)

  // 포지션 수정 모달
  const [editingPosition, setEditingPosition] = useState<(PortfolioPosition & { ideaTickers: string }) | null>(null)
  const [posForm, setPosForm] = useState({ entry_price: '', quantity: '', entry_date: '', notes: '' })
  const [posSaving, setPosSaving] = useState(false)

  // 매매 기록 수정 모달
  const [editingTrade, setEditingTrade] = useState<Trade | null>(null)
  const [tradeForm, setTradeForm] = useState({ price: '', quantity: '', trade_date: '', reason: '', notes: '' })
  const [tradeSaving, setTradeSaving] = useState(false)

  // CSV 임포트
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{
    csv_trades_parsed?: number
    date_range?: string
    created_ideas?: number
    created_positions?: number
    created_trades?: number
    skipped_stocks?: string[]
  } | null>(null)

  // 탭/접기 상태
  const [activeTab, setActiveTab] = useState<'overview' | 'history' | 'stocks' | 'habits' | 'chart' | 'review'>('overview')
  const [habits, setHabits] = useState<TradeHabitsResponse | null>(null)
  const [showAllMonths, setShowAllMonths] = useState(false)

  const dateRange = useMemo(() => {
    if (periodPreset === 'ALL') return { start: undefined, end: undefined }
    const end = new Date()
    const start = new Date()
    const months = { '1M': 1, '3M': 3, '6M': 6, '1Y': 12 }[periodPreset]
    start.setMonth(start.getMonth() - months)
    return {
      start: start.toISOString().slice(0, 10),
      end: end.toISOString().slice(0, 10),
    }
  }, [periodPreset])

  useEffect(() => {
    loadAnalysis()
    analysisApi.getRiskMetrics(dateRange.start, dateRange.end).then(setRiskMetrics).catch(() => {})
    analysisApi.getTradeHabits(dateRange.start, dateRange.end).then(setHabits).catch(() => {})
  }, [dateRange])

  useEffect(() => {
    dashboardV2Api.get().then(setDashboardV2).catch(() => {})
  }, [])

  const loadAnalysis = async () => {
    try {
      setLoading(true)
      const data = await tradeApi.getAnalysis(dateRange.start, dateRange.end)
      setAnalysis(data)
    } catch (err) {
      setError('매매 분석 데이터를 불러오는데 실패했습니다.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  // 포지션 수정 핸들러
  const openPositionEdit = (pos: PortfolioPosition & { ideaTickers: string }) => {
    setEditingPosition(pos)
    setPosForm({
      entry_price: String(pos.entry_price),
      quantity: String(pos.quantity),
      entry_date: pos.entry_date || '',
      notes: '',
    })
  }

  const savePositionEdit = async () => {
    if (!editingPosition) return
    setPosSaving(true)
    try {
      const updateData: Record<string, unknown> = {}
      if (posForm.entry_price && Number(posForm.entry_price) !== editingPosition.entry_price)
        updateData.entry_price = Number(posForm.entry_price)
      if (posForm.quantity && Number(posForm.quantity) !== editingPosition.quantity)
        updateData.quantity = Number(posForm.quantity)
      if (posForm.entry_date && posForm.entry_date !== editingPosition.entry_date)
        updateData.entry_date = posForm.entry_date
      if (posForm.notes)
        updateData.notes = posForm.notes

      if (Object.keys(updateData).length === 0) {
        setEditingPosition(null)
        return
      }

      await positionApi.update(editingPosition.id, updateData)
      setEditingPosition(null)
      dashboardV2Api.get().then(setDashboardV2).catch(() => {})
      loadAnalysis()
    } catch (err) {
      console.error('포지션 수정 실패:', err)
      alert('수정에 실패했습니다.')
    } finally {
      setPosSaving(false)
    }
  }

  // 매매 기록 수정 핸들러
  const openTradeEdit = (trade: Trade) => {
    setEditingTrade(trade)
    setTradeForm({
      price: String(trade.price),
      quantity: String(trade.quantity),
      trade_date: trade.trade_date || '',
      reason: trade.reason || '',
      notes: trade.notes || '',
    })
  }

  const saveTradeEdit = async () => {
    if (!editingTrade) return
    setTradeSaving(true)
    try {
      const updateData: Record<string, unknown> = {}
      if (tradeForm.price && Number(tradeForm.price) !== editingTrade.price)
        updateData.price = Number(tradeForm.price)
      if (tradeForm.quantity && Number(tradeForm.quantity) !== editingTrade.quantity)
        updateData.quantity = Number(tradeForm.quantity)
      if (tradeForm.trade_date && tradeForm.trade_date !== editingTrade.trade_date)
        updateData.trade_date = tradeForm.trade_date
      if (tradeForm.reason !== (editingTrade.reason || ''))
        updateData.reason = tradeForm.reason
      if (tradeForm.notes !== (editingTrade.notes || ''))
        updateData.notes = tradeForm.notes

      if (Object.keys(updateData).length === 0) {
        setEditingTrade(null)
        return
      }

      await tradeApi.update(editingTrade.id, updateData)
      setEditingTrade(null)
      loadAnalysis()
    } catch (err) {
      console.error('매매 기록 수정 실패:', err)
      alert('수정에 실패했습니다.')
    } finally {
      setTradeSaving(false)
    }
  }

  // CSV 임포트 핸들러
  const handleCsvImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!confirm('기존 매매 데이터를 모두 삭제하고 CSV 데이터로 대체합니다.\n정말 진행하시겠습니까?')) {
      e.target.value = ''
      return
    }
    setImporting(true)
    setImportResult(null)
    try {
      const result = await tradeApi.importCsv(file, true)
      setImportResult(result.summary)
      dashboardV2Api.get().then(setDashboardV2).catch(() => {})
      loadAnalysis()
    } catch (err) {
      console.error('CSV 임포트 실패:', err)
      alert('CSV 임포트에 실패했습니다.')
    } finally {
      setImporting(false)
      e.target.value = ''
    }
  }

  // 보유 포지션 추출 (DashboardV2 API 기반)
  const openPositions = useMemo(() => {
    if (!dashboardV2) return []
    const positions: (PortfolioPosition & { ideaTickers: string })[] = []
    for (const idea of dashboardV2.active_ideas) {
      for (const pos of idea.positions) {
        positions.push({ ...pos, ideaTickers: idea.tickers.join(', ') })
      }
    }
    return positions
  }, [dashboardV2])

  // 포트폴리오 합계 (DashboardV2 stats 직접 사용)
  const portfolioSummary = useMemo(() => {
    if (!dashboardV2) return { totalInvested: 0, totalEval: 0, totalProfit: 0, totalPct: 0 }
    const s = dashboardV2.stats
    return {
      totalInvested: s.total_invested,
      totalEval: s.total_eval ?? s.total_invested,
      totalProfit: s.total_unrealized_profit ?? 0,
      totalPct: s.total_return_pct ?? 0,
    }
  }, [dashboardV2])

  // 최근 거래 날짜 그룹핑
  const recentTradesByDate = useMemo(() => {
    if (!analysis) return []
    const groups: { date: string; trades: typeof analysis.recent_trades }[] = []
    for (const t of analysis.recent_trades) {
      const last = groups[groups.length - 1]
      if (last && last.date === t.trade_date) {
        last.trades.push(t)
      } else {
        groups.push({ date: t.trade_date, trades: [t] })
      }
    }
    return groups
  }, [analysis])

  // 종목별 정렬 (수익 기준)
  const topStocks = useMemo(() => {
    if (!analysis) return { winners: [] as TickerTradeStats[], losers: [] as TickerTradeStats[] }
    const sorted = [...analysis.ticker_stats].sort((a, b) => b.realized_profit - a.realized_profit)
    return {
      winners: sorted.filter(s => s.realized_profit > 0).slice(0, 5),
      losers: sorted.filter(s => s.realized_profit < 0).sort((a, b) => a.realized_profit - b.realized_profit).slice(0, 5),
    }
  }, [analysis])

  const fmt = (num: number) => new Intl.NumberFormat('ko-KR').format(num)
  const fmtC = (num: number) => {
    if (Math.abs(num) >= 1_0000_0000) return `${(num / 1_0000_0000).toFixed(1)}억`
    if (Math.abs(num) >= 1_0000) return `${(num / 1_0000).toFixed(0)}만`
    return fmt(num)
  }
  const fmtPct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
  const pnlColor = (n: number | null | undefined) =>
    n == null ? 'text-gray-400' : n >= 0 ? 'text-red-500' : 'text-blue-500'

  if (loading) return <TradeAnalysisSkeleton />
  if (error) return <div className="p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg">{error}</div>
  if (!analysis) return null

  const { summary, monthly_stats, ticker_stats } = analysis
  const visibleMonths = showAllMonths ? monthly_stats : monthly_stats.slice(0, 6)
  const maxMonthlyProfit = Math.max(...monthly_stats.map(m => Math.abs(m.realized_profit)), 1)

  return (
    <div className="space-y-5">
      {/* 헤더 */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {(['overview', 'history', 'stocks', 'habits', 'chart', 'review'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  activeTab === tab
                    ? 'bg-primary-500 text-white'
                    : 'text-gray-500 dark:text-t-text-muted hover:bg-gray-100 dark:hover:bg-t-bg-elevated'
                }`}
              >
                {{ overview: '종합', history: '거래내역', stocks: '종목분석', habits: '습관분석', chart: '차트분석', review: '복기' }[tab]}
              </button>
            ))}
          </div>
          <label className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg cursor-pointer transition-colors ${
          importing
            ? 'bg-gray-200 dark:bg-gray-700 text-gray-400 cursor-not-allowed'
            : 'border border-gray-300 dark:border-t-border text-gray-600 dark:text-t-text-muted hover:bg-gray-50 dark:hover:bg-t-bg-elevated'
        }`}>
          <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM6.293 6.707a1 1 0 010-1.414l3-3a1 1 0 011.414 0l3 3a1 1 0 01-1.414 1.414L11 5.414V13a1 1 0 11-2 0V5.414L7.707 6.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
          </svg>
          {importing ? '임포트 중...' : 'CSV 임포트'}
          <input type="file" accept=".csv" className="hidden" onChange={handleCsvImport} disabled={importing} />
        </label>
        </div>
        {/* 기간 선택 프리셋 */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-400 mr-1">기간</span>
          {(['1M', '3M', '6M', '1Y', 'ALL'] as PeriodPreset[]).map(p => (
            <button
              key={p}
              onClick={() => setPeriodPreset(p)}
              className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                periodPreset === p
                  ? 'bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-900 font-medium'
                  : 'text-gray-500 dark:text-t-text-muted hover:bg-gray-100 dark:hover:bg-t-bg-elevated'
              }`}
            >
              {{ '1M': '1개월', '3M': '3개월', '6M': '6개월', '1Y': '1년', 'ALL': '전체' }[p]}
            </button>
          ))}
        </div>
      </div>

      {importResult && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3 text-xs">
          <span className="font-medium text-green-800 dark:text-green-200">임포트 완료</span>
          <span className="text-green-700 dark:text-green-300 ml-2">
            {importResult.csv_trades_parsed}건 / Position {importResult.created_positions} / Trade {importResult.created_trades}
          </span>
          <button onClick={() => setImportResult(null)} className="ml-2 text-green-500 hover:underline">닫기</button>
        </div>
      )}

      {/* ====== 종합 탭 ====== */}
      {activeTab === 'overview' && (
        <>
          {/* 핵심 지표 4칸 */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-white dark:bg-t-bg-card rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 dark:text-t-text-muted mb-1">총 실현손익</div>
              <div className={`text-2xl font-bold font-mono ${pnlColor(summary.total_realized_profit)}`}>
                {summary.total_realized_profit >= 0 ? '+' : ''}{fmtC(summary.total_realized_profit)}
              </div>
              <div className="mt-2 flex items-center gap-2 text-xs text-gray-400">
                <span>{summary.total_trades}건 거래</span>
                <span>|</span>
                <span>평균 {fmtPct(summary.avg_return_pct)}</span>
              </div>
            </div>
            <div className="bg-white dark:bg-t-bg-card rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 dark:text-t-text-muted mb-1">승률</div>
              <div className="text-2xl font-bold font-mono text-gray-900 dark:text-t-text-primary">
                {summary.win_rate.toFixed(1)}%
              </div>
              <div className="mt-2 h-2 bg-gray-100 dark:bg-t-bg-elevated rounded-full overflow-hidden">
                <div className="h-full bg-red-400 rounded-full" style={{ width: `${summary.win_rate}%` }} />
              </div>
              <div className="mt-1 flex justify-between text-xs text-gray-400">
                <span className="text-red-500">{summary.winning_trades}승</span>
                <span className="text-blue-500">{summary.losing_trades}패</span>
              </div>
            </div>
            <div className="bg-white dark:bg-t-bg-card rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 dark:text-t-text-muted mb-1">미실현 손익</div>
              <div className={`text-2xl font-bold font-mono ${pnlColor(portfolioSummary.totalProfit)}`}>
                {portfolioSummary.totalProfit >= 0 ? '+' : ''}{fmtC(portfolioSummary.totalProfit)}
              </div>
              <div className="mt-2 text-xs text-gray-400">
                투자 {fmtC(portfolioSummary.totalInvested)} / 평가 {fmtC(portfolioSummary.totalEval)}
              </div>
            </div>
            <div className="bg-white dark:bg-t-bg-card rounded-xl p-4 shadow-sm">
              <div className="text-xs text-gray-500 dark:text-t-text-muted mb-1">리스크</div>
              {riskMetrics ? (
                <>
                  <div className="flex items-baseline gap-2">
                    <span className="text-lg font-bold text-blue-500">MDD {riskMetrics.mdd.max_drawdown_pct.toFixed(1)}%</span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-x-3 text-xs text-gray-400">
                    <span>PF {riskMetrics.profit_factor !== null ? (riskMetrics.profit_factor === Infinity ? 'INF' : riskMetrics.profit_factor.toFixed(1)) : '-'}</span>
                    <span>Sharpe {riskMetrics.sharpe_ratio !== null ? riskMetrics.sharpe_ratio.toFixed(2) : '-'}</span>
                    <span>{riskMetrics.streak.current_streak}연{riskMetrics.streak.current_type === 'win' ? '승' : '패'}</span>
                    <span>HHI {riskMetrics.concentration.hhi}</span>
                  </div>
                </>
              ) : (
                <div className="text-lg font-bold text-gray-300">-</div>
              )}
            </div>
          </div>

          {/* 보유 포지션 컴팩트 카드 */}
          {openPositions.length > 0 && (
            <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm">
              <div className="px-4 py-3 border-b border-gray-100 dark:border-t-border flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary">
                  보유 {openPositions.length}종목
                </h2>
                <span className={`text-sm font-bold font-mono ${pnlColor(portfolioSummary.totalPct)}`}>
                  {fmtPct(portfolioSummary.totalPct)}
                </span>
              </div>
              <div className="divide-y divide-gray-50 dark:divide-t-border">
                {openPositions.map(pos => {
                  const cp = pos.current_price
                  const ep = Number(pos.entry_price)
                  const pct = pos.unrealized_return_pct ?? null
                  const profit = pos.unrealized_profit ?? null
                  return (
                    <div key={pos.id} className="px-4 py-2.5 flex items-center gap-3 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/30 group">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span
                            className="text-sm font-medium text-gray-900 dark:text-t-text-primary truncate cursor-pointer hover:text-primary-500 hover:underline"
                            onClick={() => setChartModal({ stockCode: pos.ticker, stockName: pos.stock_name || pos.ticker })}
                          >
                            {pos.stock_name || pos.ticker}
                          </span>
                          <span className="text-xs text-gray-400">{pos.quantity}주</span>
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5">
                          {fmt(ep)}원 &rarr; {cp ? `${fmt(cp)}원` : '-'}
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className={`text-sm font-bold font-mono ${pnlColor(pct)}`}>
                          {pct != null ? fmtPct(pct) : '-'}
                        </div>
                        <div className={`text-xs font-mono ${pnlColor(profit)}`}>
                          {profit != null ? `${profit >= 0 ? '+' : ''}${fmtC(profit)}` : ''}
                        </div>
                      </div>
                      <button
                        onClick={() => openPositionEdit(pos)}
                        className="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-primary-500 transition-all"
                        title="수정"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                          <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                        </svg>
                      </button>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* 월별 손익 바 차트 */}
          {monthly_stats.length > 0 && (
            <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary">월별 손익</h2>
                {monthly_stats.length > 6 && (
                  <button onClick={() => setShowAllMonths(!showAllMonths)} className="text-xs text-primary-500 hover:underline">
                    {showAllMonths ? '접기' : `전체 ${monthly_stats.length}개월`}
                  </button>
                )}
              </div>
              <div className="space-y-1.5">
                {visibleMonths.map(m => {
                  const pct = (m.realized_profit / maxMonthlyProfit) * 100
                  const isPositive = m.realized_profit >= 0
                  return (
                    <div key={m.month} className="flex items-center gap-2 text-xs">
                      <span className="w-14 text-gray-500 dark:text-t-text-muted shrink-0 text-right font-mono">{m.month.slice(2)}</span>
                      <div className="flex-1 flex items-center h-5">
                        <div className="w-1/2 flex justify-end">
                          {!isPositive && (
                            <div
                              className="h-4 bg-blue-400/70 dark:bg-blue-500/50 rounded-l"
                              style={{ width: `${Math.abs(pct)}%` }}
                            />
                          )}
                        </div>
                        <div className="w-px h-5 bg-gray-200 dark:bg-t-border shrink-0" />
                        <div className="w-1/2">
                          {isPositive && (
                            <div
                              className="h-4 bg-red-400/70 dark:bg-red-500/50 rounded-r"
                              style={{ width: `${Math.abs(pct)}%` }}
                            />
                          )}
                        </div>
                      </div>
                      <span className={`w-20 text-right font-mono shrink-0 ${pnlColor(m.realized_profit)}`}>
                        {m.realized_profit >= 0 ? '+' : ''}{fmtC(m.realized_profit)}
                      </span>
                      <span className="w-10 text-right text-gray-400 shrink-0">{m.win_rate.toFixed(0)}%</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* 승/패 Top 종목 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {topStocks.winners.length > 0 && (
              <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
                <h3 className="text-sm font-semibold text-red-500 mb-2">Top 수익 종목</h3>
                <div className="space-y-2">
                  {topStocks.winners.map((s: TickerTradeStats, i: number) => (
                    <div key={s.ticker} className="flex items-center gap-2">
                      <span className="w-5 text-xs text-gray-400 text-right">{i + 1}</span>
                      <span
                        className="flex-1 text-sm text-gray-900 dark:text-t-text-primary truncate cursor-pointer hover:text-primary-500 hover:underline"
                        onClick={() => setChartModal({ stockCode: s.ticker, stockName: s.stock_name || s.ticker })}
                      >
                        {s.stock_name || s.ticker}
                      </span>
                      <span className="text-sm font-mono text-red-500 font-medium">+{fmtC(s.realized_profit)}</span>
                      <span className="text-xs text-gray-400 w-12 text-right">{s.trade_count}건</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {topStocks.losers.length > 0 && (
              <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
                <h3 className="text-sm font-semibold text-blue-500 mb-2">Top 손실 종목</h3>
                <div className="space-y-2">
                  {topStocks.losers.map((s: TickerTradeStats, i: number) => (
                    <div key={s.ticker} className="flex items-center gap-2">
                      <span className="w-5 text-xs text-gray-400 text-right">{i + 1}</span>
                      <span
                        className="flex-1 text-sm text-gray-900 dark:text-t-text-primary truncate cursor-pointer hover:text-primary-500 hover:underline"
                        onClick={() => setChartModal({ stockCode: s.ticker, stockName: s.stock_name || s.ticker })}
                      >
                        {s.stock_name || s.ticker}
                      </span>
                      <span className="text-sm font-mono text-blue-500 font-medium">{fmtC(s.realized_profit)}</span>
                      <span className="text-xs text-gray-400 w-12 text-right">{s.trade_count}건</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 승률 추이 (리스크) */}
          {riskMetrics && riskMetrics.win_rate_trend.length > 0 && (
            <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary mb-2">
                승률 추이
                <span className="font-normal text-xs text-gray-400 ml-2">최근 10건 롤링</span>
              </h3>
              <div className="relative flex items-stretch gap-0.5 h-28">
                {/* 50% 기준선 */}
                <div className="absolute left-0 right-0 border-t border-dashed border-gray-300 dark:border-gray-600" style={{ bottom: '50%' }} />
                <span className="absolute -left-0.5 text-[10px] text-gray-400 font-mono" style={{ bottom: 'calc(50% - 6px)' }}>50%</span>
                {riskMetrics.win_rate_trend.map((p) => (
                  <div key={p.trade_index} className="flex-1 flex flex-col justify-end group relative">
                    <div
                      className={`w-full rounded-t transition-all cursor-default ${
                        p.win_rate >= 60 ? 'bg-green-400 dark:bg-green-600' :
                        p.win_rate >= 40 ? 'bg-yellow-400 dark:bg-yellow-600' :
                        'bg-red-400 dark:bg-red-600'
                      }`}
                      style={{ height: `${p.win_rate}%` }}
                    />
                    {/* 호버 툴팁 */}
                    <div className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-gray-800 dark:bg-gray-700 text-white text-[10px] rounded whitespace-nowrap z-10 pointer-events-none">
                      <div className="font-mono font-medium">{p.win_rate.toFixed(0)}%</div>
                      {p.date && <div className="text-gray-300">{p.date.slice(5)}</div>}
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex justify-between text-xs text-gray-400 mt-1.5">
                <span>과거 &larr;</span>
                <span className={`font-mono font-medium ${
                  (riskMetrics.win_rate_trend[riskMetrics.win_rate_trend.length - 1]?.win_rate ?? 0) >= 50 ? 'text-green-500' : 'text-red-500'
                }`}>
                  최근 {riskMetrics.win_rate_trend[riskMetrics.win_rate_trend.length - 1]?.win_rate.toFixed(0)}%
                </span>
              </div>
            </div>
          )}
        </>
      )}

      {/* ====== 거래내역 탭 ====== */}
      {activeTab === 'history' && (
        <>
          {recentTradesByDate.length > 0 ? (
            <div className="space-y-3">
              {recentTradesByDate.map(group => (
                <div key={group.date} className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm overflow-hidden">
                  <div className="px-4 py-2 bg-gray-50 dark:bg-t-bg border-b border-gray-100 dark:border-t-border">
                    <span className="text-xs font-medium text-gray-500 dark:text-t-text-muted">{group.date}</span>
                    <span className="text-xs text-gray-400 ml-2">{group.trades.length}건</span>
                  </div>
                  <div className="divide-y divide-gray-50 dark:divide-t-border">
                    {group.trades.map(trade => (
                      <div key={trade.id} className="px-4 py-2.5 flex items-center gap-3 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/30 group">
                        <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-semibold ${TRADE_TYPE_COLORS[trade.trade_type as TradeType] || 'bg-gray-100 text-gray-600'}`}>
                          {TRADE_TYPE_LABELS[trade.trade_type as TradeType] || trade.trade_type}
                        </span>
                        <div className="flex-1 min-w-0">
                          <span
                            className="text-sm text-gray-900 dark:text-t-text-primary cursor-pointer hover:text-primary-500 hover:underline"
                            onClick={() => trade.stock_code && setChartModal({ stockCode: trade.stock_code, stockName: trade.stock_name || trade.stock_code })}
                          >
                            {trade.stock_name || trade.stock_code}
                          </span>
                          <span className="text-xs text-gray-400 ml-2">
                            {fmt(trade.price)}원 x {trade.quantity}주
                          </span>
                        </div>
                        <div className="text-right shrink-0">
                          <div className="text-xs text-gray-500 font-mono">{fmtC(trade.total_amount)}</div>
                          {trade.realized_profit != null && (
                            <div className={`text-xs font-mono font-medium ${pnlColor(trade.realized_profit)}`}>
                              {trade.realized_profit >= 0 ? '+' : ''}{fmtC(trade.realized_profit)}
                              {trade.realized_return_pct != null && (
                                <span className="ml-1">({fmtPct(trade.realized_return_pct)})</span>
                              )}
                            </div>
                          )}
                        </div>
                        <button
                          onClick={() => openTradeEdit(trade as Trade)}
                          className="opacity-0 group-hover:opacity-100 text-gray-300 hover:text-primary-500 transition-all"
                          title="수정"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                            <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                          </svg>
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400">거래 내역이 없습니다.</div>
          )}
        </>
      )}

      {/* ====== 종목분석 탭 ====== */}
      {activeTab === 'stocks' && (
        <>
          {ticker_stats.length > 0 ? (
            <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 dark:bg-t-bg border-b border-gray-100 dark:border-t-border text-xs text-gray-500 dark:text-t-text-muted">
                      <th className="px-4 py-2.5 text-left font-medium">종목</th>
                      <th className="px-3 py-2.5 text-right font-medium">거래</th>
                      <th className="px-3 py-2.5 text-right font-medium">실현손익</th>
                      <th className="px-3 py-2.5 text-right font-medium">평균수익률</th>
                      <th className="px-3 py-2.5 text-right font-medium">승률</th>
                      <th className="px-3 py-2.5 text-right font-medium">매수총액</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50 dark:divide-t-border">
                    {ticker_stats.map(s => (
                      <tr key={s.ticker} className="hover:bg-gray-50 dark:hover:bg-t-bg-elevated/30">
                        <td className="px-4 py-2.5">
                          <div
                            className="font-medium text-gray-900 dark:text-t-text-primary cursor-pointer hover:text-primary-500 hover:underline"
                            onClick={() => setChartModal({ stockCode: s.ticker, stockName: s.stock_name || s.ticker })}
                          >
                            {s.stock_name || s.ticker}
                          </div>
                          {s.stock_name && <div className="text-xs text-gray-400">{s.ticker}</div>}
                        </td>
                        <td className="px-3 py-2.5 text-right text-gray-500">{s.trade_count}건</td>
                        <td className={`px-3 py-2.5 text-right font-mono font-medium ${pnlColor(s.realized_profit)}`}>
                          {s.realized_profit >= 0 ? '+' : ''}{fmtC(s.realized_profit)}
                        </td>
                        <td className={`px-3 py-2.5 text-right font-mono ${pnlColor(s.avg_return_pct)}`}>
                          {fmtPct(s.avg_return_pct)}
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <span className="text-gray-600 dark:text-t-text-secondary">{s.win_rate.toFixed(0)}%</span>
                          <span className="text-xs text-gray-400 ml-1">({s.winning_trades}/{s.winning_trades + s.losing_trades})</span>
                        </td>
                        <td className="px-3 py-2.5 text-right text-gray-500 font-mono">{fmtC(s.total_buy_amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400">종목 데이터가 없습니다.</div>
          )}
        </>
      )}

      {/* ====== 습관분석 탭 ====== */}
      {activeTab === 'habits' && (
        <>
          {!habits ? (
            <div className="text-center py-12 text-gray-400">로딩 중...</div>
          ) : habits.total_sell_trades < 5 ? (
            <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-8 text-center">
              <div className="text-4xl mb-3">📊</div>
              <div className="text-gray-600 dark:text-t-text-secondary font-medium">분석에 충분한 매매 기록이 필요합니다</div>
              <div className="text-xs text-gray-400 mt-1">최소 5건의 매도 기록이 필요합니다 (현재 {habits.total_sell_trades}건)</div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* 카드 1: 기대값 + 손익비 */}
              {habits.expectancy && habits.win_loss_ratio && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* 기대값 */}
                  <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary mb-3">매매당 기대값</h3>
                    <div className={`text-2xl font-bold font-mono ${habits.expectancy.is_positive ? 'text-red-500' : 'text-blue-500'}`}>
                      {habits.expectancy.expectancy >= 0 ? '+' : ''}{fmtC(habits.expectancy.expectancy)}원
                    </div>
                    <div className={`text-sm font-mono ${habits.expectancy.is_positive ? 'text-red-400' : 'text-blue-400'}`}>
                      ({habits.expectancy.expectancy_pct >= 0 ? '+' : ''}{habits.expectancy.expectancy_pct.toFixed(2)}%)
                    </div>
                    <div className="mt-3 space-y-1.5 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500 dark:text-t-text-muted">승률 × 평균수익</span>
                        <span className="text-red-500 font-mono">
                          {habits.expectancy.win_rate.toFixed(1)}% × +{fmtC(habits.expectancy.avg_win_amount)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500 dark:text-t-text-muted">패률 × 평균손실</span>
                        <span className="text-blue-500 font-mono">
                          {habits.expectancy.loss_rate.toFixed(1)}% × -{fmtC(habits.expectancy.avg_loss_amount)}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* 손익비 */}
                  <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary mb-3">손익비</h3>
                    <div className="flex items-baseline gap-2">
                      <span className="text-2xl font-bold font-mono text-gray-900 dark:text-t-text-primary">
                        {habits.win_loss_ratio.ratio.toFixed(2)}
                      </span>
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                        habits.win_loss_ratio.grade === 'excellent' ? 'bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300' :
                        habits.win_loss_ratio.grade === 'good' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300' :
                        habits.win_loss_ratio.grade === 'average' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/50 dark:text-yellow-300' :
                        'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300'
                      }`}>
                        {{ excellent: '우수', good: '양호', average: '보통', poor: '미흡' }[habits.win_loss_ratio.grade]}
                      </span>
                    </div>
                    <div className="mt-3 space-y-2">
                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-red-500">평균수익률 +{habits.win_loss_ratio.avg_win_pct.toFixed(1)}%</span>
                        </div>
                        <div className="h-2 bg-gray-100 dark:bg-t-bg-elevated rounded-full overflow-hidden">
                          <div className="h-full bg-red-400 rounded-full" style={{ width: `${Math.min(habits.win_loss_ratio.avg_win_pct * 3, 100)}%` }} />
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-blue-500">평균손실률 -{habits.win_loss_ratio.avg_loss_pct.toFixed(1)}%</span>
                        </div>
                        <div className="h-2 bg-gray-100 dark:bg-t-bg-elevated rounded-full overflow-hidden">
                          <div className="h-full bg-blue-400 rounded-full" style={{ width: `${Math.min(habits.win_loss_ratio.avg_loss_pct * 3, 100)}%` }} />
                        </div>
                      </div>
                    </div>
                    <div className="mt-3 text-xs text-gray-500 dark:text-t-text-muted">{habits.win_loss_ratio.comment}</div>
                  </div>
                </div>
              )}

              {/* 카드 2: 보유기간 분석 */}
              {habits.holding_period && (
                <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary mb-3">보유기간 분석</h3>
                  <div className="grid grid-cols-2 gap-4 mb-3">
                    <div>
                      <div className="text-xs text-gray-500 dark:text-t-text-muted mb-1">수익 매매 평균</div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-bold font-mono text-red-500">{habits.holding_period.avg_win_days.toFixed(1)}일</span>
                        <div className="flex-1 h-3 bg-gray-100 dark:bg-t-bg-elevated rounded-full overflow-hidden">
                          <div className="h-full bg-red-400 rounded-full" style={{ width: `${Math.min(habits.holding_period.avg_win_days / Math.max(habits.holding_period.avg_win_days, habits.holding_period.avg_loss_days) * 100, 100)}%` }} />
                        </div>
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500 dark:text-t-text-muted mb-1">손실 매매 평균</div>
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-bold font-mono text-blue-500">{habits.holding_period.avg_loss_days.toFixed(1)}일</span>
                        <div className="flex-1 h-3 bg-gray-100 dark:bg-t-bg-elevated rounded-full overflow-hidden">
                          <div className="h-full bg-blue-400 rounded-full" style={{ width: `${Math.min(habits.holding_period.avg_loss_days / Math.max(habits.holding_period.avg_win_days, habits.holding_period.avg_loss_days) * 100, 100)}%` }} />
                        </div>
                      </div>
                    </div>
                  </div>

                  {habits.holding_period.by_period.length > 0 && (
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-xs">
                        <thead>
                          <tr className="border-b border-gray-100 dark:border-t-border text-gray-500 dark:text-t-text-muted">
                            <th className="py-1.5 text-left font-medium">구간</th>
                            <th className="py-1.5 text-right font-medium">건수</th>
                            <th className="py-1.5 text-right font-medium">승률</th>
                            <th className="py-1.5 text-right font-medium">평균수익률</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50 dark:divide-t-border">
                          {habits.holding_period.by_period.map(p => (
                            <tr key={p.period}>
                              <td className="py-1.5 text-gray-700 dark:text-t-text-secondary">{p.period}</td>
                              <td className="py-1.5 text-right text-gray-500">{p.count}건</td>
                              <td className="py-1.5 text-right font-mono">{p.count > 0 ? `${p.win_rate.toFixed(0)}%` : '-'}</td>
                              <td className={`py-1.5 text-right font-mono ${p.avg_return_pct >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                                {p.count > 0 ? fmtPct(p.avg_return_pct) : '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  <div className="mt-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
                    {habits.holding_period.diagnosis}
                  </div>
                </div>
              )}

              {/* 카드 3: 승패 후 패턴 */}
              {habits.sequential_pattern && habits.sequential_pattern.after_win && (
                <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary mb-3">
                    승패 후 매매 패턴
                    {habits.sequential_pattern.revenge_trading_detected && (
                      <span className="ml-2 text-xs px-1.5 py-0.5 bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300 rounded">복수매매 주의</span>
                    )}
                    {habits.sequential_pattern.overconfidence_detected && (
                      <span className="ml-2 text-xs px-1.5 py-0.5 bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-300 rounded">자만매매 주의</span>
                    )}
                  </h3>
                  <div className="space-y-2.5">
                    {[
                      { label: '승리 후', data: habits.sequential_pattern.after_win!, color: 'red' },
                      { label: '패배 후', data: habits.sequential_pattern.after_loss!, color: 'blue' },
                      ...(habits.sequential_pattern.after_streak_loss && habits.sequential_pattern.after_streak_loss.count > 0
                        ? [{ label: '2연패 후', data: habits.sequential_pattern.after_streak_loss, color: 'purple' }]
                        : []),
                    ].map(item => (
                      <div key={item.label} className="flex items-center gap-3">
                        <span className="w-16 text-xs text-gray-500 dark:text-t-text-muted shrink-0">{item.label}</span>
                        <span className="w-10 text-xs text-gray-400 text-right shrink-0">{item.data.count}건</span>
                        <div className="flex-1 h-4 bg-gray-100 dark:bg-t-bg-elevated rounded-full overflow-hidden relative">
                          <div
                            className={`h-full rounded-full ${
                              item.color === 'red' ? 'bg-red-400' :
                              item.color === 'blue' ? 'bg-blue-400' : 'bg-purple-400'
                            }`}
                            style={{ width: `${item.data.win_rate}%` }}
                          />
                          <span className="absolute inset-0 flex items-center justify-center text-[10px] font-mono font-medium text-gray-700 dark:text-gray-200">
                            {item.data.win_rate.toFixed(0)}%
                          </span>
                        </div>
                        <span className={`w-14 text-xs font-mono text-right shrink-0 ${item.data.avg_return_pct >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                          {fmtPct(item.data.avg_return_pct)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 카드 4: 요일별 성과 히트맵 */}
              {habits.weekday_performance && (
                <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary mb-3">요일별 성과</h3>
                  <div className="grid grid-cols-5 gap-2">
                    {habits.weekday_performance.by_weekday.map(d => {
                      const isBest = d.day === habits.weekday_performance!.best_day
                      const isWorst = d.day === habits.weekday_performance!.worst_day
                      const bgColor = d.count === 0 ? 'bg-gray-50 dark:bg-t-bg-elevated' :
                        d.win_rate >= 70 ? 'bg-red-50 dark:bg-red-900/20' :
                        d.win_rate >= 55 ? 'bg-orange-50 dark:bg-orange-900/20' :
                        d.win_rate >= 40 ? 'bg-gray-50 dark:bg-t-bg-elevated' :
                        'bg-blue-50 dark:bg-blue-900/20'
                      return (
                        <div key={d.day} className={`${bgColor} rounded-lg p-2.5 text-center relative`}>
                          {isBest && <span className="absolute top-1 right-1 text-[10px] text-red-500 font-medium">BEST</span>}
                          {isWorst && d.count > 0 && <span className="absolute top-1 right-1 text-[10px] text-blue-500 font-medium">WORST</span>}
                          <div className="text-xs text-gray-500 dark:text-t-text-muted">{d.day}</div>
                          <div className="text-lg font-bold font-mono text-gray-900 dark:text-t-text-primary mt-0.5">
                            {d.count > 0 ? `${d.win_rate.toFixed(0)}%` : '-'}
                          </div>
                          <div className="text-[10px] text-gray-400">{d.count}건</div>
                          <div className={`text-[10px] font-mono ${d.avg_return_pct >= 0 ? 'text-red-400' : 'text-blue-400'}`}>
                            {d.count > 0 ? fmtPct(d.avg_return_pct) : ''}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* 카드 5: 매매 빈도 분석 */}
              {habits.frequency_analysis && (
                <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary mb-3">
                    매매 빈도 분석
                    {habits.frequency_analysis.overtrading_warning && (
                      <span className="ml-2 text-xs px-1.5 py-0.5 bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300 rounded">과매매 주의</span>
                    )}
                  </h3>

                  <div className="flex items-center gap-4 mb-4">
                    <div>
                      <div className="text-xs text-gray-500 dark:text-t-text-muted">주간 평균</div>
                      <div className="text-xl font-bold font-mono text-gray-900 dark:text-t-text-primary">
                        {habits.frequency_analysis.avg_trades_per_week.toFixed(1)}건
                      </div>
                    </div>
                    {habits.frequency_analysis.high_freq_stats && habits.frequency_analysis.low_freq_stats && (
                      <div className="flex-1 grid grid-cols-2 gap-3">
                        <div className="text-center bg-gray-50 dark:bg-t-bg-elevated rounded-lg p-2">
                          <div className="text-[10px] text-gray-400">고빈도 주간</div>
                          <div className="text-sm font-mono font-medium text-gray-700 dark:text-t-text-secondary">
                            승률 {habits.frequency_analysis.high_freq_stats.win_rate.toFixed(0)}%
                          </div>
                          <div className={`text-xs font-mono ${habits.frequency_analysis.high_freq_stats.avg_return_pct >= 0 ? 'text-red-400' : 'text-blue-400'}`}>
                            {fmtPct(habits.frequency_analysis.high_freq_stats.avg_return_pct)}
                          </div>
                        </div>
                        <div className="text-center bg-gray-50 dark:bg-t-bg-elevated rounded-lg p-2">
                          <div className="text-[10px] text-gray-400">저빈도 주간</div>
                          <div className="text-sm font-mono font-medium text-gray-700 dark:text-t-text-secondary">
                            승률 {habits.frequency_analysis.low_freq_stats.win_rate.toFixed(0)}%
                          </div>
                          <div className={`text-xs font-mono ${habits.frequency_analysis.low_freq_stats.avg_return_pct >= 0 ? 'text-red-400' : 'text-blue-400'}`}>
                            {fmtPct(habits.frequency_analysis.low_freq_stats.avg_return_pct)}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {habits.frequency_analysis.weekly_data.length > 0 && (
                    <div>
                      <div className="text-xs text-gray-400 mb-1.5">최근 12주 매매 빈도</div>
                      <div className="flex items-stretch gap-1.5 h-28">
                        {habits.frequency_analysis.weekly_data.map(w => {
                          const maxCount = Math.max(...habits.frequency_analysis!.weekly_data.map(d => d.trade_count), 1)
                          const heightPct = (w.trade_count / maxCount) * 100
                          return (
                            <div key={w.week} className="flex-1 flex flex-col justify-end items-center group relative">
                              {/* 건수 라벨 */}
                              {w.trade_count > 0 && (
                                <span className="text-[10px] font-mono text-gray-400 mb-0.5">{w.trade_count}</span>
                              )}
                              <div
                                className={`w-full rounded-t transition-all cursor-default ${
                                  w.win_rate >= 60 ? 'bg-red-400 dark:bg-red-600' :
                                  w.win_rate >= 40 ? 'bg-yellow-400 dark:bg-yellow-600' :
                                  'bg-blue-400 dark:bg-blue-600'
                                }`}
                                style={{ height: `${heightPct}%`, minHeight: w.trade_count > 0 ? '6px' : '0' }}
                              />
                              {/* 호버 툴팁 */}
                              <div className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-gray-800 dark:bg-gray-700 text-white text-[10px] rounded whitespace-nowrap z-10 pointer-events-none">
                                <div className="font-mono font-medium">{w.trade_count}건 / 승률 {w.win_rate.toFixed(0)}%</div>
                                <div className={`font-mono ${w.avg_return_pct >= 0 ? 'text-red-300' : 'text-blue-300'}`}>
                                  평균 {fmtPct(w.avg_return_pct)}
                                </div>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                      <div className="flex justify-between text-[10px] text-gray-400 mt-1">
                        <span>&larr; {habits.frequency_analysis.weekly_data[0]?.week.slice(5)}</span>
                        <span>{habits.frequency_analysis.weekly_data[habits.frequency_analysis.weekly_data.length - 1]?.week.slice(5)} &rarr;</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* ====== 차트분석 탭 ====== */}
      {activeTab === 'chart' && (
        <Suspense fallback={
          <div className="space-y-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-6 animate-pulse">
                <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded mb-4" />
                <div className="grid grid-cols-3 gap-3">
                  {[1, 2, 3].map(j => (
                    <div key={j} className="h-20 bg-gray-100 dark:bg-t-bg-elevated rounded-lg" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        }>
          <ChartAnalysisTab startDate={dateRange.start} endDate={dateRange.end} />
        </Suspense>
      )}

      {/* ====== 복기 탭 ====== */}
      {activeTab === 'review' && (
        <Suspense fallback={
          <div className="space-y-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-6 animate-pulse">
                <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded mb-4" />
                <div className="grid grid-cols-3 gap-3">
                  {[1, 2, 3].map(j => (
                    <div key={j} className="h-20 bg-gray-100 dark:bg-t-bg-elevated rounded-lg" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        }>
          <TradeReviewTab startDate={dateRange.start} endDate={dateRange.end} />
        </Suspense>
      )}

      {/* 데이터 없음 */}
      {summary.total_trades === 0 && (
        <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-8 text-center">
          <div className="text-gray-400 dark:text-t-text-muted">아직 매매 기록이 없습니다.</div>
          <div className="text-xs text-gray-400 mt-1">포지션 매매 또는 CSV 임포트로 시작하세요.</div>
        </div>
      )}

      {/* ===== 포지션 수정 모달 ===== */}
      {editingPosition && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setEditingPosition(null)}>
          <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-xl max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="p-5 border-b border-gray-200 dark:border-t-border">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-t-text-primary">포지션 수정</h3>
              <p className="text-sm text-gray-500 dark:text-t-text-muted mt-1">{editingPosition.stock_name || editingPosition.ticker}</p>
            </div>
            <div className="p-5 space-y-4">
              {[
                { label: '매입가', key: 'entry_price' as const, type: 'number', ph: String(editingPosition.entry_price) },
                { label: '수량', key: 'quantity' as const, type: 'number', ph: String(editingPosition.quantity) },
                { label: '매입일', key: 'entry_date' as const, type: 'date', ph: '' },
                { label: '메모', key: 'notes' as const, type: 'text', ph: '수정 사유 (선택)' },
              ].map(f => (
                <div key={f.key}>
                  <label className="block text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-1">{f.label}</label>
                  <input
                    type={f.type}
                    value={posForm[f.key]}
                    onChange={e => setPosForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                    className="w-full rounded-lg border border-gray-300 dark:border-t-border bg-white dark:bg-t-bg px-3 py-2 text-sm text-gray-900 dark:text-t-text-primary focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    placeholder={f.ph}
                  />
                </div>
              ))}
            </div>
            <div className="p-5 border-t border-gray-200 dark:border-t-border flex justify-end gap-3">
              <button onClick={() => setEditingPosition(null)} className="px-4 py-2 text-sm text-gray-700 dark:text-t-text-secondary bg-gray-100 dark:bg-t-bg-elevated rounded-lg hover:bg-gray-200 dark:hover:bg-t-bg transition-colors">취소</button>
              <button onClick={savePositionEdit} disabled={posSaving} className="px-4 py-2 text-sm text-white bg-primary-500 rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors">{posSaving ? '저장 중...' : '저장'}</button>
            </div>
          </div>
        </div>
      )}

      {/* ===== 매매 기록 수정 모달 ===== */}
      {editingTrade && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setEditingTrade(null)}>
          <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-xl max-w-md w-full" onClick={e => e.stopPropagation()}>
            <div className="p-5 border-b border-gray-200 dark:border-t-border">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-t-text-primary">매매 기록 수정</h3>
              <p className="text-sm text-gray-500 dark:text-t-text-muted mt-1">
                {editingTrade.stock_name || editingTrade.stock_code} - {TRADE_TYPE_LABELS[editingTrade.trade_type as TradeType] || editingTrade.trade_type}
              </p>
            </div>
            <div className="p-5 space-y-4">
              {[
                { label: '거래가', key: 'price' as const, type: 'number' },
                { label: '수량', key: 'quantity' as const, type: 'number' },
                { label: '거래일', key: 'trade_date' as const, type: 'date' },
                { label: '사유', key: 'reason' as const, type: 'text' },
                { label: '메모', key: 'notes' as const, type: 'text' },
              ].map(f => (
                <div key={f.key}>
                  <label className="block text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-1">{f.label}</label>
                  <input
                    type={f.type}
                    value={tradeForm[f.key]}
                    onChange={e => setTradeForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                    className="w-full rounded-lg border border-gray-300 dark:border-t-border bg-white dark:bg-t-bg px-3 py-2 text-sm text-gray-900 dark:text-t-text-primary focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
              ))}
            </div>
            <div className="p-5 border-t border-gray-200 dark:border-t-border flex justify-end gap-3">
              <button onClick={() => setEditingTrade(null)} className="px-4 py-2 text-sm text-gray-700 dark:text-t-text-secondary bg-gray-100 dark:bg-t-bg-elevated rounded-lg hover:bg-gray-200 dark:hover:bg-t-bg transition-colors">취소</button>
              <button onClick={saveTradeEdit} disabled={tradeSaving} className="px-4 py-2 text-sm text-white bg-primary-500 rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors">{tradeSaving ? '저장 중...' : '저장'}</button>
            </div>
          </div>
        </div>
      )}

      {/* ===== 종목 차트 모달 ===== */}
      {chartModal && (
        <TradeChartModal
          stockCode={chartModal.stockCode}
          stockName={chartModal.stockName}
          isOpen={true}
          onClose={() => setChartModal(null)}
        />
      )}
    </div>
  )
}
