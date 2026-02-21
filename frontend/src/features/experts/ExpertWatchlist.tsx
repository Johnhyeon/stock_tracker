import { useEffect, useState } from 'react'
import { useDataStore } from '../../store/useDataStore'
import { Card } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import type { ExpertPerformanceDetailResponse } from '../../types/data'
import { expertApi } from '../../services/api'

type TabType = 'hot' | 'rising' | 'performance' | 'cross-check'

export default function ExpertWatchlist() {
  const {
    expertHotStocks,
    expertRisingStocks,
    expertCrossCheck,
    expertHotLoading,
    expertRisingLoading,
    expertSyncing,
    expertSyncResult,
    syncExpertMentions,
    fetchExpertHotStocks,
    fetchExpertRisingStocks,
    fetchExpertCrossCheck,
  } = useDataStore()

  const [activeTab, setActiveTab] = useState<TabType>('hot')
  const [daysBack, setDaysBack] = useState(7)

  // 성과분석 전용 상태
  const [perfDetail, setPerfDetail] = useState<ExpertPerformanceDetailResponse | null>(null)
  const [perfLoading, setPerfLoading] = useState(false)
  const [perfDaysBack, setPerfDaysBack] = useState(30)
  const [simAmount, setSimAmount] = useState(1000000)

  useEffect(() => {
    fetchExpertHotStocks(daysBack)
    fetchExpertRisingStocks(daysBack)
    fetchExpertCrossCheck()
  }, [fetchExpertHotStocks, fetchExpertRisingStocks, fetchExpertCrossCheck, daysBack])

  useEffect(() => {
    if (activeTab === 'performance') {
      setPerfLoading(true)
      expertApi.getPerformanceDetail(perfDaysBack)
        .then(data => setPerfDetail(data))
        .catch(() => setPerfDetail(null))
        .finally(() => setPerfLoading(false))
    }
  }, [activeTab, perfDaysBack])

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
          <h1 className="text-2xl font-bold">Expert Watchlist</h1>
          <p className="text-sm text-gray-500 dark:text-t-text-muted mt-1">
            전문가들이 주목하는 종목
          </p>
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => setActiveTab('hot')}
              className={`px-3 py-1.5 text-sm rounded-full ${
                activeTab === 'hot'
                  ? 'bg-orange-500 text-white'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border'
              }`}
            >
              Hot 종목
            </button>
            <button
              onClick={() => setActiveTab('rising')}
              className={`px-3 py-1.5 text-sm rounded-full ${
                activeTab === 'rising'
                  ? 'bg-red-500 text-white'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border'
              }`}
            >
              급상승
            </button>
            <button
              onClick={() => setActiveTab('performance')}
              className={`px-3 py-1.5 text-sm rounded-full ${
                activeTab === 'performance'
                  ? 'bg-green-500 text-white'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border'
              }`}
            >
              성과 분석
            </button>
            <button
              onClick={() => setActiveTab('cross-check')}
              className={`px-3 py-1.5 text-sm rounded-full ${
                activeTab === 'cross-check'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border'
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
            className="text-sm border rounded px-2 py-1 bg-white dark:bg-t-bg-elevated dark:border-t-border-hover dark:text-t-text-primary"
          >
            <option value={3}>최근 3일</option>
            <option value={7}>최근 7일</option>
            <option value={14}>최근 14일</option>
            <option value={30}>최근 30일</option>
          </select>
          <Button
            onClick={() => syncExpertMentions()}
            variant="primary"
            disabled={expertSyncing}
          >
            {expertSyncing ? '동기화 중...' : '데이터 동기화'}
          </Button>
        </div>
      </div>

      {/* 동기화 결과 */}
      {expertSyncResult && (
        <Card className="p-4 bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800">
          <p className="text-sm text-green-700 dark:text-green-400">
            동기화 완료: {expertSyncResult.total_stocks}개 종목, {expertSyncResult.total_mentions}개 언급
            {expertSyncResult.new_mentions > 0 && (
              <span className="font-medium ml-1">
                (신규 {expertSyncResult.new_mentions}개)
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
            <span className="text-sm text-gray-500 dark:text-t-text-muted font-normal">
              (최근 {daysBack}일 언급 순위)
            </span>
          </h2>
          {expertHotLoading ? (
            <p className="text-gray-500 dark:text-t-text-muted">로딩 중...</p>
          ) : expertHotStocks.length === 0 ? (
            <p className="text-gray-500 dark:text-t-text-muted">
              데이터가 없습니다. "데이터 동기화" 버튼을 눌러주세요.
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              {expertHotStocks.map((stock, index) => (
                <div
                  key={stock.stock_name}
                  className="p-3 rounded-lg border border-gray-200 dark:border-t-border hover:shadow-md transition-shadow"
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
                        <p className="text-xs text-gray-500 dark:text-t-text-muted">{stock.stock_code}</p>
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
                    <div className="flex justify-between items-center py-1 border-t border-gray-100 dark:border-t-border/50">
                      <span className="text-sm font-medium">
                        {formatPrice(stock.current_price)}
                      </span>
                      <span
                        className={`text-sm font-medium ${
                          (stock.price_change_rate || 0) > 0
                            ? 'text-red-500'
                            : (stock.price_change_rate || 0) < 0
                            ? 'text-blue-500'
                            : 'text-gray-500 dark:text-t-text-muted'
                        }`}
                      >
                        {(stock.price_change_rate || 0) > 0 ? '+' : ''}
                        {stock.price_change_rate?.toFixed(2)}%
                      </span>
                    </div>
                  )}

                  {/* 언급 정보 */}
                  <div className="flex justify-between items-center text-xs text-gray-500 dark:text-t-text-muted mt-1">
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
            <span className="text-sm text-gray-500 dark:text-t-text-muted font-normal">
              (최근 {Math.floor(daysBack / 2)}일 vs 이전 {Math.ceil(daysBack / 2)}일)
            </span>
          </h2>
          {expertRisingLoading ? (
            <p className="text-gray-500 dark:text-t-text-muted">로딩 중...</p>
          ) : expertRisingStocks.length === 0 ? (
            <p className="text-gray-500 dark:text-t-text-muted">급상승 종목이 없습니다.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              {expertRisingStocks.map((stock, index) => (
                <div
                  key={stock.stock_name}
                  className="p-3 rounded-lg border border-gray-200 dark:border-t-border hover:shadow-md transition-shadow"
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
                        <p className="text-xs text-gray-500 dark:text-t-text-muted">{stock.stock_code}</p>
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
                    <div className="flex justify-between items-center py-1 border-t border-gray-100 dark:border-t-border/50">
                      <span className="text-sm font-medium">
                        {formatPrice(stock.current_price)}
                      </span>
                      <span
                        className={`text-sm font-medium ${
                          (stock.price_change_rate || 0) > 0
                            ? 'text-red-500'
                            : (stock.price_change_rate || 0) < 0
                            ? 'text-blue-500'
                            : 'text-gray-500 dark:text-t-text-muted'
                        }`}
                      >
                        {(stock.price_change_rate || 0) > 0 ? '+' : ''}
                        {stock.price_change_rate?.toFixed(2)}%
                      </span>
                    </div>
                  )}

                  {/* 언급 변화 */}
                  <div className="flex justify-between items-center text-xs text-gray-500 dark:text-t-text-muted mt-1">
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
          {/* 기간 선택 */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500 dark:text-t-text-muted">분석 기간:</span>
            {[14, 30, 60, 90].map(d => (
              <button
                key={d}
                onClick={() => setPerfDaysBack(d)}
                className={`px-3 py-1 text-sm rounded ${
                  perfDaysBack === d
                    ? 'bg-green-500 text-white'
                    : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted'
                }`}
              >
                {d}일
              </button>
            ))}
          </div>

          {perfLoading ? (
            <Card className="p-6">
              <p className="text-gray-500 dark:text-t-text-muted">성과 데이터 계산 중...</p>
            </Card>
          ) : !perfDetail || perfDetail.items.length === 0 ? (
            <Card className="p-6">
              <p className="text-gray-500 dark:text-t-text-muted">성과 데이터가 없습니다. OHLCV 데이터가 수집된 종목만 분석됩니다.</p>
            </Card>
          ) : (
            <>
              {/* 요약 카드 4개 */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="p-4 text-center">
                  <p className="text-sm text-gray-500 dark:text-t-text-muted">분석 종목</p>
                  <p className="text-2xl font-bold">{perfDetail.summary.total}개</p>
                </Card>
                <Card className="p-4 text-center">
                  <p className="text-sm text-gray-500 dark:text-t-text-muted">평균 수익률</p>
                  <p className={`text-2xl font-bold ${perfDetail.summary.avg_return >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                    {perfDetail.summary.avg_return >= 0 ? '+' : ''}{perfDetail.summary.avg_return.toFixed(2)}%
                  </p>
                </Card>
                <Card className="p-4 text-center">
                  <p className="text-sm text-gray-500 dark:text-t-text-muted">승률</p>
                  <p className={`text-2xl font-bold ${perfDetail.summary.win_rate >= 50 ? 'text-red-500' : 'text-blue-500'}`}>
                    {perfDetail.summary.win_rate.toFixed(1)}%
                  </p>
                </Card>
                <Card className="p-4 text-center">
                  <p className="text-sm text-gray-500 dark:text-t-text-muted">중앙값 수익률</p>
                  <p className={`text-2xl font-bold ${perfDetail.summary.median_return >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                    {perfDetail.summary.median_return >= 0 ? '+' : ''}{perfDetail.summary.median_return.toFixed(2)}%
                  </p>
                </Card>
              </div>

              {/* 시뮬레이션 매수금액 입력 */}
              <Card className="p-4">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-sm font-medium">시뮬레이션 매수금액:</span>
                  <input
                    type="number"
                    value={simAmount}
                    onChange={(e) => setSimAmount(Number(e.target.value) || 0)}
                    className="w-40 px-3 py-1.5 text-sm border rounded dark:bg-t-bg-elevated dark:border-t-border"
                    step={100000}
                    min={0}
                  />
                  <span className="text-sm text-gray-500 dark:text-t-text-muted">원</span>
                  <div className="flex gap-1 ml-2">
                    {[500000, 1000000, 3000000, 5000000].map(v => (
                      <button
                        key={v}
                        onClick={() => setSimAmount(v)}
                        className={`px-2 py-1 text-xs rounded ${
                          simAmount === v
                            ? 'bg-green-500 text-white'
                            : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted'
                        }`}
                      >
                        {(v / 10000).toFixed(0)}만
                      </button>
                    ))}
                  </div>
                </div>
              </Card>

              {/* 수익률 바 차트 */}
              <Card className="p-6">
                <h3 className="text-lg font-semibold mb-4">수익률 순위 차트</h3>
                <div className="space-y-1.5">
                  {perfDetail.items.map((item) => {
                    const maxAbs = Math.max(
                      ...perfDetail.items.map(i => Math.abs(i.return_rate)),
                      1
                    )
                    const barWidth = Math.min(Math.abs(item.return_rate) / maxAbs * 100, 100)
                    const isPositive = item.return_rate >= 0
                    return (
                      <div key={item.stock_code} className="flex items-center gap-2 text-sm">
                        <span className="w-6 text-right text-gray-400 text-xs shrink-0">
                          {item.rank}
                        </span>
                        <span className="w-24 truncate shrink-0 font-medium" title={item.stock_name}>
                          {item.stock_name}
                        </span>
                        <div className="flex-1 flex items-center h-5">
                          {isPositive ? (
                            <div className="w-1/2 flex justify-end">
                              <div className="w-0" />
                            </div>
                          ) : (
                            <div className="w-1/2 flex justify-end">
                              <div
                                className="h-4 rounded-l bg-blue-400 dark:bg-blue-500"
                                style={{ width: `${barWidth}%` }}
                              />
                            </div>
                          )}
                          {isPositive ? (
                            <div className="w-1/2">
                              <div
                                className="h-4 rounded-r bg-red-400 dark:bg-red-500"
                                style={{ width: `${barWidth}%` }}
                              />
                            </div>
                          ) : (
                            <div className="w-1/2">
                              <div className="w-0" />
                            </div>
                          )}
                        </div>
                        <span className={`w-20 text-right font-medium shrink-0 ${isPositive ? 'text-red-500' : 'text-blue-500'}`}>
                          {isPositive ? '+' : ''}{item.return_rate.toFixed(2)}%
                        </span>
                      </div>
                    )
                  })}
                </div>
              </Card>

              {/* 전체 순위 테이블 */}
              <Card className="p-6">
                <h3 className="text-lg font-semibold mb-4">전체 순위 테이블</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b dark:border-t-border text-gray-500 dark:text-t-text-muted">
                        <th className="py-2 px-2 text-left w-10">#</th>
                        <th className="py-2 px-2 text-left">종목명</th>
                        <th className="py-2 px-2 text-right">첫 언급일</th>
                        <th className="py-2 px-2 text-right">매수가</th>
                        <th className="py-2 px-2 text-right">현재가</th>
                        <th className="py-2 px-2 text-right">수익률</th>
                        <th className="py-2 px-2 text-right">시뮬 P&L</th>
                        <th className="py-2 px-2 text-right">1D</th>
                        <th className="py-2 px-2 text-right">3D</th>
                        <th className="py-2 px-2 text-right">7D</th>
                        <th className="py-2 px-2 text-right">14D</th>
                        <th className="py-2 px-2 text-right">언급수</th>
                      </tr>
                    </thead>
                    <tbody>
                      {perfDetail.items.map((item) => {
                        const simPnl = Math.round(simAmount * item.return_rate / 100)
                        return (
                          <tr
                            key={item.stock_code}
                            className="border-b dark:border-t-border/50 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50"
                          >
                            <td className="py-2 px-2 text-gray-400">{item.rank}</td>
                            <td className="py-2 px-2">
                              <div className="font-medium">{item.stock_name}</div>
                              <div className="text-xs text-gray-400">{item.stock_code}</div>
                            </td>
                            <td className="py-2 px-2 text-right text-gray-600 dark:text-t-text-muted">
                              {formatDate(item.mention_date)}
                            </td>
                            <td className="py-2 px-2 text-right">{item.mention_price.toLocaleString()}</td>
                            <td className="py-2 px-2 text-right">{item.current_price.toLocaleString()}</td>
                            <td className={`py-2 px-2 text-right font-bold ${item.return_rate >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                              {item.return_rate >= 0 ? '+' : ''}{item.return_rate.toFixed(2)}%
                            </td>
                            <td className={`py-2 px-2 text-right font-medium ${simPnl >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                              {simPnl >= 0 ? '+' : ''}{simPnl.toLocaleString()}
                            </td>
                            <PeriodReturnCell value={item.return_1d} />
                            <PeriodReturnCell value={item.return_3d} />
                            <PeriodReturnCell value={item.return_7d} />
                            <PeriodReturnCell value={item.return_14d} />
                            <td className="py-2 px-2 text-right text-gray-500">{item.mention_count}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                    {/* 합계 행 */}
                    <tfoot>
                      <tr className="border-t-2 dark:border-t-border font-bold">
                        <td colSpan={5} className="py-2 px-2">합계 ({perfDetail.summary.total}종목)</td>
                        <td className={`py-2 px-2 text-right ${perfDetail.summary.avg_return >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                          평균 {perfDetail.summary.avg_return >= 0 ? '+' : ''}{perfDetail.summary.avg_return.toFixed(2)}%
                        </td>
                        <td className={`py-2 px-2 text-right ${(() => {
                          const totalPnl = perfDetail.items.reduce((sum, it) => sum + Math.round(simAmount * it.return_rate / 100), 0)
                          return totalPnl >= 0 ? 'text-red-500' : 'text-blue-500'
                        })()}`}>
                          {(() => {
                            const totalPnl = perfDetail.items.reduce((sum, it) => sum + Math.round(simAmount * it.return_rate / 100), 0)
                            return `${totalPnl >= 0 ? '+' : ''}${totalPnl.toLocaleString()}`
                          })()}
                        </td>
                        <td colSpan={5} />
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </Card>
            </>
          )}
        </div>
      )}

      {/* ==================== 내 종목 크로스 체크 탭 ==================== */}
      {activeTab === 'cross-check' && (
        <Card className="p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <span className="text-blue-500">내 아이디어</span> &times; 전문가 관심
          </h2>
          {expertCrossCheck.length === 0 ? (
            <p className="text-gray-500 dark:text-t-text-muted">
              내 아이디어 종목 중 전문가들도 주목하는 종목이 없습니다.
            </p>
          ) : (
            <div className="space-y-3">
              {expertCrossCheck.map((item) => (
                <div
                  key={`${item.stock_code}-${item.idea_title}`}
                  className="flex items-center justify-between p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{item.stock_name}</span>
                      <span className="text-xs text-gray-500 dark:text-t-text-muted">{item.stock_code}</span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-t-text-muted">
                      아이디어: {item.idea_title}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-bold text-blue-600">
                      {item.expert_mention_count}회
                    </p>
                    <p className="text-xs text-gray-500 dark:text-t-text-muted">
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

function PeriodReturnCell({ value }: { value: number | null }) {
  if (value === null) return <td className="py-2 px-2 text-right text-gray-300 dark:text-gray-600">-</td>
  return (
    <td className={`py-2 px-2 text-right ${value >= 0 ? 'text-red-400' : 'text-blue-400'}`}>
      {value >= 0 ? '+' : ''}{value.toFixed(1)}%
    </td>
  )
}
