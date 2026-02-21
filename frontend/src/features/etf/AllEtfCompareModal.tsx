import { useState, useEffect, useMemo } from 'react'
import { etfRotationApi, type EtfCompareItem } from '../../services/api'

interface AllEtfCompareModalProps {
  isOpen: boolean
  onClose: () => void
}

// 테마별 색상 (구분하기 쉽도록 다양한 색상)
const COLORS = [
  '#ef4444', '#f97316', '#eab308', '#84cc16', '#22c55e',
  '#14b8a6', '#06b6d4', '#0ea5e9', '#3b82f6', '#6366f1',
  '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f43f5e',
  '#78716c', '#57534e', '#44403c', '#292524', '#1c1917',
  '#64748b', '#475569',
]

type PeriodType = '2025' | '2026'

const PERIOD_CONFIG: Record<PeriodType, { startDate: string; label: string }> = {
  '2025': { startDate: '2025-01-02', label: '2025년~' },
  '2026': { startDate: '2026-01-02', label: '2026년~' },
}

export default function AllEtfCompareModal({ isOpen, onClose }: AllEtfCompareModalProps) {
  const [data, setData] = useState<EtfCompareItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedThemes, setSelectedThemes] = useState<Set<string>>(new Set())
  const [hoveredTheme, setHoveredTheme] = useState<string | null>(null)
  const [period, setPeriod] = useState<PeriodType>('2026')

  // ESC 키로 닫기
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (isOpen) {
      window.addEventListener('keydown', handleEsc)
      return () => window.removeEventListener('keydown', handleEsc)
    }
  }, [isOpen, onClose])

  useEffect(() => {
    if (!isOpen) return

    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        const result = await etfRotationApi.getAllEtfCompare(PERIOD_CONFIG[period].startDate)
        setData(result.etfs)
        // 기본으로 상위 5개, 하위 2개 선택
        const initial = new Set<string>()
        result.etfs.slice(0, 5).forEach(e => initial.add(e.theme))
        result.etfs.slice(-2).forEach(e => initial.add(e.theme))
        setSelectedThemes(initial)
      } catch (err) {
        setError('데이터를 불러오는데 실패했습니다')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [isOpen, period])

  // 차트 데이터 계산
  const chartData = useMemo(() => {
    if (data.length === 0) return { dates: [], series: [] }

    // 날짜 목록 (첫 번째 ETF 기준)
    const dates = data[0]?.data.map(d => d.date) || []

    // 선택된 테마만 필터링
    const series = data
      .filter(etf => selectedThemes.has(etf.theme))
      .map((etf) => ({
        theme: etf.theme,
        color: COLORS[data.findIndex(e => e.theme === etf.theme) % COLORS.length],
        points: etf.data.map(d => d.pct),
        latestPct: etf.latest_pct,
      }))

    return { dates, series }
  }, [data, selectedThemes])

  // 차트 그리기
  const renderChart = () => {
    const { dates, series } = chartData
    if (dates.length === 0 || series.length === 0) return null

    const width = 900
    const height = 500
    const padding = { top: 30, right: 120, bottom: 50, left: 60 }
    const chartWidth = width - padding.left - padding.right
    const chartHeight = height - padding.top - padding.bottom

    // Y축 범위 계산
    const allPcts = series.flatMap(s => s.points)
    const minPct = Math.min(...allPcts, 0)
    const maxPct = Math.max(...allPcts, 0)
    const yRange = maxPct - minPct || 1
    const yPadding = yRange * 0.1

    const yMin = minPct - yPadding
    const yMax = maxPct + yPadding

    // 좌표 변환 함수
    const xScale = (i: number) => padding.left + (i / (dates.length - 1)) * chartWidth
    const yScale = (pct: number) => padding.top + chartHeight - ((pct - yMin) / (yMax - yMin)) * chartHeight

    // Y축 눈금
    const yTicks = 8
    const yTickValues = Array.from({ length: yTicks + 1 }, (_, i) =>
      Math.round(yMin + (i / yTicks) * (yMax - yMin))
    )

    // X축 눈금 (월별)
    const monthLabels: { idx: number; label: string }[] = []
    let lastMonth = ''
    dates.forEach((date, i) => {
      const month = date.substring(0, 7)
      if (month !== lastMonth) {
        monthLabels.push({ idx: i, label: month.substring(5) + '월' })
        lastMonth = month
      }
    })

    return (
      <svg width={width} height={height} className="w-full">
        {/* 배경 */}
        <rect x={padding.left} y={padding.top} width={chartWidth} height={chartHeight} fill="white" />

        {/* 가로 그리드 */}
        {yTickValues.map((val, i) => (
          <g key={`y-${i}`}>
            <line
              x1={padding.left}
              y1={yScale(val)}
              x2={padding.left + chartWidth}
              y2={yScale(val)}
              stroke={val === 0 ? '#374151' : '#e5e7eb'}
              strokeWidth={val === 0 ? 1.5 : 1}
            />
            <text
              x={padding.left - 8}
              y={yScale(val)}
              textAnchor="end"
              dominantBaseline="middle"
              fontSize="11"
              fill="#6b7280"
            >
              {val > 0 ? '+' : ''}{val}%
            </text>
          </g>
        ))}

        {/* 세로 그리드 (월별) */}
        {monthLabels.map(({ idx, label }) => (
          <g key={`x-${idx}`}>
            <line
              x1={xScale(idx)}
              y1={padding.top}
              x2={xScale(idx)}
              y2={padding.top + chartHeight}
              stroke="#e5e7eb"
              strokeWidth="1"
            />
            <text
              x={xScale(idx)}
              y={padding.top + chartHeight + 20}
              textAnchor="middle"
              fontSize="11"
              fill="#6b7280"
            >
              {label}
            </text>
          </g>
        ))}

        {/* 차트 라인 */}
        {series.map(s => {
          const points = s.points.map((pct, i) => `${xScale(i)},${yScale(pct)}`).join(' ')
          const isHighlighted = hoveredTheme === null || hoveredTheme === s.theme

          return (
            <polyline
              key={s.theme}
              fill="none"
              stroke={s.color}
              strokeWidth={hoveredTheme === s.theme ? 3 : 1.5}
              strokeOpacity={isHighlighted ? 1 : 0.2}
              points={points}
              style={{ transition: 'stroke-opacity 0.2s, stroke-width 0.2s' }}
            />
          )
        })}

        {/* Y축 라벨 */}
        <text
          x={15}
          y={padding.top + chartHeight / 2}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="12"
          fill="#6b7280"
          transform={`rotate(-90, 15, ${padding.top + chartHeight / 2})`}
        >
          수익률 (%)
        </text>

        {/* 범례 */}
        {series.map((s, i) => {
          const y = padding.top + i * 20
          return (
            <g
              key={s.theme}
              onMouseEnter={() => setHoveredTheme(s.theme)}
              onMouseLeave={() => setHoveredTheme(null)}
              style={{ cursor: 'pointer' }}
            >
              <line
                x1={padding.left + chartWidth + 10}
                y1={y + 8}
                x2={padding.left + chartWidth + 25}
                y2={y + 8}
                stroke={s.color}
                strokeWidth="2"
              />
              <text
                x={padding.left + chartWidth + 30}
                y={y + 8}
                dominantBaseline="middle"
                fontSize="11"
                fill={hoveredTheme === s.theme ? '#000' : '#6b7280'}
                fontWeight={hoveredTheme === s.theme ? 'bold' : 'normal'}
              >
                {s.theme} ({s.latestPct > 0 ? '+' : ''}{s.latestPct.toFixed(0)}%)
              </text>
            </g>
          )
        })}
      </svg>
    )
  }

  const toggleTheme = (theme: string) => {
    setSelectedThemes(prev => {
      const next = new Set(prev)
      if (next.has(theme)) {
        next.delete(theme)
      } else {
        next.add(theme)
      }
      return next
    })
  }

  const selectAll = () => setSelectedThemes(new Set(data.map(e => e.theme)))
  const selectNone = () => setSelectedThemes(new Set())
  const selectTop5 = () => setSelectedThemes(new Set(data.slice(0, 5).map(e => e.theme)))
  const selectBottom5 = () => setSelectedThemes(new Set(data.slice(-5).map(e => e.theme)))

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-t-bg-card rounded-lg shadow-xl max-w-6xl w-full max-h-[95vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 py-4 border-b bg-gray-50 dark:bg-t-bg-elevated">
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-t-text-primary">전체 ETF 수익률 비교</h2>
              <p className="text-sm text-gray-500 dark:text-t-text-muted">{PERIOD_CONFIG[period].label} 현재 (시작일 기준 수익률)</p>
            </div>
            <div className="flex gap-1">
              {(Object.keys(PERIOD_CONFIG) as PeriodType[]).map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                    period === p
                      ? 'bg-indigo-600 text-white'
                      : 'bg-gray-200 dark:bg-t-border text-gray-600 dark:text-t-text-muted hover:bg-gray-300 dark:hover:bg-t-border-hover'
                  }`}
                >
                  {p}년
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-t-text-muted dark:text-t-text-muted text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* 본문 */}
        <div className="p-6 overflow-y-auto max-h-[calc(95vh-80px)]">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 rounded-lg p-4 text-red-700">
              {error}
            </div>
          )}

          {!loading && !error && (
            <>
              {/* 테마 선택 */}
              <div className="mb-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm font-medium text-gray-700 dark:text-t-text-secondary">테마 선택:</span>
                  <button onClick={selectAll} className="px-2 py-1 text-xs bg-gray-100 dark:bg-t-bg-elevated rounded hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border">전체</button>
                  <button onClick={selectNone} className="px-2 py-1 text-xs bg-gray-100 dark:bg-t-bg-elevated rounded hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border">해제</button>
                  <button onClick={selectTop5} className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200">상위 5</button>
                  <button onClick={selectBottom5} className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200">하위 5</button>
                </div>
                <div className="flex flex-wrap gap-1">
                  {data.map((etf, idx) => (
                    <button
                      key={etf.theme}
                      onClick={() => toggleTheme(etf.theme)}
                      className={`px-2 py-1 text-xs rounded-full border transition-colors ${
                        selectedThemes.has(etf.theme)
                          ? 'border-transparent text-white'
                          : 'border-gray-300 dark:border-t-border text-gray-500 dark:text-t-text-muted bg-white dark:bg-t-bg-card'
                      }`}
                      style={{
                        backgroundColor: selectedThemes.has(etf.theme)
                          ? COLORS[idx % COLORS.length]
                          : undefined,
                      }}
                    >
                      {etf.theme} ({etf.latest_pct > 0 ? '+' : ''}{etf.latest_pct.toFixed(0)}%)
                    </button>
                  ))}
                </div>
              </div>

              {/* 차트 */}
              <div className="border rounded-lg bg-gray-50 dark:bg-t-bg-elevated p-4 overflow-x-auto">
                {renderChart()}
              </div>

              {/* 순위 테이블 */}
              <div className="mt-4 grid grid-cols-2 gap-4">
                <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4">
                  <h3 className="font-semibold text-red-800 mb-2">상승 TOP 5</h3>
                  <div className="space-y-1">
                    {data.slice(0, 5).map((etf, idx) => (
                      <div key={etf.theme} className="flex justify-between text-sm">
                        <span>{idx + 1}. {etf.theme}</span>
                        <span className="font-medium text-red-600">+{etf.latest_pct.toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
                  <h3 className="font-semibold text-blue-800 mb-2">하락 TOP 5</h3>
                  <div className="space-y-1">
                    {data.slice(-5).reverse().map((etf, idx) => (
                      <div key={etf.theme} className="flex justify-between text-sm">
                        <span>{idx + 1}. {etf.theme}</span>
                        <span className={`font-medium ${etf.latest_pct >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                          {etf.latest_pct > 0 ? '+' : ''}{etf.latest_pct.toFixed(1)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
