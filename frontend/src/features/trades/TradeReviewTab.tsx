import { useState, useEffect, useMemo } from 'react'
import { analysisApi } from '../../services/api'
import type {
  WhatIfResponse, WhatIfPosition, WhatIfRuleSummary,
  TradeContextResponse,
  FlowWinRateResponse,
  ClusterResponse, TradeCluster,
} from '../../types/trade_review'

interface Props {
  startDate?: string
  endDate?: string
}

const fmtPct = (n: number | null | undefined) =>
  n == null ? '-' : `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`

const fmtAmt = (n: number) => {
  const abs = Math.abs(n)
  if (abs >= 1e8) return `${(n / 1e8).toFixed(1)}억`
  if (abs >= 1e4) return `${(n / 1e4).toFixed(0)}만`
  return n.toLocaleString('ko-KR')
}

const pnlColor = (n: number | null | undefined) =>
  n == null ? 'text-gray-400' : n >= 0 ? 'text-red-500' : 'text-blue-500'

type SubTab = 'what-if' | 'context' | 'flow' | 'cluster'

export default function TradeReviewTab({ startDate, endDate }: Props) {
  const [subTab, setSubTab] = useState<SubTab>('what-if')

  return (
    <div className="space-y-4">
      {/* 서브탭 */}
      <div className="flex items-center gap-1.5">
        {([
          ['what-if', 'What-If'],
          ['context', '컨텍스트'],
          ['flow', '수급분석'],
          ['cluster', '패턴분석'],
        ] as [SubTab, string][]).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setSubTab(key)}
            className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
              subTab === key
                ? 'bg-gray-800 dark:bg-gray-200 text-white dark:text-gray-900 font-medium'
                : 'text-gray-500 dark:text-t-text-muted hover:bg-gray-100 dark:hover:bg-t-bg-elevated'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {subTab === 'what-if' && <WhatIfSection startDate={startDate} endDate={endDate} />}
      {subTab === 'context' && <ContextSection startDate={startDate} endDate={endDate} />}
      {subTab === 'flow' && <FlowWinRateSection startDate={startDate} endDate={endDate} />}
      {subTab === 'cluster' && <ClusterSection startDate={startDate} endDate={endDate} />}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// What-If Section
// ═══════════════════════════════════════════════════════════

function WhatIfSection({ startDate, endDate }: { startDate?: string; endDate?: string }) {
  const [data, setData] = useState<WhatIfResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [ruleFilter, setRuleFilter] = useState<'all' | 'hold' | 'stop' | 'take' | 'half'>('all')

  useEffect(() => {
    setLoading(true)
    analysisApi.getWhatIf(startDate, endDate).then(setData).catch(() => setData(null)).finally(() => setLoading(false))
  }, [startDate, endDate])

  const filteredSummaries = useMemo(() => {
    if (!data) return []
    return data.rule_summaries.filter(s => {
      if (ruleFilter === 'all') return true
      if (ruleFilter === 'hold') return s.rule.includes('일 보유')
      if (ruleFilter === 'stop') return s.rule.includes('손절')
      if (ruleFilter === 'take') return s.rule.includes('익절') && !s.rule.includes('반익절')
      if (ruleFilter === 'half') return s.rule.includes('반익절')
      return true
    })
  }, [data, ruleFilter])

  if (loading) return <LoadingSkeleton />
  if (!data || data.positions.length === 0) return <EmptyState message="청산된 포지션이 없습니다." />

  return (
    <div className="space-y-4">
      {/* 실제 vs 대안 비교 헤더 */}
      <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary">
            규칙별 집계
            <span className="text-xs text-gray-400 font-normal ml-2">실제 평균 {fmtPct(data.actual_avg_return_pct)}</span>
          </h3>
          <div className="flex gap-1">
            {([['all', '전체'], ['hold', '보유기간'], ['stop', '손절'], ['take', '익절'], ['half', '반익절']] as [typeof ruleFilter, string][]).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setRuleFilter(key)}
                className={`px-2 py-0.5 text-[10px] rounded ${ruleFilter === key ? 'bg-primary-500 text-white' : 'text-gray-400 hover:bg-gray-100 dark:hover:bg-t-bg-elevated'}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr className="border-b border-gray-100 dark:border-t-border text-gray-500 dark:text-t-text-muted">
                <th className="py-1.5 text-left font-medium">규칙</th>
                <th className="py-1.5 text-right font-medium">적용</th>
                <th className="py-1.5 text-right font-medium">트리거</th>
                <th className="py-1.5 text-right font-medium">평균수익</th>
                <th className="py-1.5 text-right font-medium">차이</th>
                <th className="py-1.5 text-right font-medium">우위</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50 dark:divide-t-border">
              {filteredSummaries.map(s => (
                <RuleSummaryRow key={s.rule} summary={s} />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 포지션별 아코디언 */}
      <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm">
        <div className="px-4 py-3 border-b border-gray-100 dark:border-t-border">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary">
            포지션별 상세 ({data.positions.length}건)
          </h3>
        </div>
        <div className="divide-y divide-gray-50 dark:divide-t-border">
          {data.positions.map(pos => (
            <div key={pos.position_id}>
              <button
                onClick={() => setExpanded(expanded === pos.position_id ? null : pos.position_id)}
                className="w-full px-4 py-2.5 flex items-center gap-3 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/30 text-left"
              >
                <span className="text-sm font-medium text-gray-900 dark:text-t-text-primary truncate">{pos.stock_name}</span>
                <span className="text-xs text-gray-400">{pos.entry_date} ~ {pos.exit_date}</span>
                <span className="text-xs text-gray-400">{pos.holding_days}일</span>
                <span className={`ml-auto text-sm font-mono font-medium ${pnlColor(pos.actual_return_pct)}`}>
                  {fmtPct(pos.actual_return_pct)}
                </span>
                <svg className={`w-4 h-4 text-gray-400 transition-transform ${expanded === pos.position_id ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {expanded === pos.position_id && (
                <div className="px-4 pb-3">
                  <PositionAlternatives position={pos} />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function RuleSummaryRow({ summary: s }: { summary: WhatIfRuleSummary }) {
  const diff = s.total_diff_pct
  const isBetter = diff > 0.5
  const isWorse = diff < -0.5
  return (
    <tr className={`${isBetter ? 'bg-red-50/50 dark:bg-red-900/10' : isWorse ? 'bg-blue-50/50 dark:bg-blue-900/10' : ''}`}>
      <td className="py-1.5 text-gray-700 dark:text-t-text-secondary font-medium">{s.rule}</td>
      <td className="py-1.5 text-right text-gray-500">{s.applicable_count}</td>
      <td className="py-1.5 text-right text-gray-500">{s.triggered_count}</td>
      <td className={`py-1.5 text-right font-mono ${pnlColor(s.avg_return_pct)}`}>{fmtPct(s.avg_return_pct)}</td>
      <td className={`py-1.5 text-right font-mono font-medium ${pnlColor(diff)}`}>{fmtPct(diff)}</td>
      <td className="py-1.5 text-right">
        <span className="text-red-500 text-[10px]">{s.better_count}W</span>
        <span className="text-gray-300 mx-0.5">/</span>
        <span className="text-blue-500 text-[10px]">{s.worse_count}L</span>
      </td>
    </tr>
  )
}

function PositionAlternatives({ position }: { position: WhatIfPosition }) {
  const groups = useMemo(() => {
    const hold = position.alternatives.filter(a => a.rule.includes('일 보유'))
    const stop = position.alternatives.filter(a => a.rule.includes('손절'))
    const take = position.alternatives.filter(a => a.rule.includes('익절') && !a.rule.includes('반익절'))
    const half = position.alternatives.filter(a => a.rule.includes('반익절'))
    return [
      { label: '보유기간 변동', items: hold },
      { label: '손절 규칙', items: stop },
      { label: '익절 규칙', items: take },
      { label: '반익절', items: half },
    ]
  }, [position])

  return (
    <div className="space-y-2">
      {groups.map(g => g.items.length > 0 && (
        <div key={g.label}>
          <div className="text-[10px] text-gray-400 mb-1">{g.label}</div>
          <div className="flex flex-wrap gap-1.5">
            {g.items.map(alt => (
              <div
                key={alt.rule}
                className={`px-2 py-1 rounded text-[10px] font-mono ${
                  alt.triggered
                    ? alt.diff_pct != null && alt.diff_pct > 0
                      ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400'
                      : 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                    : 'bg-gray-50 dark:bg-t-bg-elevated text-gray-400'
                }`}
              >
                <span className="font-medium">{alt.rule}</span>
                {alt.return_pct != null && (
                  <span className="ml-1">{fmtPct(alt.return_pct)}</span>
                )}
                {alt.triggered && alt.diff_pct != null && (
                  <span className="ml-1 opacity-70">({fmtPct(alt.diff_pct)})</span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// Context Section
// ═══════════════════════════════════════════════════════════

function ContextSection({ startDate, endDate }: { startDate?: string; endDate?: string }) {
  const [positions, setPositions] = useState<WhatIfPosition[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [context, setContext] = useState<TradeContextResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [posLoading, setPosLoading] = useState(true)

  // 포지션 목록 로딩 (What-If 데이터 재사용)
  useEffect(() => {
    setPosLoading(true)
    analysisApi.getWhatIf(startDate, endDate)
      .then(data => {
        setPositions(data.positions)
        if (data.positions.length > 0 && !selectedId) {
          setSelectedId(data.positions[0].position_id)
        }
      })
      .catch(() => {})
      .finally(() => setPosLoading(false))
  }, [startDate, endDate])

  // 선택된 포지션의 컨텍스트 로딩
  useEffect(() => {
    if (!selectedId) return
    setLoading(true)
    analysisApi.getTradeContext(selectedId).then(setContext).catch(() => setContext(null)).finally(() => setLoading(false))
  }, [selectedId])

  if (posLoading) return <LoadingSkeleton />
  if (positions.length === 0) return <EmptyState message="청산된 포지션이 없습니다." />

  return (
    <div className="space-y-4">
      {/* 포지션 선택 */}
      <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
        <select
          value={selectedId}
          onChange={e => setSelectedId(e.target.value)}
          className="w-full rounded-lg border border-gray-300 dark:border-t-border bg-white dark:bg-t-bg px-3 py-2 text-sm text-gray-900 dark:text-t-text-primary"
        >
          {positions.map(p => (
            <option key={p.position_id} value={p.position_id}>
              {p.stock_name} ({p.entry_date} ~ {p.exit_date}) {fmtPct(p.actual_return_pct)}
            </option>
          ))}
        </select>
      </div>

      {loading ? <LoadingSkeleton /> : context && (
        <>
          {/* 요약 카드 */}
          <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
            <div className="flex items-center gap-3 mb-3">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary">
                {context.stock_name}
              </h3>
              <span className={`text-sm font-mono font-medium ${pnlColor(context.return_pct)}`}>
                {fmtPct(context.return_pct)}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(context.summary).map(([key, value]) => (
                <span key={key} className="px-2 py-1 bg-gray-100 dark:bg-t-bg-elevated rounded text-xs text-gray-600 dark:text-t-text-secondary">
                  {value}
                </span>
              ))}
            </div>
          </div>

          {/* 수급 바 차트 */}
          {context.flow_bars.length > 0 && (
            <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary mb-3">투자자 수급</h3>
              <FlowBarChart bars={context.flow_bars} entryDate={context.entry_date} exitDate={context.exit_date} />
            </div>
          )}

          {/* 상대강도 */}
          {context.relative_strength.length > 0 && (
            <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary mb-3">
                KOSPI 대비 초과수익률
              </h3>
              <RelativeStrengthChart points={context.relative_strength} entryDate={context.entry_date} exitDate={context.exit_date} />
            </div>
          )}
        </>
      )}
    </div>
  )
}

function FlowBarChart({ bars, entryDate, exitDate }: { bars: TradeContextResponse['flow_bars']; entryDate: string; exitDate: string | null }) {
  const filtered = bars

  if (filtered.length === 0) return null

  const maxAmt = Math.max(...filtered.map(b => Math.max(Math.abs(b.foreign_net), Math.abs(b.institution_net))), 1)

  return (
    <div className="space-y-0.5 max-h-64 overflow-y-auto">
      {filtered.map(bar => {
        const isEntry = bar.date === entryDate
        const isExit = exitDate && bar.date === exitDate
        return (
          <div key={bar.date} className={`flex items-center gap-2 text-[10px] ${isEntry || isExit ? 'bg-yellow-50 dark:bg-yellow-900/10' : ''}`}>
            <span className="w-16 text-gray-400 shrink-0 text-right font-mono">
              {bar.date.slice(5)}
              {isEntry && <span className="text-yellow-600 ml-0.5">B</span>}
              {isExit && <span className="text-purple-600 ml-0.5">S</span>}
            </span>
            <div className="flex-1 flex items-center h-4 gap-0.5">
              {/* 외인 */}
              <div className="flex-1 flex justify-end">
                {bar.foreign_net < 0 && (
                  <div
                    className="h-3 bg-red-300/60 dark:bg-red-500/40 rounded-l"
                    style={{ width: `${(Math.abs(bar.foreign_net) / maxAmt) * 100}%` }}
                  />
                )}
              </div>
              <div className="flex-1">
                {bar.foreign_net >= 0 && (
                  <div
                    className="h-3 bg-red-400 dark:bg-red-600 rounded-r"
                    style={{ width: `${(bar.foreign_net / maxAmt) * 100}%` }}
                  />
                )}
              </div>
            </div>
            <div className="flex-1 flex items-center h-4 gap-0.5">
              {/* 기관 */}
              <div className="flex-1 flex justify-end">
                {bar.institution_net < 0 && (
                  <div
                    className="h-3 bg-blue-300/60 dark:bg-blue-500/40 rounded-l"
                    style={{ width: `${(Math.abs(bar.institution_net) / maxAmt) * 100}%` }}
                  />
                )}
              </div>
              <div className="flex-1">
                {bar.institution_net >= 0 && (
                  <div
                    className="h-3 bg-blue-400 dark:bg-blue-600 rounded-r"
                    style={{ width: `${(bar.institution_net / maxAmt) * 100}%` }}
                  />
                )}
              </div>
            </div>
          </div>
        )
      })}
      <div className="flex items-center gap-3 text-[10px] text-gray-400 mt-2">
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-red-400 rounded" /> 외인</span>
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 bg-blue-400 rounded" /> 기관</span>
      </div>
    </div>
  )
}

function RelativeStrengthChart({ points, entryDate, exitDate }: {
  points: TradeContextResponse['relative_strength']
  entryDate: string
  exitDate: string | null
}) {
  if (points.length < 2) return null

  const width = 600
  const height = 120
  const padding = { top: 10, right: 10, bottom: 20, left: 40 }

  const values = points.map(p => p.value)
  const minVal = Math.min(...values, 0)
  const maxVal = Math.max(...values, 0)
  const range = Math.max(maxVal - minVal, 1)

  const xScale = (i: number) => padding.left + (i / (points.length - 1)) * (width - padding.left - padding.right)
  const yScale = (v: number) => padding.top + (1 - (v - minVal) / range) * (height - padding.top - padding.bottom)

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i).toFixed(1)} ${yScale(p.value).toFixed(1)}`).join(' ')
  const zeroY = yScale(0)

  // 진입/청산 인덱스
  const entryIdx = points.findIndex(p => p.date >= entryDate)
  const exitIdx = exitDate ? points.findIndex(p => p.date >= exitDate) : -1

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      {/* 0 기준선 */}
      <line x1={padding.left} x2={width - padding.right} y1={zeroY} y2={zeroY} stroke="currentColor" className="text-gray-300 dark:text-gray-600" strokeDasharray="4 2" />
      <text x={padding.left - 4} y={zeroY + 3} textAnchor="end" className="text-[9px] fill-gray-400">0%</text>

      {/* 상대강도 라인 */}
      <path d={pathD} fill="none" stroke="currentColor" className="text-emerald-500" strokeWidth={1.5} />

      {/* 진입 마커 */}
      {entryIdx >= 0 && (
        <line x1={xScale(entryIdx)} x2={xScale(entryIdx)} y1={padding.top} y2={height - padding.bottom}
          stroke="currentColor" className="text-yellow-500" strokeDasharray="3 2" />
      )}
      {/* 청산 마커 */}
      {exitIdx >= 0 && (
        <line x1={xScale(exitIdx)} x2={xScale(exitIdx)} y1={padding.top} y2={height - padding.bottom}
          stroke="currentColor" className="text-purple-500" strokeDasharray="3 2" />
      )}

      {/* 날짜 레이블 */}
      <text x={padding.left} y={height - 4} className="text-[8px] fill-gray-400">{points[0].date.slice(5)}</text>
      <text x={width - padding.right} y={height - 4} textAnchor="end" className="text-[8px] fill-gray-400">{points[points.length - 1].date.slice(5)}</text>
    </svg>
  )
}

// ═══════════════════════════════════════════════════════════
// Flow Win Rate Section
// ═══════════════════════════════════════════════════════════

function FlowWinRateSection({ startDate, endDate }: { startDate?: string; endDate?: string }) {
  const [data, setData] = useState<FlowWinRateResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    analysisApi.getFlowWinRate(startDate, endDate).then(setData).catch(() => setData(null)).finally(() => setLoading(false))
  }, [startDate, endDate])

  if (loading) return <LoadingSkeleton />
  if (!data || data.total_trades === 0) return <EmptyState message="매매 데이터가 없습니다." />

  const quadrantColors: Record<string, string> = {
    '쌍끌이 매수': 'border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10',
    '외인 주도': 'border-orange-200 dark:border-orange-800 bg-orange-50/50 dark:bg-orange-900/10',
    '기관 주도': 'border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/10',
    '수급 역행': 'border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/30',
  }

  return (
    <div className="space-y-4">
      {/* 인사이트 */}
      {data.insight && (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
          {data.insight}
        </div>
      )}

      {/* 4분면 그리드 */}
      <div className="grid grid-cols-2 gap-3">
        {data.quadrants.map(q => (
          <div key={q.name} className={`rounded-xl border p-4 ${quadrantColors[q.label] || 'border-gray-200 dark:border-gray-700'}`}>
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="text-xs text-gray-500 dark:text-t-text-muted">{q.name}</div>
                <div className="text-sm font-semibold text-gray-900 dark:text-t-text-primary">{q.label}</div>
              </div>
              <span className="text-xs text-gray-400">{q.trade_count}건</span>
            </div>
            <div className="flex items-baseline gap-3">
              <div>
                <div className="text-xs text-gray-400">승률</div>
                <div className={`text-xl font-bold font-mono ${q.win_rate >= 50 ? 'text-red-500' : 'text-blue-500'}`}>
                  {q.win_rate.toFixed(0)}%
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400">평균수익</div>
                <div className={`text-sm font-mono font-medium ${pnlColor(q.avg_return_pct)}`}>
                  {fmtPct(q.avg_return_pct)}
                </div>
              </div>
            </div>
            {q.trade_count > 0 && (
              <div className="mt-2 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div className="h-full bg-red-400 rounded-full" style={{ width: `${q.win_rate}%` }} />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* 수급 역행 매매 리스트 */}
      {data.contra_trades.length > 0 && (
        <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm">
          <div className="px-4 py-3 border-b border-gray-100 dark:border-t-border">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary">
              수급 역행 매매
              <span className="text-xs text-gray-400 font-normal ml-2">외인+기관 모두 순매도 구간 매수</span>
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100 dark:border-t-border text-gray-500 dark:text-t-text-muted">
                  <th className="px-4 py-1.5 text-left font-medium">종목</th>
                  <th className="px-3 py-1.5 text-right font-medium">진입일</th>
                  <th className="px-3 py-1.5 text-right font-medium">수익률</th>
                  <th className="px-3 py-1.5 text-right font-medium">외인</th>
                  <th className="px-3 py-1.5 text-right font-medium">기관</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-t-border">
                {data.contra_trades.map((ct, i) => (
                  <tr key={i}>
                    <td className="px-4 py-1.5 text-gray-900 dark:text-t-text-primary">{ct.stock_name}</td>
                    <td className="px-3 py-1.5 text-right text-gray-400 font-mono">{ct.entry_date.slice(5)}</td>
                    <td className={`px-3 py-1.5 text-right font-mono font-medium ${pnlColor(ct.return_pct)}`}>
                      {fmtPct(ct.return_pct)}
                    </td>
                    <td className="px-3 py-1.5 text-right text-red-400 font-mono">{fmtAmt(ct.foreign_net)}</td>
                    <td className="px-3 py-1.5 text-right text-blue-400 font-mono">{fmtAmt(ct.institution_net)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 통계 */}
      <div className="text-xs text-gray-400 text-right">
        전체 {data.total_trades}건 중 수급 데이터 확인 {data.flow_available_trades}건
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// Cluster Section
// ═══════════════════════════════════════════════════════════

function ClusterSection({ startDate, endDate }: { startDate?: string; endDate?: string }) {
  const [data, setData] = useState<ClusterResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedCluster, setExpandedCluster] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    analysisApi.getTradeClusters(startDate, endDate).then(setData).catch(() => setData(null)).finally(() => setLoading(false))
  }, [startDate, endDate])

  if (loading) return <LoadingSkeleton />
  if (!data || data.clusters.length === 0) return <EmptyState message="분류 가능한 매매가 없습니다." />

  return (
    <div className="space-y-4">
      {/* Best / Worst 하이라이트 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {data.best_pattern && (
          <PatternHighlight pattern={data.best_pattern} type="best" />
        )}
        {data.worst_pattern && (
          <PatternHighlight pattern={data.worst_pattern} type="worst" />
        )}
      </div>

      {/* 패턴별 카드 */}
      <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm">
        <div className="px-4 py-3 border-b border-gray-100 dark:border-t-border">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary">
            전체 패턴 ({data.clusters.length}개)
            <span className="text-xs text-gray-400 font-normal ml-2">
              {data.total_clustered}/{data.total_positions}건 분류됨
            </span>
          </h3>
        </div>
        <div className="divide-y divide-gray-50 dark:divide-t-border">
          {data.clusters.map(cluster => (
            <div key={cluster.pattern_key}>
              <button
                onClick={() => setExpandedCluster(expandedCluster === cluster.pattern_key ? null : cluster.pattern_key)}
                className="w-full px-4 py-2.5 flex items-center gap-2 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/30 text-left"
              >
                <ConditionBadges conditions={cluster.conditions} />
                <span className="text-xs text-gray-400 ml-auto shrink-0">{cluster.trade_count}건</span>
                <span className={`text-xs font-mono font-medium shrink-0 ${cluster.win_rate >= 50 ? 'text-red-500' : 'text-blue-500'}`}>
                  {cluster.win_rate.toFixed(0)}%
                </span>
                <span className={`text-xs font-mono shrink-0 ${pnlColor(cluster.avg_return_pct)}`}>
                  {fmtPct(cluster.avg_return_pct)}
                </span>
                <svg className={`w-3.5 h-3.5 text-gray-400 transition-transform shrink-0 ${expandedCluster === cluster.pattern_key ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {expandedCluster === cluster.pattern_key && cluster.trades.length > 0 && (
                <div className="px-4 pb-3">
                  <div className="space-y-1">
                    {cluster.trades.map((t, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className="text-gray-700 dark:text-t-text-secondary truncate flex-1">{t.stock_name}</span>
                        <span className="text-gray-400 font-mono">{t.entry_date.slice(5)}</span>
                        <span className="text-gray-400">{t.holding_days}일</span>
                        <span className={`font-mono font-medium ${pnlColor(t.return_pct)}`}>{fmtPct(t.return_pct)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function PatternHighlight({ pattern, type }: { pattern: TradeCluster; type: 'best' | 'worst' }) {
  const isBest = type === 'best'
  return (
    <div className={`rounded-xl border p-4 ${
      isBest
        ? 'border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10'
        : 'border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/10'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
          isBest ? 'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300' : 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300'
        }`}>
          {isBest ? 'BEST' : 'WORST'}
        </span>
        <span className="text-xs text-gray-400">{pattern.trade_count}건</span>
      </div>
      <ConditionBadges conditions={pattern.conditions} />
      <div className="flex items-baseline gap-3 mt-2">
        <div>
          <div className="text-xs text-gray-400">승률</div>
          <div className={`text-lg font-bold font-mono ${pattern.win_rate >= 50 ? 'text-red-500' : 'text-blue-500'}`}>
            {pattern.win_rate.toFixed(0)}%
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-400">평균수익</div>
          <div className={`text-sm font-mono font-medium ${pnlColor(pattern.avg_return_pct)}`}>
            {fmtPct(pattern.avg_return_pct)}
          </div>
        </div>
      </div>
    </div>
  )
}

function ConditionBadges({ conditions }: { conditions: Record<string, string> }) {
  const badgeColors: Record<string, string> = {
    '위': 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    '아래': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    '근접': 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
    '상': 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    '하': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    '중': 'bg-gray-100 text-gray-600 dark:bg-gray-700/50 dark:text-gray-300',
    '고': 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    '저': 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400',
    '보통': 'bg-gray-100 text-gray-600 dark:bg-gray-700/50 dark:text-gray-300',
    '단기': 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
    '중기': 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
    '장기': 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
  }

  const labels: Record<string, string> = {
    ma20: 'MA20',
    bb: 'BB',
    volume: '거래량',
    holding: '보유',
  }

  return (
    <div className="flex flex-wrap gap-1">
      {Object.entries(conditions).map(([key, value]) => (
        <span
          key={key}
          className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${badgeColors[value] || 'bg-gray-100 text-gray-600 dark:bg-gray-700/50 dark:text-gray-300'}`}
        >
          {labels[key] || key} {value}
        </span>
      ))}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// Common Components
// ═══════════════════════════════════════════════════════════

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map(i => (
        <div key={i} className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-6 animate-pulse">
          <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded mb-4" />
          <div className="grid grid-cols-3 gap-3">
            {[1, 2, 3].map(j => (
              <div key={j} className="h-16 bg-gray-100 dark:bg-t-bg-elevated rounded-lg" />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-8 text-center">
      <div className="text-gray-400 dark:text-t-text-muted">{message}</div>
    </div>
  )
}
