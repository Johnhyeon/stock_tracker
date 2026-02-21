import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader } from '../../components/ui/Card'
import { financialApi } from '../../services/api'
import type { FinancialSummary, AnnualFinancialData, FinancialRatios } from '../../types/financial'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Legend,
} from 'recharts'

interface FinancialTabProps {
  stockCode: string
}

function formatBillion(value: number | null | undefined): string {
  if (value == null) return '-'
  const abs = Math.abs(value)
  if (abs >= 1_0000_0000_0000) return `${(value / 1_0000_0000_0000).toFixed(1)}조`
  if (abs >= 1_0000_0000) return `${(value / 1_0000_0000).toFixed(0)}억`
  if (abs >= 10000) return `${(value / 10000).toFixed(0)}만`
  return value.toLocaleString()
}

function formatPct(value: number | null | undefined, suffix = '%'): string {
  if (value == null) return '-'
  return `${value.toFixed(1)}${suffix}`
}

function ratioColor(value: number | null | undefined, thresholds?: { good: number; bad: number; invert?: boolean }): string {
  if (value == null) return 'text-gray-500 dark:text-t-text-muted'
  const t = thresholds || { good: 10, bad: 0 }
  if (t.invert) {
    return value <= t.good ? 'text-green-600 dark:text-green-400' : value >= t.bad ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-t-text-primary'
  }
  return value >= t.good ? 'text-green-600 dark:text-green-400' : value <= t.bad ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-t-text-primary'
}

/** 전기 대비 증감률 계산 */
function calcChange(current: number | null | undefined, prev: number | null | undefined): number | null {
  if (current == null || prev == null || prev === 0) return null
  return ((current - prev) / Math.abs(prev)) * 100
}

/** 증감률 배지 */
function ChangeBadge({ change }: { change: number | null }) {
  if (change == null) return null
  const isPositive = change > 0
  const isZero = Math.abs(change) < 0.05
  const color = isZero
    ? 'text-gray-400'
    : isPositive
      ? 'text-red-500 dark:text-red-400'
      : 'text-blue-500 dark:text-blue-400'
  const arrow = isZero ? '' : isPositive ? '+' : ''
  return (
    <span className={`text-[10px] ml-1 ${color}`}>
      {arrow}{change.toFixed(1)}%
    </span>
  )
}

export default function FinancialTab({ stockCode }: FinancialTabProps) {
  const [summary, setSummary] = useState<FinancialSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [collecting, setCollecting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    financialApi.getSummary(stockCode)
      .then(setSummary)
      .catch(() => setError('재무 데이터 로드 실패'))
      .finally(() => setLoading(false))
  }, [stockCode])

  const handleCollect = async () => {
    setCollecting(true)
    try {
      const result = await financialApi.collect(stockCode)
      if (result.collected_count > 0) {
        const fresh = await financialApi.getSummary(stockCode)
        setSummary(fresh)
      } else {
        setError(result.message || 'DART 고유번호를 먼저 동기화해 주세요')
      }
    } catch {
      setError('수집 실패. DART 고유번호가 동기화되어 있는지 확인하세요.')
    } finally {
      setCollecting(false)
    }
  }

  if (loading) {
    return <div className="text-center py-10 text-gray-500 dark:text-t-text-muted">로딩 중...</div>
  }

  if (error && !summary?.has_data) {
    return (
      <div className="text-center py-10">
        <p className="text-gray-500 dark:text-t-text-muted mb-4">{error}</p>
        <button
          onClick={handleCollect}
          disabled={collecting}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          {collecting ? '수집 중...' : '재무제표 수집'}
        </button>
      </div>
    )
  }

  if (!summary?.has_data) {
    return (
      <div className="text-center py-10">
        <p className="text-gray-500 dark:text-t-text-muted mb-4">재무제표 데이터가 없습니다.</p>
        <button
          onClick={handleCollect}
          disabled={collecting}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          {collecting ? '수집 중...' : '재무제표 수집'}
        </button>
      </div>
    )
  }

  const { annual_data, quarterly_data, latest_ratios } = summary

  return (
    <div className="space-y-6">
      {/* 핵심 비율 카드 */}
      {latest_ratios && <RatioCards ratios={latest_ratios} />}

      {/* 연간 실적 */}
      {annual_data.length > 0 && (
        <Card>
          <CardHeader>
            <h2 className="font-semibold text-gray-900 dark:text-t-text-primary">연간 실적</h2>
          </CardHeader>
          <CardContent>
            <FinancialTable data={annual_data} />
          </CardContent>
        </Card>
      )}

      {/* 분기별 실적 */}
      {quarterly_data.length > 0 && (
        <Card>
          <CardHeader>
            <h2 className="font-semibold text-gray-900 dark:text-t-text-primary">분기별 실적</h2>
          </CardHeader>
          <CardContent>
            <FinancialTable data={quarterly_data} />
          </CardContent>
        </Card>
      )}

      {/* 실적 추이 차트 (연간 + 분기 나란히) */}
      {(annual_data.length >= 2 || quarterly_data.length >= 2) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {annual_data.length >= 2 && (
            <Card>
              <CardHeader>
                <h2 className="font-semibold text-gray-900 dark:text-t-text-primary text-sm">연간 실적 추이</h2>
              </CardHeader>
              <CardContent>
                <GroupedBarChart data={[...annual_data].reverse()} />
              </CardContent>
            </Card>
          )}
          {quarterly_data.length >= 2 && (
            <Card>
              <CardHeader>
                <h2 className="font-semibold text-gray-900 dark:text-t-text-primary text-sm">분기별 실적 추이</h2>
              </CardHeader>
              <CardContent>
                <GroupedBarChart data={[...quarterly_data].reverse()} />
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* 수집 버튼 */}
      <div className="text-center">
        <button
          onClick={handleCollect}
          disabled={collecting}
          className="text-sm text-gray-500 dark:text-t-text-muted hover:text-primary-600 dark:hover:text-primary-400 disabled:opacity-50"
        >
          {collecting ? '수집 중...' : '재무 데이터 갱신'}
        </button>
      </div>
    </div>
  )
}

function RatioCards({ ratios }: { ratios: FinancialRatios }) {
  const items = [
    { label: 'PER', value: ratios.per, fmt: (v: number) => `${v.toFixed(1)}x`, color: ratioColor(ratios.per, { good: 0, bad: 50, invert: true }) },
    { label: 'PBR', value: ratios.pbr, fmt: (v: number) => `${v.toFixed(2)}x`, color: ratioColor(ratios.pbr, { good: 0, bad: 5, invert: true }) },
    { label: 'ROE', value: ratios.roe, fmt: (v: number) => formatPct(v), color: ratioColor(ratios.roe, { good: 10, bad: 0 }) },
    { label: 'ROA', value: ratios.roa, fmt: (v: number) => formatPct(v), color: ratioColor(ratios.roa, { good: 5, bad: 0 }) },
    { label: '영업이익률', value: ratios.operating_margin, fmt: (v: number) => formatPct(v), color: ratioColor(ratios.operating_margin, { good: 10, bad: 0 }) },
    { label: '부채비율', value: ratios.debt_ratio, fmt: (v: number) => formatPct(v), color: ratioColor(ratios.debt_ratio, { good: 100, bad: 200, invert: true }) },
    { label: '유동비율', value: ratios.current_ratio, fmt: (v: number) => formatPct(v), color: ratioColor(ratios.current_ratio, { good: 150, bad: 100 }) },
    { label: '매출성장률', value: ratios.revenue_growth, fmt: (v: number) => formatPct(v), color: ratioColor(ratios.revenue_growth, { good: 10, bad: 0 }) },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {items.map((item) => (
        <div key={item.label} className="p-3 bg-white dark:bg-t-bg-card rounded-lg border border-gray-200 dark:border-t-border">
          <div className="text-xs text-gray-500 dark:text-t-text-muted">{item.label}</div>
          <div className={`text-lg font-bold mt-0.5 ${item.value != null ? item.color : 'text-gray-400'}`}>
            {item.value != null ? item.fmt(item.value) : '-'}
          </div>
        </div>
      ))}
    </div>
  )
}

function FinancialTable({ data }: { data: AnnualFinancialData[] }) {
  const rows = [
    { label: '매출액', key: 'revenue' as const },
    { label: '영업이익', key: 'operating_income' as const },
    { label: '당기순이익', key: 'net_income' as const },
    { label: '자산총계', key: 'total_assets' as const },
    { label: '부채총계', key: 'total_liabilities' as const },
    { label: '자본총계', key: 'total_equity' as const },
  ]

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b dark:border-t-border">
            <th className="text-left py-2 px-2 font-medium text-gray-600 dark:text-t-text-muted">항목</th>
            {data.map((d) => (
              <th key={`${d.bsns_year}-${d.reprt_code}`} className="text-right py-2 px-2 font-medium text-gray-600 dark:text-t-text-muted">
                {d.bsns_year} {d.reprt_name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-b dark:border-t-border last:border-0 hover:bg-gray-50 dark:hover:bg-t-bg-card/50">
              <td className="py-2 px-2 font-medium text-gray-900 dark:text-t-text-primary whitespace-nowrap">{row.label}</td>
              {data.map((d, idx) => {
                const val = d[row.key]
                // 다음 항목이 이전 기간 (data는 최신→과거 순)
                const prevVal = idx < data.length - 1 ? data[idx + 1][row.key] : null
                const change = calcChange(val, prevVal)
                return (
                  <td
                    key={`${d.bsns_year}-${d.reprt_code}-${row.key}`}
                    className={`py-2 px-2 text-right ${
                      val != null && val < 0
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-gray-900 dark:text-t-text-primary'
                    }`}
                  >
                    <span>{formatBillion(val)}</span>
                    <ChangeBadge change={change} />
                  </td>
                )
              })}
            </tr>
          ))}
          {/* 비율 행 */}
          {data.some((d) => d.ratios?.roe != null) && (
            <>
              <tr className="border-b dark:border-t-border">
                <td className="py-2 px-2 font-medium text-gray-500 dark:text-t-text-muted">ROE</td>
                {data.map((d) => (
                  <td key={`${d.bsns_year}-roe`} className={`py-2 px-2 text-right ${ratioColor(d.ratios?.roe, { good: 10, bad: 0 })}`}>
                    {formatPct(d.ratios?.roe)}
                  </td>
                ))}
              </tr>
              <tr className="border-b dark:border-t-border last:border-0">
                <td className="py-2 px-2 font-medium text-gray-500 dark:text-t-text-muted">영업이익률</td>
                {data.map((d) => (
                  <td key={`${d.bsns_year}-opm`} className={`py-2 px-2 text-right ${ratioColor(d.ratios?.operating_margin, { good: 10, bad: 0 })}`}>
                    {formatPct(d.ratios?.operating_margin)}
                  </td>
                ))}
              </tr>
            </>
          )}
        </tbody>
      </table>
    </div>
  )
}

/** 매출/영업이익/순이익 그룹형 막대 차트 */
function GroupedBarChart({ data }: { data: AnnualFinancialData[] }) {
  // 단위 결정 (가장 큰 값 기준)
  const allValues = data.flatMap((d) => [d.revenue ?? 0, d.operating_income ?? 0, d.net_income ?? 0])
  const maxAbs = Math.max(...allValues.map(Math.abs), 1)
  const hasNegative = allValues.some((v) => v < 0)
  const divider = maxAbs >= 1_0000_0000_0000 ? 1_0000_0000_0000
    : maxAbs >= 1_0000_0000 ? 1_0000_0000
    : 1
  const unit = divider === 1_0000_0000_0000 ? '조' : divider === 1_0000_0000 ? '억' : ''

  const chartData = data.map((d) => ({
    name: d.reprt_code === '11011'
      ? d.bsns_year
      : `${d.bsns_year.slice(2)}${d.reprt_name}`,
    매출액: (d.revenue ?? 0) / divider,
    영업이익: (d.operating_income ?? 0) / divider,
    순이익: (d.net_income ?? 0) / divider,
  }))

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const tooltipFormatter = (value: any, name: any) => [
    `${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}${unit}`,
    name,
  ]

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" opacity={0.2} vertical={false} />
        <XAxis dataKey="name" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis
          tick={{ fontSize: 10 }}
          tickFormatter={(v: number) => `${v.toLocaleString()}${unit}`}
          width={55}
          axisLine={false}
          tickLine={false}
          domain={hasNegative ? ['auto', 'auto'] : [0, 'auto']}
        />
        <Tooltip
          formatter={tooltipFormatter}
          contentStyle={{
            backgroundColor: 'var(--tooltip-bg, #fff)',
            border: '1px solid var(--tooltip-border, #e5e7eb)',
            borderRadius: '8px',
            fontSize: '12px',
          }}
        />
        <Legend wrapperStyle={{ fontSize: '11px' }} />
        {hasNegative && <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="2 2" />}
        <Bar dataKey="매출액" fill="#3b82f6" radius={[3, 3, 0, 0]} fillOpacity={0.85} />
        <Bar dataKey="영업이익" fill="#22c55e" radius={[3, 3, 0, 0]} fillOpacity={0.85} />
        <Bar dataKey="순이익" fill="#f59e0b" radius={[3, 3, 0, 0]} fillOpacity={0.85} />
      </BarChart>
    </ResponsiveContainer>
  )
}
