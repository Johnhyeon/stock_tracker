import { useState, useEffect, useRef, useCallback } from 'react'
import { etfRotationApi, type EtfHeatmapItem, type RotationSignal, type RealtimeEtfItem } from '../../services/api'
import ThemeDetailModal from './ThemeDetailModal'
import AllEtfCompareModal from './AllEtfCompareModal'

type Period = 'realtime' | '1d' | '5d' | '20d' | '60d'

const periodLabels: Record<Period, string> = {
  'realtime': '실시간',
  '1d': '1일',
  '5d': '5일',
  '20d': '20일',
  '60d': '60일',
}

// 등락률에 따른 색상 클래스
function getChangeColorClass(change: number | null): string {
  if (change === null) return 'bg-gray-100 text-gray-500'
  if (change >= 5) return 'bg-red-500 text-white'
  if (change >= 3) return 'bg-red-400 text-white'
  if (change >= 1) return 'bg-red-200 text-red-800'
  if (change >= 0) return 'bg-red-50 text-red-600'
  if (change >= -1) return 'bg-blue-50 text-blue-600'
  if (change >= -3) return 'bg-blue-200 text-blue-800'
  if (change >= -5) return 'bg-blue-400 text-white'
  return 'bg-blue-500 text-white'
}

// 거래대금 비율에 따른 아이콘
function getVolumeIndicator(ratio: number | null): string {
  if (ratio === null) return ''
  if (ratio >= 3) return '🔥🔥'
  if (ratio >= 2) return '🔥'
  if (ratio >= 1.5) return '📈'
  if (ratio <= 0.5) return '📉'
  return ''
}

// 시그널 타입별 배지 색상
function getSignalBadgeClass(signalType: string): string {
  switch (signalType) {
    case 'STRONG_UP':
      return 'bg-red-100 text-red-700 border-red-300'
    case 'MOMENTUM_UP':
      return 'bg-orange-100 text-orange-700 border-orange-300'
    case 'REVERSAL_UP':
      return 'bg-yellow-100 text-yellow-700 border-yellow-300'
    case 'STRONG_DOWN':
      return 'bg-blue-100 text-blue-700 border-blue-300'
    default:
      return 'bg-gray-100 text-gray-700 border-gray-300'
  }
}

// 시그널 타입 한글
function getSignalLabel(signalType: string): string {
  switch (signalType) {
    case 'STRONG_UP':
      return '강세 전환'
    case 'MOMENTUM_UP':
      return '모멘텀'
    case 'REVERSAL_UP':
      return '반등 시도'
    case 'STRONG_DOWN':
      return '약세 전환'
    default:
      return signalType
  }
}

// 금액 포맷
function formatAmount(value: number | null): string {
  if (value === null) return '-'
  if (value >= 1e12) return `${(value / 1e12).toFixed(1)}조`
  if (value >= 1e8) return `${(value / 1e8).toFixed(0)}억`
  if (value >= 1e4) return `${(value / 1e4).toFixed(0)}만`
  return value.toLocaleString()
}

export default function EtfRotationHeatmap() {
  const [period, setPeriod] = useState<Period>('realtime')
  const [themes, setThemes] = useState<EtfHeatmapItem[]>([])
  const [realtimeThemes, setRealtimeThemes] = useState<RealtimeEtfItem[]>([])
  const [signals, setSignals] = useState<RotationSignal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [selectedTheme, setSelectedTheme] = useState<string | null>(null)
  const [showCompareModal, setShowCompareModal] = useState(false)
  const [marketStatus, setMarketStatus] = useState<'open' | 'closed' | 'error'>('closed')
  const refreshIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchRealtimeData = useCallback(async () => {
    try {
      const data = await etfRotationApi.getRealtimeHeatmap()
      setRealtimeThemes(data.themes)
      setLastUpdated(data.updated_at)
      setMarketStatus(data.market_status)
      setError(null)
    } catch (err) {
      console.error('실시간 데이터 조회 실패:', err)
      setError('실시간 데이터를 불러오는데 실패했습니다')
    }
  }, [])

  const fetchHistoricalData = useCallback(async (p: '1d' | '5d' | '20d' | '60d') => {
    try {
      const [heatmapRes, signalsRes] = await Promise.all([
        etfRotationApi.getHeatmap(p),
        etfRotationApi.getSignals(),
      ])
      setThemes(heatmapRes.themes)
      setSignals(signalsRes.signals)
      setLastUpdated(heatmapRes.generated_at)
      setError(null)
    } catch (err) {
      setError('데이터를 불러오는데 실패했습니다')
      console.error(err)
    }
  }, [])

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      if (period === 'realtime') {
        await fetchRealtimeData()
        // 시그널도 함께 조회
        try {
          const signalsRes = await etfRotationApi.getSignals()
          setSignals(signalsRes.signals)
        } catch (err) {
          console.warn('시그널 조회 실패:', err)
        }
      } else {
        await fetchHistoricalData(period)
      }
      setLoading(false)
    }
    fetchData()
  }, [period, fetchRealtimeData, fetchHistoricalData])

  // 실시간 모드일 때 1분마다 자동 갱신
  useEffect(() => {
    if (period === 'realtime') {
      refreshIntervalRef.current = setInterval(() => {
        fetchRealtimeData()
      }, 60000) // 1분
    }

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
        refreshIntervalRef.current = null
      }
    }
  }, [period, fetchRealtimeData])

  const getChangeValue = (item: EtfHeatmapItem | RealtimeEtfItem): number | null => {
    if (period === 'realtime') {
      return (item as RealtimeEtfItem).change_1d
    }
    const historicalItem = item as EtfHeatmapItem
    switch (period) {
      case '1d': return historicalItem.change_1d
      case '5d': return historicalItem.change_5d
      case '20d': return historicalItem.change_20d
      case '60d': return historicalItem.change_60d
      default: return historicalItem.change_5d
    }
  }

  // 시그널이 있는 테마 찾기
  const getSignalForTheme = (theme: string): RotationSignal | undefined => {
    return signals.find(s => s.theme === theme)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  const handleRetry = async () => {
    setLoading(true)
    setError(null)
    if (period === 'realtime') {
      await fetchRealtimeData()
    } else {
      await fetchHistoricalData(period)
    }
    setLoading(false)
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        {error}
        <button
          onClick={handleRetry}
          className="ml-2 text-red-600 underline hover:no-underline"
        >
          다시 시도
        </button>
      </div>
    )
  }

  return (
    <>
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">섹터 순환매 히트맵</h2>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-gray-500">
              {period === 'realtime' ? 'KIS API 실시간' : 'ETF 등락률 기준'} • {lastUpdated ? new Date(lastUpdated).toLocaleString('ko-KR') : ''}
            </p>
            {period === 'realtime' && (
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                marketStatus === 'open'
                  ? 'bg-green-100 text-green-700'
                  : marketStatus === 'closed'
                    ? 'bg-gray-100 text-gray-600'
                    : 'bg-red-100 text-red-700'
              }`}>
                {marketStatus === 'open' ? '🟢 장중' : marketStatus === 'closed' ? '⚪ 장마감' : '🔴 오류'}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {period === 'realtime' && (
            <button
              onClick={fetchRealtimeData}
              disabled={loading}
              className="px-3 py-1.5 text-sm font-medium rounded-md bg-green-500 text-white hover:bg-green-600 disabled:opacity-50 transition-colors"
            >
              {loading ? '갱신중...' : '🔄 새로고침'}
            </button>
          )}
          <button
            onClick={() => setShowCompareModal(true)}
            className="px-3 py-1.5 text-sm font-medium rounded-md bg-gradient-to-r from-purple-500 to-indigo-500 text-white hover:from-purple-600 hover:to-indigo-600 transition-all shadow-sm"
          >
            전체 비교 차트
          </button>
          <div className="flex gap-1">
            {(Object.keys(periodLabels) as Period[]).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  period === p
                    ? p === 'realtime'
                      ? 'bg-green-600 text-white'
                      : 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {periodLabels[p]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 시그널 요약 */}
      {signals.length > 0 && (
        <div className="bg-gradient-to-r from-orange-50 to-yellow-50 border border-orange-200 rounded-lg p-4">
          <h3 className="font-semibold text-orange-800 mb-2">순환매 시그널</h3>
          <div className="flex flex-wrap gap-2">
            {signals.slice(0, 6).map((signal) => (
              <div
                key={signal.etf_code}
                className={`px-3 py-1.5 rounded-full border text-sm font-medium ${getSignalBadgeClass(signal.signal_type)}`}
              >
                <span className="mr-1">{getSignalLabel(signal.signal_type)}</span>
                <span className="font-bold">{signal.theme}</span>
                <span className="ml-1 opacity-75">
                  ({signal.change_5d > 0 ? '+' : ''}{signal.change_5d.toFixed(1)}%)
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 히트맵 그리드 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
        {(period === 'realtime' ? realtimeThemes : themes).map((item) => {
          const changeValue = getChangeValue(item)
          const signal = getSignalForTheme(item.theme)
          const isRealtime = period === 'realtime'
          const realtimeItem = item as RealtimeEtfItem
          const historicalItem = item as EtfHeatmapItem

          return (
            <div
              key={item.etf_code}
              className={`relative rounded-lg p-3 transition-transform hover:scale-105 cursor-pointer ${getChangeColorClass(changeValue)}`}
              title={`${item.etf_name}${isRealtime ? `\n현재가: ${realtimeItem.current_price?.toLocaleString()}원` : `\n거래대금: ${formatAmount(historicalItem.trading_value)}`}`}
              onClick={() => setSelectedTheme(item.theme)}
            >
              {/* 순위 배지 */}
              {item.rank && item.rank <= 3 && (
                <div className="absolute -top-2 -left-2 w-6 h-6 rounded-full bg-yellow-400 text-yellow-900 text-xs font-bold flex items-center justify-center shadow">
                  {item.rank}
                </div>
              )}

              {/* 시그널 표시 */}
              {signal && (
                <div className="absolute -top-1 -right-1 text-xs">
                  {signal.signal_type === 'STRONG_UP' && '🚀'}
                  {signal.signal_type === 'MOMENTUM_UP' && '📈'}
                  {signal.signal_type === 'REVERSAL_UP' && '🔄'}
                  {signal.signal_type === 'STRONG_DOWN' && '📉'}
                </div>
              )}

              {/* 테마명 */}
              <div className="font-bold text-sm truncate">{item.theme}</div>

              {/* 등락률 */}
              <div className="text-lg font-bold mt-1">
                {changeValue !== null ? (
                  <>
                    {changeValue > 0 ? '+' : ''}
                    {changeValue.toFixed(1)}%
                  </>
                ) : (
                  '-'
                )}
              </div>

              {/* 실시간 모드: 현재가 / 히스토리 모드: 거래대금 */}
              <div className="text-xs opacity-75 mt-1 flex items-center gap-1">
                {isRealtime ? (
                  <span>{realtimeItem.current_price?.toLocaleString()}원</span>
                ) : (
                  <>
                    <span>{formatAmount(historicalItem.trading_value)}</span>
                    <span>{getVolumeIndicator(historicalItem.trading_value_ratio)}</span>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* 범례 */}
      <div className="flex items-center justify-center gap-4 text-xs text-gray-500 pt-4 border-t">
        <div className="flex items-center gap-1">
          <span className="w-4 h-4 rounded bg-red-500"></span>
          <span>+5% 이상</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-4 h-4 rounded bg-red-200"></span>
          <span>+1~3%</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-4 h-4 rounded bg-gray-100"></span>
          <span>보합</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-4 h-4 rounded bg-blue-200"></span>
          <span>-1~3%</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-4 h-4 rounded bg-blue-500"></span>
          <span>-5% 이하</span>
        </div>
        <div className="flex items-center gap-1 ml-4">
          <span>🔥</span>
          <span>거래량 급증</span>
        </div>
      </div>

      {/* 상세 테이블 */}
      <div className="bg-white rounded-lg border overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b">
          <h3 className="font-semibold text-gray-900">상세 데이터</h3>
        </div>
        <div className="overflow-x-auto">
          {period === 'realtime' ? (
            // 실시간 테이블
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">순위</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">테마</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">현재가</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">등락률</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">5일</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">20일</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">고가</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">저가</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {realtimeThemes.map((item, idx) => (
                  <tr key={item.etf_code} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-sm text-gray-500">{idx + 1}</td>
                    <td className="px-4 py-2 text-sm font-medium text-gray-900">
                      {item.theme}
                      <span className="ml-1 text-xs text-gray-400">({item.etf_code})</span>
                    </td>
                    <td className="px-4 py-2 text-sm text-right font-medium text-gray-900">
                      {item.current_price?.toLocaleString()}
                    </td>
                    <td className={`px-4 py-2 text-sm text-right font-bold ${item.change_1d && item.change_1d > 0 ? 'text-red-600' : item.change_1d && item.change_1d < 0 ? 'text-blue-600' : 'text-gray-500'}`}>
                      {item.change_1d !== null ? `${item.change_1d > 0 ? '+' : ''}${item.change_1d.toFixed(2)}%` : '-'}
                    </td>
                    <td className={`px-4 py-2 text-sm text-right ${item.change_5d && item.change_5d > 0 ? 'text-red-600' : item.change_5d && item.change_5d < 0 ? 'text-blue-600' : 'text-gray-500'}`}>
                      {item.change_5d !== null ? `${item.change_5d > 0 ? '+' : ''}${item.change_5d.toFixed(1)}%` : '-'}
                    </td>
                    <td className={`px-4 py-2 text-sm text-right ${item.change_20d && item.change_20d > 0 ? 'text-red-600' : item.change_20d && item.change_20d < 0 ? 'text-blue-600' : 'text-gray-500'}`}>
                      {item.change_20d !== null ? `${item.change_20d > 0 ? '+' : ''}${item.change_20d.toFixed(1)}%` : '-'}
                    </td>
                    <td className="px-4 py-2 text-sm text-right text-red-500">
                      {item.high_price?.toLocaleString()}
                    </td>
                    <td className="px-4 py-2 text-sm text-right text-blue-500">
                      {item.low_price?.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            // 히스토리 테이블
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">순위</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">테마</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">1일</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">5일</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">20일</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">60일</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">거래대금</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">평균比</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {themes.map((item, idx) => (
                  <tr key={item.etf_code} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-sm text-gray-500">{idx + 1}</td>
                    <td className="px-4 py-2 text-sm font-medium text-gray-900">
                      {item.theme}
                      <span className="ml-1 text-xs text-gray-400">({item.etf_code})</span>
                    </td>
                    <td className={`px-4 py-2 text-sm text-right ${item.change_1d && item.change_1d > 0 ? 'text-red-600' : item.change_1d && item.change_1d < 0 ? 'text-blue-600' : 'text-gray-500'}`}>
                      {item.change_1d !== null ? `${item.change_1d > 0 ? '+' : ''}${item.change_1d.toFixed(1)}%` : '-'}
                    </td>
                    <td className={`px-4 py-2 text-sm text-right font-medium ${item.change_5d && item.change_5d > 0 ? 'text-red-600' : item.change_5d && item.change_5d < 0 ? 'text-blue-600' : 'text-gray-500'}`}>
                      {item.change_5d !== null ? `${item.change_5d > 0 ? '+' : ''}${item.change_5d.toFixed(1)}%` : '-'}
                    </td>
                    <td className={`px-4 py-2 text-sm text-right ${item.change_20d && item.change_20d > 0 ? 'text-red-600' : item.change_20d && item.change_20d < 0 ? 'text-blue-600' : 'text-gray-500'}`}>
                      {item.change_20d !== null ? `${item.change_20d > 0 ? '+' : ''}${item.change_20d.toFixed(1)}%` : '-'}
                    </td>
                    <td className={`px-4 py-2 text-sm text-right ${item.change_60d && item.change_60d > 0 ? 'text-red-600' : item.change_60d && item.change_60d < 0 ? 'text-blue-600' : 'text-gray-500'}`}>
                      {item.change_60d !== null ? `${item.change_60d > 0 ? '+' : ''}${item.change_60d.toFixed(1)}%` : '-'}
                    </td>
                    <td className="px-4 py-2 text-sm text-right text-gray-600">
                      {formatAmount(item.trading_value)}
                    </td>
                    <td className="px-4 py-2 text-sm text-right">
                      {item.trading_value_ratio !== null ? (
                        <span className={item.trading_value_ratio >= 1.5 ? 'text-orange-600 font-medium' : 'text-gray-500'}>
                          {item.trading_value_ratio.toFixed(1)}x
                        </span>
                      ) : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>

    {/* 테마 상세 모달 */}
    <ThemeDetailModal
      themeName={selectedTheme}
      onClose={() => setSelectedTheme(null)}
    />

    {/* 전체 비교 차트 모달 */}
    <AllEtfCompareModal
      isOpen={showCompareModal}
      onClose={() => setShowCompareModal(false)}
    />
    </>
  )
}
