import { useEffect, useState } from 'react'
import { useDataStore } from '../../store/useDataStore'
import { Card } from '../../components/ui/Card'
import Button from '../../components/ui/Button'

type TabType = 'hot' | 'rising' | 'performance' | 'cross-check'

export default function TraderWatchlist() {
  const {
    traderHotStocks,
    traderRisingStocks,
    traderPerformance,
    traderCrossCheck,
    traderHotLoading,
    traderRisingLoading,
    traderPerformanceLoading,
    traderSyncing,
    traderSyncResult,
    syncTraderMentions,
    fetchTraderHotStocks,
    fetchTraderRisingStocks,
    fetchTraderPerformance,
    fetchTraderCrossCheck,
  } = useDataStore()

  const [activeTab, setActiveTab] = useState<TabType>('hot')
  const [daysBack, setDaysBack] = useState(7)

  useEffect(() => {
    fetchTraderHotStocks(daysBack)
    fetchTraderRisingStocks(daysBack)
    fetchTraderPerformance(30)
    fetchTraderCrossCheck()
  }, [fetchTraderHotStocks, fetchTraderRisingStocks, fetchTraderPerformance, fetchTraderCrossCheck, daysBack])

  const formatPrice = (price: number | null) => {
    if (price === null) return '-'
    return price.toLocaleString() + '원'
  }

  const formatVolume = (volume: number | null) => {
    if (volume === null) return '-'
    if (volume >= 1000000) return `${(volume / 1000000).toFixed(1)}M`
    if (volume >= 1000) return `${(volume / 1000).toFixed(1)}K`
    return volume.toString()
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('ko-KR', {
      month: 'short',
      day: 'numeric',
    })
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Trader Watchlist</h1>
          <p className="text-sm text-gray-500 mt-1">
            수익 트레이더들이 주목하는 종목
          </p>
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => setActiveTab('hot')}
              className={`px-3 py-1.5 text-sm rounded-full ${
                activeTab === 'hot'
                  ? 'bg-orange-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              Hot 종목
            </button>
            <button
              onClick={() => setActiveTab('rising')}
              className={`px-3 py-1.5 text-sm rounded-full ${
                activeTab === 'rising'
                  ? 'bg-red-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              급상승
            </button>
            <button
              onClick={() => setActiveTab('performance')}
              className={`px-3 py-1.5 text-sm rounded-full ${
                activeTab === 'performance'
                  ? 'bg-green-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              성과 분석
            </button>
            <button
              onClick={() => setActiveTab('cross-check')}
              className={`px-3 py-1.5 text-sm rounded-full ${
                activeTab === 'cross-check'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              내 종목
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
          <Button
            onClick={() => syncTraderMentions()}
            variant="primary"
            disabled={traderSyncing}
          >
            {traderSyncing ? '동기화 중...' : '데이터 동기화'}
          </Button>
        </div>
      </div>

      {/* 동기화 결과 */}
      {traderSyncResult && (
        <Card className="p-4 bg-green-50 border-green-200">
          <p className="text-sm text-green-700">
            동기화 완료: {traderSyncResult.total_stocks}개 종목, {traderSyncResult.total_mentions}개 언급
            {traderSyncResult.new_mentions > 0 && (
              <span className="font-medium ml-1">
                (신규 {traderSyncResult.new_mentions}개)
              </span>
            )}
          </p>
        </Card>
      )}

      {/* ==================== Hot 종목 탭 ==================== */}
      {activeTab === 'hot' && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <span className="text-orange-500">Hot</span> 종목
            <span className="text-sm text-gray-500 font-normal">
              (최근 {daysBack}일 언급 순위)
            </span>
          </h2>
          {traderHotLoading ? (
            <p className="text-gray-500">로딩 중...</p>
          ) : traderHotStocks.length === 0 ? (
            <p className="text-gray-500">
              데이터가 없습니다. "데이터 동기화" 버튼을 눌러주세요.
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              {traderHotStocks.map((stock, index) => (
                <div
                  key={stock.stock_name}
                  className="p-3 rounded-lg border border-gray-200 hover:shadow-md transition-shadow"
                >
                  {/* 헤더 */}
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <div className="flex items-center gap-1">
                        <span className="text-gray-400 text-sm">#{index + 1}</span>
                        {stock.is_new && (
                          <span className="text-xs bg-yellow-100 text-yellow-700 px-1 rounded">
                            NEW
                          </span>
                        )}
                      </div>
                      <p className="font-medium">{stock.stock_name}</p>
                      {stock.stock_code && (
                        <p className="text-xs text-gray-500">{stock.stock_code}</p>
                      )}
                    </div>
                    {stock.weighted_score !== null && (
                      <div className="text-right">
                        <div className="text-lg font-bold text-orange-500">
                          {stock.weighted_score.toFixed(1)}
                        </div>
                        <div className="text-xs text-gray-400">점수</div>
                      </div>
                    )}
                  </div>

                  {/* 주가 정보 */}
                  {stock.current_price !== null && (
                    <div className="flex justify-between items-center py-1 border-t border-gray-100">
                      <span className="text-sm font-medium">
                        {formatPrice(stock.current_price)}
                      </span>
                      <span
                        className={`text-sm font-medium ${
                          (stock.price_change_rate || 0) > 0
                            ? 'text-red-500'
                            : (stock.price_change_rate || 0) < 0
                            ? 'text-blue-500'
                            : 'text-gray-500'
                        }`}
                      >
                        {(stock.price_change_rate || 0) > 0 ? '+' : ''}
                        {stock.price_change_rate?.toFixed(2)}%
                      </span>
                    </div>
                  )}

                  {/* 언급 정보 */}
                  <div className="flex justify-between items-center text-xs text-gray-500 mt-1">
                    <span>
                      언급 {stock.mention_count}회
                      {stock.avg_mention_change !== null && (
                        <span className={`ml-1 ${stock.avg_mention_change >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                          (평균 {stock.avg_mention_change >= 0 ? '+' : ''}{stock.avg_mention_change.toFixed(1)}%)
                        </span>
                      )}
                    </span>
                    {stock.volume !== null && (
                      <span>거래량 {formatVolume(stock.volume)}</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    {formatDate(stock.first_mention_date)} ~ {formatDate(stock.last_mention_date)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* ==================== 급상승 탭 ==================== */}
      {activeTab === 'rising' && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <span className="text-red-500">급상승</span> 종목
            <span className="text-sm text-gray-500 font-normal">
              (최근 {Math.floor(daysBack / 2)}일 vs 이전 {Math.ceil(daysBack / 2)}일)
            </span>
          </h2>
          {traderRisingLoading ? (
            <p className="text-gray-500">로딩 중...</p>
          ) : traderRisingStocks.length === 0 ? (
            <p className="text-gray-500">급상승 종목이 없습니다.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              {traderRisingStocks.map((stock, index) => (
                <div
                  key={stock.stock_name}
                  className="p-3 rounded-lg border border-gray-200 hover:shadow-md transition-shadow"
                >
                  {/* 헤더 */}
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <div className="flex items-center gap-1">
                        <span className="text-gray-400 text-sm">#{index + 1}</span>
                        {stock.is_new && (
                          <span className="text-xs bg-yellow-100 text-yellow-700 px-1 rounded">
                            NEW
                          </span>
                        )}
                      </div>
                      <p className="font-medium">{stock.stock_name}</p>
                      {stock.stock_code && (
                        <p className="text-xs text-gray-500">{stock.stock_code}</p>
                      )}
                    </div>
                    {stock.weighted_score !== null && (
                      <div className="text-right">
                        <div className="text-lg font-bold text-red-500">
                          {stock.weighted_score.toFixed(1)}
                        </div>
                        <div className="text-xs text-gray-400">점수</div>
                      </div>
                    )}
                  </div>

                  {/* 주가 정보 */}
                  {stock.current_price !== null && (
                    <div className="flex justify-between items-center py-1 border-t border-gray-100">
                      <span className="text-sm font-medium">
                        {formatPrice(stock.current_price)}
                      </span>
                      <span
                        className={`text-sm font-medium ${
                          (stock.price_change_rate || 0) > 0
                            ? 'text-red-500'
                            : (stock.price_change_rate || 0) < 0
                            ? 'text-blue-500'
                            : 'text-gray-500'
                        }`}
                      >
                        {(stock.price_change_rate || 0) > 0 ? '+' : ''}
                        {stock.price_change_rate?.toFixed(2)}%
                      </span>
                    </div>
                  )}

                  {/* 언급 변화 */}
                  <div className="flex justify-between items-center text-xs text-gray-500 mt-1">
                    <span>
                      언급 {stock.prev_mentions}→{stock.recent_mentions}회
                      <span
                        className={`ml-1 font-medium ${
                          stock.growth_rate > 0 ? 'text-red-500' : 'text-blue-500'
                        }`}
                      >
                        ({stock.growth_rate > 0 ? '+' : ''}{stock.growth_rate.toFixed(0)}%)
                      </span>
                    </span>
                    {stock.volume !== null && (
                      <span>거래량 {formatVolume(stock.volume)}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* ==================== 성과 분석 탭 ==================== */}
      {activeTab === 'performance' && (
        <div className="space-y-6">
          {traderPerformanceLoading ? (
            <Card className="p-6">
              <p className="text-gray-500">로딩 중...</p>
            </Card>
          ) : traderPerformance === null ? (
            <Card className="p-6">
              <p className="text-gray-500">성과 데이터가 없습니다.</p>
            </Card>
          ) : (
            <>
              {/* 요약 카드 */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="p-4 text-center">
                  <p className="text-sm text-gray-500">분석 종목</p>
                  <p className="text-2xl font-bold">{traderPerformance.total_stocks}개</p>
                </Card>
                <Card className="p-4 text-center">
                  <p className="text-sm text-gray-500">평균 수익률</p>
                  <p className={`text-2xl font-bold ${
                    traderPerformance.avg_performance >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {traderPerformance.avg_performance >= 0 ? '+' : ''}
                    {traderPerformance.avg_performance.toFixed(2)}%
                  </p>
                </Card>
                <Card className="p-4 text-center">
                  <p className="text-sm text-gray-500">승률</p>
                  <p className={`text-2xl font-bold ${
                    traderPerformance.win_rate >= 50 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {traderPerformance.win_rate.toFixed(1)}%
                  </p>
                </Card>
                <Card className="p-4 text-center">
                  <p className="text-sm text-gray-500">7일 후 평균</p>
                  <p className={`text-2xl font-bold ${
                    (traderPerformance.performance_7d ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {(traderPerformance.performance_7d ?? 0) >= 0 ? '+' : ''}
                    {(traderPerformance.performance_7d ?? 0).toFixed(2)}%
                  </p>
                </Card>
              </div>

              {/* 수익률 통계 */}
              <Card className="p-6">
                <h3 className="text-lg font-semibold mb-4">기간별 성과</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-sm text-gray-500">1일 후</p>
                    <p className={`text-xl font-bold ${
                      (traderPerformance.performance_1d ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {(traderPerformance.performance_1d ?? 0) >= 0 ? '+' : ''}
                      {(traderPerformance.performance_1d ?? 0).toFixed(2)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">3일 후</p>
                    <p className={`text-xl font-bold ${
                      (traderPerformance.performance_3d ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {(traderPerformance.performance_3d ?? 0) >= 0 ? '+' : ''}
                      {(traderPerformance.performance_3d ?? 0).toFixed(2)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">7일 후</p>
                    <p className={`text-xl font-bold ${
                      (traderPerformance.performance_7d ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {(traderPerformance.performance_7d ?? 0) >= 0 ? '+' : ''}
                      {(traderPerformance.performance_7d ?? 0).toFixed(2)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">14일 후</p>
                    <p className={`text-xl font-bold ${
                      (traderPerformance.performance_14d ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {(traderPerformance.performance_14d ?? 0) >= 0 ? '+' : ''}
                      {(traderPerformance.performance_14d ?? 0).toFixed(2)}%
                    </p>
                  </div>
                </div>
              </Card>

              {/* 최고/최저 종목 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {traderPerformance.best_stock && traderPerformance.best_performance !== null && (
                  <Card className="p-6">
                    <h3 className="text-lg font-semibold mb-2 text-green-600">최고 수익 종목</h3>
                    <p className="text-xl font-bold">{traderPerformance.best_stock}</p>
                    <p className="text-2xl font-bold text-green-600">
                      +{traderPerformance.best_performance.toFixed(2)}%
                    </p>
                  </Card>
                )}
                {traderPerformance.worst_stock && traderPerformance.worst_performance !== null && (
                  <Card className="p-6">
                    <h3 className="text-lg font-semibold mb-2 text-red-600">최저 수익 종목</h3>
                    <p className="text-xl font-bold">{traderPerformance.worst_stock}</p>
                    <p className="text-2xl font-bold text-red-600">
                      {traderPerformance.worst_performance.toFixed(2)}%
                    </p>
                  </Card>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* ==================== 내 종목 크로스 체크 탭 ==================== */}
      {activeTab === 'cross-check' && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <span className="text-blue-500">내 아이디어</span> &times; 트레이더 관심
          </h2>
          {traderCrossCheck.length === 0 ? (
            <p className="text-gray-500">
              내 아이디어 종목 중 트레이더들도 주목하는 종목이 없습니다.
            </p>
          ) : (
            <div className="space-y-3">
              {traderCrossCheck.map((item) => (
                <div
                  key={`${item.stock_code}-${item.idea_title}`}
                  className="flex items-center justify-between p-3 bg-blue-50 rounded-lg"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{item.stock_name}</span>
                      <span className="text-xs text-gray-500">{item.stock_code}</span>
                    </div>
                    <p className="text-sm text-gray-600">
                      아이디어: {item.idea_title}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold text-blue-600">
                      {item.trader_mention_count}회
                    </p>
                    <p className="text-xs text-gray-500">
                      마지막 언급: {formatDate(item.last_mentioned)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
