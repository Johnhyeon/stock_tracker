import { useEffect, useMemo, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useIdeaStore } from '../../store/useIdeaStore'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import { mentionsApi, themeSetupApi, dataApi } from '../../services/api'
import type { TrendingMentionItem } from '../../services/api'
import type { PriceData } from '../../types/data'
import type { IdeaSummary } from '../../types/idea'
import { useMarketStatus } from '../../hooks/useMarketStatus'
import { useRealtimePolling } from '../../hooks/useRealtimePolling'

type ViewMode = 'card' | 'list'

// thesis에서 이미지 URL 추출
function extractImages(text: string): string[] {
  const markdownImagePattern = /!\[.*?\]\((https?:\/\/[^\s)]+)\)/g
  const plainUrlPattern = /(https?:\/\/[^\s<>]+\.(?:jpg|jpeg|png|gif|webp|bmp|svg)(?:\?[^\s<>]*)?)/gi

  const images: string[] = []
  let match

  while ((match = markdownImagePattern.exec(text)) !== null) {
    images.push(match[1])
  }

  if (images.length === 0) {
    while ((match = plainUrlPattern.exec(text)) !== null) {
      images.push(match[0])
    }
  }

  return images
}

// thesis에서 이미지 관련 텍스트 제거하고 순수 텍스트만 추출
function extractText(text: string): string {
  return text
    .replace(/!\[.*?\]\([^)]+\)/g, '')
    .replace(/(https?:\/\/[^\s<>]+\.(?:jpg|jpeg|png|gif|webp|bmp|svg)(?:\?[^\s<>]*)?)/gi, '')
    .replace(/\n+/g, ' ')
    .trim()
}

const healthVariant = {
  healthy: 'success',
  deteriorating: 'warning',
  broken: 'danger',
} as const

const healthLabel = {
  healthy: '건강',
  deteriorating: '악화',
  broken: '손상',
} as const

// 카드 뷰 컴포넌트
function IdeaCard({ idea }: { idea: IdeaSummary }) {
  const isWatching = idea.status === 'watching'
  const daysRemaining = idea.time_remaining_days
  const isOverdue = daysRemaining < 0

  const images = useMemo(() => extractImages(idea.thesis), [idea.thesis])
  const textContent = useMemo(() => extractText(idea.thesis), [idea.thesis])

  return (
    <Link to={`/ideas/${idea.id}`}>
      <Card className="hover:shadow-md transition-shadow h-full">
        <CardContent>
          <div className="flex justify-between items-start mb-3">
            <div>
              <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">{idea.tickers.join(', ') || '종목 미지정'}</h3>
              {idea.sector && <p className="text-sm text-gray-500 dark:text-gray-400">{idea.sector}</p>}
            </div>
            <Badge variant={healthVariant[idea.fundamental_health]}>
              {healthLabel[idea.fundamental_health]}
            </Badge>
          </div>

          {images.length > 0 && (
            <div className="mb-3 -mx-2">
              <img
                src={images[0]}
                alt="아이디어 이미지"
                className="w-full h-32 object-cover rounded-lg"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none'
                }}
              />
            </div>
          )}

          <p className="text-sm text-gray-600 dark:text-gray-300 line-clamp-2 mb-4">{textContent || idea.thesis}</p>

          <div className="grid grid-cols-2 gap-4 text-sm">
            {!isWatching && (
              <div>
                <span className="text-gray-500 dark:text-gray-400">투자금:</span>
                <span className="ml-1 font-medium text-gray-900 dark:text-gray-100">
                  {Number(idea.total_invested).toLocaleString()}원
                </span>
              </div>
            )}
            <div>
              <span className="text-gray-500 dark:text-gray-400">목표:</span>
              <span className="ml-1 font-medium text-gray-900 dark:text-gray-100">{Number(idea.target_return_pct)}%</span>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">{isWatching ? '관심일:' : '보유일:'}</span>
              <span className="ml-1 font-medium text-gray-900 dark:text-gray-100">{idea.days_active}일</span>
            </div>
            {!isWatching && (
              <div>
                <span className="text-gray-500 dark:text-gray-400">잔여:</span>
                <span className={`ml-1 font-medium ${isOverdue ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-gray-100'}`}>
                  {isOverdue ? `${Math.abs(daysRemaining)}일 초과` : `${daysRemaining}일`}
                </span>
              </div>
            )}
          </div>

          {idea.positions.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">보유 포지션</div>
              <div className="space-y-1.5">
                {idea.positions.map((pos) => (
                  <div key={pos.id} className="flex items-center justify-between text-xs bg-gray-50 dark:bg-gray-700 px-2 py-1.5 rounded">
                    <div className="flex items-center gap-1.5">
                      <span className="font-medium text-gray-900 dark:text-gray-100">{pos.stock_name || pos.ticker}</span>
                      <span className="text-gray-400 dark:text-gray-500">{pos.quantity}주</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {pos.current_price && (
                        <span className="text-gray-500 dark:text-gray-400">
                          {Number(pos.current_price).toLocaleString()}원
                        </span>
                      )}
                      {pos.unrealized_return_pct != null && (
                        <span className={`font-medium ${pos.unrealized_return_pct >= 0 ? 'text-red-500 dark:text-red-400' : 'text-blue-500 dark:text-blue-400'}`}>
                          {pos.unrealized_return_pct >= 0 ? '+' : ''}{pos.unrealized_return_pct.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  )
}

// 목록 뷰 컴포넌트
function IdeaListItem({ idea }: { idea: IdeaSummary }) {
  const isWatching = idea.status === 'watching'
  const daysRemaining = idea.time_remaining_days
  const isOverdue = daysRemaining < 0

  const images = useMemo(() => extractImages(idea.thesis), [idea.thesis])
  const textContent = useMemo(() => extractText(idea.thesis), [idea.thesis])

  return (
    <Link to={`/ideas/${idea.id}`}>
      <div className="flex gap-4 p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:shadow-md transition-shadow">
        {images.length > 0 && (
          <div className="flex-shrink-0">
            <img
              src={images[0]}
              alt="아이디어 이미지"
              className="w-20 h-20 object-cover rounded-lg"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none'
              }}
            />
          </div>
        )}

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-base truncate text-gray-900 dark:text-gray-100">
              {idea.tickers.join(', ') || '종목 미지정'}
            </h3>
            {idea.sector && (
              <span className="text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">({idea.sector})</span>
            )}
            <Badge variant={healthVariant[idea.fundamental_health]} size="sm">
              {healthLabel[idea.fundamental_health]}
            </Badge>
          </div>

          <p className="text-sm text-gray-600 dark:text-gray-300 line-clamp-1 mb-2">{textContent || idea.thesis}</p>

          <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
            {!isWatching && (
              <span>투자금: {Number(idea.total_invested).toLocaleString()}원</span>
            )}
            <span>목표: {Number(idea.target_return_pct)}%</span>
            <span>{isWatching ? '관심:' : '보유:'} {idea.days_active}일</span>
            {!isWatching && (
              <span className={isOverdue ? 'text-red-600 dark:text-red-400' : ''}>
                잔여: {isOverdue ? `${Math.abs(daysRemaining)}일 초과` : `${daysRemaining}일`}
              </span>
            )}
            {idea.positions.length > 0 && (
              <span className="text-primary-600 dark:text-primary-400">포지션 {idea.positions.length}개</span>
            )}
          </div>
        </div>
      </div>
    </Link>
  )
}

// 뷰 모드 토글 버튼
function ViewModeToggle({
  viewMode,
  onChange,
}: {
  viewMode: ViewMode
  onChange: (mode: ViewMode) => void
}) {
  return (
    <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
      <button
        onClick={() => onChange('card')}
        className={`p-1.5 rounded transition-colors ${
          viewMode === 'card' ? 'bg-white dark:bg-gray-600 shadow-sm text-primary-600 dark:text-primary-400' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
        }`}
        title="카드 보기"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
        </svg>
      </button>
      <button
        onClick={() => onChange('list')}
        className={`p-1.5 rounded transition-colors ${
          viewMode === 'list' ? 'bg-white dark:bg-gray-600 shadow-sm text-primary-600 dark:text-primary-400' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
        }`}
        title="목록 보기"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
    </div>
  )
}

// 아이디어 섹션 렌더링
function IdeaSection({
  ideas,
  viewMode,
  emptyMessage,
}: {
  ideas: IdeaSummary[]
  viewMode: ViewMode
  emptyMessage: string
}) {
  if (ideas.length === 0) {
    return <p className="text-gray-500 dark:text-gray-400 text-center py-4">{emptyMessage}</p>
  }

  if (viewMode === 'list') {
    return (
      <div className="space-y-2">
        {ideas.map((idea) => (
          <IdeaListItem key={idea.id} idea={idea} />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {ideas.map((idea) => (
        <IdeaCard key={idea.id} idea={idea} />
      ))}
    </div>
  )
}

export default function Dashboard() {
  const { dashboard, loading, error, fetchDashboard } = useIdeaStore()
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    const saved = localStorage.getItem('dashboard-view-mode')
    return (saved as ViewMode) || 'card'
  })
  const [convergence, setConvergence] = useState<TrendingMentionItem[]>([])
  const [topTheme, setTopTheme] = useState<string | null>(null)
  const [livePrices, setLivePrices] = useState<Record<string, PriceData>>({})
  const { isMarketOpen } = useMarketStatus()

  useEffect(() => {
    fetchDashboard()
    // 시장 시그널 로드
    mentionsApi.getConvergence(7, 2).then(setConvergence).catch(() => {})
    themeSetupApi.getEmerging(1, 30).then(res => {
      if (res.themes?.length > 0) setTopTheme(res.themes[0].theme_name)
    }).catch(() => {})
  }, [fetchDashboard])

  // 보유 포지션 종목코드 추출
  const positionStockCodes = useMemo(() => {
    if (!dashboard) return []
    const codes = new Set<string>()
    const allIdeas = [...dashboard.research_ideas, ...dashboard.chart_ideas]
    for (const idea of allIdeas) {
      for (const pos of idea.positions) {
        if (pos.is_open && pos.ticker) {
          codes.add(pos.ticker)
        }
      }
    }
    return Array.from(codes)
  }, [dashboard])

  // 실시간 가격 조회
  const fetchLivePrices = useCallback(async () => {
    if (positionStockCodes.length === 0) return
    try {
      const prices = await dataApi.getMultiplePrices(positionStockCodes)
      setLivePrices(prices)
    } catch {
      // 조용히 실패
    }
  }, [positionStockCodes])

  // 초기 로드
  useEffect(() => {
    fetchLivePrices()
  }, [fetchLivePrices])

  // 장중 30초 자동 갱신
  useRealtimePolling(fetchLivePrices, 30_000, { onlyMarketHours: true, enabled: positionStockCodes.length > 0 })

  useEffect(() => {
    localStorage.setItem('dashboard-view-mode', viewMode)
  }, [viewMode])

  // 실시간 미실현 손익 재계산 (훅은 early return 전에 호출해야 함)
  const liveUnrealizedReturn = useMemo(() => {
    if (!dashboard || Object.keys(livePrices).length === 0) return null
    let totalReturn = 0
    const allIdeas = [...dashboard.research_ideas, ...dashboard.chart_ideas]
    for (const idea of allIdeas) {
      for (const pos of idea.positions) {
        if (!pos.is_open) continue
        const live = livePrices[pos.ticker]
        if (live) {
          const currentPrice = Number(live.current_price)
          totalReturn += (currentPrice - Number(pos.entry_price)) * pos.quantity
        } else if (pos.unrealized_profit != null) {
          totalReturn += Number(pos.unrealized_profit)
        }
      }
    }
    return totalReturn
  }, [livePrices, dashboard])

  if (loading) return <div className="text-center py-10 text-gray-600 dark:text-gray-300">로딩 중...</div>
  if (error) return <div className="text-center py-10 text-red-600 dark:text-red-400">{error}</div>
  if (!dashboard) return <div className="text-center py-10 text-gray-600 dark:text-gray-300">데이터가 없습니다.</div>

  const { stats, research_ideas, chart_ideas, watching_ideas } = dashboard
  const displayUnrealized = liveUnrealizedReturn ?? Number(stats.total_unrealized_return)

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">대시보드</h1>
        <ViewModeToggle viewMode={viewMode} onChange={setViewMode} />
      </div>

      {/* 시장 시그널 (교차 언급 + 핫 테마) */}
      {(convergence.length > 0 || topTheme) && (
        <div className="mb-6 grid gap-4 md:grid-cols-2">
          {convergence.length > 0 && (
            <Card>
              <CardContent>
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">교차 시그널</span>
                  <Badge variant="danger" size="sm">{convergence.length}종목</Badge>
                </div>
                <div className="flex flex-wrap gap-2">
                  {convergence.slice(0, 8).map(item => (
                    <Link key={item.stock_code} to={`/stocks/${item.stock_code}`}>
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-red-50 dark:bg-red-900/20 text-sm text-red-700 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors">
                        <span className="font-medium">{item.stock_name || item.stock_code}</span>
                        <span className="text-xs text-red-500 dark:text-red-400">{item.source_count}src/{item.total_mentions}</span>
                      </span>
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
          {topTheme && (
            <Card>
              <CardContent>
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">오늘의 신흥 테마</span>
                </div>
                <Link to={`/emerging/${encodeURIComponent(topTheme)}`}>
                  <span className="text-lg font-bold text-primary-600 dark:text-primary-400 hover:underline">
                    {topTheme}
                  </span>
                </Link>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* 첫 번째 줄: 아이디어 관련 */}
      <div className="grid gap-4 md:grid-cols-3 mb-4">
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500 dark:text-gray-400">총 아이디어</div>
            <div className="text-3xl font-bold text-gray-900 dark:text-gray-100">{stats.total_ideas}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500 dark:text-gray-400">활성 아이디어</div>
            <div className="text-3xl font-bold text-green-600 dark:text-green-400">{stats.active_ideas}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500 dark:text-gray-400">관심 종목</div>
            <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">{stats.watching_ideas}</div>
          </CardContent>
        </Card>
      </div>

      {/* 두 번째 줄: 투자 성과 관련 */}
      <div className="grid gap-4 md:grid-cols-3 mb-8">
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500 dark:text-gray-400">총 투자금</div>
            <div className="text-3xl font-bold text-gray-900 dark:text-gray-100">
              {Number(stats.total_invested).toLocaleString()}원
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="flex items-center gap-1.5">
              <span className="text-sm text-gray-500 dark:text-gray-400">미실현 손익</span>
              {liveUnrealizedReturn != null && (
                <span className="text-xs text-green-600 dark:text-green-400">LIVE</span>
              )}
              {!isMarketOpen && <span className="text-xs text-gray-400 dark:text-gray-500">(장마감)</span>}
            </div>
            <div className={`text-3xl font-bold ${
              displayUnrealized >= 0 ? 'text-red-500 dark:text-red-400' : 'text-blue-500 dark:text-blue-400'
            }`}>
              {displayUnrealized >= 0 ? '+' : ''}
              {Math.round(displayUnrealized).toLocaleString()}원
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <div className="text-sm text-gray-500 dark:text-gray-400">평균 수익률</div>
            <div className={`text-3xl font-bold ${
              stats.avg_return_pct != null
                ? stats.avg_return_pct >= 0
                  ? 'text-red-500 dark:text-red-400'
                  : 'text-blue-500 dark:text-blue-400'
                : 'text-gray-900 dark:text-gray-100'
            }`}>
              {stats.avg_return_pct != null
                ? `${stats.avg_return_pct >= 0 ? '+' : ''}${stats.avg_return_pct.toFixed(1)}%`
                : '-'}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 보유 종목 실시간 시세 */}
      {positionStockCodes.length > 0 && Object.keys(livePrices).length > 0 && (
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-3">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">보유 종목 실시간</h2>
            {isMarketOpen && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                LIVE
              </span>
            )}
            {!isMarketOpen && (
              <span className="text-xs text-gray-400 dark:text-gray-500">(장마감)</span>
            )}
          </div>
          <div className="grid gap-2 grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {positionStockCodes.map(code => {
              const price = livePrices[code]
              if (!price) return null
              const isUp = Number(price.change_rate) >= 0
              return (
                <Link key={code} to={`/stocks/${code}`}>
                  <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:shadow-sm transition-shadow">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                        {price.stock_name || code}
                      </span>
                      <span className="text-xs text-gray-400 dark:text-gray-500">{code}</span>
                    </div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                        {Number(price.current_price).toLocaleString()}
                      </span>
                      <span className={`text-sm font-medium ${isUp ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                        {isUp ? '+' : ''}{Number(price.change_rate).toFixed(2)}%
                      </span>
                    </div>
                  </div>
                </Link>
              )
            })}
          </div>
        </div>
      )}

      <div className="grid gap-8 lg:grid-cols-2">
        <div>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  리서치 포지션 <span className="text-primary-600 dark:text-primary-400">(60%)</span>
                </h2>
                <Badge variant="info">{research_ideas.length}개</Badge>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                기업 분석 기반 - 논리가 유효한 동안 보유
              </p>
            </CardHeader>
            <CardContent>
              <IdeaSection
                ideas={research_ideas}
                viewMode={viewMode}
                emptyMessage="활성 리서치 아이디어가 없습니다."
              />
            </CardContent>
          </Card>
        </div>

        <div>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  차트 포지션 <span className="text-gray-600 dark:text-gray-400">(40%)</span>
                </h2>
                <Badge>{chart_ideas.length}개</Badge>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                기술적 분석 기반 - 정해진 기간/목표 준수
              </p>
            </CardHeader>
            <CardContent>
              <IdeaSection
                ideas={chart_ideas}
                viewMode={viewMode}
                emptyMessage="활성 차트 아이디어가 없습니다."
              />
            </CardContent>
          </Card>
        </div>
      </div>

      {watching_ideas.length > 0 && (
        <div className="mt-8">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                  관심 종목 <span className="text-blue-600 dark:text-blue-400">(Watching)</span>
                </h2>
                <Badge variant="info">{watching_ideas.length}개</Badge>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                포지션 진입 전 관찰 중인 아이디어
              </p>
            </CardHeader>
            <CardContent>
              {viewMode === 'list' ? (
                <div className="space-y-2">
                  {watching_ideas.map((idea) => (
                    <IdeaListItem key={idea.id} idea={idea} />
                  ))}
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {watching_ideas.map((idea) => (
                    <IdeaCard key={idea.id} idea={idea} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
