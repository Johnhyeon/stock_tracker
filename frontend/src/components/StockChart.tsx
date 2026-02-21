import { useEffect, useRef, useState, memo, useCallback } from 'react'
import { createChart, createSeriesMarkers, IChartApi, ISeriesApi, CandlestickSeries, HistogramSeries, LineSeries, UTCTimestamp, LogicalRange } from 'lightweight-charts'
import { themeSetupApi, dataApi } from '../services/api'
import ChartDrawings from './ChartDrawings'
import { useDarkMode } from '../hooks/useDarkMode'

const CHART_COLORS = {
  light: {
    background: '#ffffff',
    text: '#333333',
    grid: '#f0f0f0',
    border: '#e0e0e0',
    volume: '#9ca3af',
  },
  dark: {
    background: '#0a0a0f',
    text: '#94a3b8',
    grid: '#1a1a28',
    border: '#1e1e2e',
    volume: '#2a2a3d',
  },
} as const

// 거래일 체크 (주말 제외)
function isTradingDay(): boolean {
  const now = new Date()
  const kstOffset = 9 * 60 * 60 * 1000
  const kst = new Date(now.getTime() + kstOffset)
  const day = kst.getUTCDay()
  return day !== 0 && day !== 6
}

// 장 시간 체크
function isMarketOpen(): boolean {
  if (!isTradingDay()) return false
  const now = new Date()
  const kstOffset = 9 * 60 * 60 * 1000
  const kst = new Date(now.getTime() + kstOffset)
  const hours = kst.getUTCHours()
  const minutes = kst.getUTCMinutes()
  const timeInMinutes = hours * 60 + minutes
  return timeInMinutes >= 540 && timeInMinutes <= 930 // 09:00 ~ 15:30
}

export interface OHLCVCandle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

// 일봉 → 주봉 집계
function aggregateWeekly(candles: OHLCVCandle[]): OHLCVCandle[] {
  if (candles.length === 0) return []
  const weeks: OHLCVCandle[] = []
  let wOpen = 0, wHigh = 0, wLow = 0, wClose = 0, wVol = 0, wTime = 0
  let prevWeekKey = -1

  for (const c of candles) {
    const d = new Date(c.time * 1000)
    // ISO week key: year * 100 + weekNumber
    const dayOfYear = Math.floor((d.getTime() - new Date(d.getFullYear(), 0, 1).getTime()) / 86400000)
    const weekKey = d.getFullYear() * 100 + Math.floor((dayOfYear + new Date(d.getFullYear(), 0, 1).getDay()) / 7)

    if (prevWeekKey !== -1 && weekKey !== prevWeekKey) {
      weeks.push({ time: wTime, open: wOpen, high: wHigh, low: wLow, close: wClose, volume: wVol })
      wOpen = 0
    }

    if (wOpen === 0) {
      wOpen = c.open; wHigh = c.high; wLow = c.low; wVol = 0
      wTime = c.time
    }
    wHigh = Math.max(wHigh, c.high)
    wLow = Math.min(wLow, c.low)
    wClose = c.close
    wVol += c.volume
    prevWeekKey = weekKey
  }
  if (wOpen > 0) {
    weeks.push({ time: wTime, open: wOpen, high: wHigh, low: wLow, close: wClose, volume: wVol })
  }
  return weeks
}

// 일봉 → 월봉 집계
function aggregateMonthly(candles: OHLCVCandle[]): OHLCVCandle[] {
  if (candles.length === 0) return []
  const months: OHLCVCandle[] = []
  let mOpen = 0, mHigh = 0, mLow = 0, mClose = 0, mVol = 0, mTime = 0
  let prevMonthKey = -1

  for (const c of candles) {
    const d = new Date(c.time * 1000)
    const monthKey = d.getFullYear() * 100 + d.getMonth()

    if (prevMonthKey !== -1 && monthKey !== prevMonthKey) {
      months.push({ time: mTime, open: mOpen, high: mHigh, low: mLow, close: mClose, volume: mVol })
      mOpen = 0
    }

    if (mOpen === 0) {
      mOpen = c.open; mHigh = c.high; mLow = c.low; mVol = 0
      mTime = c.time
    }
    mHigh = Math.max(mHigh, c.high)
    mLow = Math.min(mLow, c.low)
    mClose = c.close
    mVol += c.volume
    prevMonthKey = monthKey
  }
  if (mOpen > 0) {
    months.push({ time: mTime, open: mOpen, high: mHigh, low: mLow, close: mClose, volume: mVol })
  }
  return months
}

function aggregateByTimeframe(candles: OHLCVCandle[], tf: ChartTimeframe): OHLCVCandle[] {
  if (tf === 'weekly') return aggregateWeekly(candles)
  if (tf === 'monthly') return aggregateMonthly(candles)
  return candles
}

// 아이디어 마커 타입 (종목 상세에서 사용)
export interface IdeaMarker {
  date: string  // YYYY-MM-DD
  source: 'my' | 'others'
  author?: string
}

// 매수 마커 타입
interface EntryMarker {
  date: string  // YYYY-MM-DD
  price: number
  quantity?: number
}

// 매매 마커 타입
export interface TradeMarker {
  date: string       // YYYY-MM-DD
  price: number
  quantity: number
  trade_type: 'BUY' | 'ADD_BUY' | 'SELL' | 'PARTIAL_SELL'
}

// 실적발표 마커 타입
export interface EarningsMarker {
  date: string       // YYYY-MM-DD
  label: string      // 예: "Q1", "반기", "Q3", "연간"
}

export type ChartTimeframe = 'daily' | 'weekly' | 'monthly'

export interface StockChartProps {
  stockCode: string
  stockName: string
  patternType?: string
  height?: number
  days?: number
  ohlcvData?: OHLCVCandle[]  // 외부에서 데이터 전달 시 사용
  initialPriceLine?: number  // 진입가/기준가 라인
  priceLineLabel?: string    // 라인 라벨 (기본: '기준가')
  priceLineColor?: string    // 라인 색상 (기본: '#dc2626')
  avgEntryPrice?: number     // 포지션 평균 매수가 라인
  entryMarkers?: EntryMarker[]  // 매수 지점 마커
  showHeader?: boolean  // 헤더 표시 여부
  enableScrollLoad?: boolean  // 스크롤 시 추가 로딩 활성화
  ideaMarkers?: IdeaMarker[]  // 아이디어 마커
  showIdeaMarkers?: boolean   // 아이디어 마커 표시 여부
  tradeMarkers?: TradeMarker[]  // 매매 마커 (매수/매도)
  showTradeMarkers?: boolean    // 매매 마커 표시 여부
  earningsMarkers?: EarningsMarker[]  // 실적발표 마커
  showEarningsMarkers?: boolean       // 실적발표 마커 표시 여부
  enableDrawing?: boolean     // 드로잉 활성화
  disableTradingViewLink?: boolean  // TradingView 클릭 비활성화
  visibleDays?: number  // 초기 표시 범위 (설정 시 fitContent 대신 최근 N일만 표시, 나머지는 스크롤)
  watchlistStartDate?: string  // 관심종목 시작일 (YYYY-MM-DD)
  showTimeframeSelector?: boolean   // 일/주/월 타임프레임 셀렉터 표시
  initialTimeframe?: ChartTimeframe // 초기 타임프레임 (기본: 'daily')
  showMAToggle?: boolean            // 이평선 on/off 토글 표시
  initialMaVisible?: { ma1: boolean; ma2: boolean; ma3: boolean; ma4: boolean; ma5: boolean }
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
  priceLineColor = '#dc2626',
  avgEntryPrice,
  entryMarkers,
  showHeader = true,
  enableScrollLoad = true,
  ideaMarkers,
  showIdeaMarkers = false,
  tradeMarkers,
  showTradeMarkers = false,
  earningsMarkers,
  showEarningsMarkers = false,
  enableDrawing = false,
  disableTradingViewLink = true,
  visibleDays,
  watchlistStartDate,
  showTimeframeSelector = false,
  initialTimeframe = 'daily',
  showMAToggle = false,
  initialMaVisible,
}: StockChartProps) {
  const { isDark } = useDarkMode()
  const colors = isDark ? CHART_COLORS.dark : CHART_COLORS.light
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const ma5SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma20SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma60SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma120SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma240SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [chartReady, setChartReady] = useState(false)
  const [timeframe, setTimeframe] = useState<ChartTimeframe>(initialTimeframe)
  const [maVisible, setMaVisible] = useState(initialMaVisible ?? { ma1: true, ma2: true, ma3: true, ma4: true, ma5: true })

  // 외부에서 initialTimeframe 변경 시 동기화
  useEffect(() => {
    setTimeframe(initialTimeframe)
  }, [initialTimeframe])

  // 스크롤 로딩용 상태
  const allCandlesRef = useRef<OHLCVCandle[]>([])
  const hasMoreRef = useRef(true)
  const isLoadingMoreRef = useRef(false)
  // 사용자 지정 price line 참조 (제거/재생성용)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const userPriceLinesRef = useRef<any[]>([])
  // 마커 플러그인 참조 (lightweight-charts v5)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markersPluginRef = useRef<any>(null)
  // TradingView 링크 (한국어)
  const tradingViewUrl = `https://kr.tradingview.com/chart/?symbol=KRX:${stockCode}`

  // 변경 빈도 낮은 props를 ref로 관리 (useEffect 의존성 최소화)
  const propsRef = useRef({ ohlcvData, initialPriceLine, priceLineLabel, priceLineColor, avgEntryPrice, entryMarkers, ideaMarkers, showIdeaMarkers, earningsMarkers, showEarningsMarkers, visibleDays, enableScrollLoad, watchlistStartDate, timeframe })
  propsRef.current = { ohlcvData, initialPriceLine, priceLineLabel, priceLineColor, avgEntryPrice, entryMarkers, ideaMarkers, showIdeaMarkers, earningsMarkers, showEarningsMarkers, visibleDays, enableScrollLoad, watchlistStartDate, timeframe }

  // 차트 데이터 업데이트 함수 (Effect 간 공유)
  const updateChartDataRef = useRef<((candles: OHLCVCandle[]) => void) | null>(null)

  // ===== Effect 1: 차트 생성 + 데이터 로드 (stockCode/days 변경 시만 재생성) =====
  useEffect(() => {
    let isDisposed = false
    if (!containerRef.current) return

    setChartReady(false)
    setLoading(true)
    setError(null)
    allCandlesRef.current = []
    hasMoreRef.current = true
    userPriceLinesRef.current = []

    // 차트 생성
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { color: colors.background },
        textColor: colors.text,
      },
      grid: {
        vertLines: { color: colors.grid },
        horzLines: { color: colors.grid },
      },
      crosshair: { mode: 1 },
      rightPriceScale: {
        borderColor: colors.border,
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: colors.border,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 7,
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
      priceFormat: { type: 'price', precision: 0, minMove: 1 },
    })
    candleSeriesRef.current = candleSeries

    // 마커 플러그인 생성 (v5 API)
    markersPluginRef.current = createSeriesMarkers(candleSeries, [])

    // 거래량 시리즈 추가
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: colors.volume,
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })
    volumeSeriesRef.current = volumeSeries

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })

    // 이동평균선 시리즈 추가 (5, 20, 60, 120, 240)
    const maOpts = { lineWidth: 1 as const, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }
    const ma5Series = chart.addSeries(LineSeries, { ...maOpts, color: '#a855f7' })   // 보라
    const ma20Series = chart.addSeries(LineSeries, { ...maOpts, color: '#ef4444' })  // 빨강
    const ma60Series = chart.addSeries(LineSeries, { ...maOpts, color: '#10b981' })  // 초록
    const ma120Series = chart.addSeries(LineSeries, { ...maOpts, color: '#3b82f6' }) // 파랑
    const ma240Series = chart.addSeries(LineSeries, { ...maOpts, color: '#f59e0b' }) // 주황
    ma5SeriesRef.current = ma5Series
    ma20SeriesRef.current = ma20Series
    ma60SeriesRef.current = ma60Series
    ma120SeriesRef.current = ma120Series
    ma240SeriesRef.current = ma240Series

    // 차트 데이터 업데이트 함수
    const updateChartData = (candles: OHLCVCandle[]) => {
      // 0값 캔들 필터링 (장 시작 전 또는 비거래일 데이터)
      const validCandles = candles.filter(c => c.close > 0 && c.open > 0)
      const candleData = validCandles.map((c: OHLCVCandle) => ({
        time: (c.time) as UTCTimestamp,
        open: c.open, high: c.high, low: c.low, close: c.close,
      }))
      const volumeData = validCandles.map((c: OHLCVCandle) => ({
        time: (c.time) as UTCTimestamp,
        value: c.volume,
        color: c.close >= c.open ? 'rgba(239, 68, 68, 0.3)' : 'rgba(59, 130, 246, 0.3)',
      }))

      candleSeries.setData(candleData)
      volumeSeries.setData(volumeData)

      // 이동평균선 계산 (슬라이딩 윈도우 O(n))
      // 타임프레임별 MA 기간: 일봉 5/20/60/120/240, 주봉 5/10/20/40/120, 월봉 3/6/12/24/60
      const tf = propsRef.current.timeframe
      const maPeriods = tf === 'monthly' ? [3, 6, 12, 24, 60]
                      : tf === 'weekly'  ? [5, 10, 20, 40, 120]
                      : [5, 20, 60, 120, 240]

      const calcMA = (period: number) => {
        const data: { time: UTCTimestamp; value: number }[] = []
        if (validCandles.length < period) return data
        let sum = 0
        for (let i = 0; i < period; i++) sum += validCandles[i].close
        data.push({ time: (validCandles[period - 1].time) as UTCTimestamp, value: sum / period })
        for (let i = period; i < validCandles.length; i++) {
          sum += validCandles[i].close - validCandles[i - period].close
          data.push({ time: (validCandles[i].time) as UTCTimestamp, value: sum / period })
        }
        return data
      }
      const ma1Data = calcMA(maPeriods[0]); const ma2Data = calcMA(maPeriods[1])
      const ma3Data = calcMA(maPeriods[2]); const ma4Data = calcMA(maPeriods[3])
      const ma5Data = calcMA(maPeriods[4])
      ma5Series.setData(ma1Data.length > 0 ? ma1Data : [])
      ma20Series.setData(ma2Data.length > 0 ? ma2Data : [])
      ma60Series.setData(ma3Data.length > 0 ? ma3Data : [])
      ma120Series.setData(ma4Data.length > 0 ? ma4Data : [])
      ma240Series.setData(ma5Data.length > 0 ? ma5Data : [])
    }
    updateChartDataRef.current = updateChartData

    // 데이터 로드
    const loadData = async () => {
      try {
        const props = propsRef.current
        let candles: OHLCVCandle[]
        let hasMore = true

        if (props.ohlcvData && props.ohlcvData.length > 0) {
          candles = props.ohlcvData
          hasMore = false
        } else {
          const data = await themeSetupApi.getStockOHLCV(stockCode, days)
          if (!data.candles || data.candles.length === 0) {
            setError('데이터 없음')
            return
          }
          candles = data.candles
          hasMore = data.has_more ?? true
        }

        allCandlesRef.current = candles
        hasMoreRef.current = hasMore
        const displayCandles = aggregateByTimeframe(candles, propsRef.current.timeframe)
        updateChartData(displayCandles)

        // 40/60일 고가선 (데이터 기반, 자동 표시)
        if (!props.ohlcvData) {
          const recent40 = candles.slice(-40)
          const high40 = recent40.length > 0 ? Math.max(...recent40.map(c => c.high)) : null
          const recent60 = candles.slice(-60)
          const high60 = recent60.length > 0 ? Math.max(...recent60.map(c => c.high)) : null

          if (high40) {
            candleSeries.createPriceLine({ price: high40, color: '#f97316', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '' })
          }
          if (high60 && high60 !== high40) {
            candleSeries.createPriceLine({ price: high60, color: '#8b5cf6', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '' })
          }
        }

        // 초기 표시 범위
        if (props.visibleDays && candles.length > props.visibleDays) {
          const from = candles.length - props.visibleDays
          chart.timeScale().setVisibleLogicalRange({ from, to: candles.length - 1 })
        } else {
          chart.timeScale().fitContent()
        }
      } catch (err) {
        console.error('OHLCV 로드 실패:', err)
        if (allCandlesRef.current.length === 0) setError('로드 실패')
      } finally {
        setLoading(false)
      }
    }

    // 추가 데이터 로드 (스크롤 시)
    const loadMoreData = async () => {
      if (isLoadingMoreRef.current || !hasMoreRef.current || !propsRef.current.enableScrollLoad || propsRef.current.ohlcvData) return
      const candles = allCandlesRef.current
      if (candles.length === 0) return

      isLoadingMoreRef.current = true
      setLoadingMore(true)

      try {
        const oldestTime = candles[0].time
        const oldestDate = new Date(oldestTime * 1000)
        const beforeDateStr = oldestDate.toISOString().split('T')[0]

        const data = await themeSetupApi.getStockOHLCV(stockCode, 90, beforeDateStr)
        if (data.candles && data.candles.length > 0) {
          const existingTimes = new Set(candles.map(c => c.time))
          const newCandles = data.candles.filter((c: OHLCVCandle) => !existingTimes.has(c.time))
          if (newCandles.length > 0) {
            const mergedCandles = [...newCandles, ...candles]
            allCandlesRef.current = mergedCandles
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
      if (!range || !propsRef.current.enableScrollLoad || propsRef.current.ohlcvData || propsRef.current.timeframe !== 'daily') return
      if (range.from <= 5 && hasMoreRef.current && !isLoadingMoreRef.current) loadMoreData()
    }
    chart.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleRangeChange)

    // 오늘 실시간 봉 업데이트 함수
    const updateLiveCandle = async () => {
      if (isDisposed || !candleSeriesRef.current || !volumeSeriesRef.current) return
      try {
        const price = await dataApi.getPrice(stockCode, false)
        if (isDisposed || !price) return

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
        if (close <= 0) return

        candleSeriesRef.current.update({ time: todayTimestamp, open, high, low, close })
        volumeSeriesRef.current.update({
          time: todayTimestamp, value: vol,
          color: close >= open ? 'rgba(239, 68, 68, 0.3)' : 'rgba(59, 130, 246, 0.3)',
        })
      } catch {
        // 조용히 실패
      }
    }

    loadData().then(() => {
      if (!isDisposed && !propsRef.current.ohlcvData && isMarketOpen() && propsRef.current.timeframe === 'daily') updateLiveCandle()
      if (!isDisposed) setChartReady(true)
    })

    // 장중 60초 폴링 (일봉에서만)
    const liveCandleTimer = !propsRef.current.ohlcvData ? setInterval(() => {
      if (isMarketOpen() && propsRef.current.timeframe === 'daily') updateLiveCandle()
    }, 60_000) : null

    // 리사이즈 핸들러 (debounce로 스크롤바 레이아웃 루프 방지)
    let resizeTimer: ReturnType<typeof setTimeout> | null = null
    let lastWidth = containerRef.current.clientWidth
    const handleResize = () => {
      if (resizeTimer) clearTimeout(resizeTimer)
      resizeTimer = setTimeout(() => {
        if (containerRef.current && chartRef.current) {
          const newWidth = containerRef.current.clientWidth
          if (newWidth !== lastWidth) {
            lastWidth = newWidth
            chartRef.current.applyOptions({ width: newWidth })
          }
        }
      }, 150)
    }
    window.addEventListener('resize', handleResize)

    return () => {
      isDisposed = true
      window.removeEventListener('resize', handleResize)
      if (resizeTimer) clearTimeout(resizeTimer)
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange)
      if (liveCandleTimer) clearInterval(liveCandleTimer)
      updateChartDataRef.current = null
      if (chartRef.current) {
        chartRef.current.remove()
        chartRef.current = null
      }
      candleSeriesRef.current = null
      markersPluginRef.current = null
      volumeSeriesRef.current = null
      ma5SeriesRef.current = null
      ma20SeriesRef.current = null
      ma60SeriesRef.current = null
      ma120SeriesRef.current = null
      ma240SeriesRef.current = null
      setChartReady(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stockCode, days])

  // ===== Effect 2: height 변경 시 차트 리사이즈 (재생성 없이) =====
  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.applyOptions({ height })
    }
  }, [height])

  // ===== Effect 3: Price Lines 업데이트 (재생성 없이) =====
  useEffect(() => {
    if (!chartReady || !candleSeriesRef.current) return

    // 기존 사용자 price lines 제거
    for (const line of userPriceLinesRef.current) {
      try { candleSeriesRef.current.removePriceLine(line) } catch { /* ignore */ }
    }
    userPriceLinesRef.current = []

    // 기준가/진입가 라인
    if (initialPriceLine) {
      const line = candleSeriesRef.current.createPriceLine({
        price: initialPriceLine, color: priceLineColor, lineWidth: 2,
        lineStyle: 0, axisLabelVisible: true, title: priceLineLabel !== '기준가' ? priceLineLabel : '',
      })
      userPriceLinesRef.current.push(line)
    }

    // 포지션 평균 매수가 라인 (초록색 점선)
    if (avgEntryPrice && avgEntryPrice !== initialPriceLine) {
      const line = candleSeriesRef.current.createPriceLine({
        price: avgEntryPrice, color: '#16a34a', lineWidth: 2,
        lineStyle: 2, axisLabelVisible: true, title: '평단',
      })
      userPriceLinesRef.current.push(line)
    }
  }, [chartReady, initialPriceLine, avgEntryPrice, priceLineLabel, priceLineColor])

  // ===== Effect 4: Markers 업데이트 (재생성 없이) =====
  const updateMarkers = useCallback(() => {
    if (!candleSeriesRef.current) return
    const candles = allCandlesRef.current
    if (candles.length === 0) return

    try {
      const candleTimes = candles.map(c => c.time)
      const minTime = Math.min(...candleTimes)
      const maxTime = Math.max(...candleTimes)

      const allMarkers: Array<{
        time: UTCTimestamp; position: 'belowBar' | 'aboveBar'
        color: string; shape: 'arrowUp' | 'arrowDown' | 'circle'; text: string
      }> = []

      if (entryMarkers && entryMarkers.length > 0) {
        for (const marker of entryMarkers) {
          const timestamp = new Date(marker.date).getTime() / 1000
          allMarkers.push({
            time: timestamp as UTCTimestamp, position: 'belowBar', color: '#16a34a',
            shape: 'arrowUp', text: `매수 ${marker.price.toLocaleString()}원`,
          })
        }
      }

      if (showIdeaMarkers && ideaMarkers && ideaMarkers.length > 0) {
        for (const marker of ideaMarkers) {
          const timestamp = new Date(marker.date).getTime() / 1000
          const isMy = marker.source === 'my'
          allMarkers.push({
            time: timestamp as UTCTimestamp, position: 'aboveBar',
            color: isMy ? '#8b5cf6' : '#f59e0b', shape: 'circle',
            text: marker.author || (isMy ? '내 아이디어' : '아이디어'),
          })
        }
      }

      if (showTradeMarkers && tradeMarkers && tradeMarkers.length > 0) {
        for (const tm of tradeMarkers) {
          const timestamp = new Date(tm.date).getTime() / 1000
          const isBuy = tm.trade_type === 'BUY' || tm.trade_type === 'ADD_BUY'
          const tag = { BUY: 'B', ADD_BUY: '+B', SELL: 'S', PARTIAL_SELL: '-S' }[tm.trade_type] || tm.trade_type
          const shortPrice = tm.price >= 10000 ? `${Math.round(tm.price / 1000)}k` : tm.price.toLocaleString()
          allMarkers.push({
            time: timestamp as UTCTimestamp,
            position: isBuy ? 'belowBar' : 'aboveBar',
            color: isBuy ? '#16a34a' : '#dc2626',
            shape: isBuy ? 'arrowUp' : 'arrowDown',
            text: `${tag} ${shortPrice}`,
          })
        }
      }

      if (showEarningsMarkers && earningsMarkers && earningsMarkers.length > 0) {
        for (const em of earningsMarkers) {
          const timestamp = new Date(em.date).getTime() / 1000
          allMarkers.push({
            time: timestamp as UTCTimestamp, position: 'aboveBar',
            color: '#ec4899', shape: 'circle',
            text: `실발 ${em.label}`,
          })
        }
      }

      if (watchlistStartDate) {
        const timestamp = new Date(watchlistStartDate).getTime() / 1000
        allMarkers.push({
          time: timestamp as UTCTimestamp, position: 'aboveBar',
          color: '#eab308', shape: 'circle',
          text: '관심 시작',
        })
      }

      const filtered = allMarkers
        .filter(m => m.time >= minTime && m.time <= maxTime)
        .sort((a, b) => a.time - b.time)

      if (markersPluginRef.current) {
        markersPluginRef.current.setMarkers(filtered.length > 0 ? filtered : [])
      }
    } catch (markerErr) {
      console.warn('마커 설정 실패:', markerErr)
    }
  }, [entryMarkers, ideaMarkers, showIdeaMarkers, tradeMarkers, showTradeMarkers, earningsMarkers, showEarningsMarkers, watchlistStartDate])

  useEffect(() => {
    if (!chartReady) return
    updateMarkers()
  }, [chartReady, updateMarkers])

  // ===== Effect 5: 다크모드 전환 시 차트 색상 업데이트 =====
  useEffect(() => {
    if (!chartRef.current) return
    chartRef.current.applyOptions({
      layout: {
        background: { color: colors.background },
        textColor: colors.text,
      },
      grid: {
        vertLines: { color: colors.grid },
        horzLines: { color: colors.grid },
      },
      rightPriceScale: { borderColor: colors.border },
      timeScale: { borderColor: colors.border },
    })
  }, [isDark, colors])

  // ===== Effect 6: 이평선 가시성 토글 =====
  useEffect(() => {
    if (!chartReady) return
    ma5SeriesRef.current?.applyOptions({ visible: maVisible.ma1 })
    ma20SeriesRef.current?.applyOptions({ visible: maVisible.ma2 })
    ma60SeriesRef.current?.applyOptions({ visible: maVisible.ma3 })
    ma120SeriesRef.current?.applyOptions({ visible: maVisible.ma4 })
    ma240SeriesRef.current?.applyOptions({ visible: maVisible.ma5 })
  }, [chartReady, maVisible])

  // ===== Effect 7: 타임프레임 전환 시 데이터 재렌더링 =====
  useEffect(() => {
    if (!chartReady || !updateChartDataRef.current) return
    const raw = allCandlesRef.current
    if (raw.length === 0) return
    const aggregated = aggregateByTimeframe(raw, timeframe)
    updateChartDataRef.current(aggregated)
    chartRef.current?.timeScale().fitContent()
  }, [timeframe, chartReady])

  const handleTimeframeChange = useCallback((tf: ChartTimeframe) => {
    setTimeframe(tf)
  }, [])

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


      {/* 타임프레임 셀렉터 + 이평선 토글 */}
      {(showTimeframeSelector || showMAToggle) && (
        <div className="flex items-center gap-3 mb-1">
          {showTimeframeSelector && (
            <div className="flex items-center gap-1">
              {([['daily', '일'], ['weekly', '주'], ['monthly', '월']] as const).map(([tf, label]) => (
                <button
                  key={tf}
                  onClick={(e) => { e.stopPropagation(); handleTimeframeChange(tf) }}
                  className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
                    timeframe === tf
                      ? 'bg-indigo-500 text-white'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
          {showMAToggle && (() => {
            const maLabels = timeframe === 'monthly' ? [3, 6, 12, 24, 60]
                           : timeframe === 'weekly'  ? [5, 10, 20, 40, 120]
                           : [5, 20, 60, 120, 240]
            const maColors = ['#a855f7', '#ef4444', '#10b981', '#3b82f6', '#f59e0b']
            const maKeys = ['ma1', 'ma2', 'ma3', 'ma4', 'ma5'] as const
            const allOn = maKeys.every(k => maVisible[k])
            const allOff = maKeys.every(k => !maVisible[k])
            return (
              <div className="flex items-center gap-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    const nextVal = !allOn
                    setMaVisible({ ma1: nextVal, ma2: nextVal, ma3: nextVal, ma4: nextVal, ma5: nextVal })
                  }}
                  className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-all mr-0.5 ${
                    allOff
                      ? 'bg-gray-200 dark:bg-gray-700 text-gray-400 dark:text-gray-500'
                      : 'bg-gray-700 dark:bg-gray-300 text-white dark:text-gray-800'
                  }`}
                >
                  MA
                </button>
                {maKeys.map((key, i) => (
                  <button
                    key={key}
                    onClick={(e) => { e.stopPropagation(); setMaVisible(prev => ({ ...prev, [key]: !prev[key] })) }}
                    className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-all ${
                      maVisible[key]
                        ? 'text-white'
                        : 'text-gray-400 dark:text-gray-500 opacity-40'
                    }`}
                    style={{ backgroundColor: maVisible[key] ? maColors[i] : 'transparent', border: `1px solid ${maColors[i]}` }}
                  >
                    {maLabels[i]}
                  </button>
                ))}
              </div>
            )
          })()}
        </div>
      )}

      {/* 차트 컨테이너 */}
      <div
        ref={containerRef}
        className={`relative rounded-lg overflow-hidden border border-gray-200 dark:border-t-border${disableTradingViewLink ? '' : ' cursor-pointer'}`}
        style={{ height: `${height}px` }}
        onClick={disableTradingViewLink ? undefined : () => window.open(tradingViewUrl, '_blank')}
        title={disableTradingViewLink ? undefined : 'TradingView에서 보기'}
      >
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/80 dark:bg-t-bg/80 z-10">
            <div className="animate-pulse text-gray-400 dark:text-t-text-muted text-sm">로딩 중...</div>
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
          <div className="absolute inset-0 flex items-center justify-center bg-white/80 dark:bg-t-bg/80 z-10">
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
