import { useEffect, useRef, useState, memo } from 'react'
import { createChart, IChartApi, ISeriesApi, CandlestickSeries, HistogramSeries, LineSeries, UTCTimestamp, LogicalRange } from 'lightweight-charts'
import { themeSetupApi } from '../services/api'

export interface OHLCVCandle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

// 매수 마커 타입
interface EntryMarker {
  date: string  // YYYY-MM-DD
  price: number
  quantity?: number
}

interface StockChartProps {
  stockCode: string
  stockName: string
  patternType?: string
  height?: number
  days?: number
  ohlcvData?: OHLCVCandle[]  // 외부에서 데이터 전달 시 사용
  initialPriceLine?: number  // 진입가/기준가 라인
  priceLineLabel?: string    // 라인 라벨 (기본: '기준가')
  avgEntryPrice?: number     // 포지션 평균 매수가 라인
  entryMarkers?: EntryMarker[]  // 매수 지점 마커
  showHeader?: boolean  // 헤더 표시 여부
  enableScrollLoad?: boolean  // 스크롤 시 추가 로딩 활성화
}

function StockChartComponent({
  stockCode,
  stockName,
  patternType,
  height = 250,
  days = 90,
  ohlcvData,
  initialPriceLine,
  priceLineLabel = '기준가',
  avgEntryPrice,
  entryMarkers,
  showHeader = true,
  enableScrollLoad = true,
}: StockChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const ma60SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [chartReady, setChartReady] = useState(false)

  // 스크롤 로딩용 상태
  const allCandlesRef = useRef<OHLCVCandle[]>([])
  const hasMoreRef = useRef(true)
  const isLoadingMoreRef = useRef(false)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markersApiRef = useRef<any>(null)

  // TradingView 링크 (한국어)
  const tradingViewUrl = `https://kr.tradingview.com/chart/?symbol=KRX:${stockCode}`

  // 마커 생성 함수
  const updateMarkers = (candleSeries: ISeriesApi<'Candlestick'>, candles: OHLCVCandle[], showIdea: boolean) => {
    const candleTimes = candles.map(c => c.time)
    const minTime = Math.min(...candleTimes)
    const maxTime = Math.max(...candleTimes)

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const allMarkers: any[] = []

    // 매수 지점 마커
    if (entryMarkers && entryMarkers.length > 0) {
      entryMarkers.forEach(marker => {
        const timestamp = new Date(marker.date).getTime() / 1000
        if (timestamp >= minTime && timestamp <= maxTime) {
          allMarkers.push({
            time: (timestamp + KST_TO_UTC) as UTCTimestamp,
            position: 'belowBar' as const,
            color: '#16a34a',
            shape: 'arrowUp' as const,
            text: `매수 ${marker.price.toLocaleString()}원`,
          })
        }
      })
    }

    // 아이디어 언급 마커 (showIdea가 true일 때만)
    if (showIdea && ideaMarkers && ideaMarkers.length > 0) {
      const timestampToDate = new Map<string, number>()
      candles.forEach(c => {
        const d = new Date(c.time * 1000)
        const year = d.getFullYear()
        const month = String(d.getMonth() + 1).padStart(2, '0')
        const day = String(d.getDate()).padStart(2, '0')
        const dateStr = `${year}-${month}-${day}`
        timestampToDate.set(dateStr, c.time + KST_TO_UTC)
      })

      const groupedByDate = new Map<string, IdeaMarker[]>()
      ideaMarkers.forEach(marker => {
        const existing = groupedByDate.get(marker.date) || []
        existing.push(marker)
        groupedByDate.set(marker.date, existing)
      })

      groupedByDate.forEach((markers, date) => {
        const candleTime = timestampToDate.get(date)
        if (candleTime === undefined) return

        const hasMy = markers.some(m => m.source === 'my')
        const othersMarkers = markers.filter(m => m.source === 'others')
        const othersCount = othersMarkers.length

        if (hasMy) {
          allMarkers.push({
            time: candleTime as UTCTimestamp,
            position: 'aboveBar' as const,
            color: '#f59e0b',
            shape: 'circle' as const,
            text: '💡',
          })
        }

        if (othersCount > 0) {
          let text = ''
          if (othersCount === 1) {
            text = othersMarkers[0].author || '💬'
          } else {
            const firstName = othersMarkers[0].author || '💬'
            text = `${firstName} +${othersCount - 1}`
          }

          allMarkers.push({
            time: candleTime as UTCTimestamp,
            position: 'aboveBar' as const,
            color: '#8b5cf6',
            shape: 'circle' as const,
            text,
          })
        }
      })
    }

    // 마커 정렬
    allMarkers.sort((a, b) => a.time - b.time)

    // 기존 마커 API가 있으면 setMarkers로 업데이트, 없으면 새로 생성
    if (markersApiRef.current) {
      markersApiRef.current.setMarkers(allMarkers as SeriesMarker<Time>[])
    } else {
      markersApiRef.current = createSeriesMarkers(candleSeries, allMarkers as SeriesMarker<Time>[])
    }
  }

  useEffect(() => {
    if (!containerRef.current) return

    // 차트 생성
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: height,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: '#e0e0e0',
        scaleMargins: {
          top: 0.1,
          bottom: 0.2,
        },
      },
      timeScale: {
        borderColor: '#e0e0e0',
        timeVisible: true,
        secondsVisible: false,
      },
    })

    chartRef.current = chart

    // 캔들스틱 시리즈 추가
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#ef4444',
      downColor: '#3b82f6',
      borderUpColor: '#ef4444',
      borderDownColor: '#3b82f6',
      wickUpColor: '#ef4444',
      wickDownColor: '#3b82f6',
    })
    candleSeriesRef.current = candleSeries

    // 거래량 시리즈 추가
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: '#9ca3af',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: 'volume',
    })
    volumeSeriesRef.current = volumeSeries

    // 거래량 스케일 설정
    chart.priceScale('volume').applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    })

    // 60일선 시리즈 추가
    const ma60Series = chart.addSeries(LineSeries, {
      color: '#10b981', // 초록색
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })
    ma60SeriesRef.current = ma60Series

    // 차트 데이터 업데이트 함수
    const updateChartData = (candles: OHLCVCandle[]) => {
      // 캔들 데이터 변환 (KST→UTC 보정)
      const candleData = candles.map((c: OHLCVCandle) => ({
        time: (c.time + KST_TO_UTC) as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))

      // 거래량 데이터 변환 (KST→UTC 보정)
      const volumeData = candles.map((c: OHLCVCandle) => ({
        time: (c.time + KST_TO_UTC) as UTCTimestamp,
        value: c.volume,
        color: c.close >= c.open ? 'rgba(239, 68, 68, 0.3)' : 'rgba(59, 130, 246, 0.3)',
      }))

      candleSeries.setData(candleData)
      volumeSeries.setData(volumeData)

      // 60일 이동평균선 계산
      const ma60Data: { time: UTCTimestamp; value: number }[] = []
      for (let i = 59; i < candles.length; i++) {
        const sum = candles.slice(i - 59, i + 1).reduce((acc, c) => acc + c.close, 0)
        ma60Data.push({
          time: (candles[i].time + KST_TO_UTC) as UTCTimestamp,
          value: sum / 60,
        })
      }
      if (ma60Data.length > 0) {
        ma60Series.setData(ma60Data)
      }
    }

    // 데이터 로드
    const loadData = async () => {
      setLoading(true)
      setError(null)

      try {
        let candles: OHLCVCandle[]
        let hasMore = true

        // 외부 데이터가 있으면 사용, 없으면 API 조회
        if (ohlcvData && ohlcvData.length > 0) {
          candles = ohlcvData
          hasMore = false  // 외부 데이터는 추가 로딩 없음
        } else {
          const data = await themeSetupApi.getStockOHLCV(stockCode, days)
          if (!data.candles || data.candles.length === 0) {
            setError('데이터 없음')
            return
          }
          candles = data.candles
          hasMore = data.has_more ?? true
        }

        // 상태 저장
        allCandlesRef.current = candles
        hasMoreRef.current = hasMore

        // 차트 업데이트
        updateChartData(candles)

        // 기준가/진입가 라인 (빨간색 실선)
        if (initialPriceLine) {
          candleSeries.createPriceLine({
            price: initialPriceLine,
            color: '#dc2626',
            lineWidth: 2,
            lineStyle: 0, // Solid
            axisLabelVisible: true,
            title: '', // 차트 내부 라벨 제거 (캔들 가림 방지)
          })
        }

        // 포지션 평균 매수가 라인 (초록색 점선)
        if (avgEntryPrice && avgEntryPrice !== initialPriceLine) {
          candleSeries.createPriceLine({
            price: avgEntryPrice,
            color: '#16a34a',
            lineWidth: 2,
            lineStyle: 2, // Dashed
            axisLabelVisible: true,
            title: '평단',
          })
        }

        // 매수 지점 마커 (lightweight-charts v4에서는 series.setMarkers 사용)
        if (entryMarkers && entryMarkers.length > 0) {
          try {
            // 캔들 데이터의 시간 범위 확인
            const candleTimes = candles.map(c => c.time)
            const minTime = Math.min(...candleTimes)
            const maxTime = Math.max(...candleTimes)

            const markers = entryMarkers
              .map(marker => {
                const timestamp = new Date(marker.date).getTime() / 1000
                return {
                  time: timestamp as UTCTimestamp,
                  position: 'belowBar' as const,
                  color: '#16a34a',
                  shape: 'arrowUp' as const,
                  text: `매수 ${marker.price.toLocaleString()}원`,
                }
              })
              // 캔들 시간 범위 내의 마커만 필터링
              .filter(m => m.time >= minTime && m.time <= maxTime)
              // 시간순 정렬 (lightweight-charts 요구사항)
              .sort((a, b) => a.time - b.time)

            if (markers.length > 0) {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              ;(candleSeries as any).setMarkers(markers)
            }
          } catch (markerErr) {
            console.warn('마커 설정 실패:', markerErr)
            // 마커 에러는 무시하고 차트는 표시
          }
        }

        // 외부 데이터 사용 시 고가선 표시 생략
        if (!ohlcvData) {
          // 최근 40일 고가
          const recent40 = candles.slice(-40)
          const high40 = recent40.length > 0 ? Math.max(...recent40.map(c => c.high)) : null

          // 최근 60일 고가
          const recent60 = candles.slice(-60)
          const high60 = recent60.length > 0 ? Math.max(...recent60.map(c => c.high)) : null

          // 40일 고가선 (주황색)
          if (high40) {
            candleSeries.createPriceLine({
              price: high40,
              color: '#f97316',
              lineWidth: 1,
              lineStyle: 2, // Dashed
              axisLabelVisible: false,
              title: '',
            })
          }

          // 60일 고가선 (보라색)
          if (high60 && high60 !== high40) {
            candleSeries.createPriceLine({
              price: high60,
              color: '#8b5cf6',
              lineWidth: 1,
              lineStyle: 2, // Dashed
              axisLabelVisible: false,
              title: '',
            })
          }
        }

        // 전체 데이터가 보이도록 조정
        chart.timeScale().fitContent()
      } catch (err) {
        console.error('OHLCV 로드 실패:', err)
        // 차트 데이터가 없을 때만 에러 표시
        if (allCandlesRef.current.length === 0) {
          setError('로드 실패')
        }
      } finally {
        setLoading(false)
      }
    }

    // 추가 데이터 로드 (스크롤 시)
    const loadMoreData = async () => {
      if (isLoadingMoreRef.current || !hasMoreRef.current || !enableScrollLoad || ohlcvData) {
        return
      }

      const candles = allCandlesRef.current
      if (candles.length === 0) return

      isLoadingMoreRef.current = true
      setLoadingMore(true)

      try {
        // 가장 오래된 데이터의 날짜
        const oldestTime = candles[0].time
        const oldestDate = new Date(oldestTime * 1000)
        const beforeDateStr = oldestDate.toISOString().split('T')[0]

        // 추가 데이터 로드
        const data = await themeSetupApi.getStockOHLCV(stockCode, 90, beforeDateStr)
        if (data.candles && data.candles.length > 0) {
          // 기존 데이터와 병합 (중복 제거)
          const existingTimes = new Set(candles.map(c => c.time))
          const newCandles = data.candles.filter((c: OHLCVCandle) => !existingTimes.has(c.time))

          if (newCandles.length > 0) {
            // 새 데이터를 앞에 추가
            const mergedCandles = [...newCandles, ...candles]
            allCandlesRef.current = mergedCandles

            // 차트 업데이트
            updateChartData(mergedCandles)
          }

          hasMoreRef.current = data.has_more ?? (newCandles.length >= 90)
        } else {
          hasMoreRef.current = false
        }
      } catch (err) {
        console.error('추가 데이터 로드 실패:', err)
      } finally {
        isLoadingMoreRef.current = false
        setLoadingMore(false)
      }
    }

    // 스크롤(visible range) 변경 감지
    const handleVisibleRangeChange = (range: LogicalRange | null) => {
      if (!range || !enableScrollLoad || ohlcvData) return

      // 왼쪽 끝에 도달했는지 확인 (from이 5 이하면 로딩)
      if (range.from <= 5 && hasMoreRef.current && !isLoadingMoreRef.current) {
        loadMoreData()
      }
    }

    chart.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleRangeChange)

    // 오늘 실시간 봉 업데이트 함수
    const updateLiveCandle = async () => {
      if (isDisposed || !candleSeriesRef.current || !volumeSeriesRef.current) return
      try {
        const price = await dataApi.getPrice(stockCode, false) // 캐시 안 씀
        if (isDisposed || !price) return

        // KST 기준 오늘 날짜 → UTC 자정 timestamp (차트 표시용)
        const now = new Date()
        const kstOffset = 9 * 60 * 60 * 1000
        const kstNow = new Date(now.getTime() + kstOffset)
        const todayTimestamp = Math.floor(
          Date.UTC(kstNow.getUTCFullYear(), kstNow.getUTCMonth(), kstNow.getUTCDate()) / 1000
        ) as UTCTimestamp

        const open = Number(price.open_price)
        const high = Number(price.high_price)
        const low = Number(price.low_price)
        const close = Number(price.current_price)
        const vol = Number(price.volume)

        if (close <= 0) return // 유효하지 않은 데이터 무시

        candleSeriesRef.current.update({
          time: todayTimestamp,
          open, high, low, close,
        })
        volumeSeriesRef.current.update({
          time: todayTimestamp,
          value: vol,
          color: close >= open ? 'rgba(239, 68, 68, 0.3)' : 'rgba(59, 130, 246, 0.3)',
        })
      } catch {
        // 조용히 실패
      }
    }

    loadData().then(() => {
      // OHLCV 로드 완료 후 오늘 캔들 1회 조회
      if (!isDisposed && !ohlcvData) {
        updateLiveCandle()
      }
      // 차트 준비 완료
      if (!isDisposed) {
        setChartReady(true)
      }
    })

    // 장중 60초 폴링
    let liveCandleTimer: ReturnType<typeof setInterval> | null = null
    if (!ohlcvData) {
      liveCandleTimer = setInterval(() => {
        if (isMarketOpen()) {
          updateLiveCandle()
        }
      }, 60_000)
    }

    // 리사이즈 핸들러
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: containerRef.current.clientWidth,
        })
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange)
      if (chartRef.current) {
        chartRef.current.remove()
        chartRef.current = null
      }
    }
  }, [stockCode, days, height, ohlcvData, initialPriceLine, priceLineLabel, avgEntryPrice, entryMarkers, enableScrollLoad])

  return (
    <div className="stock-chart-wrapper">
      {/* 헤더 - TradingView 링크 포함 */}
      {showHeader && (
        <div className="flex items-center justify-between mb-2">
          <a
            href={tradingViewUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 hover:text-blue-600 transition-colors group"
          >
            <span className="font-medium text-sm group-hover:underline">{stockName}</span>
            <span className="text-xs text-gray-400">{stockCode}</span>
            <svg
              className="w-3 h-3 text-gray-400 group-hover:text-blue-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
          </a>
          <div className="flex items-center gap-2">
            {patternType && (
              <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">
                {patternType}
              </span>
            )}
          </div>
        </div>
      )}


      {/* 차트 컨테이너 */}
      <div
        ref={containerRef}
        className="relative rounded overflow-hidden border border-gray-200 cursor-pointer"
        style={{ height: `${height}px` }}
        onClick={() => window.open(tradingViewUrl, '_blank')}
        title="TradingView에서 보기"
      >
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-80 z-10">
            <div className="animate-pulse text-gray-400 text-sm">로딩 중...</div>
          </div>
        )}
        {loadingMore && (
          <div className="absolute top-2 left-2 z-10">
            <div className="flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">
              <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              과거 데이터 로딩...
            </div>
          </div>
        )}
        {error && !loading && allCandlesRef.current.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-80 z-10">
            <div className="text-red-400 text-sm">{error}</div>
          </div>
        )}
        {/* 드로잉 오버레이 */}
        {enableDrawing && chartReady && chartRef.current && candleSeriesRef.current && (
          <ChartDrawings
            stockCode={stockCode}
            chart={chartRef.current}
            series={candleSeriesRef.current}
            containerRef={containerRef as React.RefObject<HTMLDivElement>}
            height={height}
            enabled={enableDrawing}
          />
        )}
      </div>
    </div>
  )
}

export const StockChart = memo(StockChartComponent)
