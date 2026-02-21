import { Fragment, useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { pullbackApi, type SignalStock, type SignalSummary, type SignalType, type SignalDetailResponse, type TrendTheme, type SqueezeTheme, type MZBacktestResponse, type MZBacktestHoldingStats, type MZBacktestSignal } from '../../services/api'
import type { ChartTimeframe } from '../../components/StockChart'
import { StockChart } from '../../components/StockChart'
import { WatchlistStar } from '../../components/WatchlistStar'
import { useWatchlist } from '../../hooks/useWatchlist'
import { useRealtimePolling } from '../../hooks/useRealtimePolling'

type TabKey = SignalType | 'watchlist' | 'top_picks'

const SIGNAL_TABS: { key: TabKey; label: string }[] = [
  { key: 'top_picks', label: 'TOP' },
  { key: 'pullback', label: '눌림목' },
  { key: 'high_breakout', label: '전고점 돌파' },
  { key: 'resistance_test', label: '저항 돌파 시도' },
  { key: 'support_test', label: '지지선 테스트' },
  { key: 'mss_proximity', label: 'MSS 근접' },
  { key: 'momentum_zone', label: '관성 구간' },
  { key: 'ma120_turn', label: '120일선 전환' },
  { key: 'candle_squeeze', label: '캔들 수축' },
  { key: 'candle_expansion', label: '캔들 확장' },
  { key: 'watchlist', label: '관심종목' },
]

const GRADE_COLORS: Record<string, string> = {
  A: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400',
  B: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400',
  C: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400',
  D: 'bg-gray-100 text-gray-600 dark:bg-gray-700/40 dark:text-gray-400',
}

function formatPrice(v: number | null | undefined): string {
  if (v == null) return '-'
  return v.toLocaleString()
}

function formatPct(v: number | null | undefined, showSign = true): string {
  if (v == null) return '-'
  const sign = showSign && v >= 0 ? '+' : ''
  return `${sign}${v.toFixed(1)}%`
}

function formatAmount(amount: number | null | undefined): string {
  if (amount == null) return '-'
  const sign = amount >= 0 ? '+' : ''
  const abs = Math.abs(amount)
  if (abs >= 100000000) return `${sign}${(amount / 100000000).toFixed(1)}억`
  if (abs >= 10000) return `${sign}${(amount / 10000).toFixed(0)}만`
  return `${sign}${amount.toLocaleString()}`
}

function ScoreBar({ score }: { score: number | undefined }) {
  const s = score ?? 0
  const width = Math.min(100, Math.max(0, s))
  const color =
    s >= 80 ? 'bg-green-500' :
    s >= 60 ? 'bg-blue-500' :
    s >= 40 ? 'bg-yellow-500' :
    'bg-gray-400'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${width}%` }} />
      </div>
      <span className="text-xs font-medium w-8 text-right">{s.toFixed(0)}</span>
    </div>
  )
}

function ExpandedRow({ stockCode, stockName, priceLine, priceLineLabel, priceLineColor, initialTimeframe, initialMaVisible }: {
  stockCode: string; stockName: string
  priceLine?: number; priceLineLabel?: string; priceLineColor?: string
  initialTimeframe?: ChartTimeframe
  initialMaVisible?: { ma1: boolean; ma2: boolean; ma3: boolean; ma4: boolean; ma5: boolean }
}) {
  const [detail, setDetail] = useState<SignalDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    pullbackApi.getDetail(stockCode).then(d => {
      if (!cancelled) {
        setDetail(d)
        setLoading(false)
      }
    }).catch(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [stockCode])

  if (loading) {
    return (
      <tr>
        <td colSpan={8} className="py-6 text-center text-gray-400 dark:text-t-text-muted text-sm">
          상세 데이터 로딩 중...
        </td>
      </tr>
    )
  }

  if (!detail) {
    return (
      <tr>
        <td colSpan={8} className="py-4 text-center text-gray-400 dark:text-t-text-muted text-sm">
          데이터를 불러올 수 없습니다
        </td>
      </tr>
    )
  }

  const flowHistory = detail.flow_history ?? []

  // 수급 합계
  const flowTotals = flowHistory.reduce(
    (acc, f) => ({
      foreign: acc.foreign + (f.foreign_net ?? 0),
      institution: acc.institution + (f.institution_net ?? 0),
      individual: acc.individual + (f.individual_net ?? 0),
    }),
    { foreign: 0, institution: 0, individual: 0 }
  )

  return (
    <tr>
      <td colSpan={8} className="p-0">
        <div className="bg-gray-50 dark:bg-t-bg border-t border-b dark:border-t-border px-4 py-3">
          {/* 분석 요약 + 상세 링크 */}
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm text-gray-600 dark:text-t-text-muted italic">
              {detail.analysis_summary}
            </div>
            <Link
              to={`/stocks/${stockCode}`}
              className="flex-shrink-0 ml-4 px-3 py-1.5 text-xs font-medium bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-400 rounded-lg hover:bg-indigo-200 dark:hover:bg-indigo-900/50 transition-colors"
            >
              종목 상세 →
            </Link>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-3">
            {/* 왼쪽: 차트 (180일 기본, 스크롤로 2년치) - 3/5 */}
            <div className="lg:col-span-3 chart-grid-cell">
              <h4 className="text-xs font-medium text-gray-500 dark:text-t-text-muted mb-1">차트 (180일 / 스크롤로 2년)</h4>
              <StockChart
                stockCode={stockCode}
                stockName={stockName}
                height={520}
                days={500}
                visibleDays={180}
                showHeader={false}
                enableScrollLoad
                disableTradingViewLink
                initialPriceLine={priceLine}
                priceLineLabel={priceLineLabel}
                priceLineColor={priceLineColor}
                showTimeframeSelector
                initialTimeframe={initialTimeframe}
                showMAToggle
                initialMaVisible={initialMaVisible}
              />
            </div>
            {/* 오른쪽: 수급 테이블 - 2/5 */}
            <div className="lg:col-span-2">
              <h4 className="text-xs font-medium text-gray-500 dark:text-t-text-muted mb-1">20일 수급표</h4>
              {flowHistory.length > 0 ? (
                <div className="max-h-[520px] overflow-y-auto border dark:border-t-border rounded">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-100 dark:bg-t-bg-elevated sticky top-0">
                      <tr>
                        <th className="py-1.5 px-2 text-left font-medium text-gray-600 dark:text-t-text-muted">날짜</th>
                        <th className="py-1.5 px-2 text-right font-medium text-gray-600 dark:text-t-text-muted">외국인</th>
                        <th className="py-1.5 px-2 text-right font-medium text-gray-600 dark:text-t-text-muted">기관</th>
                        <th className="py-1.5 px-2 text-right font-medium text-gray-600 dark:text-t-text-muted">개인</th>
                      </tr>
                    </thead>
                    <tbody>
                      {flowHistory.map((f, i) => (
                        <tr key={i} className="border-t dark:border-t-border">
                          <td className="py-1 px-2 text-gray-500 dark:text-t-text-muted">{(f.date ?? '').slice(5)}</td>
                          <td className={`py-1 px-2 text-right ${(f.foreign_net ?? 0) >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                            {formatAmount(f.foreign_net)}
                          </td>
                          <td className={`py-1 px-2 text-right ${(f.institution_net ?? 0) >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                            {formatAmount(f.institution_net)}
                          </td>
                          <td className={`py-1 px-2 text-right ${(f.individual_net ?? 0) >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                            {formatAmount(f.individual_net)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="bg-gray-100 dark:bg-t-bg-elevated border-t dark:border-t-border font-medium">
                      <tr>
                        <td className="py-1.5 px-2 text-gray-700 dark:text-t-text-primary">합계</td>
                        <td className={`py-1.5 px-2 text-right ${flowTotals.foreign >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                          {formatAmount(flowTotals.foreign)}
                        </td>
                        <td className={`py-1.5 px-2 text-right ${flowTotals.institution >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                          {formatAmount(flowTotals.institution)}
                        </td>
                        <td className={`py-1.5 px-2 text-right ${flowTotals.individual >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                          {formatAmount(flowTotals.individual)}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              ) : (
                <div className="h-[520px] flex items-center justify-center text-sm text-gray-400 border dark:border-t-border rounded">수급 데이터 없음</div>
              )}
            </div>
          </div>
        </div>
      </td>
    </tr>
  )
}

function MZBacktestPanel() {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<MZBacktestResponse | null>(null)
  const [lookback, setLookback] = useState(365)
  const [holdDays, setHoldDays] = useState('5,10,20')
  const [minScore, setMinScore] = useState(40)

  const runBacktest = async () => {
    setLoading(true)
    try {
      const data = await pullbackApi.getMZBacktest({
        lookback_days: lookback,
        holding_days: holdDays,
        min_score: minScore,
        step_days: lookback >= 365 ? 2 : 1,
      })
      setResult(data)
    } catch (err) {
      console.error('백테스트 실행 실패:', err)
    } finally {
      setLoading(false)
    }
  }

  const refKey = result ? `${result.params.holding_days[Math.min(1, result.params.holding_days.length - 1)]}d` : '10d'

  return (
    <div className="bg-white dark:bg-t-bg-card rounded-lg shadow">
      <button
        onClick={() => setOpen(p => !p)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 transition-colors"
      >
        <span className="text-sm font-semibold text-gray-800 dark:text-t-text-primary">
          관성 구간 백테스트
        </span>
        <span className="text-gray-400 text-xs">{open ? '접기' : '펼치기'}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 border-t dark:border-t-border space-y-4">
          {/* 파라미터 */}
          <div className="flex flex-wrap items-end gap-3 pt-3">
            <div>
              <label className="block text-xs text-gray-500 dark:text-t-text-muted mb-1">분석 기간</label>
              <div className="flex gap-1">
                {[90, 180, 365].map(d => (
                  <button key={d} onClick={() => setLookback(d)}
                    className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${lookback === d ? 'bg-amber-500 text-white' : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200'}`}
                  >{d}일</button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 dark:text-t-text-muted mb-1">보유기간</label>
              <div className="flex gap-1">
                {['5,10,20', '5,10,20,30', '3,5,10'].map(h => (
                  <button key={h} onClick={() => setHoldDays(h)}
                    className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${holdDays === h ? 'bg-amber-500 text-white' : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200'}`}
                  >{h}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 dark:text-t-text-muted mb-1">최소 점수</label>
              <div className="flex gap-1">
                {[40, 60, 80].map(s => (
                  <button key={s} onClick={() => setMinScore(s)}
                    className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${minScore === s ? 'bg-amber-500 text-white' : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200'}`}
                  >{s}+</button>
                ))}
              </div>
            </div>
            <button
              onClick={runBacktest}
              disabled={loading}
              className="px-4 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded disabled:opacity-50 transition-colors"
            >
              {loading ? '분석 중...' : '실행'}
            </button>
          </div>

          {/* 로딩 */}
          {loading && (
            <div className="text-center py-8 text-gray-400 dark:text-t-text-muted text-sm">
              전 종목 슬라이딩 윈도우 스캔 중... (1~2분 소요)
            </div>
          )}

          {/* 결과 */}
          {result && !loading && (
            <div className="space-y-4">
              {/* 요약 카드 3개 */}
              <div className="grid grid-cols-3 gap-3">
                <SummaryCard label="총 신호" value={`${result.total_signals}건`} />
                <SummaryCard
                  label={`평균 수익률 (${refKey})`}
                  value={result.holding_stats[refKey] ? `${result.holding_stats[refKey]!.avg_return >= 0 ? '+' : ''}${result.holding_stats[refKey]!.avg_return.toFixed(2)}%` : '-'}
                  color={result.holding_stats[refKey] && result.holding_stats[refKey]!.avg_return >= 0 ? 'text-red-500' : 'text-blue-500'}
                />
                <SummaryCard
                  label={`승률 (${refKey})`}
                  value={result.holding_stats[refKey] ? `${result.holding_stats[refKey]!.win_rate.toFixed(1)}%` : '-'}
                  color={result.holding_stats[refKey] && result.holding_stats[refKey]!.win_rate >= 50 ? 'text-red-500' : 'text-blue-500'}
                />
              </div>

              {/* 보유기간별 성과 카드 */}
              <div>
                <h4 className="text-xs font-semibold text-gray-600 dark:text-t-text-muted mb-2">보유기간별 성과</h4>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
                  {result.params.holding_days.map(hd => {
                    const key = `${hd}d`
                    const stats = result.holding_stats[key] as MZBacktestHoldingStats | null
                    if (!stats) return (
                      <div key={key} className="p-3 bg-gray-50 dark:bg-t-bg rounded-lg text-center text-xs text-gray-400">
                        {key}: 데이터 없음
                      </div>
                    )
                    return (
                      <div key={key} className="p-3 bg-gray-50 dark:bg-t-bg rounded-lg text-xs space-y-1">
                        <div className="font-semibold text-sm text-gray-800 dark:text-t-text-primary">{key} ({stats.sample_count}건)</div>
                        <div className="flex justify-between">
                          <span className="text-gray-500 dark:text-t-text-muted">평균</span>
                          <span className={stats.avg_return >= 0 ? 'text-red-500 font-medium' : 'text-blue-500 font-medium'}>{stats.avg_return >= 0 ? '+' : ''}{stats.avg_return.toFixed(2)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500 dark:text-t-text-muted">중앙값</span>
                          <span>{stats.median >= 0 ? '+' : ''}{stats.median.toFixed(2)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500 dark:text-t-text-muted">승률</span>
                          <span className={stats.win_rate >= 50 ? 'text-red-500 font-medium' : 'text-blue-500'}>{stats.win_rate.toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500 dark:text-t-text-muted">Q1~Q3</span>
                          <span>{stats.q1.toFixed(1)}% ~ {stats.q3.toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500 dark:text-t-text-muted">최대수익</span>
                          <span className="text-red-500">+{stats.max_return.toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500 dark:text-t-text-muted">최대손실</span>
                          <span className="text-blue-500">{stats.max_loss.toFixed(1)}%</span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* 점수 구간별 성과 */}
              {result.score_analysis.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-600 dark:text-t-text-muted mb-2">점수 구간별 성과 ({refKey} 기준)</h4>
                  <table className="w-full text-xs">
                    <thead className="bg-gray-100 dark:bg-t-bg-elevated">
                      <tr>
                        <th className="py-1.5 px-3 text-left font-medium text-gray-600 dark:text-t-text-muted">점수 구간</th>
                        <th className="py-1.5 px-3 text-right font-medium text-gray-600 dark:text-t-text-muted">표본수</th>
                        <th className="py-1.5 px-3 text-right font-medium text-gray-600 dark:text-t-text-muted">평균 수익률</th>
                        <th className="py-1.5 px-3 text-right font-medium text-gray-600 dark:text-t-text-muted">승률</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.score_analysis.map(b => (
                        <tr key={b.label} className="border-t dark:border-t-border">
                          <td className="py-1.5 px-3 text-gray-700 dark:text-t-text-primary">{b.label}점</td>
                          <td className="py-1.5 px-3 text-right">{b.count}</td>
                          <td className={`py-1.5 px-3 text-right font-medium ${b.avg_return >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                            {b.avg_return >= 0 ? '+' : ''}{b.avg_return.toFixed(2)}%
                          </td>
                          <td className={`py-1.5 px-3 text-right ${b.win_rate >= 50 ? 'text-red-500' : 'text-blue-500'}`}>
                            {b.win_rate.toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* 월별 성과 */}
              {result.monthly_analysis.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-600 dark:text-t-text-muted mb-2">월별 성과 ({refKey} 기준)</h4>
                  <div className="max-h-60 overflow-y-auto">
                    <table className="w-full text-xs">
                      <thead className="bg-gray-100 dark:bg-t-bg-elevated sticky top-0">
                        <tr>
                          <th className="py-1.5 px-3 text-left font-medium text-gray-600 dark:text-t-text-muted">월</th>
                          <th className="py-1.5 px-3 text-right font-medium text-gray-600 dark:text-t-text-muted">신호 수</th>
                          <th className="py-1.5 px-3 text-right font-medium text-gray-600 dark:text-t-text-muted">평균 수익률</th>
                          <th className="py-1.5 px-3 text-right font-medium text-gray-600 dark:text-t-text-muted">승률</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.monthly_analysis.map(m => (
                          <tr key={m.month} className="border-t dark:border-t-border">
                            <td className="py-1.5 px-3 text-gray-700 dark:text-t-text-primary">{m.month}</td>
                            <td className="py-1.5 px-3 text-right">{m.signal_count}</td>
                            <td className={`py-1.5 px-3 text-right font-medium ${m.avg_return >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                              {m.avg_return >= 0 ? '+' : ''}{m.avg_return.toFixed(2)}%
                            </td>
                            <td className={`py-1.5 px-3 text-right ${m.win_rate >= 50 ? 'text-red-500' : 'text-blue-500'}`}>
                              {m.win_rate.toFixed(1)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* 상위/하위 종목 */}
              {(result.top_performers.length > 0 || result.worst_performers.length > 0) && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  <PerformerTable title="상위 종목" items={result.top_performers} refKey={refKey} />
                  <PerformerTable title="하위 종목" items={result.worst_performers} refKey={refKey} />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SummaryCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="p-3 bg-gray-50 dark:bg-t-bg rounded-lg text-center">
      <div className="text-xs text-gray-500 dark:text-t-text-muted mb-1">{label}</div>
      <div className={`text-lg font-bold ${color || 'text-gray-800 dark:text-t-text-primary'}`}>{value}</div>
    </div>
  )
}

function PerformerTable({ title, items, refKey }: { title: string; items: MZBacktestSignal[]; refKey: string }) {
  if (items.length === 0) return null
  return (
    <div>
      <h4 className="text-xs font-semibold text-gray-600 dark:text-t-text-muted mb-2">{title} ({refKey} 기준)</h4>
      <div className="max-h-60 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="bg-gray-100 dark:bg-t-bg-elevated sticky top-0">
            <tr>
              <th className="py-1.5 px-2 text-left font-medium text-gray-600 dark:text-t-text-muted">종목</th>
              <th className="py-1.5 px-2 text-left font-medium text-gray-600 dark:text-t-text-muted">날짜</th>
              <th className="py-1.5 px-2 text-right font-medium text-gray-600 dark:text-t-text-muted">점수</th>
              <th className="py-1.5 px-2 text-right font-medium text-gray-600 dark:text-t-text-muted">진입가</th>
              <th className="py-1.5 px-2 text-right font-medium text-gray-600 dark:text-t-text-muted">수익률</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s, i) => {
              const ret = s[refKey] as number | null
              return (
                <tr key={i} className="border-t dark:border-t-border">
                  <td className="py-1 px-2 text-gray-700 dark:text-t-text-primary truncate max-w-[100px]" title={s.stock_name}>{s.stock_name}</td>
                  <td className="py-1 px-2 text-gray-500 dark:text-t-text-muted">{(s.signal_date ?? '').slice(5)}</td>
                  <td className="py-1 px-2 text-right">{s.score?.toFixed(0)}</td>
                  <td className="py-1 px-2 text-right">{s.entry_price?.toLocaleString()}</td>
                  <td className={`py-1 px-2 text-right font-medium ${ret != null && ret >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                    {ret != null ? `${ret >= 0 ? '+' : ''}${ret.toFixed(2)}%` : '-'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SqueezeThemesPanel({ themes }: { themes: SqueezeTheme[] }) {
  if (themes.length === 0) return null

  return (
    <div className="bg-white dark:bg-t-bg-card rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-800 dark:text-t-text-primary mb-1">
        재주목 테마
        <span className="ml-2 text-xs font-normal text-gray-500 dark:text-t-text-muted">
          캔들 수축 종목 2개 이상 집중된 테마 — 조정 후 재시동 가능성
        </span>
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 mt-3">
        {themes.map(t => {
          const readinessColor =
            t.readiness >= 60 ? 'text-red-500' :
            t.readiness >= 40 ? 'text-amber-500' :
            'text-gray-500 dark:text-t-text-muted'
          const readinessLabel =
            t.readiness >= 60 ? '준비됨' :
            t.readiness >= 40 ? '수축 중' :
            '초기'
          return (
            <div key={t.theme} className="p-3 bg-cyan-50/50 dark:bg-cyan-900/10 border border-cyan-200/60 dark:border-cyan-700/30 rounded-lg">
              {/* 헤더: 테마명 + 종목수 + 준비도 */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-cyan-800 dark:text-cyan-300">{t.theme}</span>
                  <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-cyan-200 dark:bg-cyan-800 text-cyan-700 dark:text-cyan-300">
                    {t.count}종목
                  </span>
                </div>
                <span className={`text-xs font-bold ${readinessColor}`}>
                  {readinessLabel} {t.readiness.toFixed(0)}
                </span>
              </div>
              {/* 지표 요약 */}
              <div className="grid grid-cols-3 gap-2 text-[11px] mb-2">
                <div className="text-center">
                  <div className="text-gray-400 dark:text-t-text-muted">수축률</div>
                  <div className={`font-bold ${t.avg_contraction_pct <= -30 ? 'text-blue-600 dark:text-blue-400' : 'text-cyan-600 dark:text-cyan-400'}`}>
                    {t.avg_contraction_pct.toFixed(0)}%
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-gray-400 dark:text-t-text-muted">조정깊이</div>
                  <div className="font-medium text-gray-700 dark:text-t-text-primary">{t.avg_correction_depth_pct.toFixed(1)}%</div>
                </div>
                <div className="text-center">
                  <div className="text-gray-400 dark:text-t-text-muted">거래량</div>
                  <div className={`font-medium ${t.avg_volume_shrink <= 0.5 ? 'text-green-600 dark:text-green-400' : 'text-gray-600 dark:text-t-text-muted'}`}>
                    {t.avg_volume_shrink.toFixed(2)}x
                  </div>
                </div>
              </div>
              {/* 종목 리스트 */}
              <div className="space-y-1">
                {t.stocks.map(s => (
                  <div key={s.code} className="flex items-center justify-between text-xs">
                    <Link
                      to={`/stocks/${s.code}`}
                      className="text-cyan-700 dark:text-cyan-400 hover:underline truncate max-w-[120px]"
                    >
                      {s.name}
                    </Link>
                    <div className="flex items-center gap-2">
                      <span className={`${(s.contraction_pct ?? 0) <= -30 ? 'text-blue-500 font-medium' : 'text-gray-500 dark:text-t-text-muted'}`}>
                        {s.contraction_pct != null ? `${s.contraction_pct.toFixed(0)}%` : '-'}
                      </span>
                      <span className="text-gray-400 dark:text-t-text-muted w-6 text-right">{s.score?.toFixed(0)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const PAGE_SIZE = 50

export default function PullbackPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('top_picks')
  const [stocks, setStocks] = useState<SignalStock[]>([])
  const [summary, setSummary] = useState<SignalSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedCode, setExpandedCode] = useState<string | null>(null)
  const [showCount, setShowCount] = useState(PAGE_SIZE)
  const { watchedCodes } = useWatchlist()

  // 품질 필터
  const [onlyProfitable, setOnlyProfitable] = useState(false)
  const [onlyGrowing, setOnlyGrowing] = useState(false)
  const [onlyInstitutional, setOnlyInstitutional] = useState(false)

  // 급등 후 눌림 서브필터
  const [onlySurgePullback, setOnlySurgePullback] = useState(false)

  // MSS 타임프레임 서브필터
  const [mssTimeframe, setMssTimeframe] = useState<'daily' | 'weekly' | 'monthly'>('daily')

  // 차트 타임프레임 (상단 설정 → 모든 차트 적용)
  const [chartTimeframe, setChartTimeframe] = useState<'daily' | 'weekly' | 'monthly'>('daily')

  const fetchSummary = useCallback(async () => {
    try {
      const data = await pullbackApi.getSummary()
      setSummary(data)
    } catch (err) {
      console.error('시그널 요약 로드 실패:', err)
    }
  }, [])

  const fetchSignals = useCallback(async (tab: TabKey, filters?: { profitable?: boolean; growing?: boolean; institutional?: boolean; surgePullback?: boolean; mssTimeframe?: string }) => {
    setLoading(true)
    setExpandedCode(null)
    setShowCount(PAGE_SIZE)
    try {
      if (tab === 'top_picks') {
        const data = await pullbackApi.getTopPicks()
        setStocks(data.stocks ?? [])
      } else if (tab === 'watchlist') {
        const codes = Array.from(watchedCodes)
        if (codes.length === 0) {
          setStocks([])
        } else {
          const data = await pullbackApi.analyzeByCode(codes)
          setStocks(data.stocks ?? [])
        }
      } else {
        const data = await pullbackApi.getSignals({
          signal_type: tab,
          only_profitable: filters?.profitable,
          only_growing: filters?.growing,
          only_institutional: filters?.institutional,
          ...(tab === 'pullback' && filters?.surgePullback ? { only_surge_pullback: true } : {}),
          ...(tab === 'mss_proximity' ? { mss_timeframe: filters?.mssTimeframe ?? 'daily' } : {}),
        })
        setStocks(data.stocks ?? [])
      }
    } catch (err) {
      console.error('시그널 목록 로드 실패:', err)
      setStocks([])
    } finally {
      setLoading(false)
    }
  }, [watchedCodes])

  // silent refetch용 ref (현재 탭/필터 추적)
  const filtersRef = useRef({ activeTab, onlyProfitable, onlyGrowing, onlyInstitutional, onlySurgePullback, mssTimeframe })
  useEffect(() => {
    filtersRef.current = { activeTab, onlyProfitable, onlyGrowing, onlyInstitutional, onlySurgePullback, mssTimeframe }
  }, [activeTab, onlyProfitable, onlyGrowing, onlyInstitutional, onlySurgePullback, mssTimeframe])

  const silentRefetch = useCallback(async () => {
    const f = filtersRef.current
    try {
      const [summaryData] = await Promise.all([pullbackApi.getSummary()])
      setSummary(summaryData)
      if (f.activeTab === 'top_picks') {
        const data = await pullbackApi.getTopPicks()
        setStocks(data.stocks ?? [])
      } else if (f.activeTab === 'watchlist') {
        const codes = Array.from(watchedCodes)
        if (codes.length > 0) {
          const data = await pullbackApi.analyzeByCode(codes)
          setStocks(data.stocks ?? [])
        }
      } else {
        const data = await pullbackApi.getSignals({
          signal_type: f.activeTab as SignalType,
          only_profitable: f.onlyProfitable,
          only_growing: f.onlyGrowing,
          only_institutional: f.onlyInstitutional,
          ...(f.activeTab === 'pullback' && f.onlySurgePullback ? { only_surge_pullback: true } : {}),
          ...(f.activeTab === 'mss_proximity' ? { mss_timeframe: f.mssTimeframe } : {}),
        })
        setStocks(data.stocks ?? [])
      }
    } catch { /* 조용히 실패 */ }
  }, [watchedCodes])

  useRealtimePolling(silentRefetch, 60_000, {
    onlyMarketHours: true,
    enabled: !loading,
  })

  useEffect(() => {
    fetchSummary()
    fetchSignals(activeTab, { profitable: onlyProfitable, growing: onlyGrowing, institutional: onlyInstitutional, surgePullback: onlySurgePullback, mssTimeframe })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 필터 변경 시 재조회
  useEffect(() => {
    if (activeTab !== 'watchlist' && activeTab !== 'top_picks') {
      fetchSignals(activeTab, { profitable: onlyProfitable, growing: onlyGrowing, institutional: onlyInstitutional, surgePullback: onlySurgePullback, mssTimeframe })
    }
  }, [onlyProfitable, onlyGrowing, onlyInstitutional, onlySurgePullback]) // eslint-disable-line react-hooks/exhaustive-deps

  // 키보드 단축키: Tab=탭전환, Ctrl+↑↓=행 이동 및 펼치기
  useEffect(() => {
    const tabKeys = SIGNAL_TABS.map(t => t.key)
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Tab') {
        e.preventDefault()
        setActiveTab(prev => {
          const idx = tabKeys.indexOf(prev)
          const next = tabKeys[(idx + (e.shiftKey ? tabKeys.length - 1 : 1)) % tabKeys.length] as TabKey
          fetchSignals(next)
          return next
        })
      }
      if (e.ctrlKey && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
        e.preventDefault()
        setExpandedCode(prev => {
          const codes = stocks.map(s => s.stock_code)
          if (codes.length === 0) return prev
          const curIdx = prev ? codes.indexOf(prev) : -1
          let nextIdx: number
          if (e.key === 'ArrowDown') {
            nextIdx = curIdx < codes.length - 1 ? curIdx + 1 : 0
          } else {
            nextIdx = curIdx > 0 ? curIdx - 1 : codes.length - 1
          }
          setTimeout(() => {
            const el = document.getElementById(`signal-row-${codes[nextIdx]}`)
            if (el) {
              const top = el.getBoundingClientRect().top + window.scrollY - 80
              window.scrollTo({ top, behavior: 'smooth' })
            }
          }, 100)
          return codes[nextIdx]
        })
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [fetchSignals, stocks])

  const handleTabChange = (tab: TabKey) => {
    setActiveTab(tab)
    fetchSignals(tab, { profitable: onlyProfitable, growing: onlyGrowing, institutional: onlyInstitutional, surgePullback: onlySurgePullback, mssTimeframe })
  }

  const handleMssTimeframeChange = (tf: 'daily' | 'weekly' | 'monthly') => {
    setMssTimeframe(tf)
    fetchSignals('mss_proximity', { profitable: onlyProfitable, growing: onlyGrowing, institutional: onlyInstitutional, surgePullback: onlySurgePullback, mssTimeframe: tf })
  }

  const toggleRow = (code: string) => {
    setExpandedCode(prev => prev === code ? null : code)
  }

  // 탭별 핵심 컬럼 렌더링
  const renderColumns = (stock: SignalStock) => {
    const st = activeTab === 'watchlist' ? stock.signal_type : stock.signal_type
    if (activeTab === 'top_picks') {
      const signalLabels: Record<string, { text: string; cls: string }> = {
        pullback: { text: '눌림목', cls: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' },
        high_breakout: { text: '전고점 돌파', cls: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
        resistance_test: { text: '저항 돌파', cls: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' },
        support_test: { text: '지지선', cls: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400' },
        mss_proximity: { text: 'MSS 근접', cls: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400' },
        momentum_zone: { text: '관성 구간', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' },
        ma120_turn: { text: '120일선', cls: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400' },
        candle_squeeze: { text: '캔들 수축', cls: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400' },
        candle_expansion: { text: '캔들 확장', cls: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400' },
      }
      const label = signalLabels[stock.signal_type] || { text: stock.signal_type, cls: 'bg-gray-100 text-gray-600' }
      return (
        <>
          <td className="py-3 px-3 text-center text-sm">
            <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${label.cls}`}>{label.text}</span>
          </td>
          <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
            {stock.percentile_60d != null ? `${stock.percentile_60d.toFixed(0)}%` : '-'}
          </td>
          <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
            {stock.volume_ratio?.toFixed(2) ?? '-'}x
          </td>
        </>
      )
    }
    if (activeTab === 'watchlist') {
      const signalLabels: Record<string, { text: string; cls: string }> = {
        pullback: { text: '눌림목', cls: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' },
        high_breakout: { text: '전고점 돌파', cls: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
        resistance_test: { text: '저항 돌파', cls: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' },
        support_test: { text: '지지선 테스트', cls: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400' },
        mss_proximity: { text: '저항선 근접', cls: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400' },
        momentum_zone: { text: '관성 구간', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' },
        ma120_turn: { text: '120일선 전환', cls: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400' },
        candle_squeeze: { text: '캔들 수축', cls: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400' },
        candle_expansion: { text: '캔들 확장', cls: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400' },
      }
      const label = signalLabels[stock.signal_type] || { text: stock.signal_type, cls: 'bg-gray-100 text-gray-600' }
      return (
        <>
          <td className="py-3 px-3 text-center text-sm">
            <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${label.cls}`}>{label.text}</span>
          </td>
          <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
            {stock.ma20_distance_pct != null ? `${stock.ma20_distance_pct >= 0 ? '+' : ''}${stock.ma20_distance_pct.toFixed(1)}%` : '-'}
          </td>
          <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
            {stock.volume_ratio?.toFixed(2) ?? '-'}x
          </td>
        </>
      )
    }
    if (st === 'pullback') {
      return (
        <>
          <td className="py-3 px-3 text-right text-sm">
            <span className="text-orange-600 dark:text-orange-400 font-medium">
              -{stock.pullback_pct?.toFixed(1) ?? '?'}%
            </span>
            {stock.surge_pct != null && stock.surge_pct >= 25 && (
              <span className="ml-1 text-red-500 text-xs font-medium" title={`급등 ${stock.surge_pct.toFixed(0)}%`}>
                ↑{stock.surge_pct.toFixed(0)}%
              </span>
            )}
          </td>
          <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
            {formatPct(stock.ma20_distance_pct)}
          </td>
          <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
            {stock.volume_ratio?.toFixed(2) ?? '-'}x
            {stock.volume_decreasing && <span className="ml-1 text-green-500 text-xs">&#9660;</span>}
          </td>
        </>
      )
    }
    if (st === 'high_breakout') {
      return (
        <>
          <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
            {formatPrice(stock.prev_high_price)}
          </td>
          <td className="py-3 px-3 text-right text-sm">
            <span className="text-red-500 font-medium">+{stock.breakout_pct?.toFixed(1) ?? '?'}%</span>
          </td>
          <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
            {stock.breakout_volume_ratio?.toFixed(1) ?? '-'}x
          </td>
        </>
      )
    }
    if (st === 'support_test') {
      return (
        <>
          <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
            {formatPrice(stock.support_price)}
          </td>
          <td className="py-3 px-3 text-right text-sm">
            <span className="text-teal-600 dark:text-teal-400 font-medium">
              {formatPct(stock.support_distance_pct, false)}
            </span>
          </td>
          <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
            {stock.support_touch_count ?? '-'}회
          </td>
        </>
      )
    }
    if (st === 'mss_proximity') {
      return (
        <>
          <td className="py-3 px-3 text-right text-sm font-medium text-sky-600 dark:text-sky-400">
            {formatPrice(stock.mss_level)}
          </td>
          <td className="py-3 px-3 text-right text-sm">
            <span className={`font-medium ${
              Math.abs(stock.mss_distance_pct ?? 0) <= 2
                ? 'text-red-500'
                : 'text-gray-600 dark:text-t-text-muted'
            }`}>
              {formatPct(stock.mss_distance_pct)}
            </span>
          </td>
          <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
            {stock.mss_touch_count ?? '-'}회
          </td>
        </>
      )
    }
    if (st === 'momentum_zone') {
      return (
        <>
          <td className="py-3 px-3 text-right text-sm">
            <span className="text-amber-600 dark:text-amber-400 font-medium">
              +{stock.mz_surge_pct?.toFixed(0) ?? '?'}%
            </span>
          </td>
          <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
            {stock.mz_consolidation_days ?? '-'}일
          </td>
          <td className="py-3 px-3 text-right text-sm">
            <span className={`font-medium ${
              (stock.mz_distance_to_upper_pct ?? 99) <= 2
                ? 'text-red-500'
                : 'text-gray-600 dark:text-t-text-muted'
            }`}>
              {stock.mz_distance_to_upper_pct != null ? `${stock.mz_distance_to_upper_pct.toFixed(1)}%` : '-'}
            </span>
          </td>
        </>
      )
    }
    if (st === 'ma120_turn') {
      return (
        <>
          <td className="py-3 px-3 text-right text-sm">
            <span className={`font-medium ${
              (stock.ma120_slope_pct ?? 0) > 0
                ? 'text-red-500'
                : (stock.ma120_slope_pct ?? 0) >= -0.1
                ? 'text-amber-500'
                : 'text-blue-500'
            }`}>
              {stock.ma120_slope_pct != null ? `${stock.ma120_slope_pct >= 0 ? '+' : ''}${stock.ma120_slope_pct.toFixed(2)}%` : '-'}
            </span>
          </td>
          <td className="py-3 px-3 text-right text-sm">
            <span className={`font-medium ${
              (stock.recovery_pct ?? 0) >= 50 ? 'text-blue-600 dark:text-blue-400' : 'text-gray-600 dark:text-t-text-muted'
            }`}>
              {stock.recovery_pct != null ? `${stock.recovery_pct.toFixed(0)}%` : '-'}
            </span>
          </td>
          <td className="py-3 px-3 text-right text-sm">
            <span className={`font-medium ${
              (stock.volume_surge_ratio ?? 0) >= 2.0 ? 'text-red-500' : 'text-gray-600 dark:text-t-text-muted'
            }`}>
              {stock.volume_surge_ratio?.toFixed(2) ?? '-'}x
            </span>
            <div className="flex gap-0.5 mt-0.5 justify-end">
              {stock.has_double_bottom && <span className="text-[10px] px-1 rounded bg-violet-100 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400">W</span>}
              {stock.resistance_broken && <span className="text-[10px] px-1 rounded bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400">돌파</span>}
              {stock.has_new_high_volume && <span className="text-[10px] px-1 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400">신고</span>}
            </div>
          </td>
        </>
      )
    }
    if (st === 'candle_squeeze') {
      return (
        <>
          <td className="py-3 px-3 text-right text-sm">
            <span className={`font-medium ${
              (stock.cs_contraction_pct ?? 0) <= -30
                ? 'text-blue-600 dark:text-blue-400'
                : 'text-cyan-600 dark:text-cyan-400'
            }`}>
              {stock.cs_contraction_pct != null ? `${stock.cs_contraction_pct.toFixed(0)}%` : '-'}
            </span>
          </td>
          <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
            {stock.cs_correction_days ?? '-'}일
          </td>
          <td className="py-3 px-3 text-right text-sm">
            <span className={`font-medium ${
              (stock.cs_volume_shrink_ratio ?? 1) <= 0.5
                ? 'text-green-600 dark:text-green-400'
                : 'text-gray-600 dark:text-t-text-muted'
            }`}>
              {stock.cs_volume_shrink_ratio?.toFixed(2) ?? '-'}x
            </span>
          </td>
        </>
      )
    }
    if (st === 'candle_expansion') {
      return (
        <>
          <td className="py-3 px-3 text-right text-sm">
            <span className={`font-medium ${
              (stock.ce_expansion_pct ?? 0) >= 50
                ? 'text-red-600 dark:text-red-400'
                : 'text-rose-600 dark:text-rose-400'
            }`}>
              +{stock.ce_expansion_pct?.toFixed(0) ?? '?'}%
            </span>
          </td>
          <td className="py-3 px-3 text-right text-sm">
            <span className={`font-medium ${
              (stock.ce_bullish_pct ?? 0) >= 60
                ? 'text-red-500'
                : 'text-gray-600 dark:text-t-text-muted'
            }`}>
              {stock.ce_bullish_pct?.toFixed(0) ?? '-'}%
            </span>
          </td>
          <td className="py-3 px-3 text-right text-sm">
            <span className={`font-medium ${
              (stock.ce_volume_surge_ratio ?? 1) >= 2.0
                ? 'text-red-500'
                : 'text-gray-600 dark:text-t-text-muted'
            }`}>
              {stock.ce_volume_surge_ratio?.toFixed(2) ?? '-'}x
            </span>
          </td>
        </>
      )
    }
    // resistance_test
    return (
      <>
        <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
          {formatPrice(stock.resistance_price)}
        </td>
        <td className="py-3 px-3 text-right text-sm">
          <span className="text-purple-600 dark:text-purple-400 font-medium">
            {formatPct(stock.resistance_distance_pct, false)}
          </span>
        </td>
        <td className="py-3 px-3 text-right text-sm text-gray-600 dark:text-t-text-muted">
          {stock.resistance_touch_count ?? '-'}회
        </td>
      </>
    )
  }

  // 탭별 헤더 컬럼
  const getColumnHeaders = () => {
    if (activeTab === 'top_picks') return ['시그널', '위치(%)', '거래량비']
    if (activeTab === 'watchlist') return ['시그널', 'MA20 거리', '거래량비']
    if (activeTab === 'pullback') return ['하락률', 'MA20 거리', '거래량비']
    if (activeTab === 'high_breakout') return ['전고점', '돌파율', '돌파거래량']
    if (activeTab === 'support_test') return ['지지선', '지지거리', '터치횟수']
    if (activeTab === 'mss_proximity') return ['MSS 레벨', '거리%', '터치횟수']
    if (activeTab === 'momentum_zone') return ['급등률', '횡보(일)', '상단거리']
    if (activeTab === 'ma120_turn') return ['MA120기울기', '회복률', '거래량비']
    if (activeTab === 'candle_squeeze') return ['수축률', '조정(일)', '거래량비']
    if (activeTab === 'candle_expansion') return ['확장률', '양봉비율', '거래량비']
    return ['저항선', '저항거리', '터치횟수']
  }

  // 종목상세 이전/다음 네비게이션용 리스트
  const stockNavList = useMemo(() =>
    stocks.map(s => ({ code: s.stock_code, name: s.stock_name })),
    [stocks]
  )

  const columnHeaders = getColumnHeaders()

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-t-text-primary">차트 시그널 스캐너</h2>
          <p className="text-sm text-gray-500 dark:text-t-text-muted">
            순수 차트 데이터 기반 시그널 감지 (눌림목 / 전고점 돌파 / 저항 돌파 / 지지선 / MSS / 관성 구간 / 120일선 전환 / 캔들 수축 / 캔들 확장)
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* 차트 타임프레임 설정 */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-500 dark:text-t-text-muted">차트:</span>
            {([['daily', '일봉'], ['weekly', '주봉'], ['monthly', '월봉']] as const).map(([tf, label]) => (
              <button
                key={tf}
                onClick={() => setChartTimeframe(tf)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  chartTimeframe === tf
                    ? 'bg-indigo-600 text-white dark:bg-indigo-500'
                    : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-gray-600'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <button
            onClick={() => { fetchSummary(); fetchSignals(activeTab, { profitable: onlyProfitable, growing: onlyGrowing, institutional: onlyInstitutional, surgePullback: onlySurgePullback, mssTimeframe }) }}
            disabled={loading}
            className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-t-bg-elevated hover:bg-gray-200 dark:hover:bg-gray-600 rounded disabled:opacity-50 text-gray-700 dark:text-t-text-primary"
          >
            새로고침
          </button>
        </div>
      </div>

      {/* 서브탭 */}
      <div className="flex gap-2">
        {SIGNAL_TABS.map(tab => {
          const count = tab.key === 'watchlist' ? watchedCodes.size : (summary?.[tab.key as keyof SignalSummary] as number ?? 0)
          const isActive = activeTab === tab.key
          return (
            <button
              key={tab.key}
              onClick={() => handleTabChange(tab.key)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? tab.key === 'top_picks' ? 'bg-amber-500 text-white dark:bg-amber-600'
                  : tab.key === 'watchlist' ? 'bg-yellow-500 text-white dark:bg-yellow-600'
                  : 'bg-indigo-600 text-white dark:bg-indigo-500'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {tab.key === 'top_picks' && <span className="mr-1">&#9733;</span>}
              {tab.key === 'watchlist' && <span className="mr-1">&#9733;</span>}
              {tab.label}
              {(summary != null || tab.key === 'watchlist') && (
                <span className={`ml-1.5 px-1.5 py-0.5 rounded-full text-xs ${
                  isActive
                    ? 'bg-white/20 text-white'
                    : 'bg-gray-200 dark:bg-gray-600 text-gray-500 dark:text-t-text-muted'
                }`}>
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* 눌림목 서브필터: 급등 후 눌림 */}
      {activeTab === 'pullback' && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 dark:text-t-text-muted">눌림목 필터:</span>
          <button
            onClick={() => setOnlySurgePullback(prev => !prev)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              onlySurgePullback
                ? 'bg-orange-500 text-white dark:bg-orange-600'
                : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            급등 후 눌림 (25%+)
          </button>
        </div>
      )}

      {/* MSS 타임프레임 서브필터 */}
      {activeTab === 'mss_proximity' && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 dark:text-t-text-muted">타임프레임:</span>
          {([['daily', '일봉'], ['weekly', '주봉'], ['monthly', '월봉']] as const).map(([tf, label]) => (
            <button
              key={tf}
              onClick={() => handleMssTimeframeChange(tf)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                mssTimeframe === tf
                  ? 'bg-sky-500 text-white dark:bg-sky-600'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {/* 품질 필터 칩 */}
      {activeTab !== 'watchlist' && activeTab !== 'top_picks' && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-500 dark:text-t-text-muted">품질 필터:</span>
          {[
            { key: 'profitable' as const, label: '수익성', state: onlyProfitable, toggle: setOnlyProfitable, color: 'green' },
            { key: 'growing' as const, label: '매출 성장', state: onlyGrowing, toggle: setOnlyGrowing, color: 'blue' },
            { key: 'institutional' as const, label: '기관 매수', state: onlyInstitutional, toggle: setOnlyInstitutional, color: 'purple' },
          ].map(f => (
            <button
              key={f.key}
              onClick={() => f.toggle(prev => !prev)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                f.state
                  ? f.color === 'green' ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400 ring-1 ring-green-300 dark:ring-green-700'
                  : f.color === 'blue' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400 ring-1 ring-blue-300 dark:ring-blue-700'
                  : 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400 ring-1 ring-purple-300 dark:ring-purple-700'
                  : 'bg-gray-100 text-gray-500 dark:bg-t-bg-elevated dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}

      {/* 관성 구간 백테스트 패널 */}
      {activeTab === 'momentum_zone' && <MZBacktestPanel />}

      {/* 캔들 수축 → 재주목 테마 패널 */}
      {activeTab === 'candle_squeeze' && summary?.squeeze_themes && (
        <SqueezeThemesPanel themes={summary.squeeze_themes} />
      )}

      {/* 트렌드 테마 (돌파/저항 시그널 기반) */}
      {(summary?.trend_themes ?? []).length > 0 && (
        <div className="bg-white dark:bg-t-bg-card rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-gray-800 dark:text-t-text-primary mb-2">
            돌파 시그널 테마 집계
            <span className="ml-2 text-xs font-normal text-gray-500 dark:text-t-text-muted">
              전고점 돌파 + 저항 돌파 종목들의 테마
            </span>
          </h3>
          <div className="flex flex-wrap gap-2">
            {(summary?.trend_themes ?? []).map((t: TrendTheme) => (
              <div
                key={t.theme}
                className="px-3 py-1.5 bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-700/40 rounded-lg"
              >
                <span className="text-sm font-medium text-indigo-700 dark:text-indigo-400">{t.theme}</span>
                <span className="ml-1.5 text-xs text-indigo-500 dark:text-indigo-300">{t.count}종목</span>
                <div className="text-xs text-gray-500 dark:text-t-text-muted mt-0.5 truncate max-w-[200px]">
                  {t.stocks.join(', ')}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 테이블 */}
      {loading ? (
        <div className="text-center py-16 text-gray-400 dark:text-t-text-muted">로딩 중...</div>
      ) : stocks.length === 0 ? (
        <div className="text-center py-16 text-gray-400 dark:text-t-text-muted">
          {activeTab === 'top_picks'
            ? 'TOP 필터 조건에 맞는 매매 후보가 없습니다'
            : activeTab === 'watchlist'
            ? watchedCodes.size === 0
              ? '관심종목이 없습니다. 다른 탭에서 ★ 아이콘을 클릭하여 추가하세요.'
              : '관심종목 중 시그널이 감지된 종목이 없습니다.'
            : '해당 시그널이 감지된 종목이 없습니다'}
        </div>
      ) : (
        <div className="bg-white dark:bg-t-bg-card rounded-lg shadow overflow-hidden">
          <table className="w-full text-sm table-fixed">
            <thead className="bg-gray-50 dark:bg-t-bg">
              <tr>
                <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted w-[15%]">종목</th>
                <th className="text-right py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted w-[10%]">현재가</th>
                {columnHeaders.map(h => (
                  <th key={h} className="text-right py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted">{h}</th>
                ))}
                <th className="text-right py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted">점수</th>
                <th className="text-center py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted">등급</th>
                <th className="text-left py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted">테마</th>
              </tr>
            </thead>
            <tbody>
              {stocks.slice(0, showCount).map(stock => {
                const isExpanded = expandedCode === stock.stock_code
                const rowKey = `${stock.stock_code}-${stock.signal_type}`
                return (
                  <Fragment key={rowKey}>
                    <tr
                      id={`signal-row-${stock.stock_code}`}
                      onClick={() => toggleRow(stock.stock_code)}
                      className={`border-t dark:border-t-border cursor-pointer transition-colors ${
                        isExpanded
                          ? 'bg-indigo-50 dark:bg-indigo-900/10'
                          : 'hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50'
                      }`}
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center">
                          <WatchlistStar
                            stockCode={stock.stock_code}
                            stockName={stock.stock_name || stock.stock_code}
                          />
                          <div>
                            <div className="flex items-center gap-1">
                              <span className="font-medium text-gray-900 dark:text-t-text-primary">
                                {stock.stock_name || stock.stock_code}
                              </span>
                              {stock.is_profitable && <span className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0" title="수익성" />}
                              {stock.is_growing && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 flex-shrink-0" title="매출성장" />}
                              {stock.has_institutional_buying && <span className="w-1.5 h-1.5 rounded-full bg-purple-500 flex-shrink-0" title="기관매수" />}
                            </div>
                            <Link
                              to={`/stocks/${stock.stock_code}`}
                              state={{ stockListContext: { source: '시그널 스캐너', stocks: stockNavList, currentIndex: stocks.indexOf(stock) } }}
                              onClick={e => e.stopPropagation()}
                              className="text-xs text-indigo-500 dark:text-indigo-400 hover:underline"
                            >
                              {stock.stock_code} →
                            </Link>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-3 text-right font-medium text-gray-900 dark:text-t-text-primary">
                        {formatPrice(stock.current_price)}
                      </td>
                      {renderColumns(stock)}
                      <td className="py-3 px-3 text-right">
                        <ScoreBar score={stock.total_score} />
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${GRADE_COLORS[stock.grade] || GRADE_COLORS.D}`}>
                          {stock.grade || '-'}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex flex-wrap gap-1">
                          {(stock.themes ?? []).slice(0, 2).map(t => (
                            <span key={t} className="text-xs bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted px-1.5 py-0.5 rounded">
                              {t}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                    {isExpanded && (
                      <ExpandedRow
                        stockCode={stock.stock_code}
                        stockName={stock.stock_name}
                        initialTimeframe={chartTimeframe}
                        {...(stock.signal_type === 'support_test' && stock.support_price
                          ? { priceLine: stock.support_price, priceLineLabel: '지지선', priceLineColor: '#14b8a6' }
                          : stock.signal_type === 'resistance_test' && stock.resistance_price
                          ? { priceLine: stock.resistance_price, priceLineLabel: '저항선', priceLineColor: '#a855f7' }
                          : stock.signal_type === 'high_breakout' && stock.prev_high_price
                          ? { priceLine: stock.prev_high_price, priceLineLabel: '전고점', priceLineColor: '#ef4444' }
                          : stock.signal_type === 'pullback' && stock.support_line
                          ? { priceLine: stock.support_line, priceLineLabel: '지지선', priceLineColor: '#f97316' }
                          : stock.signal_type === 'mss_proximity' && stock.mss_level
                          ? { priceLine: stock.mss_level, priceLineLabel: '목선', priceLineColor: '#0ea5e9' }
                          : stock.signal_type === 'momentum_zone' && stock.mz_upper_bound
                          ? { priceLine: stock.mz_upper_bound, priceLineLabel: '횡보 상단', priceLineColor: '#f59e0b' }
                          : stock.signal_type === 'ma120_turn' && stock.ma120
                          ? { priceLine: stock.ma120, priceLineLabel: 'MA120', priceLineColor: '#8b5cf6' }
                          : stock.signal_type === 'candle_squeeze' && stock.ma50
                          ? { priceLine: stock.ma50, priceLineLabel: 'MA60', priceLineColor: '#06b6d4' }
                          : stock.signal_type === 'candle_expansion' && stock.ma20
                          ? { priceLine: stock.ma20, priceLineLabel: 'MA20', priceLineColor: '#e11d48' }
                          : {})}
                        {...(stock.signal_type === 'ma120_turn'
                          ? { initialMaVisible: { ma1: false, ma2: false, ma3: false, ma4: true, ma5: false } }
                          : {})}
                      />
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
          {showCount < stocks.length && (
            <div className="py-3 text-center border-t dark:border-t-border">
              <button
                onClick={() => setShowCount(prev => prev + PAGE_SIZE)}
                className="px-4 py-2 text-sm text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/10 rounded-lg transition-colors"
              >
                더 보기 ({stocks.length - showCount}개 남음)
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
