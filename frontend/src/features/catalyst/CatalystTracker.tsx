import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import axios from 'axios'
import { catalystApi } from '../../services/api'
import type { CatalystEvent, CatalystStats, EnrichedCatalystEvent } from '../../types/catalyst'
import { CATALYST_TYPE_LABELS, CATALYST_STATUS_LABELS } from '../../types/catalyst'
import { WatchlistStar } from '../../components/WatchlistStar'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

type StatusFilter = 'active' | 'weakening' | 'expired' | 'all'
type TypeFilter = string | 'all'
type ViewMode = 'card' | 'timeline'

function RelevanceBadge({ score }: { score: number }) {
  const color =
    score >= 70 ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
    score >= 40 ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
    'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold ${color}`}>
      {score}
    </span>
  )
}

function MiniSparkline({ priceContext, eventDate }: { priceContext: Array<{ date: string; close: number }>; eventDate: string }) {
  if (!priceContext || priceContext.length < 3) return null

  const prices = priceContext.map(p => p.close)
  const minP = Math.min(...prices)
  const maxP = Math.max(...prices)
  const range = maxP - minP || 1
  const w = 120
  const h = 32

  const points = priceContext.map((p, i) => {
    const x = (i / (priceContext.length - 1)) * w
    const y = h - ((p.close - minP) / range) * (h - 4) - 2
    return `${x},${y}`
  })

  // 이벤트 날짜의 x 위치
  const eventIdx = priceContext.findIndex(p => p.date === eventDate)
  const eventX = eventIdx >= 0 ? (eventIdx / (priceContext.length - 1)) * w : -1

  const lastPrice = prices[prices.length - 1]
  const firstPrice = prices[0]
  const lineColor = lastPrice >= firstPrice ? '#ef4444' : '#3b82f6'

  return (
    <svg width={w} height={h} className="flex-shrink-0">
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={lineColor}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
      {eventX >= 0 && (
        <line x1={eventX} y1="0" x2={eventX} y2={h} stroke="#f59e0b" strokeWidth="1" strokeDasharray="2,2" />
      )}
    </svg>
  )
}

export default function CatalystTracker() {
  const [events, setEvents] = useState<EnrichedCatalystEvent[]>([])
  const [stats, setStats] = useState<CatalystStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('active')
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all')
  const [viewMode, setViewMode] = useState<ViewMode>('card')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [runningJob, setRunningJob] = useState<string | null>(null)
  const [jobResult, setJobResult] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const [eventsData, statsData] = await Promise.all([
          catalystApi.getEnriched({
            status: statusFilter === 'all' ? undefined : statusFilter,
            catalyst_type: typeFilter === 'all' ? undefined : typeFilter,
            limit: 100,
          }),
          catalystApi.getStats(),
        ])
        setEvents(eventsData)
        setStats(statsData)
      } catch (err) {
        console.error('Catalyst data fetch failed:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [statusFilter, typeFilter])

  const statusFilters: { value: StatusFilter; label: string }[] = [
    { value: 'active', label: '진행중' },
    { value: 'weakening', label: '약화' },
    { value: 'expired', label: '만료' },
    { value: 'all', label: '전체' },
  ]

  const typeFilters: { value: string; label: string }[] = [
    { value: 'all', label: '전체' },
    { value: 'policy', label: '정책' },
    { value: 'earnings', label: '실적' },
    { value: 'contract', label: '수주' },
    { value: 'theme', label: '테마' },
    { value: 'product', label: '제품' },
    { value: 'management', label: '경영' },
    { value: 'other', label: '기타' },
  ]

  const runJob = async (name: string, endpoint: string) => {
    setRunningJob(name)
    setJobResult(null)
    try {
      const { data } = await axios.post(`${API_URL}/api/v1/${endpoint}`)
      const detail = data.total_created != null
        ? ` (${data.total_created}건 감지, ${data.total_reclassified || 0}건 재분류, ${data.total_updated}건 추적)`
        : data.reclassified != null ? ` (${data.reclassified}건 재분류)`
        : data.created != null ? ` (${data.created}건 생성)` : data.updated != null ? ` (${data.updated}건 업데이트)` : ''
      setJobResult(`${name}: ${data.status}${detail}`)
      const [eventsData, statsData] = await Promise.all([
        catalystApi.getEnriched({ status: statusFilter === 'all' ? undefined : statusFilter, catalyst_type: typeFilter === 'all' ? undefined : typeFilter, limit: 100 }),
        catalystApi.getStats(),
      ])
      setEvents(eventsData)
      setStats(statsData)
    } catch (err: any) {
      setJobResult(`${name}: 실패 - ${err.response?.data?.detail || err.message}`)
    } finally {
      setRunningJob(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-t-text-primary">
            Catalyst Tracker
          </h1>
          <p className="text-xs text-gray-400 dark:text-t-text-muted mt-0.5">
            3%+ 변동 + 뉴스/공시 종목의 재료 추적 (관련도 순)
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* 뷰 토글 */}
          <div className="flex gap-1 bg-gray-100 dark:bg-t-bg rounded-lg p-0.5">
            <button
              onClick={() => setViewMode('card')}
              className={`px-2.5 py-1 rounded text-xs ${viewMode === 'card' ? 'bg-white dark:bg-t-bg-card shadow-sm text-gray-900 dark:text-t-text-primary' : 'text-gray-500 dark:text-t-text-muted'}`}
            >
              카드
            </button>
            <button
              onClick={() => setViewMode('timeline')}
              className={`px-2.5 py-1 rounded text-xs ${viewMode === 'timeline' ? 'bg-white dark:bg-t-bg-card shadow-sm text-gray-900 dark:text-t-text-primary' : 'text-gray-500 dark:text-t-text-muted'}`}
            >
              타임라인
            </button>
          </div>
          {stats && (
            <div className="flex gap-3 text-sm">
              <span className="text-green-600 dark:text-green-400">진행 {stats.active_count}</span>
              <span className="text-yellow-600 dark:text-yellow-400">약화 {stats.weakening_count}</span>
              <span className="text-gray-400">만료 {stats.expired_count}</span>
            </div>
          )}
        </div>
      </div>

      {/* 수동 실행 */}
      <div className="bg-gray-50 dark:bg-t-bg rounded-lg p-3 border border-gray-200 dark:border-t-border">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-gray-500 dark:text-t-text-muted font-medium">수동 실행:</span>
          {[
            { label: '1. 뉴스 수집 (핫)', endpoint: 'stock-news/collect-hot' },
            { label: '2. 뉴스 수집 (전체)', endpoint: 'stock-news/collect-all' },
            { label: '3. 카탈리스트 감지', endpoint: 'catalyst/detect' },
            { label: '4. 추적 업데이트', endpoint: 'catalyst/update' },
          ].map((job) => (
            <button
              key={job.endpoint}
              onClick={() => runJob(job.label, job.endpoint)}
              disabled={runningJob !== null}
              className={`px-2.5 py-1.5 text-xs rounded-md border transition-colors ${
                runningJob === job.label
                  ? 'bg-amber-100 dark:bg-amber-900/30 border-amber-300 dark:border-amber-700 text-amber-700 dark:text-amber-400 animate-pulse'
                  : 'bg-white dark:bg-t-bg-card border-gray-200 dark:border-t-border text-gray-600 dark:text-t-text-secondary hover:border-amber-300 dark:hover:border-amber-600 disabled:opacity-40'
              }`}
            >
              {runningJob === job.label ? `${job.label}...` : job.label}
            </button>
          ))}
          <span className="text-gray-300 dark:text-t-border mx-1">|</span>
          {[
            { label: '백필 (7일)', endpoint: 'catalyst/backfill?days=7' },
            { label: '재분류', endpoint: 'catalyst/reclassify' },
          ].map((job) => (
            <button
              key={job.endpoint}
              onClick={() => runJob(job.label, job.endpoint)}
              disabled={runningJob !== null}
              className={`px-2.5 py-1.5 text-xs rounded-md border transition-colors ${
                runningJob === job.label
                  ? 'bg-purple-100 dark:bg-purple-900/30 border-purple-300 dark:border-purple-700 text-purple-700 dark:text-purple-400 animate-pulse'
                  : 'bg-white dark:bg-t-bg-card border-purple-200 dark:border-purple-800 text-purple-600 dark:text-purple-400 hover:border-purple-400 dark:hover:border-purple-600 disabled:opacity-40'
              }`}
            >
              {runningJob === job.label ? `${job.label}...` : job.label}
            </button>
          ))}
        </div>
        {jobResult && (
          <div className={`mt-2 text-xs ${jobResult.includes('실패') ? 'text-red-500' : 'text-green-600 dark:text-green-400'}`}>
            {jobResult}
          </div>
        )}
      </div>

      {/* 필터 */}
      <div className="flex flex-wrap gap-2">
        <div className="flex gap-1 bg-gray-100 dark:bg-t-bg rounded-lg p-0.5">
          {statusFilters.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                statusFilter === f.value
                  ? 'bg-white dark:bg-t-bg-card text-gray-900 dark:text-t-text-primary shadow-sm'
                  : 'text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="flex gap-1 bg-gray-100 dark:bg-t-bg rounded-lg p-0.5">
          {typeFilters.map((f) => (
            <button
              key={f.value}
              onClick={() => setTypeFilter(f.value)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                typeFilter === f.value
                  ? 'bg-white dark:bg-t-bg-card text-gray-900 dark:text-t-text-primary shadow-sm'
                  : 'text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* 유형별 통계 카드 */}
      {stats && Object.keys(stats.by_type).length > 0 && (
        <div className="grid grid-cols-3 md:grid-cols-7 gap-2">
          {Object.entries(stats.by_type).map(([type, data]) => (
            <div
              key={type}
              className="bg-white dark:bg-t-bg-card rounded-lg p-2.5 border border-gray-200 dark:border-t-border text-center"
            >
              <div className="text-xs text-gray-500 dark:text-t-text-muted">
                {CATALYST_TYPE_LABELS[type] || type}
              </div>
              <div className="text-lg font-bold text-gray-900 dark:text-t-text-primary mt-0.5">
                {data.count}
              </div>
              <div className="text-[10px] text-gray-400">
                avg +{data.avg_max_return.toFixed(1)}%
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 이벤트 리스트 */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
        </div>
      ) : events.length === 0 ? (
        <div className="text-center py-12 text-gray-400 dark:text-t-text-muted">
          해당 조건의 카탈리스트가 없습니다
        </div>
      ) : viewMode === 'timeline' ? (
        <TimelineView events={events} />
      ) : (
        <div className="space-y-2">
          {events.map((event) => (
            <EnrichedCatalystCard
              key={event.id}
              event={event}
              isExpanded={expandedId === event.id}
              onToggle={() => setExpandedId(prev => prev === event.id ? null : event.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function EnrichedCatalystCard({
  event,
  isExpanded,
  onToggle,
}: {
  event: EnrichedCatalystEvent
  isExpanded: boolean
  onToggle: () => void
}) {
  const [impact, setImpact] = useState<string | null>(null)
  const [similar, setSimilar] = useState<CatalystEvent[]>([])
  const [loadingDetail, setLoadingDetail] = useState(false)

  const statusColor = {
    active: 'text-green-600 dark:text-green-400',
    weakening: 'text-yellow-600 dark:text-yellow-400',
    expired: 'text-gray-400 dark:text-t-text-muted',
  }[event.status]

  const returnColor = (val: number | null) => {
    if (val === null) return 'text-gray-400'
    return val >= 0 ? 'text-red-500 dark:text-red-400' : 'text-blue-500 dark:text-blue-400'
  }

  const barWidth = event.max_return && event.max_return > 0
    ? Math.min(Math.max((event.current_return || 0) / event.max_return * 100, 0), 100)
    : 0

  useEffect(() => {
    if (isExpanded && impact === null) {
      setLoadingDetail(true)
      Promise.all([
        catalystApi.getImpact(event.id),
        catalystApi.getSimilar(event.id),
      ]).then(([impactData, similarData]) => {
        setImpact(impactData.impact)
        setSimilar(similarData)
      }).catch(() => {
        setImpact('분석 실패')
      }).finally(() => {
        setLoadingDetail(false)
      })
    }
  }, [isExpanded]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="bg-white dark:bg-t-bg-card rounded-lg border border-gray-200 dark:border-t-border overflow-hidden">
      <div
        className="p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-t-bg-elevated/30 transition-colors"
        onClick={onToggle}
      >
        {/* 헤더 */}
        <div className="flex items-start justify-between mb-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <RelevanceBadge score={event.relevance_score} />
              <WatchlistStar stockCode={event.stock_code} stockName={event.stock_name || event.stock_code} />
              <Link
                to={`/stocks/${event.stock_code}`}
                className="font-bold text-gray-900 dark:text-t-text-primary hover:text-blue-600 dark:hover:text-blue-400"
                onClick={e => e.stopPropagation()}
              >
                {event.stock_name || event.stock_code}
              </Link>
              <span className="text-xs text-gray-400">{event.stock_code}</span>
              {event.catalyst_type && (
                <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-t-border rounded text-[10px] text-gray-600 dark:text-t-text-secondary">
                  {CATALYST_TYPE_LABELS[event.catalyst_type] || event.catalyst_type}
                </span>
              )}
            </div>
            <div className="text-sm text-gray-600 dark:text-t-text-secondary mt-0.5 truncate">
              {event.title}
            </div>
          </div>
          <div className="flex items-center gap-2 ml-2 flex-shrink-0">
            <MiniSparkline priceContext={event.price_context} eventDate={event.event_date} />
            <span className={`text-xs font-medium ${statusColor}`}>
              {CATALYST_STATUS_LABELS[event.status] || event.status}
            </span>
          </div>
        </div>

        {/* 메타 정보 */}
        <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-t-text-muted mb-2">
          <span>발생 {event.event_date}</span>
          <span>T+{event.days_alive}일</span>
          {event.price_at_event && (
            <span>
              가격 {event.price_at_event.toLocaleString()}원
              {event.price_change_pct != null && (
                <span className={returnColor(event.price_change_pct)}>
                  {' '}({event.price_change_pct > 0 ? '+' : ''}{event.price_change_pct.toFixed(1)}%)
                </span>
              )}
            </span>
          )}
        </div>

        {/* 수익률 바 */}
        {event.max_return != null && event.max_return > 0 && (
          <div className="mb-2">
            <div className="h-2 bg-gray-100 dark:bg-t-border rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  (event.current_return || 0) >= 0
                    ? 'bg-gradient-to-r from-green-400 to-green-500'
                    : 'bg-gradient-to-r from-red-400 to-red-500'
                }`}
                style={{ width: `${Math.max(barWidth, 2)}%` }}
              />
            </div>
            <div className="flex justify-between mt-0.5 text-[10px]">
              <span className={returnColor(event.current_return)}>
                수익률 {event.current_return != null ? `${event.current_return > 0 ? '+' : ''}${event.current_return.toFixed(1)}%` : '-'}
              </span>
              <span className="text-gray-400">
                최대 +{event.max_return.toFixed(1)}% (T+{event.max_return_day})
              </span>
            </div>
          </div>
        )}

        {/* 하단 태그 */}
        <div className="flex items-center gap-3 text-[11px]">
          <span className={event.flow_confirmed ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}>
            수급 {event.flow_confirmed ? 'O 동반' : 'X 이탈'}
          </span>
          <span className="text-gray-500 dark:text-t-text-muted">
            후속뉴스 {event.followup_news_count}건
          </span>
          {[
            { label: 'T1', val: event.return_t1 },
            { label: 'T5', val: event.return_t5 },
            { label: 'T10', val: event.return_t10 },
          ].map(
            ({ label, val }) =>
              val != null && (
                <span key={label} className={returnColor(val)}>
                  {label} {val > 0 ? '+' : ''}{val.toFixed(1)}%
                </span>
              ),
          )}
          <span className="ml-auto text-gray-400">
            {isExpanded ? '▲' : '▼'}
          </span>
        </div>
      </div>

      {/* 확장 상세 */}
      {isExpanded && (
        <div className="border-t border-gray-100 dark:border-t-border p-4 bg-gray-50 dark:bg-t-bg space-y-3">
          {loadingDetail ? (
            <div className="text-center py-4 text-gray-400 text-sm">AI 분석 로딩 중...</div>
          ) : (
            <>
              {/* AI 비즈니스 임팩트 */}
              {impact && (
                <div>
                  <h4 className="text-xs font-medium text-gray-700 dark:text-t-text-secondary mb-1">AI 비즈니스 임팩트</h4>
                  <p className="text-sm text-gray-600 dark:text-t-text-muted leading-relaxed bg-white dark:bg-t-bg-card rounded-lg p-3 border border-gray-200 dark:border-t-border">
                    {impact}
                  </p>
                </div>
              )}

              {/* 유사 과거 이벤트 */}
              {similar.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-gray-700 dark:text-t-text-secondary mb-1">유사 과거 이벤트</h4>
                  <div className="space-y-1">
                    {similar.map(s => (
                      <div key={s.id} className="flex items-center justify-between text-xs bg-white dark:bg-t-bg-card rounded p-2 border border-gray-200 dark:border-t-border">
                        <div className="flex-1 min-w-0">
                          <span className="text-gray-500 mr-2">{s.event_date}</span>
                          <span className="text-gray-700 dark:text-t-text-secondary truncate">{s.title}</span>
                        </div>
                        <div className="flex items-center gap-2 ml-2">
                          <span className={returnColor(s.max_return)}>
                            max {s.max_return != null ? `+${s.max_return.toFixed(1)}%` : '-'}
                          </span>
                          <span className={`${s.status === 'expired' ? 'text-gray-400' : 'text-green-500'}`}>
                            {CATALYST_STATUS_LABELS[s.status]}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function TimelineView({ events }: { events: EnrichedCatalystEvent[] }) {
  // 날짜별 그룹핑
  const grouped = new Map<string, EnrichedCatalystEvent[]>()
  for (const e of events) {
    const existing = grouped.get(e.event_date) || []
    existing.push(e)
    grouped.set(e.event_date, existing)
  }

  const sortedDates = [...grouped.keys()].sort((a, b) => b.localeCompare(a))

  const statusDot = (status: string) => {
    if (status === 'active') return 'bg-green-500'
    if (status === 'weakening') return 'bg-yellow-500'
    return 'bg-gray-400'
  }

  return (
    <div className="relative pl-6">
      {/* 수직 라인 */}
      <div className="absolute left-2.5 top-0 bottom-0 w-px bg-gray-200 dark:bg-t-border" />

      {sortedDates.map(date => {
        const dayEvents = grouped.get(date) || []
        return (
          <div key={date} className="relative mb-6">
            {/* 날짜 마커 */}
            <div className="absolute -left-3.5 top-1 w-3 h-3 rounded-full bg-amber-400 border-2 border-white dark:border-t-bg" />
            <div className="text-xs font-medium text-gray-500 dark:text-t-text-muted mb-2">{date}</div>

            <div className="space-y-1.5">
              {dayEvents.map(e => (
                <Link
                  key={e.id}
                  to={`/stocks/${e.stock_code}`}
                  className="flex items-center gap-3 p-2.5 bg-white dark:bg-t-bg-card rounded-lg border border-gray-200 dark:border-t-border hover:border-amber-300 dark:hover:border-amber-500/50 transition-colors"
                >
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${statusDot(e.status)}`} />
                  <RelevanceBadge score={e.relevance_score} />
                  <WatchlistStar stockCode={e.stock_code} stockName={e.stock_name || e.stock_code} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm text-gray-900 dark:text-t-text-primary">
                        {e.stock_name || e.stock_code}
                      </span>
                      {e.catalyst_type && (
                        <span className="text-[10px] text-gray-500">{CATALYST_TYPE_LABELS[e.catalyst_type]}</span>
                      )}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-t-text-muted truncate">{e.title}</div>
                  </div>
                  <MiniSparkline priceContext={e.price_context} eventDate={e.event_date} />
                  <div className="text-right flex-shrink-0">
                    <div className={`text-xs font-medium ${(e.current_return || 0) >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                      {e.current_return != null ? `${e.current_return > 0 ? '+' : ''}${e.current_return.toFixed(1)}%` : '-'}
                    </div>
                    <div className="text-[10px] text-gray-400">
                      T+{e.days_alive}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
