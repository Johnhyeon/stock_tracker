import { useParams, Link, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState, useMemo, useCallback } from 'react'
import { StockChart } from '../../components/StockChart'
import type { IdeaMarker, TradeMarker, EarningsMarker } from '../../components/StockChart'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import { stockProfileApi, themeSetupApi, telegramIdeaApi, dataApi, stockNewsApi, catalystApi, tradeApi, financialApi } from '../../services/api'
import type { StockProfileData } from '../../services/api'
import type { PriceData } from '../../types/data'
import type { TelegramIdea } from '../../types/telegram_idea'
import { useMarketStatus } from '../../hooks/useMarketStatus'
import { useFeatureFlags } from '../../hooks/useFeatureFlags'
import { useRealtimePolling } from '../../hooks/useRealtimePolling'
import { useWatchlist } from '../../hooks/useWatchlist'
import FinancialTab from './FinancialTab'
import SignalScannerTab from './SignalScannerTab'
import CompanyOverviewCard from './CompanyOverviewCard'
import NarrativePanel from '../smart-scanner/NarrativePanel'
import { WatchlistStar } from '../../components/WatchlistStar'

// 목록 페이지에서 전달받는 컨텍스트 (이전/다음 네비게이션용)
export interface StockListContext {
  source: string
  stocks: { code: string; name: string }[]
  currentIndex: number
}

type TabId = 'chart' | 'flow' | 'narrative' | 'news' | 'mentions' | 'sentiment' | 'themes' | 'financial' | 'signal-scanner'

interface InvestorFlowData {
  flow_date: string
  foreign_net: number
  institution_net: number
  individual_net: number
  flow_score: number
}

const TABS: { id: TabId; label: string }[] = [
  { id: 'chart', label: '차트' },
  { id: 'narrative', label: '내러티브' },
  { id: 'news', label: '뉴스/재료' },
  { id: 'flow', label: '수급' },
  { id: 'financial', label: '재무' },
  { id: 'signal-scanner', label: '시그널스캐너' },
  { id: 'mentions', label: '멘션' },
  { id: 'sentiment', label: '감정/패턴' },
  { id: 'themes', label: '테마' },
]

export default function StockDetailPage() {
  const { stockCode } = useParams<{ stockCode: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const features = useFeatureFlags()

  // 목록 네비게이션 컨텍스트
  const listCtx = useMemo<StockListContext | null>(() => {
    const state = location.state as { stockListContext?: StockListContext } | null
    if (!state?.stockListContext) return null
    const ctx = state.stockListContext
    // currentIndex를 현재 stockCode 기준으로 재계산 (뒤로가기 등 대비)
    const idx = ctx.stocks.findIndex(s => s.code === stockCode)
    if (idx === -1) return null
    return { ...ctx, currentIndex: idx }
  }, [location.state, stockCode])

  const canGoPrev = listCtx !== null && listCtx.currentIndex > 0
  const canGoNext = listCtx !== null && listCtx.currentIndex < listCtx.stocks.length - 1

  const goToStock = useCallback((direction: 'prev' | 'next') => {
    if (!listCtx) return
    const newIndex = direction === 'prev' ? listCtx.currentIndex - 1 : listCtx.currentIndex + 1
    const target = listCtx.stocks[newIndex]
    if (!target) return
    navigate(`/stocks/${target.code}`, {
      state: { stockListContext: { ...listCtx, currentIndex: newIndex } },
      replace: true,
    })
  }, [listCtx, navigate])

  // 키보드: Ctrl+ArrowLeft/Right로 이전/다음
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === 'ArrowLeft' && canGoPrev) {
        e.preventDefault()
        goToStock('prev')
      }
      if (e.ctrlKey && e.key === 'ArrowRight' && canGoNext) {
        e.preventDefault()
        goToStock('next')
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [canGoPrev, canGoNext, goToStock])

  const [profile, setProfile] = useState<StockProfileData | null>(null)
  const [flowHistory, setFlowHistory] = useState<InvestorFlowData[]>([])
  const [ideas, setIdeas] = useState<TelegramIdea[]>([])
  const [activeTab, setActiveTab] = useState<TabId>('chart')
  const [loading, setLoading] = useState(true)
  const [livePrice, setLivePrice] = useState<PriceData | null>(null)
  const [showIdeaMarkers, setShowIdeaMarkers] = useState(true)
  const [showTradeMarkers, setShowTradeMarkers] = useState(true)
  const [showEarningsMarkers, setShowEarningsMarkers] = useState(true)
  const [tradeMarkers, setTradeMarkers] = useState<TradeMarker[]>([])
  const [earningsMarkers, setEarningsMarkers] = useState<EarningsMarker[]>([])
  const { isMarketOpen } = useMarketStatus()
  const { getWatchlistDate } = useWatchlist()

  // 실시간 가격 조회
  const fetchLivePrice = useCallback(async () => {
    if (!stockCode) return
    try {
      const data = await dataApi.getPrice(stockCode)
      setLivePrice(data)
    } catch {
      // 조용히 실패
    }
  }, [stockCode])

  // 초기 실시간 가격 로드
  useEffect(() => {
    fetchLivePrice()
  }, [fetchLivePrice])

  // 장중 60초 자동 갱신
  useRealtimePolling(fetchLivePrice, 60_000, { onlyMarketHours: true, enabled: !!stockCode })

  useEffect(() => {
    if (!stockCode) return

    const fetchData = async () => {
      setLoading(true)
      try {
        const [profileResult, flowResult, ideasResult, tradesResult, earningsResult] = await Promise.allSettled([
          stockProfileApi.getProfile(stockCode),
          themeSetupApi.getStockInvestorFlow(stockCode, 30),
          features.telegram
            ? telegramIdeaApi.list({ stock_code: stockCode, days: 30, limit: 10 })
            : Promise.resolve({ items: [], total: 0 }),
          tradeApi.getByStock(stockCode),
          financialApi.getEarningsDates(stockCode),
        ])

        if (profileResult.status === 'fulfilled') {
          setProfile(profileResult.value)
        }
        if (flowResult.status === 'fulfilled' && flowResult.value.history) {
          setFlowHistory(flowResult.value.history)
        }
        if (ideasResult.status === 'fulfilled') {
          setIdeas(ideasResult.value.items)
        }
        if (tradesResult.status === 'fulfilled' && tradesResult.value.trades) {
          setTradeMarkers(
            tradesResult.value.trades
              .filter((t: any) => t.trade_date && t.price)
              .map((t: any) => ({
                date: t.trade_date,
                price: t.price,
                quantity: t.quantity,
                trade_type: t.trade_type,
              }))
          )
        }
        // 재무제표 기반 실적발표일
        if (earningsResult.status === 'fulfilled' && Array.isArray(earningsResult.value)) {
          setEarningsMarkers(earningsResult.value)
        }
      } catch (err) {
        console.error('데이터 로드 실패:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [stockCode])

  if (!stockCode) {
    return <div className="text-center py-10 text-gray-500">종목 코드가 없습니다.</div>
  }

  const stockName = profile?.stock_info?.name || ''
  const themes = profile?.themes || []

  // 아이디어를 차트 마커로 변환
  const ideaMarkers = useMemo<IdeaMarker[]>(() => {
    return ideas.map(idea => ({
      date: idea.original_date.split('T')[0],
      source: idea.source_type as 'my' | 'others',
      author: idea.forward_from_name || undefined,
    }))
  }, [ideas])

  return (
    <div className="space-y-6">
      {/* 이전/다음 네비게이션 */}
      {listCtx && listCtx.stocks.length > 1 && (
        <div className="flex items-center justify-between bg-gray-50 dark:bg-t-bg-card rounded-lg px-3 py-2 border border-gray-200 dark:border-t-border">
          <button
            onClick={() => goToStock('prev')}
            disabled={!canGoPrev}
            className="flex items-center gap-1 px-2.5 py-1 text-sm font-medium rounded-md transition-colors
              disabled:opacity-30 disabled:cursor-not-allowed
              text-gray-700 dark:text-t-text-secondary hover:bg-gray-200 dark:hover:bg-t-bg-elevated"
          >
            <span>&#8592;</span> 이전
          </button>
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-t-text-muted">
            <span className="font-medium">{listCtx.currentIndex + 1}</span>
            <span>/</span>
            <span>{listCtx.stocks.length}</span>
            <span className="text-gray-400 dark:text-t-text-muted">({listCtx.source})</span>
          </div>
          <button
            onClick={() => goToStock('next')}
            disabled={!canGoNext}
            className="flex items-center gap-1 px-2.5 py-1 text-sm font-medium rounded-md transition-colors
              disabled:opacity-30 disabled:cursor-not-allowed
              text-gray-700 dark:text-t-text-secondary hover:bg-gray-200 dark:hover:bg-t-bg-elevated"
          >
            다음 <span>&#8594;</span>
          </button>
        </div>
      )}

      {/* 헤더 + 요약 */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <WatchlistStar stockCode={stockCode} stockName={stockName || stockCode} />
            <h1 className="text-2xl font-bold text-gray-900 dark:text-t-text-primary">
              {stockName || stockCode}
            </h1>
          </div>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-sm text-gray-500 dark:text-t-text-muted">{stockCode}</span>
            {profile?.stock_info?.market && (
              <Badge variant="default" size="sm">{profile.stock_info.market}</Badge>
            )}
            {livePrice ? (
              <>
                <span className="text-lg font-semibold text-gray-900 dark:text-t-text-primary">
                  {Number(livePrice.current_price).toLocaleString()}원
                </span>
                <span className={`text-sm font-medium ${Number(livePrice.change_rate) >= 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                  {Number(livePrice.change_rate) >= 0 ? '+' : ''}{Number(livePrice.change_rate).toFixed(2)}%
                </span>
                {isMarketOpen && (
                  <span className="inline-flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                    실시간
                  </span>
                )}
                {!isMarketOpen && <span className="text-xs text-gray-400 dark:text-t-text-muted">(장마감)</span>}
              </>
            ) : profile?.ohlcv?.has_data ? (
              <>
                <span className="text-lg font-semibold text-gray-900 dark:text-t-text-primary">
                  {profile.ohlcv.latest_price?.toLocaleString()}원
                </span>
                <span className={`text-sm font-medium ${(profile.ohlcv.change_rate || 0) >= 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                  {(profile.ohlcv.change_rate || 0) >= 0 ? '+' : ''}{profile.ohlcv.change_rate}%
                </span>
              </>
            ) : null}
          </div>
          {/* 실시간 고가/저가/시가/거래량 */}
          {livePrice && (
            <div className="flex items-center gap-3 mt-1 text-xs text-gray-500 dark:text-t-text-muted">
              <span>시가 {Number(livePrice.open_price).toLocaleString()}</span>
              <span>고가 <span className="text-red-500 dark:text-red-400">{Number(livePrice.high_price).toLocaleString()}</span></span>
              <span>저가 <span className="text-blue-500 dark:text-blue-400">{Number(livePrice.low_price).toLocaleString()}</span></span>
              <span>거래량 {Number(livePrice.volume).toLocaleString()}</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {themes.slice(0, 4).map((theme) => (
            <Link key={theme} to={`/emerging/${encodeURIComponent(theme)}`}>
              <Badge variant="info" size="sm">{theme}</Badge>
            </Link>
          ))}
        </div>
      </div>

      {/* 기업 프로필 */}
      <CompanyOverviewCard stockCode={stockCode} />

      {/* 빠른 요약 카드 */}
      {profile && !loading && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <MiniStat
            label="수급 (외국인)"
            value={profile.investor_flow.has_data ? `${profile.investor_flow.consecutive_foreign_buy || 0}일 연속` : '-'}
            sub={profile.investor_flow.has_data ? `총 ${(profile.investor_flow.foreign_net_total || 0).toLocaleString()}` : ''}
            positive={(profile.investor_flow.foreign_net_total || 0) > 0}
          />
          <MiniStat
            label="유튜브"
            value={`${profile.youtube_mentions.video_count}건`}
            sub={`${profile.youtube_mentions.period_days}일간`}
            highlight={profile.youtube_mentions.is_trending}
          />
          {features.expert && (
          <MiniStat
            label="전문가"
            value={`${profile.expert_mentions.total_mentions}건`}
            sub={`${profile.expert_mentions.period_days}일간`}
          />
          )}
          <MiniStat
            label="감정분석"
            value={profile.sentiment.analysis_count > 0 ? `${profile.sentiment.avg_score.toFixed(2)}` : '-'}
            sub={`${profile.sentiment.analysis_count}건`}
            positive={profile.sentiment.avg_score > 0}
          />
          <MiniStat
            label="공시"
            value={`${profile.disclosures.length}건`}
            sub="최근 30일"
          />
        </div>
      )}

      {/* 탭 네비게이션 */}
      <div className="border-b border-gray-200 dark:border-t-border">
        <nav className="flex gap-2 -mb-px">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-2 px-3 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-t-bg-elevated dark:bg-t-border rounded-lg text-primary-600 dark:text-primary-400 border-transparent'
                  : 'border-transparent text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* 탭 콘텐츠 */}
      {activeTab === 'chart' && (
        <Card>
          <CardContent className="p-4">
            {/* 차트 옵션 */}
            <div className="flex items-center justify-end gap-4 mb-2">
              {tradeMarkers.length > 0 && (
                <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-t-text-muted cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showTradeMarkers}
                    onChange={(e) => setShowTradeMarkers(e.target.checked)}
                    className="rounded border-gray-300 dark:border-t-border text-primary-600 focus:ring-primary-500"
                  />
                  매매 내역
                </label>
              )}
              {ideaMarkers.length > 0 && (
                <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-t-text-muted cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showIdeaMarkers}
                    onChange={(e) => setShowIdeaMarkers(e.target.checked)}
                    className="rounded border-gray-300 dark:border-t-border text-primary-600 focus:ring-primary-500"
                  />
                  아이디어
                </label>
              )}
              {earningsMarkers.length > 0 && (
                <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-t-text-muted cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showEarningsMarkers}
                    onChange={(e) => setShowEarningsMarkers(e.target.checked)}
                    className="rounded border-gray-300 dark:border-t-border text-pink-600 focus:ring-pink-500"
                  />
                  실적발표
                </label>
              )}
            </div>
            <StockChart
              stockCode={stockCode}
              stockName={stockName || stockCode}
              height={650}
              days={365}
              showHeader={false}
              showTimeframeSelector
              showMAToggle
              ideaMarkers={ideaMarkers}
              showIdeaMarkers={showIdeaMarkers}
              tradeMarkers={tradeMarkers}
              showTradeMarkers={showTradeMarkers}
              earningsMarkers={earningsMarkers}
              showEarningsMarkers={showEarningsMarkers}
              enableDrawing
              disableTradingViewLink
              watchlistStartDate={getWatchlistDate(stockCode)}
            />
          </CardContent>
        </Card>
      )}

      {activeTab === 'flow' && (
        <FlowTab flowHistory={flowHistory} loading={loading} />
      )}

      {activeTab === 'financial' && (
        <FinancialTab stockCode={stockCode} />
      )}

      {activeTab === 'narrative' && (
        <div className="bg-white dark:bg-t-bg-card rounded-xl border border-gray-200 dark:border-t-border p-5">
          <NarrativePanel stockCode={stockCode} />
        </div>
      )}

      {activeTab === 'signal-scanner' && (
        <SignalScannerTab stockCode={stockCode} />
      )}

      {activeTab === 'news' && (
        <StockNewsTab stockCode={stockCode} />
      )}

      {activeTab === 'mentions' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 유튜브 멘션 */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-gray-900 dark:text-t-text-primary">유튜브 언급</h2>
                {profile?.youtube_mentions.is_trending && (
                  <Badge variant="danger" size="sm">트렌딩</Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-center py-4">
                <div className="text-3xl font-bold text-gray-900 dark:text-t-text-primary">
                  {profile?.youtube_mentions.video_count || 0}
                </div>
                <div className="text-sm text-gray-500 dark:text-t-text-muted">
                  최근 {profile?.youtube_mentions.period_days || 14}일간 영상 수
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 전문가 멘션 */}
          {features.expert && (
          <Card>
            <CardHeader>
              <h2 className="font-semibold text-gray-900 dark:text-t-text-primary">전문가 언급</h2>
            </CardHeader>
            <CardContent>
              <div className="text-center py-4">
                <div className="text-3xl font-bold text-gray-900 dark:text-t-text-primary">
                  {profile?.expert_mentions.total_mentions || 0}
                </div>
                <div className="text-sm text-gray-500 dark:text-t-text-muted">
                  최근 {profile?.expert_mentions.period_days || 14}일간 총 언급
                </div>
              </div>
            </CardContent>
          </Card>
          )}

          {/* 텔레그램 아이디어 */}
          {features.telegram && (
          <Card className="lg:col-span-2">
            <CardHeader>
              <h2 className="font-semibold text-gray-900 dark:text-t-text-primary">텔레그램 아이디어</h2>
            </CardHeader>
            <CardContent>
              {ideas.length === 0 ? (
                <div className="text-center py-4 text-gray-500">관련 아이디어 없음</div>
              ) : (
                <div className="space-y-3 max-h-[400px] overflow-y-auto">
                  {ideas.map((idea) => (
                    <div key={idea.id} className="p-3 bg-gray-50 dark:bg-t-bg-elevated rounded-lg">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-gray-500 dark:text-t-text-muted">
                          {new Date(idea.original_date).toLocaleDateString()}
                        </span>
                        {idea.forward_from_name && (
                          <span className="text-xs text-gray-500 dark:text-t-text-muted">
                            {idea.forward_from_name}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-700 dark:text-t-text-secondary line-clamp-3">
                        {idea.message_text}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
          )}
        </div>
      )}

      {activeTab === 'sentiment' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 감정분석 */}
          <Card>
            <CardHeader>
              <h2 className="font-semibold text-gray-900 dark:text-t-text-primary">감정분석 요약</h2>
            </CardHeader>
            <CardContent>
              {!profile?.sentiment.analysis_count ? (
                <div className="text-center py-4 text-gray-500">감정분석 데이터 없음</div>
              ) : (
                <div className="space-y-4">
                  <div className="text-center py-4">
                    <div className={`text-4xl font-bold ${
                      profile.sentiment.avg_score > 0.3 ? 'text-red-600 dark:text-red-400' :
                      profile.sentiment.avg_score < -0.3 ? 'text-blue-600 dark:text-blue-400' :
                      'text-gray-600 dark:text-t-text-muted'
                    }`}>
                      {profile.sentiment.avg_score.toFixed(3)}
                    </div>
                    <div className="text-sm text-gray-500 dark:text-t-text-muted mt-1">
                      평균 감정 점수 ({profile.sentiment.analysis_count}건)
                    </div>
                    <div className="text-xs text-gray-400 dark:text-t-text-muted mt-1">
                      -1 (매우 부정) ~ +1 (매우 긍정)
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* 차트 패턴 */}
          <Card>
            <CardHeader>
              <h2 className="font-semibold text-gray-900 dark:text-t-text-primary">차트 패턴</h2>
            </CardHeader>
            <CardContent>
              {!profile?.chart_patterns.length ? (
                <div className="text-center py-4 text-gray-500">활성 차트 패턴 없음</div>
              ) : (
                <div className="space-y-3">
                  {profile.chart_patterns.map((pattern, i) => (
                    <div key={i} className="p-3 bg-gray-50 dark:bg-t-bg-elevated rounded-lg">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-gray-900 dark:text-t-text-primary">
                          {pattern.pattern_type || '알 수 없음'}
                        </span>
                        {pattern.confidence != null && (
                          <Badge variant={pattern.confidence >= 70 ? 'success' : 'warning'} size="sm">
                            {pattern.confidence.toFixed(0)}%
                          </Badge>
                        )}
                      </div>
                      {pattern.analysis_date && (
                        <div className="text-xs text-gray-500 dark:text-t-text-muted mt-1">
                          분석일: {pattern.analysis_date}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* 최근 공시 */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <h2 className="font-semibold text-gray-900 dark:text-t-text-primary">최근 공시</h2>
            </CardHeader>
            <CardContent>
              {!profile?.disclosures.length ? (
                <div className="text-center py-4 text-gray-500">최근 30일 공시 없음</div>
              ) : (
                <div className="space-y-2">
                  {profile.disclosures.map((d, i) => (
                    <div key={i} className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-t-border last:border-0">
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-gray-900 dark:text-t-text-primary truncate">{d.title}</div>
                        {d.type && <div className="text-xs text-gray-500 dark:text-t-text-muted">{d.type}</div>}
                      </div>
                      <span className="text-xs text-gray-500 dark:text-t-text-muted ml-4 flex-shrink-0">{d.date}</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'themes' && (
        <Card>
          <CardHeader>
            <h2 className="font-semibold text-gray-900 dark:text-t-text-primary">소속 테마</h2>
          </CardHeader>
          <CardContent>
            {themes.length === 0 ? (
              <div className="text-center py-4 text-gray-500">소속 테마 없음</div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {themes.map((theme) => (
                  <Link key={theme} to={`/emerging/${encodeURIComponent(theme)}`}>
                    <Badge variant="info" size="md">
                      {theme}
                    </Badge>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function MiniStat({
  label,
  value,
  sub,
  positive,
  highlight,
}: {
  label: string
  value: string
  sub?: string
  positive?: boolean
  highlight?: boolean
}) {
  return (
    <div className={`p-3 rounded-lg ${highlight ? 'bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800' : 'bg-gray-50 dark:bg-t-bg-card'}`}>
      <div className="text-xs text-gray-500 dark:text-t-text-muted">{label}</div>
      <div className={`text-sm font-semibold mt-0.5 ${
        positive === true ? 'text-red-600 dark:text-red-400' :
        positive === false ? 'text-blue-600 dark:text-blue-400' :
        'text-gray-900 dark:text-t-text-primary'
      }`}>
        {value}
      </div>
      {sub && <div className="text-xs text-gray-400 dark:text-t-text-muted">{sub}</div>}
    </div>
  )
}

// 수량 포맷 함수
function formatQty(qty: number): string {
  const sign = qty >= 0 ? '+' : ''
  const abs = Math.abs(qty)
  if (abs >= 10000) {
    return `${sign}${(qty / 10000).toFixed(1)}만`
  }
  return `${sign}${qty.toLocaleString()}`
}

// 수급 탭 컴포넌트
function FlowTab({ flowHistory, loading }: { flowHistory: InvestorFlowData[]; loading: boolean }) {
  if (loading) {
    return <div className="text-center py-10 text-gray-500 dark:text-t-text-muted">로딩 중...</div>
  }

  if (flowHistory.length === 0) {
    return <div className="text-center py-10 text-gray-500 dark:text-t-text-muted">수급 데이터 없음</div>
  }

  // 기간별 합계 계산
  const calcSum = (days: number) => {
    const slice = flowHistory.slice(0, days)
    return {
      foreign: slice.reduce((sum, f) => sum + f.foreign_net, 0),
      institution: slice.reduce((sum, f) => sum + f.institution_net, 0),
      individual: slice.reduce((sum, f) => sum + f.individual_net, 0),
    }
  }

  const sum5 = calcSum(5)
  const sum10 = calcSum(10)
  const sum20 = calcSum(20)

  // 연속 순매수일 계산
  const calcConsecutive = (type: 'foreign' | 'institution') => {
    let count = 0
    for (const f of flowHistory) {
      const val = type === 'foreign' ? f.foreign_net : f.institution_net
      if (val > 0) count++
      else break
    }
    return count
  }

  const foreignConsec = calcConsecutive('foreign')
  const instConsec = calcConsecutive('institution')

  // 막대 차트용 최대값
  const maxVal = Math.max(
    ...flowHistory.slice(0, 20).flatMap(f => [
      Math.abs(f.foreign_net),
      Math.abs(f.institution_net),
    ])
  )

  return (
    <div className="space-y-4">
      {/* 요약 카드 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* 연속 순매수일 */}
        <Card className="bg-gradient-to-br from-red-50 to-orange-50 dark:from-red-900/20 dark:to-orange-900/20 border-red-200 dark:border-red-800/50">
          <CardContent className="p-4 text-center">
            <div className="text-xs text-gray-500 dark:text-t-text-muted mb-1">외국인 연속</div>
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {foreignConsec > 0 ? `${foreignConsec}일` : '-'}
            </div>
            <div className="text-xs text-gray-500 dark:text-t-text-muted">순매수</div>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 border-blue-200 dark:border-blue-800/50">
          <CardContent className="p-4 text-center">
            <div className="text-xs text-gray-500 dark:text-t-text-muted mb-1">기관 연속</div>
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {instConsec > 0 ? `${instConsec}일` : '-'}
            </div>
            <div className="text-xs text-gray-500 dark:text-t-text-muted">순매수</div>
          </CardContent>
        </Card>
        {/* 외국인+기관 5일 합계 */}
        <Card className="lg:col-span-2">
          <CardContent className="p-4">
            <div className="text-xs text-gray-500 dark:text-t-text-muted mb-2">외+기 5일 합계</div>
            <div className="flex items-center gap-4">
              <div className={`text-xl font-bold ${sum5.foreign + sum5.institution >= 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                {formatQty(sum5.foreign + sum5.institution)}
              </div>
              <div className="flex-1 h-2 bg-gray-200 dark:bg-t-bg-elevated rounded-full overflow-hidden">
                {(() => {
                  const total = sum5.foreign + sum5.institution
                  const pct = Math.min(100, Math.abs(total) / (maxVal * 5) * 100)
                  return (
                    <div
                      className={`h-full ${total >= 0 ? 'bg-red-500' : 'bg-blue-500'}`}
                      style={{ width: `${pct}%` }}
                    />
                  )
                })()}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 기간별 비교 테이블 */}
      <Card>
        <CardContent className="p-4">
          <h3 className="text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-3">기간별 수급 비교</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b dark:border-t-border">
                  <th className="text-left py-2 px-3 font-medium text-gray-600 dark:text-t-text-muted">기간</th>
                  <th className="text-right py-2 px-3 font-medium text-gray-600 dark:text-t-text-muted">외국인</th>
                  <th className="text-right py-2 px-3 font-medium text-gray-600 dark:text-t-text-muted">기관</th>
                  <th className="text-right py-2 px-3 font-medium text-gray-600 dark:text-t-text-muted">개인</th>
                  <th className="text-right py-2 px-3 font-medium text-gray-600 dark:text-t-text-muted">외+기 합계</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { label: '5일', data: sum5 },
                  { label: '10일', data: sum10 },
                  { label: '20일', data: sum20 },
                ].map(({ label, data }) => (
                  <tr key={label} className="border-b dark:border-t-border last:border-0 hover:bg-gray-50 dark:hover:bg-t-bg-card/50">
                    <td className="py-2.5 px-3 font-medium text-gray-900 dark:text-t-text-primary">{label}</td>
                    <td className={`py-2.5 px-3 text-right font-medium ${data.foreign >= 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                      {formatQty(data.foreign)}
                    </td>
                    <td className={`py-2.5 px-3 text-right font-medium ${data.institution >= 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                      {formatQty(data.institution)}
                    </td>
                    <td className={`py-2.5 px-3 text-right ${data.individual >= 0 ? 'text-red-500 dark:text-red-300' : 'text-blue-500 dark:text-blue-300'}`}>
                      {formatQty(data.individual)}
                    </td>
                    <td className={`py-2.5 px-3 text-right font-bold ${data.foreign + data.institution >= 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                      {formatQty(data.foreign + data.institution)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* 누적 수급 추이 그래프 */}
      <Card>
        <CardContent className="p-4">
          <h3 className="text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-3">누적 수급 추이 (외+기)</h3>
          <CumulativeFlowChart flowHistory={flowHistory.slice(0, 20)} />
        </CardContent>
      </Card>

      {/* 일별 막대 + 상세 테이블 (반반) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 일별 수급 막대 차트 */}
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-3">일별 수급</h3>
            <div className="space-y-1">
              {flowHistory.slice(0, 15).map((flow) => {
                const foreignPct = maxVal ? (flow.foreign_net / maxVal) * 50 : 0
                const instPct = maxVal ? (flow.institution_net / maxVal) * 50 : 0
                const total = flow.foreign_net + flow.institution_net

                return (
                  <div key={flow.flow_date} className="flex items-center gap-1.5">
                    <div className="w-12 text-xs text-gray-500 dark:text-t-text-muted shrink-0">
                      {flow.flow_date.slice(5)}
                    </div>
                    <div className="flex-1 flex items-center h-4 relative">
                      <div className="absolute left-1/2 w-px h-full bg-gray-300 dark:bg-t-border" />
                      <div className="w-1/2 flex justify-end pr-0.5">
                        {foreignPct !== 0 && (
                          <div
                            className={`h-2.5 rounded-sm ${flow.foreign_net >= 0 ? 'bg-red-400 dark:bg-red-500' : 'bg-blue-400 dark:bg-blue-500'}`}
                            style={{ width: `${Math.abs(foreignPct)}%`, minWidth: '2px' }}
                          />
                        )}
                      </div>
                      <div className="w-1/2 flex justify-start pl-0.5">
                        {instPct !== 0 && (
                          <div
                            className={`h-2.5 rounded-sm ${flow.institution_net >= 0 ? 'bg-orange-400 dark:bg-orange-500' : 'bg-indigo-400 dark:bg-indigo-500'}`}
                            style={{ width: `${Math.abs(instPct)}%`, minWidth: '2px' }}
                          />
                        )}
                      </div>
                    </div>
                    <div className={`w-14 text-right text-xs font-medium ${total >= 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                      {formatQty(total)}
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="flex items-center justify-center gap-3 mt-3 pt-2 border-t dark:border-t-border text-xs text-gray-500 dark:text-t-text-muted">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-sm bg-red-400" /> 외 매수
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-sm bg-blue-400" /> 외 매도
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-sm bg-orange-400" /> 기 매수
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-sm bg-indigo-400" /> 기 매도
              </span>
            </div>
          </CardContent>
        </Card>

        {/* 일별 상세 테이블 */}
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-3">일별 상세</h3>
            <div className="overflow-x-auto max-h-[280px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white dark:bg-t-bg">
                  <tr className="border-b dark:border-t-border">
                    <th className="text-left py-1.5 px-1.5 font-medium text-gray-600 dark:text-t-text-muted text-xs">날짜</th>
                    <th className="text-right py-1.5 px-1.5 font-medium text-gray-600 dark:text-t-text-muted text-xs">외국인</th>
                    <th className="text-right py-1.5 px-1.5 font-medium text-gray-600 dark:text-t-text-muted text-xs">기관</th>
                    <th className="text-right py-1.5 px-1.5 font-medium text-gray-600 dark:text-t-text-muted text-xs">개인</th>
                    <th className="text-right py-1.5 px-1.5 font-medium text-gray-600 dark:text-t-text-muted text-xs">외+기</th>
                  </tr>
                </thead>
                <tbody>
                  {flowHistory.map((flow) => {
                    const total = flow.foreign_net + flow.institution_net
                    return (
                      <tr key={flow.flow_date} className="border-b dark:border-t-border last:border-0 hover:bg-gray-50 dark:hover:bg-t-bg-card/50">
                        <td className="py-1.5 px-1.5 text-gray-600 dark:text-t-text-muted text-xs">{flow.flow_date.slice(5)}</td>
                        <td className={`py-1.5 px-1.5 text-right text-xs font-medium ${flow.foreign_net >= 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                          {formatQty(flow.foreign_net)}
                        </td>
                        <td className={`py-1.5 px-1.5 text-right text-xs font-medium ${flow.institution_net >= 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                          {formatQty(flow.institution_net)}
                        </td>
                        <td className={`py-1.5 px-1.5 text-right text-xs ${flow.individual_net >= 0 ? 'text-red-500 dark:text-red-300' : 'text-blue-500 dark:text-blue-300'}`}>
                          {formatQty(flow.individual_net)}
                        </td>
                        <td className={`py-1.5 px-1.5 text-right text-xs font-bold ${total >= 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
                          {formatQty(total)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

// 누적 수급 선형 그래프 컴포넌트
function CumulativeFlowChart({ flowHistory }: { flowHistory: InvestorFlowData[] }) {
  // 역순 (오래된 것부터)으로 누적 계산
  const reversed = [...flowHistory].reverse()
  let cumulative = 0
  const data = reversed.map((f, i) => {
    cumulative += f.foreign_net + f.institution_net
    return { index: i, date: f.flow_date, value: cumulative }
  })

  if (data.length === 0) return null

  const minVal = Math.min(...data.map(d => d.value))
  const maxVal = Math.max(...data.map(d => d.value))
  const range = maxVal - minVal || 1
  const height = 100
  const width = 100

  // SVG path 생성
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1 || 1)) * width
    const y = height - ((d.value - minVal) / range) * height
    return `${x},${y}`
  })
  const pathD = `M ${points.join(' L ')}`

  // 제로 라인 위치
  const zeroY = height - ((0 - minVal) / range) * height

  // 최종 값
  const finalValue = data[data.length - 1]?.value || 0

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-24" preserveAspectRatio="none">
        {/* 제로 라인 */}
        <line
          x1="0" y1={zeroY} x2={width} y2={zeroY}
          stroke="currentColor"
          strokeWidth="0.5"
          className="text-gray-300 dark:text-t-text-muted"
          strokeDasharray="2,2"
        />
        {/* 누적 라인 */}
        <path
          d={pathD}
          fill="none"
          stroke={finalValue >= 0 ? '#ef4444' : '#3b82f6'}
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
        {/* 영역 채우기 */}
        <path
          d={`${pathD} L ${width},${zeroY} L 0,${zeroY} Z`}
          fill={finalValue >= 0 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(59, 130, 246, 0.1)'}
        />
      </svg>
      {/* 라벨 */}
      <div className="flex justify-between text-xs text-gray-500 dark:text-t-text-muted mt-1">
        <span>{reversed[0]?.flow_date.slice(5)}</span>
        <span className={`font-medium ${finalValue >= 0 ? 'text-red-600 dark:text-red-400' : 'text-blue-600 dark:text-blue-400'}`}>
          누적: {formatQty(finalValue)}
        </span>
        <span>{reversed[reversed.length - 1]?.flow_date.slice(5)}</span>
      </div>
    </div>
  )
}

// 종목 뉴스/카탈리스트 탭
import type { StockNewsItem, CatalystEvent as CatalystEventType, CatalystSummary } from '../../types/catalyst'
import { CATALYST_TYPE_LABELS } from '../../types/catalyst'

function StockNewsTab({ stockCode }: { stockCode: string }) {
  const [news, setNews] = useState<StockNewsItem[]>([])
  const [catalysts, setCatalysts] = useState<CatalystEventType[]>([])
  const [summary, setSummary] = useState<CatalystSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetch = async () => {
      setLoading(true)
      try {
        const [newsData, catalystData, summaryData] = await Promise.allSettled([
          stockNewsApi.getStockNews(stockCode, 14, 30),
          catalystApi.getStockCatalysts(stockCode),
          stockNewsApi.getCatalystSummary(stockCode, 14),
        ])
        if (newsData.status === 'fulfilled') setNews(newsData.value)
        if (catalystData.status === 'fulfilled') setCatalysts(catalystData.value)
        if (summaryData.status === 'fulfilled') setSummary(summaryData.value)
      } catch {}
      setLoading(false)
    }
    fetch()
  }, [stockCode])

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* 재료 요약 */}
      <div className="lg:col-span-1 space-y-4">
        {summary && (
          <Card>
            <CardHeader>
              <h3 className="font-semibold text-gray-900 dark:text-t-text-primary text-sm">재료 요약 (14일)</h3>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-gray-900 dark:text-t-text-primary mb-2">
                {summary.total_count}건
              </div>
              <div className="space-y-1">
                {Object.entries(summary.type_counts).map(([type, count]) => (
                  <div key={type} className="flex justify-between text-sm">
                    <span className="text-gray-600 dark:text-t-text-secondary">
                      {CATALYST_TYPE_LABELS[type] || type}
                    </span>
                    <span className="font-medium text-gray-900 dark:text-t-text-primary">{count}</span>
                  </div>
                ))}
              </div>
              {summary.important_news.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-100 dark:border-t-border">
                  <div className="text-xs font-medium text-gray-500 dark:text-t-text-muted mb-1">주요 뉴스</div>
                  {summary.important_news.map((n, i) => (
                    <a
                      key={i}
                      href={n.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block text-xs text-blue-600 dark:text-blue-400 hover:underline truncate mb-0.5"
                    >
                      {n.title}
                    </a>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* 카탈리스트 이벤트 */}
        {catalysts.length > 0 && (
          <Card>
            <CardHeader>
              <h3 className="font-semibold text-gray-900 dark:text-t-text-primary text-sm">카탈리스트 이력</h3>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {catalysts.map((c) => (
                  <div key={c.id} className="p-2 rounded-lg bg-gray-50 dark:bg-t-bg">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`text-[10px] px-1 py-0.5 rounded ${
                        c.status === 'active' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                        c.status === 'weakening' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' :
                        'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                      }`}>
                        {c.status === 'active' ? '진행' : c.status === 'weakening' ? '약화' : '만료'}
                      </span>
                      <span className="text-[10px] text-gray-400">{c.event_date}</span>
                    </div>
                    <div className="text-xs text-gray-700 dark:text-t-text-secondary truncate">{c.title}</div>
                    {c.current_return != null && (
                      <div className={`text-xs mt-0.5 ${c.current_return >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        수익률 {c.current_return > 0 ? '+' : ''}{c.current_return.toFixed(1)}%
                        {c.max_return != null && <span className="text-gray-400"> (max +{c.max_return.toFixed(1)}%)</span>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* 최근 뉴스 리스트 */}
      <div className="lg:col-span-2">
        <Card>
          <CardHeader>
            <h3 className="font-semibold text-gray-900 dark:text-t-text-primary text-sm">최근 뉴스 ({news.length}건)</h3>
          </CardHeader>
          <CardContent>
            {news.length === 0 ? (
              <div className="text-center py-8 text-gray-400 dark:text-t-text-muted text-sm">수집된 뉴스가 없습니다</div>
            ) : (
              <div className="space-y-1.5">
                {news.map((n) => (
                  <a
                    key={n.id}
                    href={n.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-t-border/30 transition-colors group"
                  >
                    <div className="flex items-start gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-gray-800 dark:text-t-text-primary group-hover:text-blue-600 dark:group-hover:text-blue-400 line-clamp-1">
                          {n.title}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5 text-[11px] text-gray-400">
                          <span>{n.source || '뉴스'}</span>
                          <span>{new Date(n.published_at).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                          {n.catalyst_type && (
                            <span className="px-1 py-0.5 bg-gray-100 dark:bg-t-border rounded text-[10px]">
                              {CATALYST_TYPE_LABELS[n.catalyst_type] || n.catalyst_type}
                            </span>
                          )}
                          {n.importance === 'high' && (
                            <span className="px-1 py-0.5 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded text-[10px] font-medium">
                              중요
                            </span>
                          )}
                          {n.is_quality && (
                            <span className="text-amber-500 text-[10px]">*</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
