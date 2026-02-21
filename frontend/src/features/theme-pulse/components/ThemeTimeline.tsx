import { useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts'
import type { TimelineResponse } from '../../../types/theme_pulse'

interface Props {
  data: TimelineResponse | null
}

const COLORS = [
  '#ef4444', '#f97316', '#eab308', '#22c55e',
  '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899',
]

export default function ThemeTimeline({ data }: Props) {
  const [hiddenThemes, setHiddenThemes] = useState<Set<string>>(new Set())

  const chartData = useMemo(() => {
    if (!data) return []
    return data.dates.map((date) => {
      const point: Record<string, string | number> = { date: date.slice(5) } // MM-DD
      for (const theme of data.themes) {
        const dp = theme.data.find(d => d.date === date)
        point[theme.name] = dp?.count ?? 0
      }
      return point
    })
  }, [data])

  const toggleTheme = (themeName: string) => {
    setHiddenThemes(prev => {
      const next = new Set(prev)
      if (next.has(themeName)) {
        next.delete(themeName)
      } else {
        next.add(themeName)
      }
      return next
    })
  }

  if (!data || data.themes.length === 0) {
    return <div className="text-center text-gray-400 py-8">타임라인 데이터가 없습니다.</div>
  }

  return (
    <div>
      <div className="h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
            <XAxis dataKey="date" fontSize={11} />
            <YAxis fontSize={11} />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--tooltip-bg, #fff)',
                border: '1px solid var(--tooltip-border, #e5e7eb)',
                borderRadius: '8px',
                fontSize: '12px',
              }}
            />
            <Legend onClick={(e) => toggleTheme(e.value as string)} />
            {data.themes.map((theme, idx) => (
              <Line
                key={theme.name}
                type="monotone"
                dataKey={theme.name}
                stroke={COLORS[idx % COLORS.length]}
                strokeWidth={2}
                dot={{ r: 2 }}
                hide={hiddenThemes.has(theme.name)}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="text-xs text-gray-400 dark:text-t-text-muted mt-2 text-center">
        범례를 클릭하여 토글할 수 있습니다
      </div>
    </div>
  )
}
