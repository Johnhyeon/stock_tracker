import { useEffect, useState, useMemo, lazy, Suspense, useCallback, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useIdeaStore } from '../../store/useIdeaStore'
import { ideaApi, positionApi } from '../../services/api'
import MiniSparkline, { type SparklineMap, getSparklineSinceDate } from '../../components/MiniSparkline'
import { IdeaListSkeleton } from '../../components/SkeletonLoader'
import { useRealtimePolling } from '../../hooks/useRealtimePolling'
import { useFeatureFlags } from '../../hooks/useFeatureFlags'
import AddBuyModal from './modals/AddBuyModal'
import AddPositionModal from './modals/AddPositionModal'
import ExitPositionModal from './modals/ExitPositionModal'
import PartialExitModal from './modals/PartialExitModal'
import type {
  Idea,
  IdeaSummary,
  Position,
  PositionCreate,
  PositionAddBuy,
  PositionExit,
  PositionPartialExit,
} from '../../types/idea'

// Lazy load tab content
const TelegramIdeaList = lazy(() => import('./TelegramIdeaList'))
const IdeaAnalytics = lazy(() => import('./views/IdeaAnalytics'))

type TabType = 'portfolio' | 'telegram' | 'analytics'
type TradeAction = 'buy' | 'exit' | 'partial-exit'

const TAB_CONFIG: { key: TabType; label: string; iconPath: string }[] = [
  {
    key: 'portfolio',
    label: '포트폴리오',
    iconPath: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  },
  {
    key: 'telegram',
    label: '텔레그램',
    iconPath: 'M12 19l9 2-9-18-9 18 9-2zm0 0v-8',
  },
  {
    key: 'analytics',
    label: '분석',
    iconPath: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  },
]

// ─── Utilities ───

function formatMoney(amount: number): string {
  if (amount === 0) return '0'
  const abs = Math.abs(amount)
  const sign = amount < 0 ? '-' : ''
  if (abs >= 100_000_000) return `${sign}${(abs / 100_000_000).toFixed(1)}억`
  if (abs >= 10_000) return `${sign}${Math.round(abs / 10_000).toLocaleString()}만`
  return `${sign}${abs.toLocaleString()}`
}

function daysAgo(dateString: string): string {
  const diff = Math.floor((Date.now() - new Date(dateString).getTime()) / 86_400_000)
  if (diff === 0) return '오늘'
  if (diff === 1) return '어제'
  if (diff < 7) return `${diff}일 전`
  return new Date(dateString).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })
}

/** "삼성전자(005930)" → "005930" */
function extractStockCode(ticker: string): string | null {
  const match = ticker.match(/\(([A-Za-z0-9]{6})\)$/)
  return match ? match[1] : null
}

/** 아이디어 종목별 가격 추이 바 (행 하단에 표시) */
function StockTrendBar({
  idea,
  sparklineMap,
}: {
  idea: { tickers: string[]; created_at: string }
  sparklineMap: SparklineMap
}) {
  const items = idea.tickers
    .map((t) => {
      const code = extractStockCode(t)
      if (!code) return null
      const sp = sparklineMap[code]
      if (!sp) return null
      const data = getSparklineSinceDate(sp, idea.created_at)
      if (!data) return null
      const name = sp.name || code
      return { code, name, ...data }
    })
    .filter(Boolean) as { code: string; name: string; prices: number[]; changePct: number }[]

  if (items.length === 0) return null

  return (
    <div className="flex items-center gap-3 px-4 pb-2 -mt-1">
      {items.map((item) => {
        const up = item.changePct >= 0
        return (
          <div key={item.code} className="flex items-center gap-1.5">
            <span className="text-[10px] text-gray-400 dark:text-t-text-muted">{item.name}</span>
            <MiniSparkline prices={item.prices} width={48} height={18} />
            <span
              className={`text-[10px] font-mono font-bold ${
                up ? 'text-red-500' : 'text-blue-500'
              }`}
            >
              {up ? '+' : ''}
              {item.changePct.toFixed(1)}%
            </span>
          </div>
        )
      })}
      <span className="text-[9px] text-gray-300 dark:text-t-text-muted ml-auto">등록 이후</span>
    </div>
  )
}

const HEALTH: Record<string, { dot: string; label: string; badge: string }> = {
  healthy: {
    dot: 'bg-emerald-500',
    label: '건강',
    badge: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400',
  },
  deteriorating: {
    dot: 'bg-amber-500',
    label: '악화',
    badge: 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400',
  },
  broken: {
    dot: 'bg-red-500',
    label: '손상',
    badge: 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400',
  },
}

// ─── Collapsible Section ───

function Section({
  title,
  count,
  dotColor,
  expanded,
  onToggle,
  header,
  children,
  emptyText,
}: {
  title: string
  count: number
  dotColor: string
  expanded: boolean
  onToggle: () => void
  header?: ReactNode
  children: ReactNode
  emptyText?: string
}) {
  return (
    <div>
      <button onClick={onToggle} className="w-full flex items-center justify-between py-2 px-1">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${dotColor}`} />
          <span className="text-sm font-semibold text-gray-700 dark:text-t-text-secondary">
            {title}
          </span>
          <span className="text-[10px] text-gray-400 dark:text-t-text-muted bg-gray-100 dark:bg-t-bg-elevated px-1.5 py-0.5 rounded-full font-mono">
            {count}
          </span>
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 dark:text-t-text-muted transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {expanded && (
        <div className="bg-white dark:bg-t-bg-card rounded-lg border border-gray-200 dark:border-t-border overflow-hidden">
          {header}
          {count === 0 && emptyText ? (
            <div className="text-center py-6 text-sm text-gray-400 dark:text-t-text-muted">
              {emptyText}
            </div>
          ) : (
            children
          )}
        </div>
      )}
    </div>
  )
}

// ─── Column Headers ───

function ActiveHeader() {
  return (
    <div className="flex items-center gap-3 px-4 py-1.5 bg-gray-50/80 dark:bg-t-bg-elevated/20 text-[10px] uppercase tracking-wider text-gray-400 dark:text-t-text-muted border-b border-gray-100 dark:border-t-border">
      <div className="w-2" />
      <div className="flex-1 min-w-0">종목</div>
      <div className="w-20 lg:w-24 text-right">수익률</div>
      <div className="w-14 text-right">잔여</div>
      <div className="w-[72px] text-right">매매</div>
    </div>
  )
}

function WatchingHeader() {
  return (
    <div className="flex items-center gap-3 px-4 py-1.5 bg-gray-50/80 dark:bg-t-bg-elevated/20 text-[10px] uppercase tracking-wider text-gray-400 dark:text-t-text-muted border-b border-gray-100 dark:border-t-border">
      <div className="w-2" />
      <div className="flex-1 min-w-0">종목</div>
      <div className="hidden md:block w-12">건강</div>
      <div className="text-right">목표</div>
      <div className="hidden lg:block w-14 text-right">등록</div>
    </div>
  )
}

// ─── Row: Active Idea (with P&L + trade buttons) ───

function ActiveRow({
  idea,
  onAction,
  sparklineMap,
}: {
  idea: IdeaSummary
  onAction: (idea: IdeaSummary, action: TradeAction) => void
  sparklineMap: SparklineMap
}) {
  const [showSellMenu, setShowSellMenu] = useState(false)
  const openPos = idea.positions.filter((p) => p.is_open)
  const totalQty = openPos.reduce((s, p) => s + p.quantity, 0)
  const pct = idea.total_unrealized_return_pct
  const up = (pct ?? 0) >= 0
  const h = HEALTH[idea.fundamental_health]

  const fire = (e: React.MouseEvent, action: TradeAction) => {
    e.preventDefault()
    e.stopPropagation()
    setShowSellMenu(false)
    onAction(idea, action)
  }

  return (
    <div className="border-b border-gray-50 dark:border-t-border/50 last:border-b-0">
    <Link
      to={`/ideas/${idea.id}`}
      className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 transition-colors"
    >
      {/* Health dot */}
      <div
        className={`w-2 h-2 rounded-full flex-shrink-0 ${h?.dot ?? 'bg-gray-400'}`}
        title={h?.label}
      />

      {/* Ticker + type + qty */}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-gray-900 dark:text-t-text-primary truncate">
          {idea.tickers.join(', ') || '미지정'}
        </div>
        <div className="flex items-center gap-1 mt-0.5">
          <span
            className={`text-[10px] leading-tight px-1 rounded ${
              idea.type === 'research'
                ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                : 'bg-gray-50 dark:bg-t-bg-elevated text-gray-500 dark:text-t-text-muted'
            }`}
          >
            {idea.type === 'research' ? '리서치' : '차트'}
          </span>
          {idea.sector && (
            <span className="text-[10px] text-gray-400 dark:text-t-text-muted truncate">
              {idea.sector}
            </span>
          )}
          {totalQty > 0 && (
            <span className="text-[10px] font-mono text-gray-400 dark:text-t-text-muted">
              {totalQty}주
            </span>
          )}
        </div>
      </div>

      {/* P&L */}
      <div className="w-20 lg:w-24 flex-shrink-0 text-right">
        {pct != null ? (
          <>
            <div className={`text-sm font-bold font-mono ${up ? 'text-red-500' : 'text-blue-500'}`}>
              {up ? '+' : ''}
              {pct.toFixed(1)}%
            </div>
            {(idea.total_invested ?? 0) > 0 && (
              <div className={`text-[10px] font-mono ${up ? 'text-red-400' : 'text-blue-400'}`}>
                {formatMoney(idea.total_invested ?? 0)}
              </div>
            )}
          </>
        ) : (
          <span className="text-xs text-gray-300 dark:text-t-text-muted">-</span>
        )}
      </div>

      {/* Time remaining */}
      <div className="w-14 flex-shrink-0 text-right">
        <span
          className={`text-[11px] font-mono ${
            idea.time_remaining_days <= 0
              ? 'text-red-500 font-bold'
              : idea.time_remaining_days <= 5
                ? 'text-amber-500'
                : 'text-gray-400 dark:text-t-text-muted'
          }`}
        >
          {idea.time_remaining_days <= 0 ? '만료' : `D-${idea.time_remaining_days}`}
        </span>
      </div>

      {/* Trade buttons */}
      <div
        className="w-[72px] flex-shrink-0 flex items-center justify-end gap-1"
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
        }}
      >
        <button
          onClick={(e) => fire(e, 'buy')}
          className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors"
        >
          매수
        </button>
        <div className="relative">
          <button
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              setShowSellMenu(!showSellMenu)
            }}
            className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors"
          >
            매도
          </button>
          {showSellMenu && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  setShowSellMenu(false)
                }}
              />
              <div className="absolute right-0 top-full mt-1 z-20 bg-white dark:bg-t-bg-elevated border border-gray-200 dark:border-t-border rounded-lg shadow-lg overflow-hidden min-w-[80px]">
                <button
                  onClick={(e) => fire(e, 'exit')}
                  className="w-full px-3 py-1.5 text-[11px] text-left text-gray-700 dark:text-t-text-secondary hover:bg-gray-50 dark:hover:bg-t-bg-card transition-colors"
                >
                  전량매도
                </button>
                <button
                  onClick={(e) => fire(e, 'partial-exit')}
                  className="w-full px-3 py-1.5 text-[11px] text-left text-gray-700 dark:text-t-text-secondary hover:bg-gray-50 dark:hover:bg-t-bg-card transition-colors border-t border-gray-100 dark:border-t-border"
                >
                  분할매도
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </Link>
    <StockTrendBar idea={idea} sparklineMap={sparklineMap} />
    </div>
  )
}

// ─── Row: Watching Idea ───

function WatchingRow({ idea, sparklineMap }: { idea: IdeaSummary; sparklineMap: SparklineMap }) {
  const h = HEALTH[idea.fundamental_health]

  return (
    <div className="border-b border-gray-50 dark:border-t-border/50 last:border-b-0">
    <Link
      to={`/ideas/${idea.id}`}
      className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 transition-colors"
    >
      <div className="w-2 h-2 rounded-full flex-shrink-0 bg-amber-400" />

      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-gray-900 dark:text-t-text-primary truncate">
          {idea.tickers.join(', ') || '미지정'}
        </div>
        <div className="flex items-center gap-1 mt-0.5">
          <span
            className={`text-[10px] leading-tight px-1 rounded ${
              idea.type === 'research'
                ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                : 'bg-gray-50 dark:bg-t-bg-elevated text-gray-500 dark:text-t-text-muted'
            }`}
          >
            {idea.type === 'research' ? '리서치' : '차트'}
          </span>
          {idea.sector && (
            <span className="text-[10px] text-gray-400 dark:text-t-text-muted truncate">
              {idea.sector}
            </span>
          )}
        </div>
      </div>

      {/* Health badge */}
      <div className="hidden md:block w-12 flex-shrink-0">
        {h && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${h.badge}`}>{h.label}</span>
        )}
      </div>

      {/* Target return */}
      <div className="text-right flex-shrink-0">
        <span className="text-sm font-mono text-amber-600 dark:text-amber-400 font-semibold">
          {Number(idea.target_return_pct)}%
        </span>
      </div>

      {/* Created date */}
      <div className="hidden lg:block w-14 flex-shrink-0 text-right text-[11px] text-gray-400 dark:text-t-text-muted">
        {daysAgo(idea.created_at)}
      </div>
    </Link>
    <StockTrendBar idea={idea} sparklineMap={sparklineMap} />
    </div>
  )
}

// ─── Row: Exited Idea ───

function ExitedRow({ idea }: { idea: Idea }) {
  return (
    <Link
      to={`/ideas/${idea.id}`}
      className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 transition-colors border-b border-gray-50 dark:border-t-border/50 last:border-b-0 opacity-50 hover:opacity-100"
    >
      <div className="w-2 h-2 rounded-full flex-shrink-0 bg-gray-300 dark:bg-gray-600" />

      <div className="flex-1 min-w-0">
        <span className="text-sm text-gray-500 dark:text-t-text-muted truncate block">
          {idea.tickers.join(', ') || '미지정'}
        </span>
      </div>

      <span
        className={`text-[10px] leading-tight px-1 rounded flex-shrink-0 ${
          idea.type === 'research'
            ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-500 dark:text-blue-400'
            : 'bg-gray-50 dark:bg-t-bg-elevated text-gray-400 dark:text-t-text-muted'
        }`}
      >
        {idea.type === 'research' ? '리서치' : '차트'}
      </span>

      <span className="text-[11px] text-gray-400 dark:text-t-text-muted flex-shrink-0">
        {daysAgo(idea.updated_at)}
      </span>
    </Link>
  )
}

// ─── Portfolio View ───

function PortfolioView() {
  const { dashboard, loading, fetchDashboard } = useIdeaStore()
  const [exitedIdeas, setExitedIdeas] = useState<Idea[]>([])
  const [sparklineMap, setSparklineMap] = useState<SparklineMap>({})
  const [sections, setSections] = useState({ active: true, watching: true, exited: false })
  const [modalState, setModalState] = useState<{
    type: TradeAction | null
    idea: IdeaSummary | null
    position: Position | null
  }>({ type: null, idea: null, position: null })

  useEffect(() => {
    fetchDashboard()
    ideaApi.list({ status: 'exited' }).then(setExitedIdeas).catch(() => {})
    ideaApi.getStockSparklines().then(setSparklineMap).catch((e) => console.warn('스파크라인 조회 실패:', e))
  }, [fetchDashboard])

  const silentRefetch = useCallback(async () => {
    try {
      await fetchDashboard()
      const sp = await ideaApi.getStockSparklines()
      setSparklineMap(sp)
    } catch { /* 조용히 실패 */ }
  }, [fetchDashboard])

  useRealtimePolling(silentRefetch, 30_000, {
    onlyMarketHours: true,
    enabled: !!dashboard,
  })

  const activeIdeas = useMemo(() => {
    if (!dashboard) return []
    return [...dashboard.research_ideas, ...dashboard.chart_ideas]
  }, [dashboard])

  const watchingIdeas = dashboard?.watching_ideas ?? []
  const stats = dashboard?.stats
  const toggle = (k: 'active' | 'watching' | 'exited') =>
    setSections((p) => ({ ...p, [k]: !p[k] }))

  // ─── Trade action handlers ───

  const handleAction = useCallback((idea: IdeaSummary, action: TradeAction) => {
    const openPos = idea.positions.filter((p) => p.is_open !== false)
    setModalState({ type: action, idea, position: openPos[0] || null })
  }, [])

  const closeModal = useCallback(() => {
    setModalState({ type: null, idea: null, position: null })
  }, [])

  const handleNewPosition = useCallback(
    async (form: PositionCreate) => {
      if (!modalState.idea) return
      await ideaApi.createPosition(modalState.idea.id, form)
      closeModal()
      fetchDashboard()
    },
    [modalState.idea, closeModal, fetchDashboard],
  )

  const handleAddBuy = useCallback(
    async (form: PositionAddBuy) => {
      if (!modalState.position) return
      await positionApi.addBuy(modalState.position.id, form)
      closeModal()
      fetchDashboard()
    },
    [modalState.position, closeModal, fetchDashboard],
  )

  const handleExit = useCallback(
    async (form: PositionExit) => {
      if (!modalState.position) return
      await positionApi.exit(modalState.position.id, form)
      closeModal()
      fetchDashboard()
    },
    [modalState.position, closeModal, fetchDashboard],
  )

  const handlePartialExit = useCallback(
    async (form: PositionPartialExit) => {
      const pos = modalState.position
      if (!pos) {
        // fallback: 첫 번째 오픈 포지션 사용
        const openPos = modalState.idea?.positions.filter((p) => p.is_open !== false)
        if (!openPos?.length) return
        await positionApi.partialExit(openPos[0].id, form)
      } else {
        await positionApi.partialExit(pos.id, form)
      }
      closeModal()
      fetchDashboard()
    },
    [modalState.position, modalState.idea, closeModal, fetchDashboard],
  )

  if (loading && !dashboard) return <IdeaListSkeleton />

  const totalPnl = stats?.total_unrealized_return ?? 0
  const pnlPct = stats?.avg_return_pct ?? 0
  const pnlUp = pnlPct >= 0

  return (
    <div>
      {/* Summary stats bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="bg-white dark:bg-t-bg-card rounded-lg border border-gray-200 dark:border-t-border p-3">
          <div className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-t-text-muted mb-1">
            활성
          </div>
          <div className="text-lg font-bold font-mono text-emerald-600 dark:text-emerald-400">
            {stats?.active_ideas ?? 0}
          </div>
        </div>
        <div className="bg-white dark:bg-t-bg-card rounded-lg border border-gray-200 dark:border-t-border p-3">
          <div className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-t-text-muted mb-1">
            관찰
          </div>
          <div className="text-lg font-bold font-mono text-amber-600 dark:text-amber-400">
            {stats?.watching_ideas ?? 0}
          </div>
        </div>
        <div className="bg-white dark:bg-t-bg-card rounded-lg border border-gray-200 dark:border-t-border p-3">
          <div className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-t-text-muted mb-1">
            투자금
          </div>
          <div className="text-lg font-bold font-mono text-gray-900 dark:text-t-text-primary">
            {formatMoney(stats?.total_invested ?? 0)}
          </div>
        </div>
        <div className="bg-white dark:bg-t-bg-card rounded-lg border border-gray-200 dark:border-t-border p-3">
          <div className="text-[10px] uppercase tracking-wider text-gray-400 dark:text-t-text-muted mb-1">
            총 손익
          </div>
          <div className={`text-lg font-bold font-mono ${pnlUp ? 'text-red-500' : 'text-blue-500'}`}>
            {pnlUp ? '+' : ''}
            {pnlPct.toFixed(1)}%
          </div>
          <div className={`text-[10px] font-mono ${pnlUp ? 'text-red-400' : 'text-blue-400'}`}>
            {pnlUp ? '+' : ''}
            {formatMoney(totalPnl)}원
          </div>
        </div>
      </div>

      {/* Side-by-side: Active + Watching */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <Section
          title="활성 포지션"
          count={activeIdeas.length}
          dotColor="bg-emerald-500"
          expanded={sections.active}
          onToggle={() => toggle('active')}
          header={activeIdeas.length > 0 ? <ActiveHeader /> : undefined}
          emptyText="활성 아이디어가 없습니다"
        >
          {activeIdeas.map((idea) => (
            <ActiveRow key={idea.id} idea={idea} onAction={handleAction} sparklineMap={sparklineMap} />
          ))}
        </Section>

        <Section
          title="관찰 중"
          count={watchingIdeas.length}
          dotColor="bg-amber-400"
          expanded={sections.watching}
          onToggle={() => toggle('watching')}
          header={watchingIdeas.length > 0 ? <WatchingHeader /> : undefined}
          emptyText="관찰 중인 아이디어가 없습니다"
        >
          {watchingIdeas.map((idea) => (
            <WatchingRow key={idea.id} idea={idea} sparklineMap={sparklineMap} />
          ))}
        </Section>
      </div>

      {/* Exited section (full width, collapsed) */}
      {exitedIdeas.length > 0 && (
        <Section
          title="청산 완료"
          count={exitedIdeas.length}
          dotColor="bg-gray-400"
          expanded={sections.exited}
          onToggle={() => toggle('exited')}
        >
          {exitedIdeas.map((idea) => (
            <ExitedRow key={idea.id} idea={idea} />
          ))}
        </Section>
      )}

      {/* Empty state */}
      {activeIdeas.length === 0 &&
        watchingIdeas.length === 0 &&
        exitedIdeas.length === 0 &&
        !loading && (
          <div className="text-center py-16">
            <div className="text-gray-400 dark:text-t-text-muted text-lg mb-2">
              아이디어가 없습니다
            </div>
            <p className="text-sm text-gray-400 dark:text-t-text-muted">
              새로운 아이디어를 추가해보세요.
            </p>
          </div>
        )}

      {/* ─── Trade Modals ─── */}
      {modalState.type === 'buy' && modalState.position && (
        <AddBuyModal
          isOpen
          onClose={closeModal}
          onSubmit={handleAddBuy}
          position={modalState.position}
        />
      )}
      {modalState.type === 'buy' && !modalState.position && (
        <AddPositionModal isOpen onClose={closeModal} onSubmit={handleNewPosition} tickers={modalState.idea?.tickers} />
      )}
      {modalState.type === 'exit' && (
        <ExitPositionModal isOpen onClose={closeModal} onSubmit={handleExit} />
      )}
      {modalState.type === 'partial-exit' && (
        <PartialExitModal
          isOpen
          onClose={closeModal}
          onSubmit={handlePartialExit}
          position={modalState.position}
        />
      )}
    </div>
  )
}

// ─── Loading Spinner ───

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="flex items-center gap-2 text-gray-400 dark:text-t-text-muted">
        <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <span className="text-sm">로딩 중...</span>
      </div>
    </div>
  )
}

// ─── Main Component ───

export default function IdeaList() {
  const [searchParams, setSearchParams] = useSearchParams()
  const features = useFeatureFlags()

  const visibleTabs = useMemo(() => {
    if (features.telegram) return TAB_CONFIG
    return TAB_CONFIG.filter(t => t.key !== 'telegram')
  }, [features.telegram])

  const activeTab = useMemo<TabType>(() => {
    const tabParam = searchParams.get('tab')
    if (tabParam && ['portfolio', 'telegram', 'analytics'].includes(tabParam)) {
      if (tabParam === 'telegram' && !features.telegram) return 'portfolio'
      return tabParam as TabType
    }
    if (tabParam === 'unified' || tabParam === 'manual') return 'portfolio'

    const saved = localStorage.getItem('idea-list-active-tab')
    if (saved === 'unified' || saved === 'manual') return 'portfolio'
    if (saved && ['portfolio', 'telegram', 'analytics'].includes(saved)) {
      if (saved === 'telegram' && !features.telegram) return 'portfolio'
      return saved as TabType
    }
    return 'portfolio'
  }, [searchParams, features.telegram])

  const setActiveTab = (tab: TabType) => {
    setSearchParams({ tab })
    localStorage.setItem('idea-list-active-tab', tab)
  }

  return (
    <div>
      {/* Header + Tab bar */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900 dark:text-t-text-primary">아이디어</h1>

        <div className="flex items-center bg-gray-100 dark:bg-t-bg-elevated rounded-xl p-1 gap-0.5">
          {visibleTabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab.key
                  ? 'bg-white dark:bg-t-border text-gray-900 dark:text-t-text-primary shadow-sm'
                  : 'text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary'
              }`}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d={tab.iconPath}
                />
              </svg>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <Suspense fallback={<LoadingSpinner />}>
        {activeTab === 'portfolio' && <PortfolioView />}
        {activeTab === 'telegram' && <TelegramIdeaList showSourceFilter />}
        {activeTab === 'analytics' && <IdeaAnalytics />}
      </Suspense>
    </div>
  )
}
