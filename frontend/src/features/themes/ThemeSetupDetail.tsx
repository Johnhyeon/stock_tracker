import React, { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { themeSetupApi, themeApi } from '../../services/api'
import { useFeatureFlags } from '../../hooks/useFeatureFlags'
import { Card } from '../../components/ui/Card'
import { StockChart } from '../../components/StockChart'
import type {
  ThemeSetupDetail as ThemeSetupDetailType,
  ChartPattern,
  NewsTrendItem,
  ThemeNewsItem,
} from '../../types/theme_setup'
import { PATTERN_TYPE_LABELS, PATTERN_TYPE_COLORS } from '../../types/theme_setup'

// localStorage 키
const HIDDEN_STOCKS_KEY = 'hiddenStocks'

// 숨긴 종목 관리 훅
function useHiddenStocks() {
  const [hiddenStocks, setHiddenStocks] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(HIDDEN_STOCKS_KEY)
      return new Set(saved ? JSON.parse(saved) : [])
    } catch {
      return new Set()
    }
  })

  const hideStock = useCallback((stockCode: string) => {
    setHiddenStocks(prev => {
      const next = new Set(prev)
      next.add(stockCode)
      localStorage.setItem(HIDDEN_STOCKS_KEY, JSON.stringify([...next]))
      return next
    })
  }, [])

  const showStock = useCallback((stockCode: string) => {
    setHiddenStocks(prev => {
      const next = new Set(prev)
      next.delete(stockCode)
      localStorage.setItem(HIDDEN_STOCKS_KEY, JSON.stringify([...next]))
      return next
    })
  }, [])

  const showAllStocks = useCallback(() => {
    setHiddenStocks(new Set())
    localStorage.removeItem(HIDDEN_STOCKS_KEY)
  }, [])

  const isHidden = useCallback((stockCode: string) => hiddenStocks.has(stockCode), [hiddenStocks])

  return { hiddenStocks, hideStock, showStock, showAllStocks, isHidden, hiddenCount: hiddenStocks.size }
}

// 수급 수량 포맷 (만주 단위)
function formatFlowQty(qty: number): string {
  const sign = qty >= 0 ? '+' : ''
  const abs = Math.abs(qty)
  if (abs >= 10000) {
    return `${sign}${(qty / 10000).toFixed(1)}만`
  }
  return `${sign}${qty.toLocaleString()}`
}

interface ThemeStock {
  code: string
  name: string
}

export default function ThemeSetupDetail() {
  const { themeName } = useParams<{ themeName: string }>()
  const navigate = useNavigate()
  const features = useFeatureFlags()
  const [detail, setDetail] = useState<ThemeSetupDetailType | null>(null)
  const [patterns, setPatterns] = useState<ChartPattern[]>([])
  const [newsTrend, setNewsTrend] = useState<NewsTrendItem[]>([])
  const [recentNews, setRecentNews] = useState<ThemeNewsItem[]>([])
  const [allStocks, setAllStocks] = useState<ThemeStock[]>([])
  const [investorFlow, setInvestorFlow] = useState<{
    summary: {
      foreign_net_sum: number
      institution_net_sum: number
      positive_foreign: number
      positive_institution: number
      total_stocks: number
      avg_flow_score: number
    }
    stocks: Array<{
      stock_code: string
      stock_name: string
      flow_date: string
      foreign_net: number
      institution_net: number
      individual_net: number
      flow_score: number
    }>
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'patterns' | 'charts' | 'news' | 'flow' | 'history'>('patterns')
  const [selectedFlowStock, setSelectedFlowStock] = useState<string | null>(null)
  const [stockFlowHistory, setStockFlowHistory] = useState<Array<{
    flow_date: string
    foreign_net: number
    institution_net: number
    individual_net: number
    flow_score: number
  }>>([])
  const [flowHistoryLoading, setFlowHistoryLoading] = useState(false)
  const [showHiddenStocks, setShowHiddenStocks] = useState(false)

  // 숨긴 종목 관리
  const { hideStock, showStock, showAllStocks, isHidden, hiddenCount } = useHiddenStocks()

  useEffect(() => {
    if (themeName) {
      fetchData()
    }
  }, [themeName])

  const fetchData = async () => {
    if (!themeName) return

    setLoading(true)
    setError(null)

    try {
      const results = await Promise.allSettled([
        themeSetupApi.getDetail(themeName),
        themeSetupApi.getPatterns(themeName),
        themeSetupApi.getNewsTrend(themeName, 14),
        themeSetupApi.getRecentNews(themeName, 10),
        themeApi.getThemeStocks(themeName),
        themeSetupApi.getInvestorFlow(themeName, 5),
      ])

      // detail이 없으면 기본값 사용 (셋업 미계산 테마)
      const detailResult = results[0].status === 'fulfilled' ? results[0].value : null
      const patternsResult = results[1].status === 'fulfilled' ? results[1].value : []
      const trendResult = results[2].status === 'fulfilled' ? results[2].value : []
      const newsResult = results[3].status === 'fulfilled' ? results[3].value : { news: [] }
      const stocksResult = results[4].status === 'fulfilled' ? results[4].value : { stocks: [] }
      const flowResult = results[5].status === 'fulfilled' ? results[5].value : null

      // detail이 없으면 테마맵 기반 기본값 생성
      setDetail(detailResult ?? {
        theme_name: themeName,
        rank: 0,
        total_score: 0,
        news_momentum_score: 0,
        chart_pattern_score: 0,
        mention_score: 0,
        price_action_score: 0,
        investor_flow_score: 0,
        top_stocks: [],
        stocks_with_pattern: 0,
        total_stocks: stocksResult.stocks?.length ?? 0,
        is_emerging: 0,
        setup_date: '-',
        score_breakdown: {
          news: { score: 0 },
          chart: { score: 0 },
          mention: { score: 0 },
          price: { score: 0 },
          flow: { score: 0 },
        },
        history: [],
      })
      setPatterns(patternsResult)
      setNewsTrend(trendResult)
      setRecentNews(newsResult.news)
      setAllStocks(stocksResult.stocks || [])
      if (flowResult) {
        setInvestorFlow({ summary: flowResult.summary, stocks: flowResult.stocks })
      }
    } catch (err) {
      setError('테마 셋업 상세 정보를 불러오는데 실패했습니다.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleStockFlowClick = async (stockCode: string) => {
    if (selectedFlowStock === stockCode) {
      // 이미 선택된 종목 클릭 시 닫기
      setSelectedFlowStock(null)
      setStockFlowHistory([])
      return
    }

    setSelectedFlowStock(stockCode)
    setFlowHistoryLoading(true)

    try {
      const result = await themeSetupApi.getStockInvestorFlow(stockCode, 30)
      setStockFlowHistory(result.history)
    } catch (err) {
      console.error('수급 히스토리 로드 실패:', err)
      setStockFlowHistory([])
    } finally {
      setFlowHistoryLoading(false)
    }
  }

  const getScoreColor = (score: number): string => {
    if (score >= 70) return 'text-red-500'
    if (score >= 50) return 'text-orange-500'
    if (score >= 35) return 'text-yellow-600'
    return 'text-gray-500 dark:text-t-text-muted'
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Card className="p-8 text-center">
          <div className="animate-pulse">
            <div className="h-6 bg-gray-200 dark:bg-t-border rounded w-1/3 mx-auto mb-4"></div>
            <div className="h-4 bg-gray-200 dark:bg-t-border rounded w-1/2 mx-auto"></div>
          </div>
        </Card>
      </div>
    )
  }

  if (error || !detail) {
    return (
      <div className="space-y-6">
        <Card className="p-8 text-center">
          <p className="text-red-500">{error || '데이터를 찾을 수 없습니다.'}</p>
          <button
            onClick={() => navigate('/emerging')}
            className="mt-4 text-blue-500 hover:underline"
          >
            &larr; 목록으로 돌아가기
          </button>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => navigate('/emerging')}
            className="text-sm text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary dark:text-t-text-secondary mb-2"
          >
            &larr; 이머징 테마 목록
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{detail.theme_name}</h1>
            {detail.is_emerging === 1 && (
              <span className="px-2 py-1 text-xs bg-orange-100 text-orange-700 rounded">
                Emerging
              </span>
            )}
            <span className="text-gray-400">#{detail.rank}</span>
          </div>
          <p className="text-sm text-gray-500 dark:text-t-text-muted mt-1">
            {detail.total_stocks}개 종목 중 {detail.stocks_with_pattern}개 패턴 감지 |
            분석일: {detail.setup_date}
          </p>
        </div>
        <div className="text-right">
          <div className={`text-4xl font-bold ${getScoreColor(detail.total_score)}`}>
            {detail.total_score.toFixed(1)}
          </div>
          <div className="text-sm text-gray-400">셋업 점수</div>
        </div>
      </div>

      {/* 점수 breakdown */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card className="p-3 border-l-4 border-blue-400">
          <p className="text-xs text-gray-500 dark:text-t-text-muted">뉴스</p>
          <p className="text-xl font-bold text-blue-600">{detail.news_momentum_score.toFixed(1)}</p>
          <p className="text-xs text-gray-400">/25점</p>
          {detail.score_breakdown?.news && (
            <div className="mt-1 text-xs text-gray-500 dark:text-t-text-muted space-y-0.5">
              <p>7일: {detail.score_breakdown.news['7d_count'] || 0}건</p>
              <p>WoW: {detail.score_breakdown.news.wow_change || 0}%</p>
            </div>
          )}
        </Card>
        <Card className="p-3 border-l-4 border-green-400">
          <p className="text-xs text-gray-500 dark:text-t-text-muted">차트</p>
          <p className="text-xl font-bold text-green-600">{detail.chart_pattern_score.toFixed(1)}</p>
          <p className="text-xs text-gray-400">/30점</p>
          {detail.score_breakdown?.chart && (
            <div className="mt-1 text-xs text-gray-500 dark:text-t-text-muted space-y-0.5">
              <p>비율: {((detail.score_breakdown.chart.pattern_ratio || 0) * 100).toFixed(0)}%</p>
              <p>신뢰도: {detail.score_breakdown.chart.avg_confidence?.toFixed(0) || 0}%</p>
            </div>
          )}
        </Card>
        <Card className="p-3 border-l-4 border-purple-400">
          <p className="text-xs text-gray-500 dark:text-t-text-muted">언급</p>
          <p className="text-xl font-bold text-purple-600">{detail.mention_score.toFixed(1)}</p>
          <p className="text-xs text-gray-400">/20점</p>
          {detail.score_breakdown?.mention && (
            <div className="mt-1 text-xs text-gray-500 dark:text-t-text-muted space-y-0.5">
              <p>YT: {detail.score_breakdown.mention.youtube_count || 0}개</p>
              {features.expert && <p>전문가: {detail.score_breakdown.mention.expert_count || 0}회</p>}
            </div>
          )}
        </Card>
        <Card className="p-3 border-l-4 border-cyan-400">
          <p className="text-xs text-gray-500 dark:text-t-text-muted">수급</p>
          <p className="text-xl font-bold text-cyan-600">{(detail.investor_flow_score || 0).toFixed(1)}</p>
          <p className="text-xs text-gray-400">/15점</p>
          {detail.score_breakdown?.flow && (
            <div className="mt-1 text-xs text-gray-500 dark:text-t-text-muted space-y-0.5">
              <p>외인: {detail.score_breakdown.flow.positive_foreign || 0}/{detail.score_breakdown.flow.total_stocks || 0}</p>
              <p>기관: {detail.score_breakdown.flow.positive_institution || 0}/{detail.score_breakdown.flow.total_stocks || 0}</p>
            </div>
          )}
        </Card>
        <Card className="p-3 border-l-4 border-orange-400">
          <p className="text-xs text-gray-500 dark:text-t-text-muted">가격</p>
          <p className="text-xl font-bold text-orange-600">{detail.price_action_score.toFixed(1)}</p>
          <p className="text-xs text-gray-400">/10점</p>
          {detail.score_breakdown?.price && (
            <div className="mt-1 text-xs text-gray-500 dark:text-t-text-muted space-y-0.5">
              <p>등락: {detail.score_breakdown.price.avg_change?.toFixed(2) || 0}%</p>
            </div>
          )}
        </Card>
      </div>

      {/* 탭 */}
      <div className="flex gap-2 border-b border-gray-200 dark:border-t-border">
        <button
          onClick={() => setActiveTab('patterns')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'patterns'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary dark:text-t-text-secondary'
          }`}
        >
          차트 패턴 ({patterns.length})
        </button>
        <button
          onClick={() => setActiveTab('charts')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'charts'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary dark:text-t-text-secondary'
          }`}
        >
          차트 비교
        </button>
        <button
          onClick={() => setActiveTab('news')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'news'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary dark:text-t-text-secondary'
          }`}
        >
          뉴스 추이
        </button>
        <button
          onClick={() => setActiveTab('flow')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'flow'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary dark:text-t-text-secondary'
          }`}
        >
          수급 현황
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'history'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary dark:text-t-text-secondary'
          }`}
        >
          히스토리
        </button>
      </div>

      {/* 탭 컨텐츠 */}
      {activeTab === 'patterns' && (
        <div className="space-y-4">
          {patterns.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {patterns.map((pattern) => (
                <ChartPatternCard key={pattern.stock_code} pattern={pattern} />
              ))}
            </div>
          ) : (
            <Card className="p-8 text-center text-gray-500 dark:text-t-text-muted">
              감지된 패턴이 없습니다.
            </Card>
          )}
        </div>
      )}

      {activeTab === 'charts' && (
        <div className="space-y-4">
          {allStocks.length > 0 ? (
            <>
              {/* 헤더 */}
              <div className="flex items-center justify-between">
                <p className="text-sm text-gray-500 dark:text-t-text-muted">
                  {detail.theme_name} 테마 전체 종목 차트 ({allStocks.length}개)
                </p>
                <div className="flex items-center gap-3">
                  {hiddenCount > 0 && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setShowHiddenStocks(!showHiddenStocks)}
                        className="text-xs text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary dark:text-t-text-secondary"
                      >
                        숨긴 종목 {hiddenCount}개 {showHiddenStocks ? '접기' : '보기'}
                      </button>
                      <button
                        onClick={showAllStocks}
                        className="text-xs text-blue-500 hover:underline"
                      >
                        전체 복원
                      </button>
                    </div>
                  )}
                  <p className="text-xs text-gray-400">
                    KIS API | 90일 캔들 차트
                  </p>
                </div>
              </div>

              {/* 숨긴 종목 표시 */}
              {showHiddenStocks && hiddenCount > 0 && (
                <Card className="p-3 bg-gray-50 dark:bg-t-bg-elevated">
                  <p className="text-xs text-gray-500 dark:text-t-text-muted mb-2">숨긴 종목 (클릭하여 복원)</p>
                  <div className="flex flex-wrap gap-2">
                    {allStocks.filter(s => isHidden(s.code)).map(stock => (
                      <button
                        key={stock.code}
                        onClick={() => showStock(stock.code)}
                        className="px-2 py-1 text-xs bg-white dark:bg-t-bg-card border border-gray-200 dark:border-t-border rounded hover:bg-blue-50 dark:hover:bg-blue-900/30 dark:bg-blue-900/20 hover:border-blue-300 dark:hover:border-blue-700"
                      >
                        {stock.name} ({stock.code})
                      </button>
                    ))}
                  </div>
                </Card>
              )}

              {/* 언급된 종목 (패턴 감지된 종목) */}
              {(() => {
                const mentionedCodes = new Set(patterns.map(p => p.stock_code))
                const mentionedStocks = allStocks.filter(s => mentionedCodes.has(s.code) && !isHidden(s.code))
                const otherStocks = allStocks.filter(s => !mentionedCodes.has(s.code) && !isHidden(s.code))

                return (
                  <>
                    {mentionedStocks.length > 0 && (
                      <>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-green-600">
                            패턴 감지 종목 ({mentionedStocks.length}개)
                          </span>
                          <span className="text-xs text-gray-400">
                            YouTube/전문가 언급 + 차트 패턴 감지
                          </span>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                          {mentionedStocks.map((stock) => {
                            const patternInfo = patterns.find((p) => p.stock_code === stock.code)
                            return (
                              <Card key={stock.code} className="p-3 border-l-4 border-green-400 relative group">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    hideStock(stock.code)
                                  }}
                                  className="absolute top-2 right-2 z-10 p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:bg-red-900/20 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                                  title="차트 숨기기"
                                >
                                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                                  </svg>
                                </button>
                                <StockChart
                                  stockCode={stock.code}
                                  stockName={stock.name}
                                  patternType={
                                    patternInfo
                                      ? PATTERN_TYPE_LABELS[patternInfo.pattern_type] || patternInfo.pattern_type
                                      : undefined
                                  }
                                  height={250}
                                  days={180}
                                />
                              </Card>
                            )
                          })}
                        </div>
                      </>
                    )}

                    {/* 구분선 */}
                    {mentionedStocks.length > 0 && otherStocks.length > 0 && (
                      <div className="relative py-4">
                        <div className="absolute inset-0 flex items-center">
                          <div className="w-full border-t-2 border-gray-300 dark:border-t-border border-dashed"></div>
                        </div>
                        <div className="relative flex justify-center">
                          <span className="bg-gray-50 dark:bg-t-bg-elevated px-4 text-sm text-gray-500 dark:text-t-text-muted">
                            미감지 종목
                          </span>
                        </div>
                      </div>
                    )}

                    {/* 나머지 종목 */}
                    {otherStocks.length > 0 && (
                      <>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-500 dark:text-t-text-muted">
                            기타 테마 종목 ({otherStocks.length}개)
                          </span>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                          {otherStocks.map((stock) => (
                            <Card key={stock.code} className="p-3 opacity-80 relative group">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  hideStock(stock.code)
                                }}
                                className="absolute top-2 right-2 z-10 p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:bg-red-900/20 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                                title="차트 숨기기"
                              >
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                                </svg>
                              </button>
                              <StockChart
                                stockCode={stock.code}
                                stockName={stock.name}
                                height={250}
                                days={180}
                              />
                            </Card>
                          ))}
                        </div>
                      </>
                    )}

                    {/* 모든 종목이 숨겨진 경우 */}
                    {mentionedStocks.length === 0 && otherStocks.length === 0 && hiddenCount > 0 && (
                      <Card className="p-8 text-center text-gray-500 dark:text-t-text-muted">
                        모든 종목이 숨겨져 있습니다.
                        <button
                          onClick={showAllStocks}
                          className="ml-2 text-blue-500 hover:underline"
                        >
                          전체 복원
                        </button>
                      </Card>
                    )}
                  </>
                )
              })()}
            </>
          ) : (
            <Card className="p-8 text-center text-gray-500 dark:text-t-text-muted">
              차트를 표시할 종목이 없습니다.
            </Card>
          )}
        </div>
      )}

      {activeTab === 'news' && (
        <div className="space-y-4">
          {/* 뉴스 추이 차트 (간단한 바 차트) */}
          <Card className="p-4">
            <h3 className="text-sm font-medium text-gray-600 dark:text-t-text-muted mb-4">14일 뉴스 추이</h3>
            {newsTrend.length > 0 ? (
              <div className="flex items-end gap-1 h-32">
                {newsTrend.map((item, idx) => {
                  const maxCount = Math.max(...newsTrend.map((t) => t.mention_count), 1)
                  const height = (item.mention_count / maxCount) * 100
                  return (
                    <div key={idx} className="flex-1 flex flex-col items-center gap-1">
                      <span className="text-xs text-gray-500 dark:text-t-text-muted">{item.mention_count}</span>
                      <div
                        className="w-full bg-blue-400 rounded-t"
                        style={{ height: `${height}%`, minHeight: item.mention_count > 0 ? '4px' : '0' }}
                      />
                      <span className="text-xs text-gray-400 rotate-45 origin-left">
                        {item.date.slice(5)}
                      </span>
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="text-center text-gray-400">데이터가 없습니다.</p>
            )}
          </Card>

          {/* 최근 뉴스 */}
          <Card className="p-4">
            <h3 className="text-sm font-medium text-gray-600 dark:text-t-text-muted mb-4">최근 뉴스</h3>
            {recentNews.length > 0 ? (
              <div className="space-y-3">
                {recentNews.map((news, idx) => (
                  <div key={idx} className="border-b border-gray-100 dark:border-t-border/50 pb-3 last:border-0 last:pb-0">
                    <a
                      href={news.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-blue-600 hover:underline"
                    >
                      {news.title}
                    </a>
                    <div className="flex items-center gap-2 mt-1 text-xs text-gray-500 dark:text-t-text-muted">
                      <span>{news.source}</span>
                      <span>|</span>
                      <span>{new Date(news.published_at).toLocaleDateString('ko-KR')}</span>
                      <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-t-bg-elevated rounded">{news.keyword}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center text-gray-400">뉴스가 없습니다.</p>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'flow' && (
        <div className="space-y-4">
          {/* 수급 요약 */}
          {investorFlow && (
            <Card className="p-4">
              <h3 className="text-sm font-medium text-gray-600 dark:text-t-text-muted mb-4">수급 요약 (최근 5일)</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-3 bg-gray-50 dark:bg-t-bg-elevated rounded">
                  <p className="text-xs text-gray-500 dark:text-t-text-muted">평균 수급 점수</p>
                  <p className={`text-2xl font-bold ${investorFlow.summary.avg_flow_score >= 50 ? 'text-red-500' : 'text-blue-500'}`}>
                    {investorFlow.summary.avg_flow_score.toFixed(1)}
                  </p>
                  <p className="text-xs text-gray-400">(중립: 50)</p>
                </div>
                <div className="text-center p-3 bg-gray-50 dark:bg-t-bg-elevated rounded">
                  <p className="text-xs text-gray-500 dark:text-t-text-muted">외국인 순매수</p>
                  <p className={`text-lg font-bold ${investorFlow.summary.foreign_net_sum >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                    {investorFlow.summary.positive_foreign}/{investorFlow.summary.total_stocks}
                  </p>
                  <p className="text-xs text-gray-400">종목</p>
                </div>
                <div className="text-center p-3 bg-gray-50 dark:bg-t-bg-elevated rounded">
                  <p className="text-xs text-gray-500 dark:text-t-text-muted">기관 순매수</p>
                  <p className={`text-lg font-bold ${investorFlow.summary.institution_net_sum >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                    {investorFlow.summary.positive_institution}/{investorFlow.summary.total_stocks}
                  </p>
                  <p className="text-xs text-gray-400">종목</p>
                </div>
                <div className="text-center p-3 bg-gray-50 dark:bg-t-bg-elevated rounded">
                  <p className="text-xs text-gray-500 dark:text-t-text-muted">데이터</p>
                  <p className="text-lg font-bold text-gray-700 dark:text-t-text-secondary">
                    {investorFlow.stocks.length}
                  </p>
                  <p className="text-xs text-gray-400">종목</p>
                </div>
              </div>
            </Card>
          )}

          {/* 종목별 수급 */}
          <Card className="p-4">
            <h3 className="text-sm font-medium text-gray-600 dark:text-t-text-muted mb-4">종목별 수급 현황</h3>
            {investorFlow && investorFlow.stocks.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-t-border">
                      <th className="text-left py-2 px-2">종목</th>
                      <th className="text-right py-2 px-2">외국인</th>
                      <th className="text-right py-2 px-2">기관</th>
                      <th className="text-right py-2 px-2">개인</th>
                      <th className="text-right py-2 px-2">점수</th>
                    </tr>
                  </thead>
                  <tbody>
                    {investorFlow.stocks.map((stock) => (
                      <React.Fragment key={stock.stock_code}>
                        <tr
                          className={`border-b border-gray-100 dark:border-t-border/50 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 dark:bg-t-bg-elevated cursor-pointer ${
                            selectedFlowStock === stock.stock_code ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                          }`}
                          onClick={() => handleStockFlowClick(stock.stock_code)}
                        >
                          <td className="py-2 px-2">
                            <div className="flex items-center gap-1">
                              <span className="text-gray-400 text-xs">
                                {selectedFlowStock === stock.stock_code ? '▼' : '▶'}
                              </span>
                              <div>
                                <div className="font-medium">{stock.stock_name}</div>
                                <div className="text-xs text-gray-400">{stock.stock_code}</div>
                              </div>
                            </div>
                          </td>
                          <td className={`text-right py-2 px-2 font-medium ${stock.foreign_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                            {stock.foreign_net >= 0 ? '+' : ''}{(stock.foreign_net / 1000).toFixed(0)}천
                          </td>
                          <td className={`text-right py-2 px-2 font-medium ${stock.institution_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                            {stock.institution_net >= 0 ? '+' : ''}{(stock.institution_net / 1000).toFixed(0)}천
                          </td>
                          <td className={`text-right py-2 px-2 ${stock.individual_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                            {stock.individual_net >= 0 ? '+' : ''}{(stock.individual_net / 1000).toFixed(0)}천
                          </td>
                          <td className="text-right py-2 px-2">
                            <span className={`inline-block px-2 py-0.5 rounded text-xs ${
                              stock.flow_score >= 60 ? 'bg-red-100 text-red-700' :
                              stock.flow_score >= 50 ? 'bg-orange-100 text-orange-700' :
                              stock.flow_score >= 40 ? 'bg-gray-100 dark:bg-t-bg-elevated text-gray-700 dark:text-t-text-secondary' :
                              'bg-blue-100 text-blue-700'
                            }`}>
                              {stock.flow_score.toFixed(0)}
                            </span>
                          </td>
                        </tr>
                        {/* 차트 + 수급 히스토리 펼침 영역 */}
                        {selectedFlowStock === stock.stock_code && (
                          <tr>
                            <td colSpan={5} className="bg-gray-50 dark:bg-t-bg-elevated p-4">
                              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                {/* 차트 */}
                                <div className="bg-white dark:bg-t-bg-card rounded-lg p-3 border">
                                  <StockChart
                                    stockCode={stock.stock_code}
                                    stockName={stock.stock_name}
                                    height={300}
                                    days={180}
                                  />
                                </div>

                                {/* 수급 내역 */}
                                <div className="bg-white dark:bg-t-bg-card rounded-lg p-3 border">
                                  <h4 className="text-sm font-medium text-gray-600 dark:text-t-text-muted mb-3">최근 30일 수급</h4>
                                  {flowHistoryLoading ? (
                                    <div className="text-center text-gray-400 py-4">로딩 중...</div>
                                  ) : stockFlowHistory.length > 0 ? (
                                    <>
                                      <div className="max-h-64 overflow-y-auto">
                                        <table className="w-full text-xs">
                                          <thead className="sticky top-0 bg-white dark:bg-t-bg-card">
                                            <tr className="border-b">
                                              <th className="text-left py-1.5 px-2">날짜</th>
                                              <th className="text-right py-1.5 px-2">외국인</th>
                                              <th className="text-right py-1.5 px-2">기관</th>
                                              <th className="text-right py-1.5 px-2">개인</th>
                                              <th className="text-right py-1.5 px-2">합계</th>
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {stockFlowHistory.map((h) => {
                                              const total = h.foreign_net + h.institution_net
                                              return (
                                                <tr key={h.flow_date} className="border-b border-gray-100 dark:border-t-border/50 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 dark:bg-t-bg-elevated">
                                                  <td className="py-1.5 px-2 text-gray-600 dark:text-t-text-muted">{h.flow_date}</td>
                                                  <td className={`py-1.5 px-2 text-right ${h.foreign_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                                                    {formatFlowQty(h.foreign_net)}
                                                  </td>
                                                  <td className={`py-1.5 px-2 text-right ${h.institution_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                                                    {formatFlowQty(h.institution_net)}
                                                  </td>
                                                  <td className={`py-1.5 px-2 text-right ${h.individual_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                                                    {formatFlowQty(h.individual_net)}
                                                  </td>
                                                  <td className={`py-1.5 px-2 text-right font-medium ${total >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                                                    {formatFlowQty(total)}
                                                  </td>
                                                </tr>
                                              )
                                            })}
                                          </tbody>
                                        </table>
                                      </div>
                                      {/* 수급 요약 */}
                                      <div className="mt-3 pt-3 border-t grid grid-cols-3 gap-2 text-xs">
                                        <div className="text-center">
                                          <div className="text-gray-500 dark:text-t-text-muted">5일 합계</div>
                                          <div className={`font-medium ${
                                            stockFlowHistory.slice(0, 5).reduce((sum, h) => sum + h.foreign_net + h.institution_net, 0) >= 0
                                              ? 'text-red-600' : 'text-blue-600'
                                          }`}>
                                            {formatFlowQty(stockFlowHistory.slice(0, 5).reduce((sum, h) => sum + h.foreign_net + h.institution_net, 0))}
                                          </div>
                                        </div>
                                        <div className="text-center">
                                          <div className="text-gray-500 dark:text-t-text-muted">10일 합계</div>
                                          <div className={`font-medium ${
                                            stockFlowHistory.slice(0, 10).reduce((sum, h) => sum + h.foreign_net + h.institution_net, 0) >= 0
                                              ? 'text-red-600' : 'text-blue-600'
                                          }`}>
                                            {formatFlowQty(stockFlowHistory.slice(0, 10).reduce((sum, h) => sum + h.foreign_net + h.institution_net, 0))}
                                          </div>
                                        </div>
                                        <div className="text-center">
                                          <div className="text-gray-500 dark:text-t-text-muted">30일 합계</div>
                                          <div className={`font-medium ${
                                            stockFlowHistory.reduce((sum, h) => sum + h.foreign_net + h.institution_net, 0) >= 0
                                              ? 'text-red-600' : 'text-blue-600'
                                          }`}>
                                            {formatFlowQty(stockFlowHistory.reduce((sum, h) => sum + h.foreign_net + h.institution_net, 0))}
                                          </div>
                                        </div>
                                      </div>
                                    </>
                                  ) : (
                                    <div className="text-center text-gray-400 py-4">수급 데이터가 없습니다.</div>
                                  )}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-center text-gray-400 py-4">수급 데이터가 없습니다.</p>
            )}
          </Card>

          {/* 범례 */}
          <Card className="p-3 bg-gray-50 dark:bg-t-bg-elevated">
            <div className="flex flex-wrap gap-4 text-xs text-gray-500 dark:text-t-text-muted">
              <span><span className="text-red-500 font-medium">빨간색</span>: 순매수</span>
              <span><span className="text-blue-500 font-medium">파란색</span>: 순매도</span>
              <span>점수 50 이상: 매수 우위</span>
              <span>점수 50 미만: 매도 우위</span>
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'history' && (
        <Card className="p-4">
          <h3 className="text-sm font-medium text-gray-600 dark:text-t-text-muted mb-4">점수 히스토리</h3>
          {detail.history.length > 0 ? (
            <div className="space-y-2">
              {detail.history.map((h) => (
                <div
                  key={h.date}
                  className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-t-border/50 last:border-0"
                >
                  <span className="text-sm text-gray-600 dark:text-t-text-muted">{h.date}</span>
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-gray-400">#{h.rank}</span>
                    <span className={`text-lg font-bold ${getScoreColor(h.score)}`}>
                      {h.score.toFixed(1)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-gray-400">히스토리가 없습니다.</p>
          )}
        </Card>
      )}
    </div>
  )
}

interface ChartPatternCardProps {
  pattern: ChartPattern
}

function ChartPatternCard({ pattern }: ChartPatternCardProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <Card
      className={`p-4 cursor-pointer hover:shadow-md transition-all ${
        PATTERN_TYPE_COLORS[pattern.pattern_type]?.replace('text-', 'border-l-4 border-') ||
        'border-l-4 border-gray-300 dark:border-t-border'
      }`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between">
        <div>
          <h4 className="font-semibold">{pattern.stock_name}</h4>
          <p className="text-xs text-gray-500 dark:text-t-text-muted">{pattern.stock_code}</p>
        </div>
        <div className="text-right">
          <span
            className={`inline-block px-2 py-1 text-xs rounded ${
              PATTERN_TYPE_COLORS[pattern.pattern_type] || 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted'
            }`}
          >
            {PATTERN_TYPE_LABELS[pattern.pattern_type] || pattern.pattern_type}
          </span>
          <p className="text-sm text-gray-500 dark:text-t-text-muted mt-1">신뢰도: {pattern.confidence}%</p>
        </div>
      </div>

      <div className="mt-3 text-sm">
        <div className="flex justify-between text-gray-600 dark:text-t-text-muted">
          <span>현재가</span>
          <span className="font-medium">{pattern.current_price.toLocaleString()}원</span>
        </div>
        {pattern.price_from_support_pct !== null && pattern.price_from_support_pct !== undefined && (
          <div className="flex justify-between text-gray-600 dark:text-t-text-muted">
            <span>지지선 대비</span>
            <span className={pattern.price_from_support_pct > 0 ? 'text-red-500' : 'text-blue-500'}>
              {pattern.price_from_support_pct > 0 ? '+' : ''}
              {pattern.price_from_support_pct.toFixed(2)}%
            </span>
          </div>
        )}
        {pattern.price_from_resistance_pct !== null && pattern.price_from_resistance_pct !== undefined && (
          <div className="flex justify-between text-gray-600 dark:text-t-text-muted">
            <span>저항선 대비</span>
            <span className={pattern.price_from_resistance_pct > 0 ? 'text-red-500' : 'text-blue-500'}>
              {pattern.price_from_resistance_pct > 0 ? '+' : ''}
              {pattern.price_from_resistance_pct.toFixed(2)}%
            </span>
          </div>
        )}
      </div>

      {expanded && pattern.pattern_data && (
        <div className="mt-3 pt-3 border-t border-gray-200 dark:border-t-border">
          <p className="text-xs text-gray-500 dark:text-t-text-muted mb-2">패턴 상세</p>
          <pre className="text-xs bg-gray-50 dark:bg-t-bg-elevated p-2 rounded overflow-auto">
            {JSON.stringify(pattern.pattern_data, null, 2)}
          </pre>
        </div>
      )}
    </Card>
  )
}
