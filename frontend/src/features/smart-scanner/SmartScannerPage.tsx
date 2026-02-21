import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { smartScannerApi } from '../../services/api'
import type { SmartScannerStock, SmartScannerResponse } from '../../types/smart_scanner'
import DimensionBar from './DimensionBar'
import Badge from '../../components/ui/Badge'
import { WatchlistStar } from '../../components/WatchlistStar'
import { useRealtimePolling } from '../../hooks/useRealtimePolling'
import { useFeatureFlags } from '../../hooks/useFeatureFlags'

type SortBy = 'composite' | 'chart' | 'narrative' | 'flow' | 'social' | 'aligned'

const SORT_OPTIONS: { value: SortBy; label: string }[] = [
  { value: 'composite', label: '종합' },
  { value: 'chart', label: '차트' },
  { value: 'narrative', label: '내러티브' },
  { value: 'flow', label: '수급' },
  { value: 'social', label: '소셜' },
  { value: 'aligned', label: '정렬 차원' },
]

const gradeConfig: Record<string, { bg: string; text: string; border: string }> = {
  A: {
    bg: 'bg-emerald-50 dark:bg-emerald-900/20',
    text: 'text-emerald-700 dark:text-emerald-400',
    border: 'border-emerald-200 dark:border-emerald-800/50',
  },
  B: {
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    text: 'text-blue-700 dark:text-blue-400',
    border: 'border-blue-200 dark:border-blue-800/50',
  },
  C: {
    bg: 'bg-amber-50 dark:bg-amber-900/20',
    text: 'text-amber-700 dark:text-amber-400',
    border: 'border-amber-200 dark:border-amber-800/50',
  },
  D: {
    bg: 'bg-gray-50 dark:bg-gray-800/50',
    text: 'text-gray-600 dark:text-gray-400',
    border: 'border-gray-200 dark:border-gray-700',
  },
}

const signalLabels: Record<string, string> = {
  pullback: '눌림목',
  high_breakout: '전고점돌파',
  resistance_test: '저항접근',
}

function formatQty(qty: number): string {
  const sign = qty >= 0 ? '+' : ''
  const abs = Math.abs(qty)
  if (abs >= 10000) return `${sign}${(qty / 10000).toFixed(1)}만`
  return `${sign}${qty.toLocaleString()}`
}

export default function SmartScannerPage() {
  const features = useFeatureFlags()
  const [data, setData] = useState<SmartScannerResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [sortBy, setSortBy] = useState<SortBy>('composite')
  const [minScore, setMinScore] = useState(0)
  const [gradeFilter, setGradeFilter] = useState<string | null>(null)
  const [excludeExpert, setExcludeExpert] = useState(false)

  useEffect(() => {
    const fetch = async () => {
      setLoading(true)
      try {
        const result = await smartScannerApi.scan({
          min_score: minScore,
          limit: 200,
          sort_by: sortBy,
          exclude_expert: excludeExpert,
        })
        setData(result)
      } catch (err) {
        console.error('Smart Scanner 로드 실패:', err)
      } finally {
        setLoading(false)
      }
    }
    fetch()
  }, [sortBy, minScore, excludeExpert])

  // silent refetch용 ref (현재 필터 추적)
  const filtersRef = useRef({ sortBy, minScore, excludeExpert })
  useEffect(() => {
    filtersRef.current = { sortBy, minScore, excludeExpert }
  }, [sortBy, minScore, excludeExpert])

  const silentRefetch = useCallback(async () => {
    const f = filtersRef.current
    try {
      const result = await smartScannerApi.scan({
        min_score: f.minScore,
        limit: 200,
        sort_by: f.sortBy,
        exclude_expert: f.excludeExpert,
      })
      setData(result)
    } catch { /* 조용히 실패 */ }
  }, [])

  useRealtimePolling(silentRefetch, 60_000, {
    onlyMarketHours: true,
    enabled: !!data,
  })

  const filteredStocks = useMemo(() => {
    if (!data) return []
    let stocks = data.stocks
    if (gradeFilter) {
      stocks = stocks.filter(s => s.composite_grade === gradeFilter)
    }
    return stocks
  }, [data, gradeFilter])

  // 종목상세 이전/다음 네비게이션용 리스트
  const stockNavList = useMemo(() =>
    filteredStocks.map(s => ({ code: s.stock_code, name: s.stock_name })),
    [filteredStocks]
  )

  const summary = data?.summary || { grade_counts: {}, aligned_3_plus: 0 }

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div>
        <h1 className="text-xl font-bold text-gray-900 dark:text-t-text-primary">
          Smart Scanner
        </h1>
        <p className="text-sm text-gray-500 dark:text-t-text-muted mt-0.5">
          차트 + 내러티브 + 수급 + 소셜 4차원 교차검증
        </p>
      </div>

      {/* 요약 바 */}
      {data && (
        <div className="flex items-center gap-3 flex-wrap">
          {['A', 'B', 'C', 'D'].map(g => {
            const count = summary.grade_counts[g] || 0
            if (count === 0) return null
            const config = gradeConfig[g]
            const isActive = gradeFilter === g
            return (
              <button
                key={g}
                onClick={() => setGradeFilter(isActive ? null : g)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
                  isActive
                    ? `${config.bg} ${config.text} ${config.border} ring-2 ring-offset-1 ring-current`
                    : `${config.bg} ${config.text} ${config.border} hover:opacity-80`
                }`}
              >
                {g}등급 {count}개
              </button>
            )
          })}
          {summary.aligned_3_plus > 0 && (
            <span className="text-xs text-gray-500 dark:text-t-text-muted">
              3차원+ 정렬: {summary.aligned_3_plus}개
            </span>
          )}
          <span className="text-xs text-gray-400 dark:text-t-text-muted ml-auto">
            총 {data.count}개
          </span>
        </div>
      )}

      {/* 필터 바 */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-gray-500 dark:text-t-text-muted">정렬:</label>
          <div className="flex gap-1">
            {SORT_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setSortBy(opt.value)}
                className={`px-2 py-1 text-xs rounded-md transition-colors ${
                  sortBy === opt.value
                    ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 font-medium'
                    : 'text-gray-500 dark:text-t-text-muted hover:bg-gray-100 dark:hover:bg-t-bg-elevated'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <label className="text-xs text-gray-500 dark:text-t-text-muted">최소점수:</label>
          <input
            type="range"
            min={0}
            max={60}
            step={5}
            value={minScore}
            onChange={e => setMinScore(Number(e.target.value))}
            className="w-24 h-1.5 accent-amber-500"
          />
          <span className="text-xs text-gray-600 dark:text-t-text-secondary font-mono w-6">{minScore}</span>
        </div>

        {features.expert && (
        <div className="flex items-center gap-1.5 ml-2">
          <button
            onClick={() => setExcludeExpert(!excludeExpert)}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
              excludeExpert ? 'bg-amber-500' : 'bg-gray-300 dark:bg-gray-600'
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform ${
                excludeExpert ? 'translate-x-[18px]' : 'translate-x-[3px]'
              }`}
            />
          </button>
          <label className="text-xs text-gray-500 dark:text-t-text-muted select-none cursor-pointer" onClick={() => setExcludeExpert(!excludeExpert)}>
            전문가 제외
          </label>
          {excludeExpert && (
            <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">ON</span>
          )}
        </div>
        )}
      </div>

      {/* 로딩 */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
        </div>
      )}

      {/* 종목 카드 그리드 */}
      {!loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {filteredStocks.map((stock, index) => (
            <StockCard key={stock.stock_code} stock={stock} navList={stockNavList} navIndex={index} />
          ))}
        </div>
      )}

      {!loading && filteredStocks.length === 0 && (
        <div className="text-center py-16 text-gray-500 dark:text-t-text-muted">
          조건에 맞는 종목이 없습니다
        </div>
      )}
    </div>
  )
}

function StockCard({ stock, navList, navIndex }: { stock: SmartScannerStock; navList: { code: string; name: string }[]; navIndex: number }) {
  const config = gradeConfig[stock.composite_grade] || gradeConfig.D
  const combined = stock.foreign_net_5d + stock.institution_net_5d

  return (
    <Link
      to={`/stocks/${stock.stock_code}`}
      state={{ stockListContext: { source: 'Smart Scanner', stocks: navList, currentIndex: navIndex } }}
      className={`block p-4 rounded-xl border transition-all hover:shadow-md hover:scale-[1.01] ${config.border} bg-white dark:bg-t-bg-card`}
    >
      {/* 상단: 종목명 + 등급 + 점수 */}
      <div className="flex items-start justify-between mb-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <WatchlistStar stockCode={stock.stock_code} stockName={stock.stock_name} />
            <span className="font-semibold text-gray-900 dark:text-t-text-primary truncate">
              {stock.stock_name}
            </span>
            <span className="text-xs text-gray-400 dark:text-t-text-muted">{stock.stock_code}</span>
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="text-sm text-gray-700 dark:text-t-text-secondary">
              {stock.current_price.toLocaleString()}원
            </span>
            {combined !== 0 && (
              <span className={`text-xs font-medium ${combined > 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                외+기 {formatQty(combined)}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={`text-2xl font-bold ${config.text}`}>
            {stock.composite_grade}
          </span>
          <span className="text-sm font-medium text-gray-600 dark:text-t-text-secondary">
            {stock.composite_score}
          </span>
        </div>
      </div>

      {/* 4차원 바 */}
      <div className="space-y-1 mb-2">
        <DimensionBar label="차트" dimension={stock.chart} />
        <DimensionBar label="내러티브" dimension={stock.narrative} />
        <DimensionBar label="수급" dimension={stock.flow} />
        <DimensionBar label="소셜" dimension={stock.social} />
      </div>

      {/* 하단: 태그 + 정렬 수 */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {stock.signal_type && (
          <Badge variant="default" size="sm">{signalLabels[stock.signal_type] || stock.signal_type}</Badge>
        )}
        {stock.themes.slice(0, 2).map(t => (
          <Badge key={t} variant="info" size="sm">{t}</Badge>
        ))}
        {stock.aligned_count >= 3 && (
          <Badge variant="success" size="sm">{stock.aligned_count}/4 정렬</Badge>
        )}
        {stock.consecutive_foreign_buy >= 3 && (
          <Badge variant="danger" size="sm">외인 {stock.consecutive_foreign_buy}일</Badge>
        )}
      </div>
    </Link>
  )
}
