import { useMemo } from 'react'
import { Treemap, ResponsiveContainer, Tooltip } from 'recharts'
import { useNavigate } from 'react-router-dom'
import type { ThemePulseItem } from '../../../types/theme_pulse'

interface Props {
  items: ThemePulseItem[]
}

function getMomentumColor(momentum: number): string {
  if (momentum >= 50) return '#dc2626'
  if (momentum >= 20) return '#f97316'
  if (momentum >= 0) return '#fbbf24'
  if (momentum >= -20) return '#60a5fa'
  return '#2563eb'
}

interface TreemapContentProps {
  x: number
  y: number
  width: number
  height: number
  name: string
  momentum: number
}

const CustomTreemapContent = ({ x, y, width, height, name, momentum }: TreemapContentProps) => {
  const fontSize = width > 100 ? 13 : width > 60 ? 11 : 9
  const showName = width > 40 && height > 25
  const showMomentum = width > 50 && height > 40

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={getMomentumColor(momentum)}
        stroke="#fff"
        strokeWidth={2}
        rx={4}
        style={{ cursor: 'pointer' }}
      />
      {showName && (
        <text
          x={x + width / 2}
          y={y + height / 2 - (showMomentum ? 8 : 0)}
          textAnchor="middle"
          fill="#fff"
          fontSize={fontSize}
          fontWeight="bold"
        >
          {name.length > 8 && width < 100 ? name.slice(0, 6) + '…' : name}
        </text>
      )}
      {showMomentum && (
        <text
          x={x + width / 2}
          y={y + height / 2 + 10}
          textAnchor="middle"
          fill="#fff"
          fontSize={fontSize - 1}
          opacity={0.9}
        >
          {momentum > 0 ? '+' : ''}{momentum}%
        </text>
      )}
    </g>
  )
}

interface TooltipData {
  name: string
  news_count: number
  momentum: number
  high_importance_count: number
  top_stocks_str: string
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ payload: TooltipData }>
}

const CustomTooltip = ({ active, payload }: CustomTooltipProps) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-white dark:bg-t-bg-card p-3 rounded-lg shadow-lg border text-sm max-w-xs">
      <div className="font-bold text-gray-900 dark:text-t-text-primary mb-2">{d.name}</div>
      <div className="space-y-1 text-gray-600 dark:text-t-text-secondary">
        <div className="flex justify-between gap-4">
          <span>뉴스 수</span>
          <span className="font-medium">{d.news_count}건</span>
        </div>
        <div className="flex justify-between gap-4">
          <span>모멘텀</span>
          <span className={`font-medium ${d.momentum >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
            {d.momentum > 0 ? '+' : ''}{d.momentum}%
          </span>
        </div>
        <div className="flex justify-between gap-4">
          <span>주요 뉴스</span>
          <span className="font-medium">{d.high_importance_count}건</span>
        </div>
        {d.top_stocks_str && (
          <div className="pt-1 border-t text-xs text-gray-500 dark:text-t-text-muted">
            {d.top_stocks_str}
          </div>
        )}
      </div>
    </div>
  )
}

export default function ThemeTreemap({ items }: Props) {
  const navigate = useNavigate()

  const chartData = useMemo(() => {
    return items.map(item => ({
      name: item.theme_name,
      size: Math.max(item.news_count, 1),
      news_count: item.news_count,
      momentum: item.momentum,
      high_importance_count: item.high_importance_count,
      top_stocks_str: item.top_stocks.slice(0, 3).map(s => s.name).join(', '),
    }))
  }, [items])

  const handleClick = (data: { name: string }) => {
    if (data?.name) {
      navigate(`/themes/${encodeURIComponent(data.name)}`)
    }
  }

  return (
    <div>
      <div className="h-[400px]">
        <ResponsiveContainer width="100%" height="100%">
          <Treemap
            data={chartData}
            dataKey="size"
            aspectRatio={4 / 3}
            stroke="#fff"
            onClick={handleClick}
            content={<CustomTreemapContent x={0} y={0} width={0} height={0} name="" momentum={0} />}
          >
            <Tooltip content={<CustomTooltip />} />
          </Treemap>
        </ResponsiveContainer>
      </div>
      {/* 범례 */}
      <div className="flex flex-wrap gap-3 mt-3 text-xs text-gray-500 dark:text-t-text-muted">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded" style={{ background: '#dc2626' }} />
          50%+ 급상승
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded" style={{ background: '#f97316' }} />
          20%+ 상승
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded" style={{ background: '#fbbf24' }} />
          0%+ 유지
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded" style={{ background: '#60a5fa' }} />
          하락
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded" style={{ background: '#2563eb' }} />
          20%- 급하락
        </span>
      </div>
    </div>
  )
}
