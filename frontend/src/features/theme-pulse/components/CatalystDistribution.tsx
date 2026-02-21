import { useMemo } from 'react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import type { CatalystDistributionResponse } from '../../../types/theme_pulse'

interface Props {
  data: CatalystDistributionResponse | null
}

const PIE_COLORS = [
  '#ef4444', '#f97316', '#eab308', '#22c55e',
  '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899',
  '#6b7280', '#a855f7',
]

const CATALYST_LABELS: Record<string, string> = {
  earnings: '실적',
  policy: '정책/규제',
  partnership: '제휴/협력',
  product: '신제품/기술',
  market: '시장동향',
  management: '경영/인사',
  funding: '자금/투자',
  legal: '법률/소송',
  other: '기타',
  unknown: '미분류',
}

const IMPORTANCE_COLORS: Record<string, string> = {
  critical: '#dc2626',
  high: '#f97316',
  medium: '#eab308',
  low: '#9ca3af',
  unknown: '#d1d5db',
}

export default function CatalystDistribution({ data }: Props) {
  const pieData = useMemo(() => {
    if (!data) return []
    return data.catalyst_distribution.map(item => ({
      name: CATALYST_LABELS[item.type] || item.type,
      value: item.count,
      ratio: item.ratio,
    }))
  }, [data])

  if (!data) {
    return <div className="text-center text-gray-400 py-8">재료 분포 데이터가 없습니다.</div>
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* 파이 차트 (도넛) */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-3">재료 유형</h4>
        <div className="h-[220px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={90}
                dataKey="value"
                label={({ name, payload }) => `${name} ${(payload as { ratio?: number })?.ratio ?? 0}%`}
                labelLine={false}
                fontSize={10}
              >
                {pieData.map((_entry, idx) => (
                  <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value) => [`${value}건`, '뉴스 수']}
                contentStyle={{
                  backgroundColor: 'var(--tooltip-bg, #fff)',
                  border: '1px solid var(--tooltip-border, #e5e7eb)',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 중요도 분포 바 */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-3">중요도 분포</h4>
        <div className="space-y-3 mt-4">
          {data.importance_distribution
            .sort((a, b) => {
              const order = ['critical', 'high', 'medium', 'low', 'unknown']
              return order.indexOf(a.level) - order.indexOf(b.level)
            })
            .map(item => (
              <div key={item.level}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-gray-600 dark:text-t-text-secondary capitalize">
                    {item.level === 'critical' ? '긴급' : item.level === 'high' ? '높음' : item.level === 'medium' ? '보통' : item.level === 'low' ? '낮음' : '미분류'}
                  </span>
                  <span className="text-gray-500 dark:text-t-text-muted">{item.count}건 ({item.ratio}%)</span>
                </div>
                <div className="w-full bg-gray-100 dark:bg-t-bg-elevated rounded-full h-2.5">
                  <div
                    className="h-2.5 rounded-full transition-all"
                    style={{
                      width: `${Math.max(item.ratio, 2)}%`,
                      backgroundColor: IMPORTANCE_COLORS[item.level] || '#9ca3af',
                    }}
                  />
                </div>
              </div>
            ))}
        </div>

        {/* 총 뉴스 수 */}
        <div className="mt-4 pt-3 border-t border-gray-100 dark:border-t-border text-xs text-gray-500 dark:text-t-text-muted">
          최근 {data.period_days}일간 총 {data.total_news}건 분석
        </div>
      </div>
    </div>
  )
}
