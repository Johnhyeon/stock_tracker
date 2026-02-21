import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { analysisApi, mentionsApi } from '../../services/api'
import type { DashboardSignals, TrendingMentionItem } from '../../services/api'
import { WatchlistStar } from '../../components/WatchlistStar'
import { useFeatureFlags } from '../../hooks/useFeatureFlags'

interface ConvergedStock {
  stock_code: string
  stock_name: string
  signals: string[]
  signal_count: number
  // 각 시그널 상세
  youtube_count?: number
  expert_count?: number
  telegram_count?: number
  total_mentions?: number
  spike_ratio?: number
  recent_amount?: number
  pattern_type?: string
  pattern_confidence?: number | null
  idea_count?: number
}

const signalColors: Record<string, string> = {
  '유튜브': 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-200',
  '전문가': 'bg-orange-100 text-orange-800 dark:bg-orange-900/50 dark:text-orange-200',
  '텔레그램': 'bg-sky-100 text-sky-800 dark:bg-sky-900/50 dark:text-sky-200',
  '수급급증': 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-200',
  '차트패턴': 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/50 dark:text-indigo-200',
  '투자아이디어': 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200',
}

export default function ConvergenceView() {
  const features = useFeatureFlags()
  const [allStocks, setAllStocks] = useState<ConvergedStock[]>([])
  const [dashSignals, setDashSignals] = useState<DashboardSignals | null>(null)
  const [allMentions, setAllMentions] = useState<TrendingMentionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [daysFilter, setDaysFilter] = useState(7)
  const [minSignals, setMinSignals] = useState(2)

  useEffect(() => {
    loadData()
  }, [daysFilter])

  const loadData = async () => {
    setLoading(true)
    try {
      const [signals, mentions] = await Promise.all([
        analysisApi.getDashboardSignals(),
        mentionsApi.getTrending(daysFilter, 50),
      ])
      setDashSignals(signals)
      setAllMentions(mentions)
      mergeSignals(signals, mentions)
    } catch {
      /* silent */
    } finally {
      setLoading(false)
    }
  }

  const mergeSignals = (signals: DashboardSignals, mentions: TrendingMentionItem[]) => {
    const stockMap = new Map<string, ConvergedStock>()

    const getOrCreate = (code: string, name?: string): ConvergedStock => {
      const existing = stockMap.get(code)
      if (existing) {
        if (name && !existing.stock_name) existing.stock_name = name
        return existing
      }
      const fresh: ConvergedStock = {
        stock_code: code,
        stock_name: name || code,
        signals: [],
        signal_count: 0,
      }
      stockMap.set(code, fresh)
      return fresh
    }

    // 멘션 소스별 개별 시그널로 분리
    for (const m of mentions) {
      if (m.youtube_count && m.youtube_count > 0) {
        const s = getOrCreate(m.stock_code, m.stock_name)
        s.signals.push('유튜브')
        s.youtube_count = m.youtube_count
        s.total_mentions = (s.total_mentions || 0) + m.youtube_count
      }
      if (features.expert && m.expert_count && m.expert_count > 0) {
        const s = getOrCreate(m.stock_code, m.stock_name)
        s.signals.push('전문가')
        s.expert_count = m.expert_count
        s.total_mentions = (s.total_mentions || 0) + m.expert_count
      }
      if (m.telegram_count && m.telegram_count > 0) {
        const s = getOrCreate(m.stock_code, m.stock_name)
        s.signals.push('텔레그램')
        s.telegram_count = m.telegram_count
        s.total_mentions = (s.total_mentions || 0) + m.telegram_count
      }
    }

    // 수급 급증 종목
    for (const spike of signals.flow_spikes) {
      const s = getOrCreate(spike.stock_code)
      s.signals.push('수급급증')
      s.spike_ratio = spike.spike_ratio
      s.recent_amount = spike.recent_amount
    }

    // 차트 패턴 종목
    for (const pattern of signals.chart_patterns) {
      const s = getOrCreate(pattern.stock_code, pattern.stock_name)
      s.signals.push('차트패턴')
      s.pattern_type = pattern.pattern_type
      s.pattern_confidence = pattern.confidence
    }

    // 투자아이디어
    for (const idea of (signals.recent_ideas_stocks || [])) {
      const s = getOrCreate(idea.stock_code, idea.stock_name)
      s.signals.push('투자아이디어')
      s.idea_count = idea.idea_count
    }

    // 시그널 수 계산 및 정렬
    const merged = Array.from(stockMap.values())
      .map(s => ({ ...s, signal_count: s.signals.length }))
      .sort((a, b) => b.signal_count - a.signal_count || (b.total_mentions || 0) - (a.total_mentions || 0))

    setAllStocks(merged)
  }

  const filtered = allStocks.filter(s => s.signal_count >= minSignals)

  const formatAmount = (amount: number) => {
    if (amount >= 1_000_000_000_000) return `${(amount / 1_000_000_000_000).toFixed(1)}조`
    if (amount >= 100_000_000) return `${(amount / 100_000_000).toFixed(0)}억`
    return `${(amount / 10_000).toFixed(0)}만`
  }

  // 시그널 수 분포 통계
  const signalDist = allStocks.reduce((acc, s) => {
    acc[s.signal_count] = (acc[s.signal_count] || 0) + 1
    return acc
  }, {} as Record<number, number>)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 헤더 + 필터 */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-t-text-primary">시그널 수렴 분석</h1>
          <p className="text-sm text-gray-500 dark:text-t-text-muted mt-1">
            유튜브 · 전문가 · 텔레그램 · 수급 · 차트패턴 · 아이디어 시그널이 겹치는 종목
          </p>
        </div>
        <div className="flex gap-4 items-center">
          {/* 기간 필터 */}
          <div className="flex gap-1">
            {[3, 7, 14, 30].map(d => (
              <button
                key={d}
                onClick={() => setDaysFilter(d)}
                className={`px-3 py-1 text-sm rounded-lg ${
                  daysFilter === d
                    ? 'bg-primary-500 text-white'
                    : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-secondary hover:bg-gray-200'
                }`}
              >
                {d}일
              </button>
            ))}
          </div>
          {/* 최소 시그널 필터 */}
          <div className="flex gap-1">
            {[1, 2, 3].map(n => (
              <button
                key={n}
                onClick={() => setMinSignals(n)}
                className={`px-3 py-1 text-sm rounded-lg ${
                  minSignals === n
                    ? 'bg-primary-500 text-white'
                    : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-secondary hover:bg-gray-200'
                }`}
              >
                {n}+시그널
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 시그널 분포 요약 바 */}
      <div className="flex gap-3 flex-wrap">
        {Object.entries(signalDist)
          .sort(([a], [b]) => Number(b) - Number(a))
          .map(([count, stocks]) => (
            <div key={count} className="bg-white dark:bg-t-bg-card rounded-lg shadow px-4 py-2 text-center">
              <div className="text-lg font-bold text-primary-600 dark:text-primary-400">{stocks}</div>
              <div className="text-xs text-gray-500 dark:text-t-text-muted">{count}개 시그널</div>
            </div>
          ))}
        <div className="bg-white dark:bg-t-bg-card rounded-lg shadow px-4 py-2 text-center">
          <div className="text-lg font-bold text-gray-700 dark:text-t-text-secondary">{allStocks.length}</div>
          <div className="text-xs text-gray-500 dark:text-t-text-muted">전체 종목</div>
        </div>
      </div>

      {/* 수렴 종목 카드 */}
      {filtered.length === 0 ? (
        <div className="bg-white dark:bg-t-bg-card rounded-lg shadow p-8 text-center">
          <div className="text-gray-400 text-lg">
            {minSignals}개 이상 시그널 수렴 종목이 없습니다.
          </div>
          <div className="text-sm text-gray-500 mt-2">
            기간을 늘리거나 시그널 기준을 낮춰보세요.
          </div>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map(stock => {
            const borderColor = stock.signal_count >= 3
              ? 'border-red-500'
              : stock.signal_count >= 2
                ? 'border-primary-500'
                : 'border-gray-300 dark:border-gray-600'
            return (
              <Link
                key={stock.stock_code}
                to={`/stocks/${stock.stock_code}`}
                className={`bg-white dark:bg-t-bg-card rounded-lg shadow p-4 hover:shadow-lg transition-shadow border-l-4 ${borderColor}`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-1">
                      <WatchlistStar stockCode={stock.stock_code} stockName={stock.stock_name} />
                      <span className="font-bold text-gray-900 dark:text-t-text-primary">{stock.stock_name}</span>
                    </div>
                    <div className="text-xs text-gray-400">{stock.stock_code}</div>
                  </div>
                  <span className={`text-xs font-bold px-2 py-1 rounded-full ${
                    stock.signal_count >= 3
                      ? 'bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300'
                      : stock.signal_count >= 2
                        ? 'bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
                  }`}>
                    {stock.signal_count}개 시그널
                  </span>
                </div>

                <div className="flex flex-wrap gap-1 mb-3">
                  {stock.signals.map((sig, i) => (
                    <span key={i} className={`text-xs px-2 py-0.5 rounded-full font-medium ${signalColors[sig] || 'bg-gray-100 text-gray-600'}`}>
                      {sig}
                    </span>
                  ))}
                </div>

                <div className="text-xs text-gray-500 dark:text-t-text-muted space-y-1">
                  {(stock.youtube_count || stock.expert_count || stock.telegram_count) && (
                    <div className="flex justify-between">
                      <span>언급</span>
                      <span className="font-medium text-gray-700 dark:text-t-text-secondary">
                        {[
                          stock.youtube_count ? `YT:${stock.youtube_count}` : '',
                          features.expert && stock.expert_count ? `트:${stock.expert_count}` : '',
                          features.telegram && stock.telegram_count ? `TG:${stock.telegram_count}` : '',
                        ].filter(Boolean).join(' · ')}
                      </span>
                    </div>
                  )}
                  {stock.spike_ratio != null && (
                    <div className="flex justify-between">
                      <span>수급 급증</span>
                      <span className="font-medium text-rose-600 dark:text-rose-400">
                        {stock.spike_ratio}x ({formatAmount(stock.recent_amount!)})
                      </span>
                    </div>
                  )}
                  {stock.pattern_type && (
                    <div className="flex justify-between">
                      <span>차트 패턴</span>
                      <span className="font-medium text-indigo-600 dark:text-indigo-400">
                        {stock.pattern_type}
                        {stock.pattern_confidence != null && ` (${(stock.pattern_confidence * 100).toFixed(0)}%)`}
                      </span>
                    </div>
                  )}
                  {stock.idea_count != null && (
                    <div className="flex justify-between">
                      <span>투자아이디어</span>
                      <span className="font-medium text-emerald-600 dark:text-emerald-400">
                        {stock.idea_count}건
                      </span>
                    </div>
                  )}
                </div>
              </Link>
            )
          })}
        </div>
      )}

      {/* 개별 시그널 요약 */}
      {dashSignals && (
        <div className="grid gap-4 md:grid-cols-3">
          <div className="bg-white dark:bg-t-bg-card rounded-lg shadow p-4">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-t-text-secondary mb-2">
              언급 종목 ({allMentions.length}종목)
            </h3>
            <div className="space-y-1">
              {allMentions.slice(0, 8).map(m => (
                <div key={m.stock_code} className="flex justify-between text-xs">
                  <span className="text-gray-600 dark:text-t-text-muted">{m.stock_name}</span>
                  <span className="text-purple-600 dark:text-purple-400 font-medium">
                    {m.source_count}소스 / {m.total_mentions}건
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white dark:bg-t-bg-card rounded-lg shadow p-4">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-t-text-secondary mb-2">
              수급 급증 ({dashSignals.flow_spikes.length}종목)
            </h3>
            <div className="space-y-1">
              {dashSignals.flow_spikes.slice(0, 8).map(s => (
                <div key={s.stock_code} className="flex justify-between text-xs">
                  <span className="text-gray-600 dark:text-t-text-muted">{s.stock_code}</span>
                  <span className="text-rose-600 dark:text-rose-400 font-medium">
                    {s.spike_ratio}x / {formatAmount(s.recent_amount)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white dark:bg-t-bg-card rounded-lg shadow p-4">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-t-text-secondary mb-2">
              차트 패턴 ({dashSignals.chart_patterns.length}종목)
            </h3>
            <div className="space-y-1">
              {dashSignals.chart_patterns.slice(0, 8).map(p => (
                <div key={p.stock_code} className="flex justify-between text-xs">
                  <span className="text-gray-600 dark:text-t-text-muted">{p.stock_name}</span>
                  <span className="text-indigo-600 dark:text-indigo-400 font-medium">{p.pattern_type}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
