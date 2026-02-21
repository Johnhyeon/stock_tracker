import { useEffect, useState, useMemo } from 'react'
import { Card } from '../../components/ui/Card'
import TickerSearch from '../../components/ui/TickerSearch'
import type { Stock } from '../../components/ui/TickerSearch'
import { youtubeApi } from '../../services/api'
import type {
  MediaTimelineResponse,
  MentionBacktestResponse,
  OverheatResponse,
  OverheatStock,
  HoldingPeriodStats,
  MentionBacktestItem,
} from '../../types/data'

type TabType = 'timeline' | 'backtest' | 'overheat'

export default function YouTubeTrending() {
  const [activeTab, setActiveTab] = useState<TabType>('overheat')

  return (
    <div className="space-y-6">
      {/* 헤더 + 탭 */}
      <div>
        <h1 className="text-2xl font-bold">YouTube 종목 분석</h1>
        <div className="flex gap-2 mt-3">
          {[
            { key: 'timeline' as TabType, label: '미디어 타임라인', icon: '📊' },
            { key: 'backtest' as TabType, label: '언급 백테스트', icon: '🧪' },
            { key: 'overheat' as TabType, label: '과열 경고', icon: '🔥' },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${
                activeTab === tab.key
                  ? 'bg-red-500 text-white'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-t-border'
              }`}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>
      </div>

      {activeTab === 'timeline' && <TimelineTab />}
      {activeTab === 'backtest' && <BacktestTab />}
      {activeTab === 'overheat' && <OverheatTab />}
    </div>
  )
}

// ==================== Tab 1: 미디어 타임라인 ====================

function TimelineTab() {
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null)
  const [data, setData] = useState<MediaTimelineResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [daysBack, setDaysBack] = useState(90)

  const loadTimeline = async (stockCode: string) => {
    setLoading(true)
    try {
      const result = await youtubeApi.getStockTimeline(stockCode, daysBack)
      setData(result)
    } catch (err) {
      console.error('Timeline load error:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (selectedStock) {
      loadTimeline(selectedStock.code)
    }
  }, [selectedStock, daysBack])

  const handleSelect = (stock: Stock) => {
    setSelectedStock(stock)
  }

  // 차트 정규화 값
  const chartData = useMemo(() => {
    if (!data?.daily.length) return null
    const prices = data.daily.map((d) => d.close_price).filter((p): p is number => p !== null)
    const mentions = data.daily.map((d) => d.mention_count)
    const maxPrice = Math.max(...prices, 1)
    const minPrice = Math.min(...prices, 0)
    const maxMention = Math.max(...mentions, 1)
    return { maxPrice, minPrice, maxMention }
  }, [data])

  return (
    <>
      {/* 종목 검색 + 기간 선택 */}
      <Card className="p-4">
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-1">
              종목 검색
            </label>
            <TickerSearch onSelect={handleSelect} placeholder="종목명 또는 코드로 검색" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-1">
              기간
            </label>
            <select
              value={daysBack}
              onChange={(e) => setDaysBack(Number(e.target.value))}
              className="border rounded px-3 py-2 text-sm bg-white dark:bg-t-bg-elevated dark:border-t-border-hover dark:text-t-text-primary"
            >
              <option value={30}>30일</option>
              <option value={60}>60일</option>
              <option value={90}>90일</option>
              <option value={180}>180일</option>
              <option value={365}>1년</option>
            </select>
          </div>
        </div>
        {selectedStock && (
          <p className="mt-2 text-sm text-gray-500 dark:text-t-text-muted">
            선택: <span className="font-medium text-gray-900 dark:text-t-text-primary">{selectedStock.name}</span> ({selectedStock.code})
          </p>
        )}
      </Card>

      {loading && (
        <Card className="p-8 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-red-500 border-t-transparent mx-auto mb-2" />
          <p className="text-gray-500 dark:text-t-text-muted">데이터 로딩 중...</p>
        </Card>
      )}

      {!loading && !data && !selectedStock && (
        <Card className="p-8 text-center">
          <p className="text-gray-400 dark:text-t-text-muted text-lg mb-1">종목을 검색하세요</p>
          <p className="text-sm text-gray-400 dark:text-t-text-muted">
            종목을 선택하면 유튜브 언급과 주가 변화를 함께 확인할 수 있습니다.
          </p>
        </Card>
      )}

      {!loading && data && (
        <>
          {/* 요약 카드 3개 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="p-4 text-center">
              <p className="text-sm text-gray-500 dark:text-t-text-muted">총 언급 수</p>
              <p className="text-3xl font-bold text-red-500 mt-1">{data.summary.total_mentions}</p>
              <p className="text-xs text-gray-400 dark:text-t-text-muted mt-1">{data.summary.mention_days}일간 언급</p>
            </Card>
            <Card className="p-4 text-center">
              <p className="text-sm text-gray-500 dark:text-t-text-muted">일평균 언급</p>
              <p className="text-3xl font-bold text-orange-500 mt-1">{data.summary.avg_daily}</p>
              <p className="text-xs text-gray-400 dark:text-t-text-muted mt-1">언급일 기준 평균</p>
            </Card>
            <Card className="p-4 text-center">
              <p className="text-sm text-gray-500 dark:text-t-text-muted">첫 언급 이후 주가</p>
              <p className={`text-3xl font-bold mt-1 ${
                (data.summary.price_change_pct || 0) > 0 ? 'text-red-500' :
                (data.summary.price_change_pct || 0) < 0 ? 'text-blue-500' : 'text-gray-500'
              }`}>
                {data.summary.price_change_pct != null
                  ? `${data.summary.price_change_pct > 0 ? '+' : ''}${data.summary.price_change_pct}%`
                  : '-'}
              </p>
              <p className="text-xs text-gray-400 dark:text-t-text-muted mt-1">
                {data.summary.price_at_first_mention != null && data.summary.price_now != null
                  ? `${data.summary.price_at_first_mention.toLocaleString()}원 → ${data.summary.price_now.toLocaleString()}원`
                  : '가격 데이터 없음'}
              </p>
            </Card>
          </div>

          {/* 일별 타임라인 차트 (CSS 기반) */}
          {data.daily.length > 0 && chartData && (
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4">일별 가격 + 언급 추이</h3>
              <div className="relative">
                {/* 가격 라인 */}
                <div className="h-40 flex items-end gap-[1px] mb-1">
                  {data.daily.map((d, i) => {
                    const price = d.close_price
                    const h = price != null
                      ? ((price - chartData.minPrice) / (chartData.maxPrice - chartData.minPrice || 1)) * 100
                      : 0
                    return (
                      <div
                        key={`price-${i}`}
                        className="flex-1 group relative"
                        style={{ height: '100%' }}
                      >
                        <div
                          className="absolute bottom-0 w-full bg-blue-400/60 dark:bg-blue-500/50 rounded-t-sm transition-all"
                          style={{ height: `${Math.max(h, 2)}%` }}
                        />
                        {/* 툴팁 */}
                        <div className="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 hidden group-hover:block z-10 bg-gray-900 text-white text-[10px] rounded px-2 py-1 whitespace-nowrap">
                          <div>{d.date}</div>
                          {price != null && <div>{price.toLocaleString()}원</div>}
                          <div>언급 {d.mention_count}회</div>
                        </div>
                      </div>
                    )
                  })}
                </div>
                {/* 언급 바 */}
                <div className="h-16 flex items-end gap-[1px]">
                  {data.daily.map((d, i) => {
                    const h = (d.mention_count / chartData.maxMention) * 100
                    return (
                      <div
                        key={`mention-${i}`}
                        className="flex-1 bg-red-400/70 dark:bg-red-500/60 rounded-t-sm"
                        style={{ height: `${Math.max(h, d.mention_count > 0 ? 8 : 0)}%` }}
                      />
                    )
                  })}
                </div>
                {/* 범례 */}
                <div className="flex gap-4 mt-2 text-xs text-gray-500 dark:text-t-text-muted justify-end">
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 bg-blue-400/60 rounded-sm inline-block" /> 주가
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-3 bg-red-400/70 rounded-sm inline-block" /> 언급
                  </span>
                </div>
              </div>
            </Card>
          )}

          {/* 영상 목록 */}
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">관련 영상 ({data.videos.length}개)</h3>
            {data.videos.length === 0 ? (
              <p className="text-gray-400 dark:text-t-text-muted text-center py-4">관련 영상이 없습니다.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {data.videos.map((v) => (
                  <div
                    key={v.video_id}
                    className="flex gap-3 p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 cursor-pointer"
                    onClick={() => window.open(`https://www.youtube.com/watch?v=${v.video_id}`, '_blank')}
                  >
                    {v.thumbnail_url && (
                      <img src={v.thumbnail_url} alt="" className="w-28 h-16 object-cover rounded" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm line-clamp-2">{v.video_title}</p>
                      <p className="text-xs text-gray-500 dark:text-t-text-muted mt-1">
                        {v.channel_name} · {new Date(v.published_at).toLocaleDateString('ko-KR')}
                      </p>
                      {v.view_count != null && (
                        <p className="text-xs text-gray-400 dark:text-t-text-muted">
                          {formatViews(v.view_count)} 조회
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}
    </>
  )
}

// ==================== Tab 2: 언급 백테스트 ====================

function BacktestTab() {
  const [data, setData] = useState<MentionBacktestResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [daysBack, setDaysBack] = useState(90)
  const [minMentions, setMinMentions] = useState(3)
  const [holdingDays, setHoldingDays] = useState(['3', '7', '14'])

  const loadBacktest = async () => {
    setLoading(true)
    try {
      const result = await youtubeApi.getMentionBacktest({
        days_back: daysBack,
        min_mentions: minMentions,
        holding_days: holdingDays.join(','),
      })
      setData(result)
    } catch (err) {
      console.error('Backtest load error:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBacktest()
  }, [daysBack, minMentions, holdingDays])

  const toggleHoldingDay = (day: string) => {
    setHoldingDays((prev) => {
      if (prev.includes(day)) {
        if (prev.length === 1) return prev // 최소 1개
        return prev.filter((d) => d !== day)
      }
      return [...prev, day].sort((a, b) => Number(a) - Number(b))
    })
  }

  return (
    <>
      {/* 파라미터 패널 */}
      <Card className="p-4">
        <div className="flex flex-wrap gap-6 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-1">분석 기간</label>
            <select
              value={daysBack}
              onChange={(e) => setDaysBack(Number(e.target.value))}
              className="border rounded px-3 py-2 text-sm bg-white dark:bg-t-bg-elevated dark:border-t-border-hover dark:text-t-text-primary"
            >
              <option value={30}>30일</option>
              <option value={60}>60일</option>
              <option value={90}>90일</option>
              <option value={180}>180일</option>
              <option value={365}>1년</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-1">최소 언급수</label>
            <select
              value={minMentions}
              onChange={(e) => setMinMentions(Number(e.target.value))}
              className="border rounded px-3 py-2 text-sm bg-white dark:bg-t-bg-elevated dark:border-t-border-hover dark:text-t-text-primary"
            >
              <option value={1}>1회 이상</option>
              <option value={2}>2회 이상</option>
              <option value={3}>3회 이상</option>
              <option value={5}>5회 이상</option>
              <option value={10}>10회 이상</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-1">보유 기간</label>
            <div className="flex gap-2">
              {['3', '7', '14', '30'].map((day) => (
                <button
                  key={day}
                  onClick={() => toggleHoldingDay(day)}
                  className={`px-3 py-1.5 text-sm rounded border transition-colors ${
                    holdingDays.includes(day)
                      ? 'bg-red-500 text-white border-red-500'
                      : 'bg-white dark:bg-t-bg-elevated border-gray-300 dark:border-t-border text-gray-600 dark:text-t-text-muted'
                  }`}
                >
                  {day}일
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {loading && (
        <Card className="p-8 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-red-500 border-t-transparent mx-auto mb-2" />
          <p className="text-gray-500 dark:text-t-text-muted">백테스트 실행 중...</p>
        </Card>
      )}

      {!loading && data && (
        <>
          {/* 요약 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="p-4 text-center">
              <p className="text-sm text-gray-500 dark:text-t-text-muted">총 신호</p>
              <p className="text-3xl font-bold text-gray-900 dark:text-t-text-primary mt-1">{data.total_signals}개</p>
            </Card>
            <Card className="p-4 text-center">
              <p className="text-sm text-gray-500 dark:text-t-text-muted">평균 수익률</p>
              <p className={`text-3xl font-bold mt-1 ${
                (data.summary.avg_return as number) > 0 ? 'text-red-500' :
                (data.summary.avg_return as number) < 0 ? 'text-blue-500' : 'text-gray-500'
              }`}>
                {(data.summary.avg_return as number) > 0 ? '+' : ''}{String(data.summary.avg_return)}%
              </p>
            </Card>
            <Card className="p-4 text-center">
              <p className="text-sm text-gray-500 dark:text-t-text-muted">승률</p>
              <p className={`text-3xl font-bold mt-1 ${
                (data.summary.win_rate as number) >= 50 ? 'text-green-500' : 'text-orange-500'
              }`}>
                {String(data.summary.win_rate)}%
              </p>
            </Card>
          </div>

          {/* 보유기간별 성과 카드 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Object.entries(data.holding_stats).map(([period, stats]: [string, HoldingPeriodStats]) => (
              <Card key={period} className="p-4">
                <h4 className="font-semibold text-center mb-3 text-lg">{period} 보유</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-t-text-muted">샘플 수</span>
                    <span className="font-medium">{stats.sample_count}개</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-t-text-muted">평균 수익률</span>
                    <span className={`font-medium ${stats.avg_return > 0 ? 'text-red-500' : stats.avg_return < 0 ? 'text-blue-500' : ''}`}>
                      {stats.avg_return > 0 ? '+' : ''}{stats.avg_return}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-t-text-muted">중앙값</span>
                    <span className={`font-medium ${stats.median > 0 ? 'text-red-500' : stats.median < 0 ? 'text-blue-500' : ''}`}>
                      {stats.median > 0 ? '+' : ''}{stats.median}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-t-text-muted">승률</span>
                    <span className={`font-medium ${stats.win_rate >= 50 ? 'text-green-500' : 'text-orange-500'}`}>
                      {stats.win_rate}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-t-text-muted">최대 수익</span>
                    <span className="font-medium text-red-500">+{stats.max_return}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-t-text-muted">최대 손실</span>
                    <span className="font-medium text-blue-500">{stats.max_loss}%</span>
                  </div>
                </div>
              </Card>
            ))}
          </div>

          {/* 최고/최악 종목 */}
          {(data.summary.best_stock || data.summary.worst_stock) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {!!data.summary.best_stock && (
                <Card className="p-4 border-l-4 border-l-red-500">
                  <p className="text-sm text-gray-500 dark:text-t-text-muted">최고 수익 종목</p>
                  <p className="font-medium text-red-500 mt-1">{String(data.summary.best_stock)}</p>
                </Card>
              )}
              {!!data.summary.worst_stock && (
                <Card className="p-4 border-l-4 border-l-blue-500">
                  <p className="text-sm text-gray-500 dark:text-t-text-muted">최악 손실 종목</p>
                  <p className="font-medium text-blue-500 mt-1">{String(data.summary.worst_stock)}</p>
                </Card>
              )}
            </div>
          )}

          {/* 전체 신호 테이블 */}
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">전체 신호 목록 ({data.items.length}개)</h3>
            {data.items.length === 0 ? (
              <p className="text-gray-400 dark:text-t-text-muted text-center py-4">조건에 맞는 신호가 없습니다.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b dark:border-t-border text-left">
                      <th className="py-2 px-2 font-medium text-gray-500 dark:text-t-text-muted">종목</th>
                      <th className="py-2 px-2 font-medium text-gray-500 dark:text-t-text-muted">신호일</th>
                      <th className="py-2 px-2 font-medium text-gray-500 dark:text-t-text-muted text-right">언급수</th>
                      <th className="py-2 px-2 font-medium text-gray-500 dark:text-t-text-muted text-right">진입가</th>
                      {holdingDays.map((d) => (
                        <th key={d} className="py-2 px-2 font-medium text-gray-500 dark:text-t-text-muted text-right">{d}일</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((item: MentionBacktestItem, idx: number) => (
                      <tr key={idx} className="border-b dark:border-t-border/50 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50">
                        <td className="py-2 px-2">
                          <div className="font-medium">{item.stock_name || item.stock_code}</div>
                          <div className="text-xs text-gray-400 dark:text-t-text-muted">{item.stock_code}</div>
                        </td>
                        <td className="py-2 px-2 text-gray-600 dark:text-t-text-secondary">{item.signal_date}</td>
                        <td className="py-2 px-2 text-right">{item.mention_count}</td>
                        <td className="py-2 px-2 text-right">{item.entry_price.toLocaleString()}</td>
                        {holdingDays.map((d) => {
                          const ret = item.returns[`${d}d`]
                          return (
                            <td key={d} className={`py-2 px-2 text-right font-medium ${
                              ret == null ? 'text-gray-400' : ret > 0 ? 'text-red-500' : ret < 0 ? 'text-blue-500' : ''
                            }`}>
                              {ret != null ? `${ret > 0 ? '+' : ''}${ret}%` : '-'}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </>
  )
}

// ==================== Tab 3: 과열 경고 ====================

const STATUS_CONFIG: Record<string, { label: string; color: string; bgColor: string; desc: string }> = {
  FRENZY: { label: '광풍', color: 'text-red-700 dark:text-red-400', bgColor: 'bg-red-100 dark:bg-red-900/30', desc: '극단적 과열 - 극도의 주의' },
  OVERHEAT: { label: '과열', color: 'text-orange-700 dark:text-orange-400', bgColor: 'bg-orange-100 dark:bg-orange-900/30', desc: '이미 올랐다, 조심' },
  CONTRARIAN: { label: '역발상', color: 'text-purple-700 dark:text-purple-400', bgColor: 'bg-purple-100 dark:bg-purple-900/30', desc: '언급 증가 + 주가 하락 = 기회?' },
  COOLING: { label: '냉각', color: 'text-blue-700 dark:text-blue-400', bgColor: 'bg-blue-100 dark:bg-blue-900/30', desc: '관심 소멸 중' },
  NORMAL: { label: '보통', color: 'text-gray-700 dark:text-gray-400', bgColor: 'bg-gray-100 dark:bg-gray-700/30', desc: '평소 수준' },
}

function OverheatTab() {
  const [data, setData] = useState<OverheatResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [recentDays, setRecentDays] = useState(3)
  const [baselineDays, setBaselineDays] = useState(30)

  const loadOverheat = async () => {
    setLoading(true)
    try {
      const result = await youtubeApi.getOverheat(recentDays, baselineDays)
      setData(result)
    } catch (err) {
      console.error('Overheat load error:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadOverheat()
  }, [recentDays, baselineDays])

  const maxRatio = useMemo(() => {
    if (!data?.items.length) return 1
    return Math.max(...data.items.map((it) => it.overheat_ratio), 1)
  }, [data])

  return (
    <>
      {/* 파라미터 */}
      <Card className="p-4">
        <div className="flex flex-wrap gap-6 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-1">최근 기간</label>
            <select
              value={recentDays}
              onChange={(e) => setRecentDays(Number(e.target.value))}
              className="border rounded px-3 py-2 text-sm bg-white dark:bg-t-bg-elevated dark:border-t-border-hover dark:text-t-text-primary"
            >
              <option value={1}>1일</option>
              <option value={3}>3일</option>
              <option value={5}>5일</option>
              <option value={7}>7일</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-1">기준 기간</label>
            <select
              value={baselineDays}
              onChange={(e) => setBaselineDays(Number(e.target.value))}
              className="border rounded px-3 py-2 text-sm bg-white dark:bg-t-bg-elevated dark:border-t-border-hover dark:text-t-text-primary"
            >
              <option value={14}>14일</option>
              <option value={30}>30일</option>
              <option value={60}>60일</option>
              <option value={90}>90일</option>
            </select>
          </div>
        </div>
      </Card>

      {loading && (
        <Card className="p-8 text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-red-500 border-t-transparent mx-auto mb-2" />
          <p className="text-gray-500 dark:text-t-text-muted">과열 분석 중...</p>
        </Card>
      )}

      {!loading && data && (
        <>
          {/* 상태별 요약 카드 */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {[
              { key: 'frenzy_count', status: 'FRENZY' },
              { key: 'overheat_count', status: 'OVERHEAT' },
              { key: 'contrarian_count', status: 'CONTRARIAN' },
              { key: 'cooling_count', status: 'COOLING' },
              { key: 'total', status: 'TOTAL' },
            ].map(({ key, status }) => {
              const config = STATUS_CONFIG[status]
              const count = data.summary[key as keyof typeof data.summary]
              return (
                <Card key={key} className={`p-3 text-center ${status !== 'TOTAL' ? config?.bgColor : ''}`}>
                  <p className={`text-sm ${status !== 'TOTAL' ? config?.color : 'text-gray-500 dark:text-t-text-muted'}`}>
                    {status === 'TOTAL' ? '전체' : config?.label}
                  </p>
                  <p className={`text-2xl font-bold mt-1 ${status !== 'TOTAL' ? config?.color : 'text-gray-900 dark:text-t-text-primary'}`}>
                    {count}
                  </p>
                </Card>
              )
            })}
          </div>

          {/* 종목 리스트 */}
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">과열 종목 ({data.items.length}개)</h3>
            {data.items.length === 0 ? (
              <p className="text-gray-400 dark:text-t-text-muted text-center py-4">과열 종목이 없습니다.</p>
            ) : (
              <div className="space-y-3">
                {data.items.map((item: OverheatStock) => {
                  const config = STATUS_CONFIG[item.status] || STATUS_CONFIG.NORMAL
                  const barWidth = Math.min((item.overheat_ratio / maxRatio) * 100, 100)
                  return (
                    <div
                      key={item.stock_code}
                      className={`p-4 rounded-lg border ${
                        item.status === 'CONTRARIAN'
                          ? 'border-purple-300 dark:border-purple-700 bg-purple-50/50 dark:bg-purple-900/10'
                          : item.status === 'FRENZY'
                          ? 'border-red-300 dark:border-red-700 bg-red-50/50 dark:bg-red-900/10'
                          : 'border-gray-200 dark:border-t-border'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div>
                            <span className="font-semibold">{item.stock_name || item.stock_code}</span>
                            <span className="text-xs text-gray-400 dark:text-t-text-muted ml-2">{item.stock_code}</span>
                          </div>
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${config.bgColor} ${config.color}`} title={config.desc}>
                            {config.label}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 text-sm">
                          {item.price_change_pct != null && (
                            <span className={`font-medium ${item.price_change_pct > 0 ? 'text-red-500' : item.price_change_pct < 0 ? 'text-blue-500' : 'text-gray-500'}`}>
                              {item.price_change_pct > 0 ? '+' : ''}{item.price_change_pct}%
                            </span>
                          )}
                          <span className="text-gray-500 dark:text-t-text-muted">
                            x{item.overheat_ratio}
                          </span>
                        </div>
                      </div>
                      {/* 과열 비율 바 */}
                      <div className="h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden mb-2">
                        <div
                          className={`h-full rounded-full transition-all ${
                            item.status === 'FRENZY' ? 'bg-red-500' :
                            item.status === 'OVERHEAT' ? 'bg-orange-500' :
                            item.status === 'CONTRARIAN' ? 'bg-purple-500' :
                            item.status === 'COOLING' ? 'bg-blue-400' : 'bg-gray-400'
                          }`}
                          style={{ width: `${barWidth}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-xs text-gray-500 dark:text-t-text-muted">
                        <span>최근 {recentDays}일: {item.recent_mentions}회 (기준 일평균: {item.baseline_avg_daily})</span>
                        <span>총 {item.mention_count_total}회 · 최근 영상 {item.recent_videos_count}개</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Card>
        </>
      )}
    </>
  )
}

// ==================== 유틸 ====================

function formatViews(views: number): string {
  if (views >= 1000000) return `${(views / 1000000).toFixed(1)}M`
  if (views >= 1000) return `${(views / 1000).toFixed(1)}K`
  return views.toString()
}
