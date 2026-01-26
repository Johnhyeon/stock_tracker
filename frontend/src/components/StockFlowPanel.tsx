import { useEffect, useState } from 'react'
import { themeSetupApi } from '../services/api'

interface FlowData {
  flow_date: string
  foreign_net: number
  institution_net: number
  individual_net: number
  flow_score: number
}

interface StockFlowPanelProps {
  stockCode: string
  stockName: string
  days?: number
}

export function StockFlowPanel({ stockCode, stockName, days = 20 }: StockFlowPanelProps) {
  const [flowData, setFlowData] = useState<FlowData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchFlow = async () => {
      setLoading(true)
      try {
        const result = await themeSetupApi.getStockInvestorFlow(stockCode, days)
        if (result?.history) {
          setFlowData(result.history)
        }
      } catch (err) {
        setError('수급 데이터 없음')
      } finally {
        setLoading(false)
      }
    }
    fetchFlow()
  }, [stockCode, days])

  if (loading) {
    return (
      <div className="border rounded-lg p-4 h-full flex items-center justify-center">
        <span className="text-gray-400 text-sm animate-pulse">수급 로딩 중...</span>
      </div>
    )
  }

  if (error || flowData.length === 0) {
    return (
      <div className="border rounded-lg p-4 h-full flex items-center justify-center">
        <span className="text-gray-400 text-sm">수급 데이터 없음</span>
      </div>
    )
  }

  // 날짜 기준 오름차순 정렬 (오래된 순 → 최신 순)
  const sortedData = [...flowData].sort(
    (a, b) => new Date(a.flow_date).getTime() - new Date(b.flow_date).getTime()
  )

  // 최근 5일, 10일, 20일 합계 계산
  const calcSum = (data: FlowData[], field: keyof FlowData) =>
    data.reduce((sum, d) => sum + (d[field] as number), 0)

  const recent5 = sortedData.slice(-5)
  const recent10 = sortedData.slice(-10)
  const recent20 = sortedData

  const summaries = [
    { label: '5일', data: recent5 },
    { label: '10일', data: recent10 },
    { label: '20일', data: recent20 },
  ]

  // 최근 추세 판단
  const foreignTotal = calcSum(recent5, 'foreign_net')
  const institutionTotal = calcSum(recent5, 'institution_net')
  const netTotal = foreignTotal + institutionTotal
  const trend = netTotal > 100000000 ? 'buy' : netTotal < -100000000 ? 'sell' : 'neutral'

  // 주 단위 포맷 (만주 단위로 표시)
  const formatShares = (value: number) => {
    const abs = Math.abs(value)
    const sign = value >= 0 ? '+' : '-'
    if (abs >= 10000000) {
      // 천만주 이상 → 000만
      return `${sign}${Math.round(abs / 10000).toLocaleString()}만`
    } else if (abs >= 10000) {
      // 만주 이상
      return `${sign}${Math.round(abs / 10000).toLocaleString()}만`
    } else {
      return `${sign}${abs.toLocaleString()}`
    }
  }

  return (
    <div className="border rounded-lg p-4 h-full">
      {/* 헤더 */}
      <div className="flex justify-between items-center mb-3">
        <span className="font-medium text-sm">{stockName} 수급</span>
        <span
          className={`text-xs px-2 py-0.5 rounded ${
            trend === 'buy'
              ? 'bg-red-100 text-red-700'
              : trend === 'sell'
              ? 'bg-blue-100 text-blue-700'
              : 'bg-gray-100 text-gray-600'
          }`}
        >
          {trend === 'buy' ? '매집' : trend === 'sell' ? '이탈' : '중립'}
        </span>
      </div>

      {/* 기간별 수급 테이블 */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b">
              <th className="text-left py-1 text-gray-500 font-normal">기간</th>
              <th className="text-right py-1 text-gray-500 font-normal">외국인</th>
              <th className="text-right py-1 text-gray-500 font-normal">기관</th>
              <th className="text-right py-1 text-gray-500 font-normal">합계</th>
            </tr>
          </thead>
          <tbody>
            {summaries.map(({ label, data }) => {
              const foreign = calcSum(data, 'foreign_net')
              const institution = calcSum(data, 'institution_net')
              const total = foreign + institution
              return (
                <tr key={label} className="border-b border-gray-100">
                  <td className="py-1.5 text-gray-600">{label}</td>
                  <td className={`py-1.5 text-right ${foreign >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                    {formatShares(foreign)}
                  </td>
                  <td className={`py-1.5 text-right ${institution >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                    {formatShares(institution)}
                  </td>
                  <td className={`py-1.5 text-right font-medium ${total >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                    {formatShares(total)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* 최근 일별 수급 (최근 5일) */}
      <div className="mt-3 pt-3 border-t">
        <div className="text-xs text-gray-500 mb-2">최근 5일</div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b">
                <th className="text-left py-1 text-gray-500 font-normal">날짜</th>
                <th className="text-right py-1 text-gray-500 font-normal">외국인</th>
                <th className="text-right py-1 text-gray-500 font-normal">기관</th>
                <th className="text-right py-1 text-gray-500 font-normal">합계</th>
              </tr>
            </thead>
            <tbody>
              {recent5.slice().reverse().map((d) => {
                const date = new Date(d.flow_date)
                const dateStr = `${date.getMonth() + 1}/${date.getDate()}`
                const total = d.foreign_net + d.institution_net
                return (
                  <tr key={d.flow_date} className="border-b border-gray-100">
                    <td className="py-1.5 text-gray-600">{dateStr}</td>
                    <td className={`py-1.5 text-right ${d.foreign_net >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                      {formatShares(d.foreign_net)}
                    </td>
                    <td className={`py-1.5 text-right ${d.institution_net >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                      {formatShares(d.institution_net)}
                    </td>
                    <td className={`py-1.5 text-right font-medium ${total >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                      {formatShares(total)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
