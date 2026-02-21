import { useEffect, useRef } from 'react'
import type { PortfolioTrendPoint } from '../../types/dashboard_v2'

interface PortfolioPnLChartProps {
  data: PortfolioTrendPoint[]
}

export default function PortfolioPnLChart({ data }: PortfolioPnLChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<any>(null)

  useEffect(() => {
    if (!containerRef.current || data.length < 2) return

    let cleanup: (() => void) | undefined

    import('lightweight-charts').then(({ createChart, ColorType, AreaSeries }) => {
      if (!containerRef.current) return

      // 기존 차트 정리
      if (chartRef.current) {
        chartRef.current.remove()
        chartRef.current = null
      }

      const isDark = document.documentElement.classList.contains('dark')

      const chart = createChart(containerRef.current, {
        width: containerRef.current.clientWidth,
        height: 200,
        layout: {
          background: { type: ColorType.Solid, color: 'transparent' },
          textColor: isDark ? '#9ca3af' : '#6b7280',
          fontSize: 11,
        },
        grid: {
          vertLines: { color: isDark ? '#374151' : '#f3f4f6' },
          horzLines: { color: isDark ? '#374151' : '#f3f4f6' },
        },
        rightPriceScale: {
          borderVisible: false,
        },
        timeScale: {
          borderVisible: false,
          fixLeftEdge: true,
          fixRightEdge: true,
        },
        crosshair: {
          horzLine: { visible: false },
        },
      })

      chartRef.current = chart

      // 수익률 Area Series
      const areaSeries = chart.addSeries(AreaSeries, {
        lineColor: data[data.length - 1].return_pct >= 0 ? '#ef4444' : '#3b82f6',
        topColor: data[data.length - 1].return_pct >= 0 ? 'rgba(239,68,68,0.2)' : 'rgba(59,130,246,0.2)',
        bottomColor: data[data.length - 1].return_pct >= 0 ? 'rgba(239,68,68,0.02)' : 'rgba(59,130,246,0.02)',
        lineWidth: 2,
        priceFormat: {
          type: 'custom',
          formatter: (price: number) => `${price >= 0 ? '+' : ''}${price.toFixed(1)}%`,
        },
      })

      const chartData = data.map(d => ({
        time: d.date as any,
        value: d.return_pct,
      }))

      areaSeries.setData(chartData)
      chart.timeScale().fitContent()

      const resizeObserver = new ResizeObserver(entries => {
        for (const entry of entries) {
          chart.applyOptions({ width: entry.contentRect.width })
        }
      })
      resizeObserver.observe(containerRef.current)

      cleanup = () => {
        resizeObserver.disconnect()
        chart.remove()
        chartRef.current = null
      }
    })

    return () => cleanup?.()
  }, [data])

  if (data.length === 0) {
    return null
  }

  if (data.length === 1) {
    const point = data[0]
    const profitColor = point.return_pct >= 0
      ? 'text-red-500 dark:text-red-400'
      : 'text-blue-500 dark:text-blue-400'
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">수익 현황</h3>
        <div className="flex items-center justify-center gap-6 py-4">
          <div className="text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">투자금</div>
            <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{point.total_invested.toLocaleString('ko-KR')}</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">평가금</div>
            <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{point.total_eval.toLocaleString('ko-KR')}</div>
          </div>
          <div className="text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">손익</div>
            <div className={`text-lg font-bold ${profitColor}`}>
              {point.unrealized_profit >= 0 ? '+' : ''}{point.unrealized_profit.toLocaleString('ko-KR')}
              <span className="text-sm ml-1">({point.return_pct >= 0 ? '+' : ''}{point.return_pct.toFixed(1)}%)</span>
            </div>
          </div>
        </div>
        <p className="text-xs text-gray-400 text-center">스냅샷이 쌓이면 추이 차트가 표시됩니다</p>
      </div>
    )
  }

  const latestProfit = data[data.length - 1]

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">수익 추이 (30일)</h3>
        <div className="text-xs text-gray-500 dark:text-gray-400">
          손익 {latestProfit.unrealized_profit >= 0 ? '+' : ''}{latestProfit.unrealized_profit.toLocaleString('ko-KR')}원
        </div>
      </div>
      <div ref={containerRef} />
    </div>
  )
}
