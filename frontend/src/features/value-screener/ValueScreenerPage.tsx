import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { valueScreenerApi, ideaApi } from '../../services/api'
import type { ValueScreenerResponse, ValueMetrics } from '../../types/value_screener'
import MiniSparkline from '../../components/MiniSparkline'
import type { SparklineMap } from '../../components/MiniSparkline'
import { WatchlistStar } from '../../components/WatchlistStar'

const GRADE_COLORS: Record<string, string> = {
  A: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  B: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  C: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
  D: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
}

const GRADE_BAR_COLORS: Record<string, string> = {
  A: 'bg-emerald-500',
  B: 'bg-blue-500',
  C: 'bg-yellow-500',
  D: 'bg-red-500',
}

const SORT_OPTIONS = [
  { value: 'total', label: '종합점수' },
  { value: 'upside', label: '괴리율 (높은순)' },
  { value: 'per', label: 'PER (낮은순)' },
  { value: 'pbr', label: 'PBR (낮은순)' },
  { value: 'roe', label: 'ROE (높은순)' },
  { value: 'growth', label: '매출성장률' },
]

function fmt(v: number | null, suffix = ''): string {
  if (v === null || v === undefined) return '-'
  return `${v.toLocaleString(undefined, { maximumFractionDigits: 1 })}${suffix}`
}

function ScoreBar({ score, max = 100, color }: { score: number; max?: number; color: string }) {
  const pct = Math.min((score / max) * 100, 100)
  return (
    <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all ${color}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

function StockCard({ stock, sparkline }: { stock: ValueMetrics; sparkline?: { closes: number[] } }) {
  const prices = sparkline?.closes
  const changePct = prices && prices.length >= 2
    ? ((prices[prices.length - 1] - prices[0]) / prices[0]) * 100
    : null

  return (
    <Link
      to={`/stocks/${stock.stock_code}`}
      className="block bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 hover:shadow-md hover:border-blue-300 dark:hover:border-blue-600 transition-all"
    >
      {/* Header + Sparkline */}
      <div className="flex items-start justify-between mb-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <WatchlistStar stockCode={stock.stock_code} stockName={stock.stock_name} />
            <span className="font-semibold text-gray-900 dark:text-gray-100 truncate">
              {stock.stock_name}
            </span>
            <span className={`px-1.5 py-0.5 rounded text-xs font-bold flex-shrink-0 ${GRADE_COLORS[stock.grade]}`}>
              {stock.grade}
            </span>
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {stock.stock_code}
            {stock.current_price != null && stock.current_price > 0 && (
              <span className="ml-1.5 font-medium text-gray-700 dark:text-gray-200">
                {stock.current_price?.toLocaleString()}원
              </span>
            )}
            {stock.sector && <span className="ml-1">| {stock.sector}</span>}
          </div>
        </div>
        {/* Mini Chart */}
        {prices && prices.length >= 2 && (
          <div className="flex flex-col items-end flex-shrink-0 ml-2">
            <MiniSparkline prices={prices} width={64} height={24} />
            <span className={`text-[10px] font-medium ${changePct !== null && changePct >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
              {changePct !== null ? `${changePct >= 0 ? '+' : ''}${changePct.toFixed(1)}%` : ''}
            </span>
          </div>
        )}
      </div>

      {/* Comment */}
      {stock.comment && (
        <div className="mb-2.5 px-2 py-1.5 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/40 rounded text-xs text-amber-800 dark:text-amber-300 leading-relaxed">
          {stock.comment}
        </div>
      )}

      {/* Fair Value */}
      {stock.fair_value != null && stock.current_price != null && (
        <div className={`mb-2.5 px-2.5 py-2 rounded border text-xs ${
          stock.upside_pct != null && stock.upside_pct > 0
            ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800/40'
            : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800/40'
        }`}>
          <div className="flex items-center justify-between">
            <span className="text-gray-600 dark:text-gray-400">적정가치</span>
            <span className="font-bold text-gray-900 dark:text-gray-100">
              {stock.fair_value?.toLocaleString()}원
            </span>
          </div>
          <div className="flex items-center justify-between mt-0.5">
            <span className="text-gray-500 dark:text-gray-500 text-[10px]">
              {stock.valuation_method}
            </span>
            <span className={`font-bold ${
              stock.upside_pct != null && stock.upside_pct > 0
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-red-500 dark:text-red-400'
            }`}>
              {stock.upside_pct != null && stock.upside_pct > 0 ? '+' : ''}
              {stock.upside_pct?.toFixed(1)}% {stock.upside_pct != null && stock.upside_pct > 0 ? '저평가' : '고평가'}
            </span>
          </div>
        </div>
      )}

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm mb-3">
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">PER</span>
          <span className={`font-medium ${stock.per !== null && stock.per > 0 && stock.per <= 12 ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-700 dark:text-gray-300'}`}>
            {fmt(stock.per, 'x')}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">PBR</span>
          <span className={`font-medium ${stock.pbr !== null && stock.pbr < 1 ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-700 dark:text-gray-300'}`}>
            {fmt(stock.pbr, 'x')}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">ROE</span>
          <span className={`font-medium ${stock.roe !== null && stock.roe >= 10 ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-700 dark:text-gray-300'}`}>
            {fmt(stock.roe, '%')}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">영익률</span>
          <span className={`font-medium ${stock.operating_margin !== null && stock.operating_margin >= 10 ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-700 dark:text-gray-300'}`}>
            {fmt(stock.operating_margin, '%')}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">성장률</span>
          <span className={`font-medium ${stock.revenue_growth !== null && stock.revenue_growth > 0 ? 'text-emerald-600 dark:text-emerald-400' : stock.revenue_growth !== null && stock.revenue_growth < 0 ? 'text-red-500' : 'text-gray-700 dark:text-gray-300'}`}>
            {stock.revenue_growth !== null && stock.revenue_growth > 0 ? '+' : ''}{fmt(stock.revenue_growth, '%')}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500 dark:text-gray-400">부채</span>
          <span className={`font-medium ${stock.debt_ratio !== null && stock.debt_ratio < 100 ? 'text-emerald-600 dark:text-emerald-400' : stock.debt_ratio !== null && stock.debt_ratio >= 200 ? 'text-red-500' : 'text-gray-700 dark:text-gray-300'}`}>
            {fmt(stock.debt_ratio, '%')}
          </span>
        </div>
      </div>

      {/* Score */}
      <div className="border-t border-gray-100 dark:border-gray-700 pt-2">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-500 dark:text-gray-400">점수</span>
          <span className="text-sm font-bold text-gray-900 dark:text-gray-100">
            {stock.total_score}/100
          </span>
        </div>
        <ScoreBar score={stock.total_score} color={GRADE_BAR_COLORS[stock.grade]} />
      </div>

      {stock.bsns_year && (
        <div className="text-[10px] text-gray-400 dark:text-gray-500 mt-2 text-right">
          {stock.bsns_year}년 {stock.reprt_code || ''} 기준
        </div>
      )}
    </Link>
  )
}

export default function ValueScreenerPage() {
  const [data, setData] = useState<ValueScreenerResponse | null>(null)
  const [sparklines, setSparklines] = useState<SparklineMap>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [minScore, setMinScore] = useState(0)
  const [sortBy, setSortBy] = useState('total')
  const [gradeFilter, setGradeFilter] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    valueScreenerApi.scan({ min_score: minScore, limit: 200, sort_by: sortBy })
      .then(res => {
        if (cancelled) return
        setData(res)
        // 스파크라인 데이터 비동기 로드
        const codes = res.stocks.map(s => s.stock_code)
        if (codes.length > 0) {
          ideaApi.getStockSparklines(60, codes)
            .then(sp => { if (!cancelled) setSparklines(sp) })
            .catch(() => {})
        }
      })
      .catch(err => { if (!cancelled) setError(err.message || 'API 오류') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [minScore, sortBy])

  const filtered = useMemo(() => {
    if (!data) return []
    if (!gradeFilter) return data.stocks
    return data.stocks.filter(s => s.grade === gradeFilter)
  }, [data, gradeFilter])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        <span className="ml-3 text-gray-500 dark:text-gray-400">재무 데이터 분석 중...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 text-center text-red-500">
        <p>오류: {error}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          재시도
        </button>
      </div>
    )
  }

  if (!data) return null

  const { summary } = data

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
            재무 저평가 스크리너
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            PER/PBR/ROE/영익률/성장률/안전성 기반 종합 스코어링
          </p>
        </div>
        <div className="text-xs text-gray-400 dark:text-gray-500">
          {data.generated_at && new Date(data.generated_at).toLocaleString('ko-KR')}
        </div>
      </div>

      {/* Summary Bar */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex flex-wrap gap-4 items-center">
          {(['A', 'B', 'C', 'D'] as const).map(g => (
            <button
              key={g}
              onClick={() => setGradeFilter(gradeFilter === g ? null : g)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                gradeFilter === g
                  ? GRADE_COLORS[g] + ' ring-2 ring-offset-1 ring-blue-400'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              <span className="font-bold">{g}</span>
              <span>{summary.grade_counts[g] || 0}개</span>
            </button>
          ))}
          <div className="hidden sm:block h-6 w-px bg-gray-300 dark:bg-gray-600" />
          <div className="flex gap-4 text-sm text-gray-600 dark:text-gray-300">
            {summary.avg_per !== null && (
              <span>평균 PER <strong>{summary.avg_per}</strong></span>
            )}
            {summary.avg_pbr !== null && (
              <span>평균 PBR <strong>{summary.avg_pbr}</strong></span>
            )}
            {summary.avg_roe !== null && (
              <span>평균 ROE <strong>{summary.avg_roe}%</strong></span>
            )}
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600 dark:text-gray-400">최소 점수:</label>
          <input
            type="range"
            min={0}
            max={80}
            step={5}
            value={minScore}
            onChange={e => setMinScore(Number(e.target.value))}
            className="w-32"
          />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300 w-8">
            {minScore}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600 dark:text-gray-400">정렬:</label>
          <select
            value={sortBy}
            onChange={e => setSortBy(e.target.value)}
            className="text-sm border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300"
          >
            {SORT_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        <span className="text-sm text-gray-500 dark:text-gray-400 ml-auto">
          {filtered.length}개 종목
        </span>
      </div>

      {/* Cards Grid */}
      {filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
          조건에 맞는 종목이 없습니다
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {filtered.map(stock => (
            <StockCard
              key={stock.stock_code}
              stock={stock}
              sparkline={sparklines[stock.stock_code]}
            />
          ))}
        </div>
      )}
    </div>
  )
}
