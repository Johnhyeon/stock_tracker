import { Fragment, useState, useEffect, useCallback, useMemo } from 'react'
import { signalScannerApi, type ScannerSignal, type ScannerDetailResponse, type ChecklistItem, type ScannerAIAdvice, type ProvenPattern } from '../../services/api'
import { StockChart } from '../../components/StockChart'
import { WatchlistStar } from '../../components/WatchlistStar'
import { useWatchlist } from '../../hooks/useWatchlist'

// ── 실전 패턴 매칭 유틸 ──

function classifySignal(signal: ScannerSignal): { ma20: string; bb: string; volume: string } {
  const ma20 = signal.ma20_distance_pct != null
    ? (signal.ma20_distance_pct > 3 ? '위' : signal.ma20_distance_pct < -3 ? '아래' : '근접')
    : '근접'
  const bb = signal.bb_position != null
    ? (signal.bb_position > 0.67 ? '상' : signal.bb_position < 0.33 ? '하' : '중')
    : '중'
  const volume = signal.volume_ratio != null
    ? (signal.volume_ratio > 2 ? '고' : signal.volume_ratio < 0.5 ? '저' : '보통')
    : '보통'
  return { ma20, bb, volume }
}

function getMatchingPatterns(signal: ScannerSignal, patterns: ProvenPattern[]): ProvenPattern[] {
  const cls = classifySignal(signal)
  return patterns.filter(p => {
    const c = p.conditions
    if (c.ma20 && c.ma20 !== cls.ma20) return false
    if (c.bb && c.bb !== cls.bb) return false
    if (c.volume && c.volume !== cls.volume) return false
    return true
  })
}

const GRADE_COLORS: Record<string, string> = {
  A: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400',
  B: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400',
  C: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400',
  D: 'bg-gray-100 text-gray-600 dark:bg-gray-700/40 dark:text-gray-400',
}

const PHASE_COLORS: Record<string, string> = {
  A: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400',
  B: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400',
  C: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400',
  D: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400',
  unknown: 'bg-gray-100 text-gray-500 dark:bg-gray-700/40 dark:text-gray-400',
}

const MA_LABELS: Record<string, { text: string; cls: string }> = {
  bullish: { text: '정배열', cls: 'text-green-600 dark:text-green-400' },
  bearish: { text: '역배열', cls: 'text-red-600 dark:text-red-400' },
  mixed: { text: '혼조', cls: 'text-gray-500 dark:text-t-text-muted' },
}

const GAP_LABELS: Record<string, string> = {
  breakaway: '돌파갭',
  runaway: '진행갭',
  exhaustion: '소멸갭',
  common: '보통갭',
  none: '-',
}

function formatPrice(v: number | null | undefined): string {
  if (v == null) return '-'
  return v.toLocaleString()
}

function ScoreBar({ score, max = 100 }: { score: number; max?: number }) {
  const pct = Math.min(100, Math.max(0, (score / max) * 100))
  const color =
    pct >= 80 ? 'bg-green-500' :
    pct >= 60 ? 'bg-blue-500' :
    pct >= 40 ? 'bg-yellow-500' :
    'bg-gray-400'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium w-8 text-right">{score.toFixed(0)}</span>
    </div>
  )
}

function PhaseIndicator({ phase }: { phase: string }) {
  const phases = ['A', 'B', 'C', 'D']
  const currentIdx = phases.indexOf(phase)
  return (
    <div className="flex items-center gap-0.5">
      {phases.map((p, i) => {
        const isActive = p === phase
        const isPast = i < currentIdx
        return (
          <Fragment key={p}>
            <div className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
              isActive ? PHASE_COLORS[p] :
              isPast ? 'bg-gray-200 text-gray-500 dark:bg-gray-600 dark:text-gray-300' :
              'bg-gray-100 text-gray-400 dark:bg-gray-700 dark:text-gray-500'
            }`}>
              {p}
            </div>
            {i < 3 && (
              <svg className={`w-2.5 h-2.5 ${isPast || isActive ? 'text-gray-400' : 'text-gray-300 dark:text-gray-600'}`} fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
              </svg>
            )}
          </Fragment>
        )
      })}
    </div>
  )
}

function ChecklistPanel({ checklist }: { checklist: ChecklistItem[] }) {
  const total = checklist.reduce((s, c) => s + c.score, 0)
  const maxTotal = checklist.reduce((s, c) => s + c.max_score, 0)

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-xs font-semibold text-gray-700 dark:text-t-text-secondary">매매 체크리스트</h4>
        <span className="text-xs font-bold text-gray-600 dark:text-t-text-muted">{total.toFixed(0)}/{maxTotal}</span>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {checklist.map(item => (
          <div key={item.name} className={`p-2 rounded-lg border ${
            item.passed
              ? 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800/40'
              : 'bg-gray-50 dark:bg-t-bg border-gray-200 dark:border-t-border'
          }`}>
            <div className="flex items-center justify-between mb-0.5">
              <span className="text-xs font-medium text-gray-700 dark:text-t-text-secondary">
                {item.passed ? '✓' : '✗'} {item.label}
              </span>
              <span className="text-[10px] text-gray-500 dark:text-t-text-muted">
                {item.score.toFixed(0)}/{item.max_score}
              </span>
            </div>
            <p className="text-[10px] text-gray-500 dark:text-t-text-muted leading-tight line-clamp-2">
              {item.detail}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

// AI 분석 결과 캐시 (페이지 이동 후 복귀 시에도 유지)
const aiAdviceCache = new Map<string, ScannerAIAdvice>()

function AIAdvicePanel({ stockCode }: { stockCode: string }) {
  const [advice, setAdvice] = useState<ScannerAIAdvice | null>(() => aiAdviceCache.get(stockCode) ?? null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchAdvice = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await signalScannerApi.getAIAdvice(stockCode)
      setAdvice(result.advice)
      aiAdviceCache.set(stockCode, result.advice)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'AI 분석 실패'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  if (!advice && !loading) {
    return (
      <div className="mt-3">
        <button
          onClick={fetchAdvice}
          disabled={loading}
          className="w-full py-2 px-3 text-sm font-medium bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-700/40 rounded-lg hover:bg-indigo-100 dark:hover:bg-indigo-900/30 transition-colors disabled:opacity-50"
        >
          AI 분석 요청
        </button>
        {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
      </div>
    )
  }

  if (loading) {
    return (
      <div className="mt-3 text-center py-4 text-sm text-gray-400 dark:text-t-text-muted">
        AI 분석 중...
      </div>
    )
  }

  if (!advice) return null

  const recColors: Record<string, string> = {
    '적극매수': 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    '매수대기': 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    '관망': 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300',
    '매도검토': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  }

  return (
    <div className="mt-3 p-3 bg-indigo-50/50 dark:bg-indigo-900/10 rounded-lg border border-indigo-200/50 dark:border-indigo-800/30">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-xs font-semibold text-indigo-700 dark:text-indigo-400">AI 시그널 분석</h4>
        <div className="flex items-center gap-1.5">
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${recColors[advice.entry_recommendation] || recColors['관망']}`}>
            {advice.entry_recommendation}
          </span>
          <span className="text-[10px] text-gray-500 dark:text-t-text-muted">
            신뢰도 {(advice.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>
      <p className="text-xs text-gray-700 dark:text-t-text-secondary mb-2">{advice.phase_description}</p>
      {advice.key_observations.length > 0 && (
        <div className="mb-2">
          <div className="text-[10px] font-medium text-gray-500 dark:text-t-text-muted mb-0.5">핵심 관찰</div>
          <ul className="text-xs text-gray-600 dark:text-t-text-muted space-y-0.5">
            {advice.key_observations.map((obs, i) => (
              <li key={i} className="flex gap-1">
                <span className="text-indigo-400 shrink-0">-</span>
                <span>{obs}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <div className="text-[10px] font-medium text-green-600 dark:text-green-400 mb-0.5">진입 조건</div>
          {advice.entry_conditions.map((c, i) => (
            <div key={i} className="text-gray-600 dark:text-t-text-muted">- {c}</div>
          ))}
        </div>
        <div>
          <div className="text-[10px] font-medium text-red-600 dark:text-red-400 mb-0.5">청산 조건</div>
          {advice.exit_conditions.map((c, i) => (
            <div key={i} className="text-gray-600 dark:text-t-text-muted">- {c}</div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ExpandedRow({ stockCode, stockName }: { stockCode: string; stockName: string }) {
  const [detail, setDetail] = useState<ScannerDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    signalScannerApi.getDetail(stockCode).then(d => {
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
        <td colSpan={10} className="py-6 text-center text-gray-400 dark:text-t-text-muted text-sm">
          상세 데이터 로딩 중...
        </td>
      </tr>
    )
  }

  if (!detail) {
    return (
      <tr>
        <td colSpan={10} className="py-4 text-center text-gray-400 dark:text-t-text-muted text-sm">
          데이터를 불러올 수 없습니다
        </td>
      </tr>
    )
  }

  return (
    <tr>
      <td colSpan={10} className="p-0">
        <div className="bg-gray-50 dark:bg-t-bg border-t border-b dark:border-t-border px-4 py-3">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* 왼쪽: 차트 */}
            <div className="chart-grid-cell">
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
              />
            </div>
            {/* 오른쪽: 체크리스트 + AI */}
            <div className="space-y-3">
              <ChecklistPanel checklist={detail.checklist} />
              <AIAdvicePanel stockCode={stockCode} />
            </div>
          </div>
        </div>
      </td>
    </tr>
  )
}

const PAGE_SIZE = 50

export default function SignalScannerPage() {
  const [signals, setSignals] = useState<ScannerSignal[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedCode, setExpandedCode] = useState<string | null>(null)
  const [minScore, setMinScore] = useState(0)
  const [showCount, setShowCount] = useState(PAGE_SIZE)
  const [watchlistFilter, setWatchlistFilter] = useState(false)
  const [provenFilter, setProvenFilter] = useState(false)
  const [provenPatterns, setProvenPatterns] = useState<ProvenPattern[]>([])
  const [selectedPatternIdx, setSelectedPatternIdx] = useState<number | null>(null)
  const { isWatched } = useWatchlist()

  const fetchSignals = useCallback(async () => {
    setLoading(true)
    setExpandedCode(null)
    setShowCount(PAGE_SIZE)
    try {
      const data = await signalScannerApi.getSignals({ min_score: minScore })
      setSignals(data.signals ?? [])
    } catch (err) {
      console.error('시그널 스캐너 로드 실패:', err)
      setSignals([])
    } finally {
      setLoading(false)
    }
  }, [minScore])

  useEffect(() => {
    fetchSignals()
  }, [fetchSignals])

  // 실전 패턴 로드
  useEffect(() => {
    signalScannerApi.getProvenPatterns()
      .then(d => setProvenPatterns(d.patterns ?? []))
      .catch(() => setProvenPatterns([]))
  }, [])

  // 시그널별 매칭 패턴 캐시
  const signalPatternMap = useMemo(() => {
    if (provenPatterns.length === 0) return new Map<string, ProvenPattern[]>()
    const map = new Map<string, ProvenPattern[]>()
    for (const s of signals) {
      const matches = getMatchingPatterns(s, provenPatterns)
      if (matches.length > 0) map.set(s.stock_code, matches)
    }
    return map
  }, [signals, provenPatterns])

  // 선택된 패턴에 매칭되는 종목 코드 셋
  const selectedPatternStocks = useMemo(() => {
    if (selectedPatternIdx === null || !provenPatterns[selectedPatternIdx]) return null
    const p = provenPatterns[selectedPatternIdx]
    const codes = new Set<string>()
    for (const s of signals) {
      const cls = classifySignal(s)
      const c = p.conditions
      if ((!c.ma20 || c.ma20 === cls.ma20) && (!c.bb || c.bb === cls.bb) && (!c.volume || c.volume === cls.volume)) {
        codes.add(s.stock_code)
      }
    }
    return codes
  }, [selectedPatternIdx, provenPatterns, signals])

  const filteredSignals = useMemo(() => {
    let result = signals
    if (watchlistFilter) result = result.filter(s => isWatched(s.stock_code))
    if (selectedPatternStocks) {
      result = result.filter(s => selectedPatternStocks.has(s.stock_code))
    } else if (provenFilter) {
      result = result.filter(s => signalPatternMap.has(s.stock_code))
    }
    return result
  }, [signals, watchlistFilter, provenFilter, isWatched, signalPatternMap, selectedPatternStocks])

  // 키보드: Ctrl+화살표로 행 이동
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
        e.preventDefault()
        setExpandedCode(prev => {
          const codes = filteredSignals.map(s => s.stock_code)
          if (codes.length === 0) return prev
          const curIdx = prev ? codes.indexOf(prev) : -1
          let nextIdx: number
          if (e.key === 'ArrowDown') {
            nextIdx = curIdx < codes.length - 1 ? curIdx + 1 : 0
          } else {
            nextIdx = curIdx > 0 ? curIdx - 1 : codes.length - 1
          }
          setTimeout(() => {
            const el = document.getElementById(`ss-row-${codes[nextIdx]}`)
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
  }, [filteredSignals])

  const toggleRow = (code: string) => {
    setExpandedCode(prev => prev === code ? null : code)
  }

  // 통계
  const phaseStats = filteredSignals.reduce((acc, s) => {
    acc[s.abcd_phase] = (acc[s.abcd_phase] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-t-text-primary">시그널스캐너 매매 어드바이저</h2>
          <p className="text-sm text-gray-500 dark:text-t-text-muted">
            ABCD 매매법 + 갭 + 깬돌지 + 이평선 배열 기반 규칙 엔진
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setWatchlistFilter(prev => !prev)}
            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
              watchlistFilter
                ? 'bg-yellow-500 text-white dark:bg-yellow-600'
                : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            &#9733; 관심종목
          </button>
          <button
            onClick={() => {
              setProvenFilter(prev => !prev)
              setSelectedPatternIdx(null)
            }}
            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
              provenFilter || selectedPatternIdx !== null
                ? 'bg-emerald-500 text-white dark:bg-emerald-600'
                : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
            title="매매 복기에서 검증된 높은 승률 패턴과 매칭되는 종목만 필터"
          >
            실전 패턴{provenPatterns.length > 0 && ` (${provenPatterns.length})`}
          </button>
          <select
            value={minScore}
            onChange={e => setMinScore(Number(e.target.value))}
            className="text-sm border border-gray-300 dark:border-t-border rounded-lg px-2 py-1.5 bg-white dark:bg-t-bg-card text-gray-700 dark:text-t-text-primary"
          >
            <option value={0}>전체</option>
            <option value={40}>40점+</option>
            <option value={60}>60점+</option>
            <option value={80}>80점+</option>
          </select>
          <button
            onClick={fetchSignals}
            disabled={loading}
            className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-t-bg-elevated hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg disabled:opacity-50 text-gray-700 dark:text-t-text-primary"
          >
            새로고침
          </button>
        </div>
      </div>

      {/* ABCD 구간 통계 */}
      {filteredSignals.length > 0 && (
        <div className="flex gap-2">
          {['A', 'B', 'C', 'D'].map(phase => (
            <div key={phase} className={`px-3 py-1.5 rounded-lg text-sm ${PHASE_COLORS[phase]}`}>
              <span className="font-bold">{phase}</span>
              <span className="ml-1.5 text-xs opacity-75">{phaseStats[phase] || 0}종목</span>
            </div>
          ))}
          <div className="px-3 py-1.5 rounded-lg text-sm bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted">
            총 <span className="font-bold">{filteredSignals.length}</span>종목
          </div>
        </div>
      )}

      {/* 실전 검증 패턴 카드 */}
      {(provenFilter || selectedPatternIdx !== null) && provenPatterns.length > 0 && (
        <div className="bg-white dark:bg-t-bg-card rounded-lg shadow p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-t-text-secondary">
              검증된 패턴 ({provenPatterns.length}개)
            </h3>
            {selectedPatternIdx !== null && (
              <button
                onClick={() => setSelectedPatternIdx(null)}
                className="text-xs text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary"
              >
                선택 해제
              </button>
            )}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2">
            {provenPatterns.map((p, i) => {
              const condLabels: Record<string, string> = { ma20: 'MA20', bb: 'BB', volume: '거래량' }
              const isSelected = selectedPatternIdx === i
              // 해당 패턴 매칭 종목 수
              const matchCount = signals.filter(s => {
                const cls = classifySignal(s)
                const c = p.conditions
                return (!c.ma20 || c.ma20 === cls.ma20) && (!c.bb || c.bb === cls.bb) && (!c.volume || c.volume === cls.volume)
              }).length
              return (
                <div
                  key={i}
                  onClick={() => setSelectedPatternIdx(prev => prev === i ? null : i)}
                  className={`p-2.5 rounded-lg border cursor-pointer transition-all ${
                    isSelected
                      ? 'border-emerald-500 dark:border-emerald-400 bg-emerald-100 dark:bg-emerald-900/30 ring-2 ring-emerald-500/30'
                      : 'border-emerald-200 dark:border-emerald-800/40 bg-emerald-50/50 dark:bg-emerald-900/10 hover:border-emerald-300 dark:hover:border-emerald-700'
                  }`}
                >
                  <div className="flex flex-wrap gap-1 mb-1.5">
                    {Object.entries(p.conditions).map(([k, v]) => (
                      <span key={k} className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-800/30 text-emerald-700 dark:text-emerald-400 font-medium">
                        {condLabels[k] || k}:{v}
                      </span>
                    ))}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                      {p.win_rate.toFixed(1)}%
                    </span>
                    <span className="text-[10px] text-gray-500 dark:text-t-text-muted">
                      {p.avg_return_pct >= 0 ? '+' : ''}{p.avg_return_pct.toFixed(1)}% / {p.trade_count}건
                    </span>
                  </div>
                  <div className="mt-1 text-[10px] text-gray-400 dark:text-t-text-muted">
                    현재 매칭 <span className="font-bold text-gray-600 dark:text-t-text-secondary">{matchCount}</span>종목
                  </div>
                </div>
              )
            })}
          </div>
          {selectedPatternIdx !== null && (
            <div className="mt-3 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
              선택한 패턴에 매칭되는 {filteredSignals.length}개 종목이 아래에 표시됩니다
            </div>
          )}
        </div>
      )}

      {/* 테이블 */}
      {loading ? (
        <div className="text-center py-16 text-gray-400 dark:text-t-text-muted">로딩 중...</div>
      ) : filteredSignals.length === 0 ? (
        <div className="text-center py-16 text-gray-400 dark:text-t-text-muted">
          {watchlistFilter ? '관심종목 중 시그널이 감지된 종목이 없습니다' : '감지된 시그널이 없습니다'}
        </div>
      ) : (
        <div className="bg-white dark:bg-t-bg-card rounded-lg shadow overflow-hidden">
          <table className="w-full text-sm table-fixed">
            <thead className="bg-gray-50 dark:bg-t-bg">
              <tr>
                <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted w-[15%]">종목</th>
                <th className="text-right py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted w-[10%]">현재가</th>
                <th className="text-center py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted w-[14%]">ABCD</th>
                <th className="text-center py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted w-[8%]">이평선</th>
                <th className="text-center py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted w-[8%]">갭</th>
                <th className="text-center py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted w-[7%]">깬돌지</th>
                <th className="text-right py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted w-[13%]">점수</th>
                <th className="text-center py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted w-[7%]">등급</th>
                <th className="text-center py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted w-[7%]">실전</th>
                <th className="text-left py-3 px-3 font-medium text-gray-600 dark:text-t-text-muted w-[11%]">테마</th>
              </tr>
            </thead>
            <tbody>
              {filteredSignals.slice(0, showCount).map(stock => {
                const isExpanded = expandedCode === stock.stock_code
                return (
                  <Fragment key={stock.stock_code}>
                    <tr
                      id={`ss-row-${stock.stock_code}`}
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
                            <div className="font-medium text-gray-900 dark:text-t-text-primary">
                              {stock.stock_name || stock.stock_code}
                            </div>
                            <div className="text-xs text-gray-500 dark:text-t-text-muted">{stock.stock_code}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-3 text-right font-medium text-gray-900 dark:text-t-text-primary">
                        {formatPrice(stock.current_price)}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <PhaseIndicator phase={stock.abcd_phase} />
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span className={`text-xs font-medium ${MA_LABELS[stock.ma_alignment]?.cls || ''}`}>
                          {MA_LABELS[stock.ma_alignment]?.text || '-'}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-center text-xs text-gray-600 dark:text-t-text-muted">
                        {GAP_LABELS[stock.gap_type] || '-'}
                      </td>
                      <td className="py-3 px-3 text-center">
                        {stock.has_kkandolji ? (
                          <span className="text-green-600 dark:text-green-400 text-xs font-bold">✓</span>
                        ) : (
                          <span className="text-gray-300 dark:text-gray-600">-</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <ScoreBar score={stock.total_score} />
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${GRADE_COLORS[stock.grade] || GRADE_COLORS.D}`}>
                          {stock.grade || '-'}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-center">
                        {(() => {
                          const matches = signalPatternMap.get(stock.stock_code)
                          if (!matches || matches.length === 0) return <span className="text-gray-300 dark:text-gray-600">-</span>
                          const best = matches.reduce((a, b) => a.win_rate > b.win_rate ? a : b)
                          return (
                            <span
                              className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                best.win_rate >= 60
                                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400'
                                  : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400'
                              }`}
                              title={Object.entries(best.conditions).map(([k,v]) => `${k}:${v}`).join(' ')}
                            >
                              {best.win_rate.toFixed(0)}%
                            </span>
                          )
                        })()}
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
                      <ExpandedRow stockCode={stock.stock_code} stockName={stock.stock_name} />
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
          {showCount < filteredSignals.length && (
            <div className="py-3 text-center border-t dark:border-t-border">
              <button
                onClick={() => setShowCount(prev => prev + PAGE_SIZE)}
                className="px-4 py-2 text-sm text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/10 rounded-lg transition-colors"
              >
                더 보기 ({filteredSignals.length - showCount}개 남음)
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
