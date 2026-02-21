import { useState, useRef, useCallback, useEffect } from 'react'
import {
  backtestApi,
  themeSetupApi,
  type BacktestParams,
  type BacktestResponse,
  type BacktestTrade,
} from '../../services/api'
import { createChart, createSeriesMarkers, type IChartApi, LineSeries, CandlestickSeries, type UTCTimestamp } from 'lightweight-charts'

const ALL_SIGNALS = [
  'top',
  'pullback', 'high_breakout', 'support_test',
  'mss_proximity', 'ma120_turn',
  'candle_squeeze', 'candle_expansion',
  'momentum_zone', 'resistance_test',
]

const SIGNAL_LABELS: Record<string, string> = {
  top: 'TOP',
  pullback: '눌림목',
  high_breakout: '전고점 돌파',
  support_test: '쌍바닥 돌파',
  mss_proximity: '넥라인 근접',
  ma120_turn: '120일선 전환',
  candle_squeeze: '캔들 수축',
  candle_expansion: '캔들 확장',
  momentum_zone: '관성구간',
  resistance_test: '저항 돌파',
}

const EXIT_LABELS: Record<string, string> = {
  stop_loss: '손절',
  take_profit: '익절',
  trailing_stop: '트레일링',
  ma_deviation: 'MA이격',
  max_holding: '보유기한',
  end_of_test: '종료청산',
}

function formatKRW(n: number) {
  if (Math.abs(n) >= 1_0000_0000) return `${(n / 1_0000_0000).toFixed(1)}억`
  if (Math.abs(n) >= 1_0000) return `${(n / 1_0000).toFixed(0)}만`
  return n.toLocaleString()
}

export default function BacktestPage() {
  const [params, setParams] = useState<BacktestParams>({
    start_date: '2025-06-01',
    end_date: '2025-12-31',
    initial_capital: 10_000_000,
    max_positions: 5,
    min_signal_score: 60,
    stop_loss_pct: 7,
    take_profit_pct: 15,
    max_holding_days: 20,
    trailing_stop_pct: 5,
    ma_deviation_exit_pct: 0,
    adaptive_trailing: false,
    adaptive_dev_mid: 25,
    adaptive_dev_high: 40,
    adaptive_trail_low: 8,
    adaptive_trail_mid: 5,
    adaptive_trail_high: 3,
    adaptive_peak_drop: 10,
    adaptive_profit_trigger: 30,
    signal_types: ALL_SIGNALS.filter(s => s !== 'top'),
    step_days: 2,
    cooldown_days: 5,
  })
  const [result, setResult] = useState<BacktestResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [paramsOpen, setParamsOpen] = useState(true)
  const [tradePage, setTradePage] = useState(0)
  const [tradeSort, setTradeSort] = useState<{ key: keyof BacktestTrade; asc: boolean }>({ key: 'entry_date', asc: false })
  const [returnFilter, setReturnFilter] = useState<'all' | 'win' | 'lose'>('all')
  const [selectedTrade, setSelectedTrade] = useState<BacktestTrade | null>(null)
  const [tradeChartLoading, setTradeChartLoading] = useState(false)

  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstanceRef = useRef<IChartApi | null>(null)
  const tradeChartRef = useRef<HTMLDivElement>(null)
  const tradeChartInstanceRef = useRef<IChartApi | null>(null)

  const handleRun = async () => {
    // 프론트 사전 검증
    if (!params.start_date || !params.end_date) {
      setError('시작일과 종료일을 입력하세요.')
      return
    }
    if (params.start_date >= params.end_date) {
      setError('시작일은 종료일보다 이전이어야 합니다.')
      return
    }
    const days = (new Date(params.end_date).getTime() - new Date(params.start_date).getTime()) / 86400000
    if (days > 730) {
      setError('최대 기간은 2년(730일)입니다.')
      return
    }
    if (!(params.signal_types?.length)) {
      setError('시그널 타입을 최소 1개 선택하세요.')
      return
    }

    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await backtestApi.run(params)
      setResult(res)
      setParamsOpen(false)
      setTradePage(0)
    } catch (e: unknown) {
      // axios 에러에서 백엔드 상세 메시지 추출
      const axiosErr = e as { response?: { data?: { detail?: string } } }
      const detail = axiosErr?.response?.data?.detail
      const msg = detail || (e instanceof Error ? e.message : '백테스트 실행 실패')
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const toggleSignal = (sig: string) => {
    const cur = params.signal_types || ALL_SIGNALS
    if (sig === 'top') {
      // TOP은 단독 선택 (배타적)
      if (cur.includes('top')) {
        setParams({ ...params, signal_types: ALL_SIGNALS.filter(s => s !== 'top') })
      } else {
        setParams({ ...params, signal_types: ['top'] })
      }
    } else {
      // 개별 시그널 선택 시 top 해제
      const withoutTop = cur.filter(s => s !== 'top')
      if (withoutTop.includes(sig)) {
        setParams({ ...params, signal_types: withoutTop.filter(s => s !== sig) })
      } else {
        setParams({ ...params, signal_types: [...withoutTop, sig] })
      }
    }
  }

  // 자산 곡선 차트
  const renderChart = useCallback(() => {
    if (!chartRef.current || !result?.equity_curve.length) return
    if (chartInstanceRef.current) {
      chartInstanceRef.current.remove()
      chartInstanceRef.current = null
    }

    const isDark = document.documentElement.classList.contains('dark')
    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: 320,
      layout: {
        background: { color: isDark ? '#1f2937' : '#ffffff' },
        textColor: isDark ? '#d1d5db' : '#374151',
      },
      grid: {
        vertLines: { color: isDark ? '#374151' : '#e5e7eb' },
        horzLines: { color: isDark ? '#374151' : '#e5e7eb' },
      },
      rightPriceScale: { borderColor: isDark ? '#4b5563' : '#d1d5db' },
      timeScale: { borderColor: isDark ? '#4b5563' : '#d1d5db' },
    })
    chartInstanceRef.current = chart

    const equitySeries = chart.addSeries(LineSeries, {
      color: '#3b82f6',
      lineWidth: 2,
      title: '자산',
    })
    equitySeries.setData(
      result.equity_curve.map(p => ({ time: p.date, value: p.value }))
    )

    // 시드 기준선
    const baselineSeries = chart.addSeries(LineSeries, {
      color: '#9ca3af',
      lineWidth: 1,
      lineStyle: 2,
      title: '시드',
    })
    baselineSeries.setData(
      result.equity_curve.map(p => ({ time: p.date, value: result.summary.initial_capital }))
    )

    // 코스피/코스닥 정규화 (시드 기준, 동일 스케일)
    const seed = result.summary.initial_capital
    const normalizeIndex = (curve: { date: string; value: number }[]) => {
      if (!curve.length) return []
      const base = curve[0].value
      if (base <= 0) return []
      return curve.map(p => ({ time: p.date, value: seed * (p.value / base) }))
    }

    if (result.kospi_curve.length > 0) {
      const kospiSeries = chart.addSeries(LineSeries, {
        color: '#f59e0b',
        lineWidth: 1,
        title: 'KOSPI',
      })
      kospiSeries.setData(normalizeIndex(result.kospi_curve))
    }

    if (result.kosdaq_curve.length > 0) {
      const kosdaqSeries = chart.addSeries(LineSeries, {
        color: '#a855f7',
        lineWidth: 1,
        title: 'KOSDAQ',
      })
      kosdaqSeries.setData(normalizeIndex(result.kosdaq_curve))
    }

    chart.timeScale().fitContent()

    const handleResize = () => {
      if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth })
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [result])

  useEffect(() => {
    const cleanup = renderChart()
    return () => cleanup?.()
  }, [renderChart])

  // 매매 차트 모달
  const handleTradeClick = async (trade: BacktestTrade) => {
    setSelectedTrade(trade)
    setTradeChartLoading(true)
    try {
      const entryDate = new Date(trade.entry_date)
      const exitDate = new Date(trade.exit_date)
      const marginDays = Math.max(30, trade.holding_days * 2)
      const totalDays = Math.ceil((exitDate.getTime() - entryDate.getTime()) / 86400000) + marginDays * 2
      // 청산일 + 여유일 이후 날짜를 before_date로 지정해 해당 매매 기간 데이터를 가져옴
      const afterExit = new Date(exitDate.getTime() + marginDays * 86400000)
      const beforeDateStr = afterExit.toISOString().split('T')[0]
      const data = await themeSetupApi.getStockOHLCV(trade.stock_code, totalDays, beforeDateStr)
      // 모달이 열린 후 DOM 렌더 대기
      setTimeout(() => renderTradeChart(trade, data.candles), 50)
    } catch {
      // 차트 로드 실패 시 조용히 처리
    } finally {
      setTradeChartLoading(false)
    }
  }

  const renderTradeChart = (trade: BacktestTrade, candles: Array<{ time: number; open: number; high: number; low: number; close: number; volume: number }>) => {
    if (!tradeChartRef.current || !candles.length) return
    if (tradeChartInstanceRef.current) {
      tradeChartInstanceRef.current.remove()
      tradeChartInstanceRef.current = null
    }

    const isDark = document.documentElement.classList.contains('dark')
    const chart = createChart(tradeChartRef.current, {
      width: tradeChartRef.current.clientWidth,
      height: 350,
      layout: {
        background: { color: isDark ? '#1f2937' : '#ffffff' },
        textColor: isDark ? '#d1d5db' : '#374151',
      },
      grid: {
        vertLines: { color: isDark ? '#374151' : '#e5e7eb' },
        horzLines: { color: isDark ? '#374151' : '#e5e7eb' },
      },
      rightPriceScale: { borderColor: isDark ? '#4b5563' : '#d1d5db' },
      timeScale: { borderColor: isDark ? '#4b5563' : '#d1d5db' },
    })
    tradeChartInstanceRef.current = chart

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#ef4444',
      downColor: '#3b82f6',
      borderUpColor: '#ef4444',
      borderDownColor: '#3b82f6',
      wickUpColor: '#ef4444',
      wickDownColor: '#3b82f6',
    })
    candleSeries.setData(candles.map(c => ({
      time: c.time as UTCTimestamp,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    })))

    const entryTime = Math.floor(new Date(trade.entry_date).getTime() / 1000) as UTCTimestamp
    const exitTime = Math.floor(new Date(trade.exit_date).getTime() / 1000) as UTCTimestamp

    // 진입가/청산가 수평선
    const entryLine = chart.addSeries(LineSeries, {
      color: '#22c55e',
      lineWidth: 1,
      lineStyle: 2,
      title: `진입 ${trade.entry_price.toLocaleString()}`,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    const exitColor = trade.return_pct >= 0 ? '#ef4444' : '#3b82f6'
    const exitLine = chart.addSeries(LineSeries, {
      color: exitColor,
      lineWidth: 1,
      lineStyle: 2,
      title: `청산 ${trade.exit_price.toLocaleString()}`,
      priceLineVisible: false,
      lastValueVisible: false,
    })

    const lineCandles = candles.filter(c => c.time >= (entryTime as number) && c.time <= (exitTime as number))
    if (lineCandles.length > 0) {
      entryLine.setData(lineCandles.map(c => ({ time: c.time as UTCTimestamp, value: trade.entry_price })))
      exitLine.setData(lineCandles.map(c => ({ time: c.time as UTCTimestamp, value: trade.exit_price })))
    }

    // 마커
    createSeriesMarkers(candleSeries, [
      {
        time: entryTime,
        position: 'belowBar',
        color: '#22c55e',
        shape: 'arrowUp',
        text: `매수 ${trade.entry_price.toLocaleString()}`,
      },
      {
        time: exitTime,
        position: 'aboveBar',
        color: exitColor,
        shape: 'arrowDown',
        text: `${EXIT_LABELS[trade.exit_reason] || '청산'} ${trade.exit_price.toLocaleString()}`,
      },
    ])

    chart.timeScale().fitContent()
  }

  const closeTradeModal = () => {
    if (tradeChartInstanceRef.current) {
      tradeChartInstanceRef.current.remove()
      tradeChartInstanceRef.current = null
    }
    setSelectedTrade(null)
  }

  // 거래 필터 + 정렬
  const filteredTrades = result?.trades ? result.trades.filter(t => {
    if (returnFilter === 'win') return t.profit > 0
    if (returnFilter === 'lose') return t.profit <= 0
    return true
  }) : []

  const sortedTrades = [...filteredTrades].sort((a, b) => {
    const key = tradeSort.key
    const av = a[key]
    const bv = b[key]
    if (typeof av === 'number' && typeof bv === 'number') {
      return tradeSort.asc ? av - bv : bv - av
    }
    return tradeSort.asc
      ? String(av).localeCompare(String(bv))
      : String(bv).localeCompare(String(av))
  })

  const tradesPerPage = 50
  const totalPages = Math.ceil(sortedTrades.length / tradesPerPage)
  const pagedTrades = sortedTrades.slice(tradePage * tradesPerPage, (tradePage + 1) * tradesPerPage)

  const handleSort = (key: keyof BacktestTrade) => {
    setTradeSort(prev => ({ key, asc: prev.key === key ? !prev.asc : false }))
    setTradePage(0)
  }

  const s = result?.summary

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold dark:text-white">시그널 전략 백테스트</h1>

      {/* 파라미터 패널 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <button
          onClick={() => setParamsOpen(!paramsOpen)}
          className="w-full px-4 py-3 flex items-center justify-between text-left font-medium dark:text-white"
        >
          <span>파라미터 설정</span>
          <span className="text-gray-400">{paramsOpen ? '▲' : '▼'}</span>
        </button>
        {paramsOpen && (
          <div className="px-4 pb-4 space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <label className="block">
                <span className="text-sm text-gray-600 dark:text-gray-400">시작일</span>
                <input type="date" value={params.start_date}
                  onChange={e => setParams({ ...params, start_date: e.target.value })}
                  className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
              </label>
              <label className="block">
                <span className="text-sm text-gray-600 dark:text-gray-400">종료일</span>
                <input type="date" value={params.end_date}
                  onChange={e => setParams({ ...params, end_date: e.target.value })}
                  className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
              </label>
              <label className="block">
                <span className="text-sm text-gray-600 dark:text-gray-400">시드 (만원)</span>
                <input type="number" value={(params.initial_capital || 10_000_000) / 10000}
                  onChange={e => setParams({ ...params, initial_capital: Number(e.target.value) * 10000 })}
                  className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
              </label>
              <label className="block">
                <span className="text-sm text-gray-600 dark:text-gray-400">최대 포지션</span>
                <input type="range" min={1} max={30} value={params.max_positions}
                  onChange={e => setParams({ ...params, max_positions: Number(e.target.value) })}
                  className="mt-2 w-full" />
                <span className="text-xs dark:text-gray-400">{params.max_positions}종목</span>
              </label>
            </div>
            {/* 매매 규칙 */}
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">매매 규칙</div>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
              <label className="block">
                <span className="text-sm text-gray-600 dark:text-gray-400">최소 점수</span>
                <div className="flex gap-1 mt-1">
                  {[40, 60, 80].map(v => (
                    <button key={v}
                      onClick={() => setParams({ ...params, min_signal_score: v })}
                      className={`px-3 py-1 rounded text-sm ${params.min_signal_score === v
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 dark:text-gray-300'}`}>
                      {v}
                    </button>
                  ))}
                </div>
              </label>
              <label className="block">
                <span className="text-sm text-gray-600 dark:text-gray-400">손절 %</span>
                <input type="number" value={params.stop_loss_pct} min={1} max={30}
                  onChange={e => setParams({ ...params, stop_loss_pct: Number(e.target.value) })}
                  className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
              </label>
              <label className="block">
                <span className="text-sm text-gray-600 dark:text-gray-400">익절 %</span>
                <input type="number" value={params.take_profit_pct} min={5}
                  onChange={e => setParams({ ...params, take_profit_pct: Number(e.target.value) })}
                  className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
              </label>
              <label className="block">
                <span className="text-sm text-gray-600 dark:text-gray-400">보유기한 (일)</span>
                <input type="number" value={params.max_holding_days} min={5}
                  onChange={e => setParams({ ...params, max_holding_days: Number(e.target.value) })}
                  className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
              </label>
              <label className="block">
                <span className="text-sm text-gray-600 dark:text-gray-400">트레일링 %</span>
                <input type="number" value={params.trailing_stop_pct} min={1} max={30}
                  onChange={e => setParams({ ...params, trailing_stop_pct: Number(e.target.value) })}
                  disabled={params.adaptive_trailing}
                  className={`mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm ${params.adaptive_trailing ? 'opacity-40' : ''}`} />
              </label>
              <label className="block">
                <span className="text-sm text-gray-600 dark:text-gray-400">MA이격 청산 %</span>
                <input type="number" value={params.ma_deviation_exit_pct} min={0} max={100}
                  onChange={e => setParams({ ...params, ma_deviation_exit_pct: Number(e.target.value) })}
                  disabled={params.adaptive_trailing}
                  className={`mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm ${params.adaptive_trailing ? 'opacity-40' : ''}`} />
                <span className="text-xs text-gray-400">0=비활성</span>
              </label>
              <label className="block">
                <span className="text-sm text-gray-600 dark:text-gray-400">스캔 간격 (일)</span>
                <input type="number" value={params.step_days} min={1} max={5}
                  onChange={e => setParams({ ...params, step_days: Number(e.target.value) })}
                  className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
              </label>
              <label className="block">
                <span className="text-sm text-gray-600 dark:text-gray-400">쿨다운 (일)</span>
                <input type="number" value={params.cooldown_days} min={0} max={20}
                  onChange={e => setParams({ ...params, cooldown_days: Number(e.target.value) })}
                  className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
              </label>
            </div>

            {/* 적응형 트레일링 */}
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">적응형 트레일링</div>
            <div className="flex items-center gap-3 mb-1">
              <button
                onClick={() => setParams({ ...params, adaptive_trailing: !params.adaptive_trailing })}
                className={`relative w-11 h-6 rounded-full transition-colors ${params.adaptive_trailing ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'}`}>
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${params.adaptive_trailing ? 'translate-x-5' : ''}`} />
              </button>
              <span className="text-sm dark:text-gray-300">
                {params.adaptive_trailing ? 'ON — 이격도 비례 트레일링 + 피크 반전 감지' : 'OFF — 기본 모드 (고정 트레일링/MA이격)'}
              </span>
            </div>
            {params.adaptive_trailing && (
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 pl-2 border-l-2 border-blue-500">
                <label className="block">
                  <span className="text-sm text-gray-600 dark:text-gray-400">이격도 중간 %</span>
                  <input type="number" value={params.adaptive_dev_mid} min={5} max={60}
                    onChange={e => setParams({ ...params, adaptive_dev_mid: Number(e.target.value) })}
                    className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
                  <span className="text-xs text-gray-400">경고구간 시작</span>
                </label>
                <label className="block">
                  <span className="text-sm text-gray-600 dark:text-gray-400">이격도 높음 %</span>
                  <input type="number" value={params.adaptive_dev_high} min={10} max={80}
                    onChange={e => setParams({ ...params, adaptive_dev_high: Number(e.target.value) })}
                    className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
                  <span className="text-xs text-gray-400">극단 과열 구간</span>
                </label>
                <label className="block">
                  <span className="text-sm text-gray-600 dark:text-gray-400">트레일링 (낮음)</span>
                  <input type="number" value={params.adaptive_trail_low} min={1} max={20}
                    onChange={e => setParams({ ...params, adaptive_trail_low: Number(e.target.value) })}
                    className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
                  <span className="text-xs text-gray-400">이격 {'<'} {params.adaptive_dev_mid}%</span>
                </label>
                <label className="block">
                  <span className="text-sm text-gray-600 dark:text-gray-400">트레일링 (중간)</span>
                  <input type="number" value={params.adaptive_trail_mid} min={1} max={15}
                    onChange={e => setParams({ ...params, adaptive_trail_mid: Number(e.target.value) })}
                    className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
                  <span className="text-xs text-gray-400">이격 {params.adaptive_dev_mid}~{params.adaptive_dev_high}%</span>
                </label>
                <label className="block">
                  <span className="text-sm text-gray-600 dark:text-gray-400">트레일링 (높음)</span>
                  <input type="number" value={params.adaptive_trail_high} min={1} max={10}
                    onChange={e => setParams({ ...params, adaptive_trail_high: Number(e.target.value) })}
                    className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
                  <span className="text-xs text-gray-400">이격 {'>'} {params.adaptive_dev_high}%</span>
                </label>
                <label className="block">
                  <span className="text-sm text-gray-600 dark:text-gray-400">피크 반전 %p</span>
                  <input type="number" value={params.adaptive_peak_drop} min={3} max={30}
                    onChange={e => setParams({ ...params, adaptive_peak_drop: Number(e.target.value) })}
                    className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
                  <span className="text-xs text-gray-400">최고점 대비 하락</span>
                </label>
                <label className="block">
                  <span className="text-sm text-gray-600 dark:text-gray-400">수익 전환 %</span>
                  <input type="number" value={params.adaptive_profit_trigger} min={5} max={100}
                    onChange={e => setParams({ ...params, adaptive_profit_trigger: Number(e.target.value) })}
                    className="mt-1 block w-full rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white text-sm" />
                  <span className="text-xs text-gray-400">N%+ 시 트레일링 전환</span>
                </label>
              </div>
            )}
            <div>
              <span className="text-sm text-gray-600 dark:text-gray-400">시그널 타입</span>
              <div className="flex flex-wrap gap-2 mt-1">
                {ALL_SIGNALS.map(sig => (
                  <button key={sig}
                    onClick={() => toggleSignal(sig)}
                    className={`px-2 py-1 rounded text-xs font-medium ${(params.signal_types || []).includes(sig)
                      ? sig === 'top' ? 'bg-amber-500 text-white ring-2 ring-amber-300' : 'bg-blue-600 text-white'
                      : 'bg-gray-100 dark:bg-gray-700 dark:text-gray-400'}`}>
                    {SIGNAL_LABELS[sig] || sig}
                  </button>
                ))}
              </div>
            </div>
            <button
              onClick={handleRun}
              disabled={loading}
              className="w-full py-2 rounded bg-blue-600 hover:bg-blue-700 text-white font-medium disabled:opacity-50"
            >
              {loading ? '전 종목 스캔 중... (1~3분)' : '백테스트 실행'}
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 p-3 rounded">{error}</div>
      )}

      {loading && (
        <div className="bg-yellow-50 dark:bg-yellow-900/20 p-4 rounded text-center">
          <div className="animate-spin inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full mb-2" />
          <p className="text-sm text-gray-600 dark:text-gray-400">
            전 종목 슬라이딩 윈도우 스캔 중... 1~3분 소요될 수 있습니다.
          </p>
        </div>
      )}

      {s && result && (
        <>
          {/* 요약 카드 6개 */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <SummaryCard label="총 수익률" value={`${s.total_return_pct > 0 ? '+' : ''}${s.total_return_pct}%`}
              sub={`${formatKRW(s.final_capital - s.initial_capital)}원`}
              color={s.total_return_pct >= 0 ? 'text-red-500' : 'text-blue-500'} />
            <SummaryCard label="MDD" value={`-${s.mdd_pct}%`} sub="최대 낙폭" color="text-blue-500" />
            <SummaryCard label="승률" value={`${s.win_rate}%`} sub={`${s.total_trades}건`}
              color={s.win_rate >= 50 ? 'text-red-500' : 'text-blue-500'} />
            <SummaryCard label="평균 수익률" value={`${s.avg_return_pct > 0 ? '+' : ''}${s.avg_return_pct}%`}
              sub={`평균 ${s.avg_holding_days}일 보유`}
              color={s.avg_return_pct >= 0 ? 'text-red-500' : 'text-blue-500'} />
            <SummaryCard label="손익비" value={`${s.profit_factor}`}
              sub="총이익/총손실" color={s.profit_factor >= 1 ? 'text-red-500' : 'text-blue-500'} />
            <SummaryCard label="샤프 비율" value={`${s.sharpe_ratio}`}
              sub="연환산" color={s.sharpe_ratio >= 0 ? 'text-red-500' : 'text-blue-500'} />
          </div>

          {/* 자산 곡선 */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
            <h3 className="font-medium mb-2 dark:text-white">자산 곡선</h3>
            <div ref={chartRef} />
          </div>

          {/* 시그널별 성과 */}
          {result.signal_performance.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 overflow-x-auto">
              <h3 className="font-medium mb-2 dark:text-white">시그널별 성과</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b dark:border-gray-700 text-gray-500 dark:text-gray-400">
                    <th className="py-2 text-left">시그널</th>
                    <th className="py-2 text-right">건수</th>
                    <th className="py-2 text-right">승률</th>
                    <th className="py-2 text-right">평균 수익률</th>
                    <th className="py-2 text-right">총 손익</th>
                  </tr>
                </thead>
                <tbody>
                  {result.signal_performance.map(sp => (
                    <tr key={sp.signal_type} className="border-b dark:border-gray-700">
                      <td className="py-2 dark:text-gray-300">{SIGNAL_LABELS[sp.signal_type] || sp.signal_type}</td>
                      <td className="py-2 text-right dark:text-gray-300">{sp.count}</td>
                      <td className={`py-2 text-right ${sp.win_rate >= 50 ? 'text-red-500' : 'text-blue-500'}`}>{sp.win_rate}%</td>
                      <td className={`py-2 text-right ${sp.avg_return_pct >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        {sp.avg_return_pct > 0 ? '+' : ''}{sp.avg_return_pct}%
                      </td>
                      <td className={`py-2 text-right ${sp.total_profit >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        {formatKRW(sp.total_profit)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 월별 성과 */}
          {result.monthly_performance.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 overflow-x-auto">
              <h3 className="font-medium mb-2 dark:text-white">월별 성과</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b dark:border-gray-700 text-gray-500 dark:text-gray-400">
                    <th className="py-2 text-left">월</th>
                    <th className="py-2 text-right">수익률</th>
                    <th className="py-2 text-right">거래 수</th>
                    <th className="py-2 text-right">승률</th>
                  </tr>
                </thead>
                <tbody>
                  {result.monthly_performance.map(mp => (
                    <tr key={mp.month} className="border-b dark:border-gray-700">
                      <td className="py-2 dark:text-gray-300">{mp.month}</td>
                      <td className={`py-2 text-right ${mp.return_pct >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        {mp.return_pct > 0 ? '+' : ''}{mp.return_pct}%
                      </td>
                      <td className="py-2 text-right dark:text-gray-300">{mp.trades}</td>
                      <td className={`py-2 text-right ${mp.win_rate >= 50 ? 'text-red-500' : 'text-blue-500'}`}>{mp.win_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 매매 차트 모달 */}
          {selectedTrade && (
            <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
              onClick={closeTradeModal}>
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-3xl"
                onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between px-4 py-3 border-b dark:border-gray-700">
                  <div>
                    <span className="font-medium dark:text-white">
                      {selectedTrade.stock_name} ({selectedTrade.stock_code})
                    </span>
                    <span className={`ml-2 text-sm font-medium ${selectedTrade.return_pct >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                      {selectedTrade.return_pct > 0 ? '+' : ''}{selectedTrade.return_pct}%
                    </span>
                    <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                      {SIGNAL_LABELS[selectedTrade.signal_type]} | {selectedTrade.entry_date} ~ {selectedTrade.exit_date} ({selectedTrade.holding_days}일)
                    </span>
                  </div>
                  <button onClick={closeTradeModal}
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl leading-none">
                    &times;
                  </button>
                </div>
                <div className="p-4">
                  {tradeChartLoading ? (
                    <div className="flex items-center justify-center h-[350px]">
                      <div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" />
                    </div>
                  ) : (
                    <div ref={tradeChartRef} />
                  )}
                </div>
                <div className="px-4 pb-3 flex gap-4 text-xs text-gray-500 dark:text-gray-400">
                  <span>진입: <span className="text-green-500 font-medium">{selectedTrade.entry_price.toLocaleString()}원</span></span>
                  <span>청산: <span className={`font-medium ${selectedTrade.return_pct >= 0 ? 'text-red-500' : 'text-blue-500'}`}>{selectedTrade.exit_price.toLocaleString()}원</span></span>
                  <span>사유: {EXIT_LABELS[selectedTrade.exit_reason]}</span>
                  <span>손익: <span className={`font-medium ${selectedTrade.profit >= 0 ? 'text-red-500' : 'text-blue-500'}`}>{formatKRW(selectedTrade.profit)}원</span></span>
                </div>
              </div>
            </div>
          )}

          {/* 거래 내역 */}
          {(result?.trades?.length ?? 0) > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 overflow-x-auto">
              <div className="flex items-center justify-between mb-2">
                <h3 className="font-medium dark:text-white">
                  거래 내역 ({sortedTrades.length}건{returnFilter !== 'all' ? ` / 전체 ${result?.trades.length}건` : ''})
                </h3>
                <div className="flex items-center gap-1">
                  {([['all', '전체'], ['win', '익절'], ['lose', '손절']] as const).map(([key, label]) => (
                    <button key={key}
                      onClick={() => { setReturnFilter(key); setTradePage(0) }}
                      className={`px-2 py-1 rounded text-xs ${returnFilter === key
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 dark:text-gray-400'}`}>
                      {label}
                    </button>
                  ))}
                  <span className="mx-1 text-gray-300 dark:text-gray-600">|</span>
                  <button
                    onClick={() => { setTradeSort({ key: 'return_pct', asc: true }); setTradePage(0) }}
                    className={`px-2 py-1 rounded text-xs ${tradeSort.key === 'return_pct' && tradeSort.asc
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 dark:bg-gray-700 dark:text-gray-400'}`}>
                    수익률 ▲
                  </button>
                  <button
                    onClick={() => { setTradeSort({ key: 'return_pct', asc: false }); setTradePage(0) }}
                    className={`px-2 py-1 rounded text-xs ${tradeSort.key === 'return_pct' && !tradeSort.asc
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 dark:bg-gray-700 dark:text-gray-400'}`}>
                    수익률 ▼
                  </button>
                </div>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b dark:border-gray-700 text-gray-500 dark:text-gray-400">
                    {([
                      ['stock_name', '종목'],
                      ['signal_type', '시그널'],
                      ['signal_score', '점수'],
                      ['entry_date', '진입일'],
                      ['entry_price', '진입가'],
                      ['exit_date', '청산일'],
                      ['exit_price', '청산가'],
                      ['exit_reason', '사유'],
                      ['return_pct', '수익률'],
                      ['profit', '손익'],
                      ['holding_days', '보유일'],
                    ] as [keyof BacktestTrade, string][]).map(([key, label]) => (
                      <th key={key}
                        className="py-2 text-right first:text-left cursor-pointer hover:text-gray-700 dark:hover:text-gray-200"
                        onClick={() => handleSort(key)}>
                        {label}{tradeSort.key === key ? (tradeSort.asc ? ' ▲' : ' ▼') : ''}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pagedTrades.map((t, i) => (
                    <tr key={`${t.stock_code}-${t.entry_date}-${i}`} className="border-b dark:border-gray-700">
                      <td className="py-1.5">
                        <button onClick={() => handleTradeClick(t)}
                          className="text-blue-600 dark:text-blue-400 hover:underline text-left">
                          {t.stock_name}
                        </button>
                      </td>
                      <td className="py-1.5 text-right dark:text-gray-300 text-xs">
                        {SIGNAL_LABELS[t.signal_type] || t.signal_type}
                      </td>
                      <td className="py-1.5 text-right dark:text-gray-300">{t.signal_score}</td>
                      <td className="py-1.5 text-right dark:text-gray-300 text-xs">{t.entry_date}</td>
                      <td className="py-1.5 text-right dark:text-gray-300">{t.entry_price.toLocaleString()}</td>
                      <td className="py-1.5 text-right dark:text-gray-300 text-xs">{t.exit_date}</td>
                      <td className="py-1.5 text-right dark:text-gray-300">{t.exit_price.toLocaleString()}</td>
                      <td className="py-1.5 text-right dark:text-gray-300 text-xs">{EXIT_LABELS[t.exit_reason] || t.exit_reason}</td>
                      <td className={`py-1.5 text-right font-medium ${t.return_pct >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        {t.return_pct > 0 ? '+' : ''}{t.return_pct}%
                      </td>
                      <td className={`py-1.5 text-right ${t.profit >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        {formatKRW(t.profit)}
                      </td>
                      <td className="py-1.5 text-right dark:text-gray-300">{t.holding_days}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 mt-3">
                  <button onClick={() => setTradePage(p => Math.max(0, p - 1))}
                    disabled={tradePage === 0}
                    className="px-3 py-1 rounded text-sm bg-gray-100 dark:bg-gray-700 dark:text-gray-300 disabled:opacity-40">
                    이전
                  </button>
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {tradePage + 1} / {totalPages}
                  </span>
                  <button onClick={() => setTradePage(p => Math.min(totalPages - 1, p + 1))}
                    disabled={tradePage >= totalPages - 1}
                    className="px-3 py-1 rounded text-sm bg-gray-100 dark:bg-gray-700 dark:text-gray-300 disabled:opacity-40">
                    다음
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function SummaryCard({ label, value, sub, color }: {
  label: string; value: string; sub: string; color: string
}) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
      <div className={`text-xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-400">{sub}</div>
    </div>
  )
}
