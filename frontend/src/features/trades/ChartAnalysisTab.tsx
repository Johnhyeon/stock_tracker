import { useState, useEffect, useRef, memo } from 'react'
import { analysisApi } from '../../services/api'
import type {
  ChartAnalysisResponse,
  EntryTimingItem,
  ExitTimingItem,
  MFEMAEItem,
  MiniChartData,
  ScatterPoint,
} from '../../types/chart_analysis'
import { createChart, CandlestickSeries, createSeriesMarkers, UTCTimestamp } from 'lightweight-charts'

function useIsDark() {
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains('dark'))
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains('dark'))
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])
  return isDark
}

const fmtN = (n: number | null | undefined, d = 1) =>
  n == null ? '-' : n >= 0 ? `+${n.toFixed(d)}%` : `${n.toFixed(d)}%`

const fmtP = (n: number) => n.toLocaleString('ko-KR')

// ---------- 섹션 1: 진입 타이밍 ----------
function EntryTimingSection({ data }: { data: ChartAnalysisResponse['entry_timing'] }) {
  const [showTable, setShowTable] = useState(false)
  if (data.total_entries === 0) return <EmptySection label="진입 데이터" />

  return (
    <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4 space-y-4">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
        진입 타이밍 분석
        <span className="text-xs text-gray-400 font-normal">({data.total_entries}건)</span>
      </h3>

      {/* 요약 카드 */}
      <div className="grid grid-cols-3 gap-3">
        <SummaryCard
          title="MA 포지션"
          items={[
            { label: 'MA20 위', value: `${data.above_ma20_pct.toFixed(0)}%`, color: data.above_ma20_pct > 50 ? 'text-red-500' : 'text-blue-500' },
            { label: 'MA60 위', value: `${data.above_ma60_pct.toFixed(0)}%`, color: data.above_ma60_pct > 50 ? 'text-red-500' : 'text-blue-500' },
            { label: '평균 MA20%', value: fmtN(data.avg_ma20_pct), color: data.avg_ma20_pct >= 0 ? 'text-red-400' : 'text-blue-400' },
          ]}
        />
        <SummaryCard
          title="BB 위치"
          items={[
            { label: '하단', value: `${data.bb_lower_pct.toFixed(0)}%`, color: 'text-blue-500' },
            { label: '중앙', value: `${data.bb_middle_pct.toFixed(0)}%`, color: 'text-gray-500' },
            { label: '상단', value: `${data.bb_upper_pct.toFixed(0)}%`, color: 'text-red-500' },
          ]}
        />
        <SummaryCard
          title="거래량"
          items={[
            { label: '고거래량', value: `${data.high_volume_pct.toFixed(0)}%`, color: data.high_volume_pct > 40 ? 'text-red-500' : 'text-gray-600 dark:text-t-text-secondary' },
            { label: '평균 비율', value: `${data.avg_volume_ratio.toFixed(1)}x`, color: 'text-gray-600 dark:text-t-text-secondary' },
          ]}
        />
      </div>

      {/* 테이블 토글 */}
      <button
        onClick={() => setShowTable(v => !v)}
        className="text-xs text-primary-500 hover:underline"
      >
        {showTable ? '테이블 숨기기' : '상세 테이블 보기'}
      </button>

      {showTable && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200 dark:border-t-border text-gray-500 dark:text-t-text-muted">
                <th className="text-left py-1.5 pr-2">날짜</th>
                <th className="text-left py-1.5 pr-2">종목</th>
                <th className="text-right py-1.5 pr-2">가격</th>
                <th className="text-right py-1.5 pr-2">MA20%</th>
                <th className="text-right py-1.5 pr-2">BB</th>
                <th className="text-right py-1.5">거래량비</th>
              </tr>
            </thead>
            <tbody>
              {data.items.slice(0, 30).map((item, i) => (
                <EntryRow key={i} item={item} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function EntryRow({ item }: { item: EntryTimingItem }) {
  return (
    <tr className="border-b border-gray-100 dark:border-t-border/50 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50">
      <td className="py-1.5 pr-2 text-gray-600 dark:text-t-text-secondary font-mono">{item.trade_date.slice(5)}</td>
      <td className="py-1.5 pr-2 text-gray-900 dark:text-t-text-primary">{item.stock_name}</td>
      <td className="py-1.5 pr-2 text-right font-mono text-gray-700 dark:text-t-text-secondary">{fmtP(item.price)}</td>
      <td className={`py-1.5 pr-2 text-right font-mono ${item.ma20_pct != null && item.ma20_pct >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
        {fmtN(item.ma20_pct)}
      </td>
      <td className="py-1.5 pr-2 text-right font-mono text-gray-600 dark:text-t-text-secondary">
        {item.bb_position != null ? item.bb_position.toFixed(2) : '-'}
      </td>
      <td className={`py-1.5 text-right font-mono ${item.volume_ratio != null && item.volume_ratio > 1.5 ? 'text-red-500 font-semibold' : 'text-gray-600 dark:text-t-text-secondary'}`}>
        {item.volume_ratio != null ? `${item.volume_ratio.toFixed(1)}x` : '-'}
      </td>
    </tr>
  )
}

// ---------- 섹션 2: 청산 타이밍 ----------
function ExitTimingSection({ data }: { data: ChartAnalysisResponse['exit_timing'] }) {
  const [showTable, setShowTable] = useState(false)
  if (data.total_exits === 0) return <EmptySection label="청산 데이터" />

  return (
    <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4 space-y-4">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
        청산 타이밍 분석
        <span className="text-xs text-gray-400 font-normal">({data.total_exits}건)</span>
      </h3>

      <div className="grid grid-cols-2 gap-3">
        {/* 매도 후 주가 변화 */}
        <div className="bg-gray-50 dark:bg-t-bg-elevated rounded-lg p-3 space-y-2">
          <div className="text-xs font-medium text-gray-500 dark:text-t-text-muted">매도 후 주가 변화</div>
          {[
            { label: '5일 후', val: data.avg_after_5d },
            { label: '10일 후', val: data.avg_after_10d },
            { label: '20일 후', val: data.avg_after_20d },
          ].map(({ label, val }) => (
            <div key={label} className="flex items-center justify-between">
              <span className="text-xs text-gray-600 dark:text-t-text-secondary">{label}</span>
              <span className={`text-xs font-mono font-semibold flex items-center gap-1 ${val > 0 ? 'text-red-500' : 'text-blue-500'}`}>
                {fmtN(val)}
                {val > 3 && <span className="text-[10px]">!!!</span>}
              </span>
            </div>
          ))}
          <div className="border-t border-gray-200 dark:border-t-border pt-1.5 mt-1">
            <div className="flex justify-between text-[10px]">
              <span className="text-gray-400">조기매도</span>
              <span className="text-orange-500 font-semibold">{data.early_sell_pct.toFixed(0)}%</span>
            </div>
            <div className="flex justify-between text-[10px]">
              <span className="text-gray-400">적절매도</span>
              <span className="text-green-500 font-semibold">{data.good_sell_pct.toFixed(0)}%</span>
            </div>
          </div>
        </div>

        {/* 고점 대비 효율 */}
        <div className="bg-gray-50 dark:bg-t-bg-elevated rounded-lg p-3">
          <div className="text-xs font-medium text-gray-500 dark:text-t-text-muted mb-2">고점 대비 매도 효율</div>
          <div className={`text-xl font-bold font-mono ${data.avg_peak_vs_exit >= -3 ? 'text-green-600' : 'text-orange-500'}`}>
            {fmtN(data.avg_peak_vs_exit)}
          </div>
          <div className="text-[10px] text-gray-400 mt-1">
            보유 중 고점 대비 평균 차이
          </div>
          <div className="mt-3">
            <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-green-400 rounded-full transition-all"
                style={{ width: `${Math.max(0, Math.min(100, 100 + data.avg_peak_vs_exit * 3))}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
              <span>고점</span>
              <span>매도가</span>
            </div>
          </div>
        </div>
      </div>

      <button
        onClick={() => setShowTable(v => !v)}
        className="text-xs text-primary-500 hover:underline"
      >
        {showTable ? '테이블 숨기기' : '상세 테이블 보기'}
      </button>

      {showTable && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200 dark:border-t-border text-gray-500 dark:text-t-text-muted">
                <th className="text-left py-1.5 pr-2">날짜</th>
                <th className="text-left py-1.5 pr-2">종목</th>
                <th className="text-right py-1.5 pr-2">수익률</th>
                <th className="text-right py-1.5 pr-2">5일후</th>
                <th className="text-right py-1.5 pr-2">10일후</th>
                <th className="text-right py-1.5">고점비</th>
              </tr>
            </thead>
            <tbody>
              {data.items.slice(0, 30).map((item, i) => (
                <ExitRow key={i} item={item} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function ExitRow({ item }: { item: ExitTimingItem }) {
  return (
    <tr className="border-b border-gray-100 dark:border-t-border/50 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50">
      <td className="py-1.5 pr-2 text-gray-600 dark:text-t-text-secondary font-mono">{item.trade_date.slice(5)}</td>
      <td className="py-1.5 pr-2 text-gray-900 dark:text-t-text-primary">{item.stock_name}</td>
      <td className={`py-1.5 pr-2 text-right font-mono ${(item.realized_return_pct ?? 0) >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
        {fmtN(item.realized_return_pct)}
      </td>
      <td className={`py-1.5 pr-2 text-right font-mono ${(item.after_5d_pct ?? 0) > 0 ? 'text-red-400' : 'text-blue-400'}`}>
        {fmtN(item.after_5d_pct)}
      </td>
      <td className={`py-1.5 pr-2 text-right font-mono ${(item.after_10d_pct ?? 0) > 0 ? 'text-red-400' : 'text-blue-400'}`}>
        {fmtN(item.after_10d_pct)}
      </td>
      <td className="py-1.5 text-right font-mono text-gray-600 dark:text-t-text-secondary">
        {fmtN(item.peak_vs_exit_pct)}
      </td>
    </tr>
  )
}

// ---------- 섹션 3: MFE/MAE ----------
function MFEMAESection({ data }: { data: ChartAnalysisResponse['mfe_mae'] }) {
  const [showTable, setShowTable] = useState(false)
  if (data.total_positions === 0) return <EmptySection label="MFE/MAE 데이터" />

  return (
    <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4 space-y-4">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
        MFE/MAE 분석
        <span className="text-xs text-gray-400 font-normal">({data.total_positions}건)</span>
      </h3>

      {/* 요약 카드 */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-50 dark:bg-t-bg-elevated rounded-lg p-3 text-center">
          <div className="text-[10px] text-gray-400 mb-1">평균 MFE</div>
          <div className="text-lg font-bold font-mono text-red-500">{fmtN(data.avg_mfe)}</div>
          <div className="text-[10px] text-gray-400">최대 순간 수익</div>
        </div>
        <div className="bg-gray-50 dark:bg-t-bg-elevated rounded-lg p-3 text-center">
          <div className="text-[10px] text-gray-400 mb-1">평균 MAE</div>
          <div className="text-lg font-bold font-mono text-blue-500">{fmtN(data.avg_mae)}</div>
          <div className="text-[10px] text-gray-400">최대 순간 손실</div>
        </div>
        <div className="bg-gray-50 dark:bg-t-bg-elevated rounded-lg p-3 text-center">
          <div className="text-[10px] text-gray-400 mb-1">수익실현율</div>
          <div className={`text-lg font-bold font-mono ${data.avg_capture_ratio >= 50 ? 'text-green-600' : 'text-orange-500'}`}>
            {data.avg_capture_ratio.toFixed(0)}%
          </div>
          <div className="text-[10px] text-gray-400">실현/MFE 비율</div>
        </div>
      </div>

      {/* 스캐터 차트 */}
      {data.scatter_data.length > 0 && <ScatterChart data={data.scatter_data} />}

      <button
        onClick={() => setShowTable(v => !v)}
        className="text-xs text-primary-500 hover:underline"
      >
        {showTable ? '테이블 숨기기' : '상세 테이블 보기'}
      </button>

      {showTable && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200 dark:border-t-border text-gray-500 dark:text-t-text-muted">
                <th className="text-left py-1.5 pr-2">종목</th>
                <th className="text-right py-1.5 pr-2">진입가</th>
                <th className="text-right py-1.5 pr-2">청산가</th>
                <th className="text-right py-1.5 pr-2">수익률</th>
                <th className="text-right py-1.5 pr-2">MFE</th>
                <th className="text-right py-1.5 pr-2">MAE</th>
                <th className="text-right py-1.5">실현율</th>
              </tr>
            </thead>
            <tbody>
              {data.items.slice(0, 30).map((item, i) => (
                <MFERow key={i} item={item} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function MFERow({ item }: { item: MFEMAEItem }) {
  return (
    <tr className="border-b border-gray-100 dark:border-t-border/50 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50">
      <td className="py-1.5 pr-2 text-gray-900 dark:text-t-text-primary">{item.stock_name}</td>
      <td className="py-1.5 pr-2 text-right font-mono text-gray-600 dark:text-t-text-secondary">{fmtP(item.entry_price)}</td>
      <td className="py-1.5 pr-2 text-right font-mono text-gray-600 dark:text-t-text-secondary">{fmtP(item.exit_price)}</td>
      <td className={`py-1.5 pr-2 text-right font-mono font-semibold ${item.realized_return_pct >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
        {fmtN(item.realized_return_pct)}
      </td>
      <td className="py-1.5 pr-2 text-right font-mono text-red-400">{fmtN(item.mfe_pct)}</td>
      <td className="py-1.5 pr-2 text-right font-mono text-blue-400">{fmtN(item.mae_pct)}</td>
      <td className="py-1.5 text-right font-mono text-gray-600 dark:text-t-text-secondary">
        {item.capture_ratio != null ? `${item.capture_ratio.toFixed(0)}%` : '-'}
      </td>
    </tr>
  )
}

// ---------- 스캐터 차트 (SVG) ----------
function ScatterChart({ data }: { data: ScatterPoint[] }) {
  const isDark = useIsDark()
  const W = 400
  const H = 200
  const PAD = 35

  if (data.length === 0) return null

  const allX = data.map(d => d.x)
  const allY = data.map(d => d.y)
  const minX = Math.min(...allX, -20)
  const maxX = Math.max(...allX, 0)
  const minY = Math.min(...allY, -20)
  const maxY = Math.max(...allY, 20)

  const scaleX = (v: number) => PAD + ((v - minX) / (maxX - minX || 1)) * (W - PAD * 2)
  const scaleY = (v: number) => H - PAD - ((v - minY) / (maxY - minY || 1)) * (H - PAD * 2)

  const zeroY = scaleY(0)
  const textColor = isDark ? '#94a3b8' : '#6b7280'
  const gridColor = isDark ? '#1e1e2e' : '#e5e7eb'

  return (
    <div className="bg-gray-50 dark:bg-t-bg-elevated rounded-lg p-3">
      <div className="text-[10px] text-gray-400 mb-2">MAE vs 실현수익률</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 220 }}>
        {/* 그리드 */}
        <line x1={PAD} y1={zeroY} x2={W - PAD} y2={zeroY} stroke={gridColor} strokeDasharray="4,3" />
        <line x1={scaleX(0)} y1={PAD} x2={scaleX(0)} y2={H - PAD} stroke={gridColor} strokeDasharray="4,3" />

        {/* 축 라벨 */}
        <text x={W / 2} y={H - 5} textAnchor="middle" fontSize={9} fill={textColor}>MAE (%)</text>
        <text x={8} y={H / 2} textAnchor="middle" fontSize={9} fill={textColor} transform={`rotate(-90, 8, ${H / 2})`}>수익률 (%)</text>

        {/* 데이터 포인트 */}
        {data.map((pt, i) => (
          <circle
            key={i}
            cx={scaleX(pt.x)}
            cy={scaleY(pt.y)}
            r={4}
            fill={pt.is_winner ? '#ef4444' : '#3b82f6'}
            fillOpacity={0.7}
            stroke={pt.is_winner ? '#dc2626' : '#2563eb'}
            strokeWidth={0.5}
          >
            <title>{`${pt.stock_name}: MAE ${pt.x.toFixed(1)}%, 수익 ${pt.y.toFixed(1)}%`}</title>
          </circle>
        ))}

        {/* 범례 */}
        <circle cx={W - 80} cy={12} r={4} fill="#ef4444" fillOpacity={0.7} />
        <text x={W - 72} y={15} fontSize={9} fill={textColor}>수익</text>
        <circle cx={W - 45} cy={12} r={4} fill="#3b82f6" fillOpacity={0.7} />
        <text x={W - 37} y={15} fontSize={9} fill={textColor}>손실</text>
      </svg>
    </div>
  )
}

// ---------- 섹션 4: 미니 차트 (Best) ----------
function MiniChartsSection({ charts }: { charts: MiniChartData[] }) {
  if (charts.length === 0) return <EmptySection label="미니 차트 데이터" />

  return (
    <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4 space-y-3">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
        Best 매매 차트
        <span className="text-xs text-gray-400 font-normal">(수익률 TOP {charts.length})</span>
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {charts.map((chart, i) => (
          <MiniChart key={i} data={chart} />
        ))}
      </div>
    </div>
  )
}

// ---------- 섹션 5: 미니 차트 (Worst) ----------
function WorstMiniChartsSection({ charts }: { charts: MiniChartData[] }) {
  if (charts.length === 0) return null

  return (
    <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-4 space-y-3">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-t-text-primary flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
        Worst 매매 차트
        <span className="text-xs text-gray-400 font-normal">(손실률 TOP {charts.length})</span>
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {charts.map((chart, i) => (
          <MiniChart key={`worst-${i}`} data={chart} />
        ))}
      </div>
    </div>
  )
}

const MiniChart = memo(function MiniChart({ data }: { data: MiniChartData }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const isDark = useIsDark()

  const typeLabel = { BUY: '매수', ADD_BUY: '추매', SELL: '매도', PARTIAL_SELL: '부분매도' }[data.trade_type] || data.trade_type

  useEffect(() => {
    if (!containerRef.current || data.candles.length === 0) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 320,
      layout: {
        background: { color: isDark ? '#0a0a0f' : '#f9fafb' },
        textColor: isDark ? '#94a3b8' : '#6b7280',
        fontSize: 9,
      },
      grid: {
        vertLines: { color: isDark ? '#1a1a28' : '#f0f0f0' },
        horzLines: { color: isDark ? '#1a1a28' : '#f0f0f0' },
      },
      timeScale: {
        borderColor: isDark ? '#1e1e2e' : '#e0e0e0',
        timeVisible: false,
      },
      rightPriceScale: {
        borderColor: isDark ? '#1e1e2e' : '#e0e0e0',
      },
      handleScroll: false,
      handleScale: false,
    })

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#ef4444',
      downColor: '#3b82f6',
      borderUpColor: '#ef4444',
      borderDownColor: '#3b82f6',
      wickUpColor: '#ef4444',
      wickDownColor: '#3b82f6',
    })

    candleSeries.setData(
      data.candles.map(c => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    )

    // 매매 마커
    if (data.markers.length > 0) {
      const markers = data.markers
        .sort((a, b) => a.time - b.time)
        .map(m => ({
          time: m.time as UTCTimestamp,
          position: m.type.includes('SELL') ? 'aboveBar' as const : 'belowBar' as const,
          color: m.type.includes('SELL') ? '#3b82f6' : '#ef4444',
          shape: m.type.includes('SELL') ? 'arrowDown' as const : 'arrowUp' as const,
          text: m.type.includes('SELL') ? 'S' : 'B',
        }))
      createSeriesMarkers(candleSeries, markers)
    }

    chart.timeScale().fitContent()

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    const resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(containerRef.current)

    return () => {
      resizeObserver.disconnect()
      chart.remove()
    }
  }, [data, isDark])

  return (
    <div className="bg-gray-50 dark:bg-t-bg-elevated rounded-lg p-2.5">
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold text-gray-900 dark:text-t-text-primary">{data.stock_name}</span>
          <span className={`text-[10px] px-1 py-0.5 rounded font-medium ${
            data.trade_type.includes('SELL')
              ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300'
              : 'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300'
          }`}>
            {typeLabel}
          </span>
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          <span className="text-gray-400 font-mono">{data.trade_date.slice(5)}</span>
          {data.realized_return_pct != null && (
            <span className={`font-mono font-semibold ${data.realized_return_pct >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
              {fmtN(data.realized_return_pct)}
            </span>
          )}
        </div>
      </div>
      <div ref={containerRef} />
    </div>
  )
})

// ---------- 공통 컴포넌트 ----------
function SummaryCard({ title, items }: {
  title: string
  items: { label: string; value: string; color?: string }[]
}) {
  return (
    <div className="bg-gray-50 dark:bg-t-bg-elevated rounded-lg p-3 space-y-1.5">
      <div className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">{title}</div>
      {items.map(({ label, value, color }) => (
        <div key={label} className="flex items-center justify-between">
          <span className="text-xs text-gray-500 dark:text-t-text-muted">{label}</span>
          <span className={`text-xs font-mono font-semibold ${color || 'text-gray-700 dark:text-t-text-secondary'}`}>{value}</span>
        </div>
      ))}
    </div>
  )
}

function EmptySection({ label }: { label: string }) {
  return (
    <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-8 text-center">
      <div className="text-gray-400 dark:text-t-text-muted text-sm">{label}가 없습니다.</div>
      <div className="text-xs text-gray-400 mt-1">매매 기록이 축적되면 분석이 시작됩니다.</div>
    </div>
  )
}

// ---------- 메인 탭 컴포넌트 ----------
export default function ChartAnalysisTab({ startDate, endDate }: { startDate?: string; endDate?: string }) {
  const [data, setData] = useState<ChartAnalysisResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    analysisApi.getChartAnalysis(startDate, endDate)
      .then(res => { if (!cancelled) setData(res) })
      .catch(() => { if (!cancelled) setError('차트 분석 데이터를 불러오는데 실패했습니다.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [startDate, endDate])

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-6 animate-pulse">
            <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded mb-4" />
            <div className="grid grid-cols-3 gap-3">
              {[1, 2, 3].map(j => (
                <div key={j} className="h-20 bg-gray-100 dark:bg-t-bg-elevated rounded-lg" />
              ))}
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-sm p-8 text-center">
        <div className="text-red-500 text-sm">{error}</div>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="space-y-4">
      <EntryTimingSection data={data.entry_timing} />
      <ExitTimingSection data={data.exit_timing} />
      <MFEMAESection data={data.mfe_mae} />
      <MiniChartsSection charts={data.mini_charts} />
      <WorstMiniChartsSection charts={data.worst_mini_charts} />
    </div>
  )
}
