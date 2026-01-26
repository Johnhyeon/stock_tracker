import { useEffect, useState, useMemo } from 'react'
import { useDataStore } from '../../store/useDataStore'
import { useIdeaStore } from '../../store/useIdeaStore'
import { Card } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import MentionChart from './MentionChart'
import type { YouTubeMention } from '../../types/data'

type TabType = 'my-ideas' | 'hot-discover'
type CollectMode = 'quick' | 'normal' | 'full'

const MODE_INFO: Record<CollectMode, { label: string; desc: string }> = {
  quick: { label: '빠른', desc: '~1분, 카테고리당 5개 키워드' },
  normal: { label: '일반', desc: '~3분, 카테고리당 10개 키워드' },
  full: { label: '전체', desc: '~10분, 모든 키워드 + 인기 채널' },
}

export default function YouTubeTrending() {
  const {
    trendingTickers,
    risingTickers,
    youtubeMentions,
    trendingLoading,
    mentionsLoading,
    risingLoading,
    youtubeCollecting,
    youtubeHotCollecting,
    youtubeCollectResult,
    youtubeHotCollectResult,
    fetchTrendingTickers,
    fetchRisingTickers,
    fetchYouTubeMentions,
    collectYouTube,
    collectYouTubeHot,
  } = useDataStore()

  const { ideas, fetchIdeas } = useIdeaStore()

  const [activeTab, setActiveTab] = useState<TabType>('hot-discover')
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null)
  const [selectedTickerVideos, setSelectedTickerVideos] = useState<YouTubeMention[]>([])
  const [selectedTickerLoading, setSelectedTickerLoading] = useState(false)
  const [daysBack, setDaysBack] = useState(7)
  const [collectMode, setCollectMode] = useState<CollectMode>('normal')

  // 내 아이디어에 있는 종목 코드 추출
  const myIdeaStockCodes = useMemo(() => {
    const codes = new Set<string>()
    ideas.forEach((idea) => {
      idea.tickers.forEach((ticker) => codes.add(ticker))
    })
    return codes
  }, [ideas])

  // 내 종목만 필터링한 트렌딩
  const myTrendingTickers = useMemo(() => {
    return trendingTickers.filter((t) => myIdeaStockCodes.has(t.stock_code))
  }, [trendingTickers, myIdeaStockCodes])

  // 내 종목 관련 영상만 필터링
  const myMentions = useMemo(() => {
    return youtubeMentions.filter((m) =>
      m.mentioned_tickers.some((t) => myIdeaStockCodes.has(t))
    )
  }, [youtubeMentions, myIdeaStockCodes])

  useEffect(() => {
    fetchIdeas()
    fetchTrendingTickers(daysBack)
    fetchYouTubeMentions({ days_back: daysBack })
    fetchRisingTickers(daysBack)
  }, [fetchIdeas, fetchTrendingTickers, fetchYouTubeMentions, fetchRisingTickers, daysBack])

  // 종목 선택 시 해당 종목 영상 가져오기
  useEffect(() => {
    if (selectedTicker) {
      setSelectedTickerLoading(true)
      // API에서 해당 종목 영상 필터링
      const filtered = youtubeMentions.filter((m) =>
        m.mentioned_tickers.includes(selectedTicker)
      )
      setSelectedTickerVideos(filtered)
      setSelectedTickerLoading(false)
    } else {
      setSelectedTickerVideos([])
    }
  }, [selectedTicker, youtubeMentions])

  const formatViews = (views: number) => {
    if (views >= 1000000) return `${(views / 1000000).toFixed(1)}M`
    if (views >= 1000) return `${(views / 1000).toFixed(1)}K`
    return views.toString()
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('ko-KR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const handleTickerClick = (stockCode: string) => {
    setSelectedTicker(selectedTicker === stockCode ? null : stockCode)
  }

  return (
    <div className="space-y-6">
      {/* 헤더 + 탭 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">YouTube 종목 분석</h1>
          <div className="flex gap-2 mt-2">
            <button
              onClick={() => {
                setActiveTab('hot-discover')
                setSelectedTicker(null)
              }}
              className={`px-3 py-1 text-sm rounded-full ${
                activeTab === 'hot-discover'
                  ? 'bg-red-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              🔥 핫 종목 발굴
            </button>
            <button
              onClick={() => {
                setActiveTab('my-ideas')
                setSelectedTicker(null)
              }}
              className={`px-3 py-1 text-sm rounded-full ${
                activeTab === 'my-ideas'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              📌 내 종목 모니터링
            </button>
          </div>
        </div>
        <div className="flex gap-2 items-center">
          <select
            value={daysBack}
            onChange={(e) => setDaysBack(Number(e.target.value))}
            className="text-sm border rounded px-2 py-1"
          >
            <option value={3}>최근 3일</option>
            <option value={7}>최근 7일</option>
            <option value={14}>최근 14일</option>
            <option value={30}>최근 30일</option>
          </select>
          {activeTab === 'hot-discover' ? (
            <div className="flex gap-1 items-center">
              <select
                value={collectMode}
                onChange={(e) => setCollectMode(e.target.value as CollectMode)}
                className="text-sm border rounded px-2 py-1"
                disabled={youtubeHotCollecting}
                title={MODE_INFO[collectMode].desc}
              >
                <option value="quick">빠른 수집</option>
                <option value="normal">일반 수집</option>
                <option value="full">전체 수집</option>
              </select>
              <Button
                onClick={() => collectYouTubeHot(48, collectMode)}
                variant="primary"
                disabled={youtubeHotCollecting}
              >
                {youtubeHotCollecting ? '수집 중...' : '수집 시작'}
              </Button>
            </div>
          ) : (
            <Button
              onClick={() => collectYouTube(48)}
              variant="secondary"
              disabled={youtubeCollecting}
            >
              {youtubeCollecting ? '수집 중...' : '내 종목 수집'}
            </Button>
          )}
        </div>
      </div>

      {/* 수집 중 표시 (전역) */}
      {(youtubeHotCollecting || youtubeCollecting) && (
        <Card className="p-4 bg-amber-50 border-amber-200">
          <div className="flex items-center gap-2">
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-amber-500 border-t-transparent" />
            <p className="text-sm text-amber-700">
              {youtubeHotCollecting
                ? '핫 영상 수집 중... (다른 페이지를 봐도 계속 진행됩니다)'
                : '내 종목 영상 수집 중... (다른 페이지를 봐도 계속 진행됩니다)'}
            </p>
          </div>
        </Card>
      )}

      {/* 수집 결과 알림 */}
      {activeTab === 'hot-discover' && youtubeHotCollectResult && !youtubeHotCollecting && (
        <Card className="p-4 bg-red-50 border-red-200">
          <p className="text-sm">
            <span className="font-medium">
              [{youtubeHotCollectResult.mode === 'quick' ? '빠른' : youtubeHotCollectResult.mode === 'full' ? '전체' : '일반'}] 수집 완료:
            </span>{' '}
            {youtubeHotCollectResult.collected}개 영상 분석, {youtubeHotCollectResult.new}개 신규
            저장,{' '}
            <span className="text-red-600 font-medium">
              {youtubeHotCollectResult.tickers_found?.length || 0}개 종목 발견
            </span>
            {youtubeHotCollectResult.tickers_found &&
              youtubeHotCollectResult.tickers_found.length > 0 && (
                <span className="text-gray-500 ml-1">
                  ({youtubeHotCollectResult.tickers_found.slice(0, 10).join(', ')}
                  {youtubeHotCollectResult.tickers_found.length > 10 && ' ...'})
                </span>
              )}
          </p>
        </Card>
      )}

      {activeTab === 'my-ideas' && youtubeCollectResult && !youtubeCollecting && (
        <Card className="p-4 bg-blue-50 border-blue-200">
          <p className="text-sm">
            <span className="font-medium">수집 완료:</span>{' '}
            {youtubeCollectResult.tickers_searched &&
            youtubeCollectResult.tickers_searched.length > 0 ? (
              <>
                [{youtubeCollectResult.tickers_searched.join(', ')}] 검색 →{' '}
                {youtubeCollectResult.collected}개 영상 수집, {youtubeCollectResult.new}개 신규
              </>
            ) : (
              <span className="text-amber-600">
                검색할 종목이 없습니다. 아이디어를 먼저 등록해주세요.
              </span>
            )}
          </p>
        </Card>
      )}

      {/* ==================== 핫 종목 발굴 탭 ==================== */}
      {activeTab === 'hot-discover' && (
        <>
          {/* 급상승 종목 */}
          <Card className="p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <span className="text-red-500">🔥</span> 급상승 종목
              <span className="text-sm text-gray-500 font-normal">
                (최근 {Math.floor(daysBack / 2)}일 vs 이전 {Math.ceil(daysBack / 2)}일 비교)
              </span>
            </h2>
            {risingTickers.length === 0 && risingLoading ? (
              <p className="text-gray-500">로딩 중...</p>
            ) : risingTickers.length === 0 ? (
              <p className="text-gray-500">
                데이터가 없습니다. 우측 상단 "수집 시작" 버튼을 눌러 데이터를 수집해주세요.
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                {risingTickers.slice(0, 8).map((ticker, index) => (
                  <div
                    key={ticker.stock_code}
                    className={`p-3 rounded-lg border cursor-pointer hover:shadow-md transition-shadow ${
                      selectedTicker === ticker.stock_code
                        ? 'border-red-400 bg-red-50'
                        : 'border-gray-200'
                    }`}
                    onClick={() => handleTickerClick(ticker.stock_code)}
                  >
                    {/* 헤더: 순위, 종목명, 점수 */}
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <div className="flex items-center gap-1">
                          <span className="text-gray-400 text-sm">#{index + 1}</span>
                          {ticker.is_new && (
                            <span className="text-xs bg-yellow-100 text-yellow-700 px-1 rounded">
                              NEW
                            </span>
                          )}
                          {ticker.score_breakdown?.is_contrarian && (
                            <span className="text-xs bg-purple-100 text-purple-700 px-1 rounded" title="언급 급증 + 주가 하락 = 역발상 매수 기회">
                              역발상
                            </span>
                          )}
                        </div>
                        <p className="font-medium">{ticker.stock_name || ticker.stock_code}</p>
                        <p className="text-xs text-gray-500">{ticker.stock_code}</p>
                      </div>
                      {ticker.weighted_score != null && (
                        <div className="text-right group relative">
                          <div className="text-lg font-bold text-orange-500 cursor-help">
                            {ticker.weighted_score}
                          </div>
                          <div className="text-xs text-gray-400">점수</div>
                          {/* 점수 breakdown 툴팁 */}
                          {ticker.score_breakdown && (
                            <div className="absolute right-0 top-full mt-1 z-10 hidden group-hover:block bg-gray-900 text-white text-xs rounded-lg p-3 w-48 shadow-lg">
                              <div className="font-medium mb-2 border-b border-gray-700 pb-1">점수 상세</div>
                              <div className="space-y-1">
                                <div className="flex justify-between">
                                  <span>언급 증가율</span>
                                  <span>{ticker.score_breakdown.mention_growth}/25</span>
                                </div>
                                <div className="flex justify-between">
                                  <span>절대 언급량</span>
                                  <span>{ticker.score_breakdown.mention_volume}/15</span>
                                </div>
                                <div className="flex justify-between">
                                  <span>조회수</span>
                                  <span>{ticker.score_breakdown.view_weight}/10</span>
                                </div>
                                <div className="flex justify-between">
                                  <span>주가 모멘텀{ticker.score_breakdown.is_contrarian ? ' 🔄' : ''}</span>
                                  <span>{ticker.score_breakdown.price_momentum}/20</span>
                                </div>
                                <div className="flex justify-between">
                                  <span>거래량</span>
                                  <span>{ticker.score_breakdown.volume_score}/20</span>
                                </div>
                                {ticker.score_breakdown.new_bonus > 0 && (
                                  <div className="flex justify-between text-yellow-400">
                                    <span>신규 보너스</span>
                                    <span>+{ticker.score_breakdown.new_bonus}</span>
                                  </div>
                                )}
                              </div>
                              {ticker.score_breakdown.is_contrarian && (
                                <div className="mt-2 pt-2 border-t border-gray-700 text-purple-300 text-[10px]">
                                  🔄 언급↑ + 주가↓ = 매수 기회
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* 주가 정보 */}
                    {ticker.current_price != null && (
                      <div className="flex justify-between items-center py-1 border-t border-gray-100">
                        <span className="text-sm font-medium">
                          {ticker.current_price.toLocaleString()}원
                        </span>
                        <span
                          className={`text-sm font-medium ${
                            (ticker.price_change_rate || 0) > 0
                              ? 'text-red-500'
                              : (ticker.price_change_rate || 0) < 0
                              ? 'text-blue-500'
                              : 'text-gray-500'
                          }`}
                        >
                          {(ticker.price_change_rate || 0) > 0 ? '+' : ''}
                          {ticker.price_change_rate?.toFixed(2)}%
                        </span>
                      </div>
                    )}

                    {/* YouTube 언급 & 거래량 */}
                    <div className="flex justify-between items-center text-xs text-gray-500 mt-1">
                      <span>
                        언급 {ticker.prev_mentions}→{ticker.recent_mentions}회
                        <span
                          className={`ml-1 ${
                            ticker.growth_rate > 0 ? 'text-red-500' : 'text-blue-500'
                          }`}
                        >
                          ({ticker.growth_rate > 0 ? '+' : ''}{ticker.growth_rate}%)
                        </span>
                      </span>
                      {ticker.volume != null && (
                        <span>거래량 {formatViews(ticker.volume)}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* 선택된 종목 상세 */}
          {selectedTicker && (
            <Card className="p-6">
              <h2 className="text-lg font-semibold mb-4">
                📊 {selectedTicker} 상세
              </h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 차트 */}
                <div>
                  <h3 className="text-sm font-medium text-gray-600 mb-2">언급 추이</h3>
                  <MentionChart stockCode={selectedTicker} daysBack={daysBack} />
                </div>
                {/* 관련 영상 목록 */}
                <div>
                  <h3 className="text-sm font-medium text-gray-600 mb-2">
                    관련 영상 ({selectedTickerVideos.length}개)
                  </h3>
                  {selectedTickerLoading ? (
                    <p className="text-gray-500">로딩 중...</p>
                  ) : selectedTickerVideos.length === 0 ? (
                    <p className="text-gray-500 text-sm">관련 영상이 없습니다.</p>
                  ) : (
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {selectedTickerVideos.slice(0, 10).map((mention) => (
                        <div
                          key={mention.id}
                          className="flex gap-2 cursor-pointer hover:bg-gray-50 p-2 rounded text-sm"
                          onClick={() =>
                            window.open(
                              `https://www.youtube.com/watch?v=${mention.video_id}`,
                              '_blank'
                            )
                          }
                        >
                          {mention.thumbnail_url && (
                            <img
                              src={mention.thumbnail_url}
                              alt=""
                              className="w-20 h-12 object-cover rounded"
                            />
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="font-medium line-clamp-2">{mention.video_title}</p>
                            <p className="text-xs text-gray-500">
                              {mention.channel_name} · {formatDate(mention.published_at)}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          )}

          {/* 전체 트렌딩 & 최근 영상 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="p-6">
              <h2 className="text-lg font-semibold mb-4">📈 전체 트렌딩 (언급량 순)</h2>
              {trendingTickers.length === 0 && trendingLoading ? (
                <p className="text-gray-500">로딩 중...</p>
              ) : trendingTickers.length === 0 ? (
                <p className="text-gray-500">데이터 없음</p>
              ) : (
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {trendingTickers.map((ticker, index) => (
                    <div
                      key={ticker.stock_code}
                      className={`flex justify-between items-center p-2 rounded cursor-pointer hover:bg-gray-50 ${
                        selectedTicker === ticker.stock_code ? 'bg-red-50' : ''
                      }`}
                      onClick={() => handleTickerClick(ticker.stock_code)}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-500 w-5">{index + 1}</span>
                        <div>
                          <p className="font-medium">{ticker.stock_name || ticker.stock_code}</p>
                          <p className="text-xs text-gray-500">{ticker.stock_code}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-red-600">{ticker.mention_count}회</p>
                        <p className="text-xs text-gray-500">
                          {formatViews(ticker.total_views)} 조회
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card className="p-6">
              <h2 className="text-lg font-semibold mb-4">🎬 최근 수집 영상</h2>
              {youtubeMentions.length === 0 && mentionsLoading ? (
                <p className="text-gray-500">로딩 중...</p>
              ) : youtubeMentions.length === 0 ? (
                <p className="text-gray-500">영상이 없습니다.</p>
              ) : (
                <div className="space-y-3 max-h-80 overflow-y-auto">
                  {youtubeMentions.slice(0, 10).map((mention) => (
                    <div
                      key={mention.id}
                      className="flex gap-3 cursor-pointer hover:bg-gray-50 p-2 rounded"
                      onClick={() =>
                        window.open(
                          `https://www.youtube.com/watch?v=${mention.video_id}`,
                          '_blank'
                        )
                      }
                    >
                      {mention.thumbnail_url && (
                        <img
                          src={mention.thumbnail_url}
                          alt={mention.video_title}
                          className="w-24 h-14 object-cover rounded"
                        />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm line-clamp-2">{mention.video_title}</p>
                        <p className="text-xs text-gray-500">{mention.channel_name}</p>
                        <div className="flex gap-1 mt-1 flex-wrap">
                          {mention.mentioned_tickers.slice(0, 3).map((ticker) => (
                            <span
                              key={ticker}
                              className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded cursor-pointer hover:bg-red-200"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleTickerClick(ticker)
                              }}
                            >
                              {ticker}
                            </span>
                          ))}
                          {mention.mentioned_tickers.length > 3 && (
                            <span className="text-xs text-gray-400">
                              +{mention.mentioned_tickers.length - 3}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </>
      )}

      {/* ==================== 내 종목 모니터링 탭 ==================== */}
      {activeTab === 'my-ideas' && (
        <>
          {/* 내 아이디어 없으면 안내 */}
          {myIdeaStockCodes.size === 0 ? (
            <Card className="p-6 text-center">
              <p className="text-gray-500 mb-2">등록된 아이디어가 없습니다.</p>
              <p className="text-sm text-gray-400">
                아이디어를 먼저 등록하면 해당 종목의 YouTube 언급을 모니터링할 수 있습니다.
              </p>
            </Card>
          ) : (
            <>
              {/* 내 종목 현황 */}
              <Card className="p-6">
                <h2 className="text-lg font-semibold mb-2">📌 내 종목 언급 현황</h2>
                <p className="text-sm text-gray-500 mb-4">
                  내 아이디어에 등록된 {myIdeaStockCodes.size}개 종목 중 YouTube에서 언급된 종목
                </p>
                {myTrendingTickers.length === 0 && trendingLoading ? (
                  <p className="text-gray-500">로딩 중...</p>
                ) : myTrendingTickers.length === 0 ? (
                  <p className="text-gray-500">
                    내 종목 관련 YouTube 언급이 없습니다.
                    <br />
                    <span className="text-sm">
                      "내 종목 수집" 버튼을 눌러 데이터를 수집해보세요.
                    </span>
                  </p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                    {myTrendingTickers.map((ticker, index) => (
                      <div
                        key={ticker.stock_code}
                        className={`p-3 rounded-lg border cursor-pointer hover:shadow-md transition-shadow ${
                          selectedTicker === ticker.stock_code
                            ? 'border-blue-400 bg-blue-50'
                            : 'border-gray-200'
                        }`}
                        onClick={() => handleTickerClick(ticker.stock_code)}
                      >
                        <div className="flex justify-between items-start">
                          <div>
                            <span className="text-gray-400 text-sm">#{index + 1}</span>
                            <p className="font-medium">{ticker.stock_name || ticker.stock_code}</p>
                            <p className="text-xs text-gray-500">{ticker.stock_code}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-lg font-bold text-blue-600">
                              {ticker.mention_count}회
                            </p>
                            <p className="text-xs text-gray-500">
                              {formatViews(ticker.total_views)} 조회
                            </p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* 선택된 종목 상세 */}
              {selectedTicker && (
                <Card className="p-6">
                  <h2 className="text-lg font-semibold mb-4">
                    📊 {selectedTicker} 상세
                  </h2>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div>
                      <h3 className="text-sm font-medium text-gray-600 mb-2">언급 추이</h3>
                      <MentionChart stockCode={selectedTicker} daysBack={daysBack} />
                    </div>
                    <div>
                      <h3 className="text-sm font-medium text-gray-600 mb-2">
                        관련 영상 ({selectedTickerVideos.length}개)
                      </h3>
                      {selectedTickerVideos.length === 0 ? (
                        <p className="text-gray-500 text-sm">관련 영상이 없습니다.</p>
                      ) : (
                        <div className="space-y-2 max-h-64 overflow-y-auto">
                          {selectedTickerVideos.slice(0, 10).map((mention) => (
                            <div
                              key={mention.id}
                              className="flex gap-2 cursor-pointer hover:bg-gray-50 p-2 rounded text-sm"
                              onClick={() =>
                                window.open(
                                  `https://www.youtube.com/watch?v=${mention.video_id}`,
                                  '_blank'
                                )
                              }
                            >
                              {mention.thumbnail_url && (
                                <img
                                  src={mention.thumbnail_url}
                                  alt=""
                                  className="w-20 h-12 object-cover rounded"
                                />
                              )}
                              <div className="flex-1 min-w-0">
                                <p className="font-medium line-clamp-2">{mention.video_title}</p>
                                <p className="text-xs text-gray-500">
                                  {mention.channel_name} · {formatDate(mention.published_at)}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              )}

              {/* 내 종목 관련 최근 영상 */}
              <Card className="p-6">
                <h2 className="text-lg font-semibold mb-4">🎬 내 종목 관련 최근 영상</h2>
                {myMentions.length === 0 && mentionsLoading ? (
                  <p className="text-gray-500">로딩 중...</p>
                ) : myMentions.length === 0 ? (
                  <p className="text-gray-500 text-center py-4">
                    내 종목 관련 영상이 없습니다.
                  </p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {myMentions.slice(0, 10).map((mention) => (
                      <div
                        key={mention.id}
                        className="flex gap-4 cursor-pointer hover:bg-gray-50 p-2 rounded"
                        onClick={() =>
                          window.open(
                            `https://www.youtube.com/watch?v=${mention.video_id}`,
                            '_blank'
                          )
                        }
                      >
                        {mention.thumbnail_url && (
                          <img
                            src={mention.thumbnail_url}
                            alt={mention.video_title}
                            className="w-32 h-20 object-cover rounded"
                          />
                        )}
                        <div className="flex-1">
                          <p className="font-medium line-clamp-2">{mention.video_title}</p>
                          <p className="text-sm text-gray-500">{mention.channel_name}</p>
                          <div className="flex gap-3 text-xs text-gray-500 mt-1">
                            <span>{formatDate(mention.published_at)}</span>
                            {mention.view_count && (
                              <span>{formatViews(mention.view_count)} 조회</span>
                            )}
                          </div>
                          <div className="flex gap-1 mt-1">
                            {mention.mentioned_tickers
                              .filter((t) => myIdeaStockCodes.has(t))
                              .slice(0, 5)
                              .map((ticker) => (
                                <span
                                  key={ticker}
                                  className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded cursor-pointer hover:bg-blue-200"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    handleTickerClick(ticker)
                                  }}
                                >
                                  {ticker}
                                </span>
                              ))}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </>
          )}
        </>
      )}
    </div>
  )
}
