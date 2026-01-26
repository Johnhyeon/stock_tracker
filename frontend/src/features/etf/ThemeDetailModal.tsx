import { useState, useEffect } from 'react'
import { etfRotationApi, type ThemeDetailResponse, type EtfChartCandle, type EtfHolding } from '../../services/api'

interface ThemeDetailModalProps {
  themeName: string | null
  onClose: () => void
}

// 금액 포맷
function formatAmount(value: number | null): string {
  if (value === null) return '-'
  if (value >= 1e12) return `${(value / 1e12).toFixed(1)}조`
  if (value >= 1e8) return `${(value / 1e8).toFixed(0)}억`
  if (value >= 1e4) return `${(value / 1e4).toFixed(0)}만`
  return value.toLocaleString()
}

// 등락률 색상
function getChangeColor(value: number | null): string {
  if (value === null) return 'text-gray-500'
  if (value > 0) return 'text-red-600'
  if (value < 0) return 'text-blue-600'
  return 'text-gray-500'
}

// 미니 차트 컴포넌트
function MiniChart({ data }: { data: EtfChartCandle[] }) {
  if (data.length < 2) return <div className="text-gray-400 text-sm">데이터 부족</div>

  const prices = data.map(d => d.close)
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const range = max - min || 1

  const width = 600
  const height = 160
  const padding = { top: 20, right: 50, bottom: 30, left: 10 }
  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const points = prices.map((price, i) => {
    const x = padding.left + (i / (prices.length - 1)) * chartWidth
    const y = padding.top + chartHeight - ((price - min) / range) * chartHeight
    return `${x},${y}`
  }).join(' ')

  const isUp = prices[prices.length - 1] >= prices[0]
  const startPrice = prices[0]
  const endPrice = prices[prices.length - 1]
  const changePercent = ((endPrice - startPrice) / startPrice * 100).toFixed(1)

  // Y축 눈금 계산 (가격)
  const yTicks = 4
  const yTickValues = Array.from({ length: yTicks + 1 }, (_, i) =>
    Math.round(min + (i / yTicks) * range)
  )

  // X축 날짜 라벨 (5개)
  const xLabelCount = 5
  const xLabels = Array.from({ length: xLabelCount }, (_, i) => {
    const idx = Math.floor((i / (xLabelCount - 1)) * (data.length - 1))
    return { idx, label: data[idx]?.trade_date?.substring(5) || '' }
  })

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-40" preserveAspectRatio="xMidYMid meet">
      {/* 배경 */}
      <rect x={padding.left} y={padding.top} width={chartWidth} height={chartHeight} fill="#fafafa" rx="2" />

      {/* 가로 그리드 + Y축 라벨 */}
      {yTickValues.map((val, i) => {
        const y = padding.top + chartHeight - (i / yTicks) * chartHeight
        return (
          <g key={`y-${i}`}>
            <line
              x1={padding.left}
              y1={y}
              x2={padding.left + chartWidth}
              y2={y}
              stroke="#e0e0e0"
              strokeWidth="1"
              strokeDasharray="4,2"
            />
            <text
              x={padding.left + chartWidth + 5}
              y={y}
              dominantBaseline="middle"
              fontSize="10"
              fill="#9ca3af"
            >
              {(val / 1000).toFixed(0)}k
            </text>
          </g>
        )
      })}

      {/* 세로 그리드 + X축 라벨 */}
      {xLabels.map(({ idx, label }) => {
        const x = padding.left + (idx / (prices.length - 1)) * chartWidth
        return (
          <g key={`x-${idx}`}>
            <line
              x1={x}
              y1={padding.top}
              x2={x}
              y2={padding.top + chartHeight}
              stroke="#e0e0e0"
              strokeWidth="1"
              strokeDasharray="4,2"
            />
            <text
              x={x}
              y={height - 10}
              textAnchor="middle"
              fontSize="10"
              fill="#9ca3af"
            >
              {label}
            </text>
          </g>
        )
      })}

      {/* 차트 라인 */}
      <polyline
        fill="none"
        stroke={isUp ? '#ef4444' : '#3b82f6'}
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />

      {/* 시작/끝 포인트 */}
      <circle
        cx={padding.left}
        cy={padding.top + chartHeight - ((startPrice - min) / range) * chartHeight}
        r="4"
        fill="#6b7280"
      />
      <circle
        cx={padding.left + chartWidth}
        cy={padding.top + chartHeight - ((endPrice - min) / range) * chartHeight}
        r="5"
        fill={isUp ? '#ef4444' : '#3b82f6'}
        stroke="white"
        strokeWidth="2"
      />

      {/* 수익률 라벨 */}
      <text
        x={padding.left + chartWidth}
        y={padding.top - 5}
        textAnchor="end"
        fontSize="13"
        fontWeight="bold"
        fill={isUp ? '#ef4444' : '#3b82f6'}
      >
        {isUp ? '+' : ''}{changePercent}%
      </text>
    </svg>
  )
}

export default function ThemeDetailModal({ themeName, onClose }: ThemeDetailModalProps) {
  const [data, setData] = useState<ThemeDetailResponse | null>(null)
  const [holdings, setHoldings] = useState<EtfHolding[]>([])
  const [loading, setLoading] = useState(true)
  const [holdingsLoading, setHoldingsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showHoldings, setShowHoldings] = useState(false)

  // ESC 키로 닫기
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    if (themeName) {
      window.addEventListener('keydown', handleEsc)
      return () => window.removeEventListener('keydown', handleEsc)
    }
  }, [themeName, onClose])

  useEffect(() => {
    if (!themeName) return

    const fetchData = async () => {
      setLoading(true)
      setError(null)
      setHoldings([])
      setShowHoldings(false)
      try {
        const result = await etfRotationApi.getThemeDetail(themeName)
        setData(result)
      } catch (err) {
        setError('데이터를 불러오는데 실패했습니다')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [themeName])

  const loadHoldings = async () => {
    if (!data || holdingsLoading) return

    setHoldingsLoading(true)
    try {
      const result = await etfRotationApi.getEtfHoldings(data.etf.code, 15)
      setHoldings(result.holdings)
      setShowHoldings(true)
    } catch (err) {
      console.error('구성 종목 로딩 실패:', err)
    } finally {
      setHoldingsLoading(false)
    }
  }

  if (!themeName) return null

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 py-4 border-b bg-gray-50">
          <div>
            <h2 className="text-xl font-bold text-gray-900">{themeName}</h2>
            {data && (
              <p className="text-sm text-gray-500">
                {data.etf.name} ({data.etf.code})
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* 본문 */}
        <div className="overflow-y-auto max-h-[calc(90vh-80px)] p-6 space-y-6">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
              {error}
            </div>
          )}

          {data && (
            <>
              {/* ETF 성과 요약 */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-semibold text-gray-700 mb-3">ETF 성과 요약</h3>
                <div className="grid grid-cols-4 gap-3">
                  {(['1d', '5d', '20d', '60d'] as const).map((period) => {
                    const value = data.etf.changes[period]
                    return (
                      <div key={period} className="bg-white rounded-lg p-3 text-center border">
                        <div className="text-xs text-gray-500 mb-1">
                          {period === '1d' ? '1일' : period === '5d' ? '5일' : period === '20d' ? '20일' : '60일'}
                        </div>
                        <div className={`text-lg font-bold ${getChangeColor(value)}`}>
                          {value !== null ? `${value > 0 ? '+' : ''}${value.toFixed(1)}%` : '-'}
                        </div>
                      </div>
                    )
                  })}
                </div>

                {/* 거래대금 */}
                <div className="mt-4 flex items-center gap-4 text-sm">
                  <span className="text-gray-600">거래대금:</span>
                  <span className="font-medium">{formatAmount(data.etf.trading_value)}</span>
                  {data.etf.trading_value_ratio && (
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      data.etf.trading_value_ratio >= 1.5
                        ? 'bg-orange-100 text-orange-700'
                        : data.etf.trading_value_ratio <= 0.5
                          ? 'bg-blue-100 text-blue-700'
                          : 'bg-gray-100 text-gray-700'
                    }`}>
                      평균 대비 {data.etf.trading_value_ratio.toFixed(1)}배
                    </span>
                  )}
                </div>
              </div>

              {/* 미니 차트 */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-semibold text-gray-700 mb-3">60일 차트</h3>
                <MiniChart data={data.chart} />
                <div className="flex justify-between text-xs text-gray-400 mt-1">
                  <span>{data.chart[0]?.trade_date}</span>
                  <span>{data.chart[data.chart.length - 1]?.trade_date}</span>
                </div>
              </div>

              {/* 구성 종목 */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-gray-700">구성 종목 TOP 15</h3>
                  {!showHoldings && (
                    <button
                      onClick={loadHoldings}
                      disabled={holdingsLoading}
                      className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded-md hover:bg-blue-200 disabled:opacity-50"
                    >
                      {holdingsLoading ? '로딩...' : '종목 보기'}
                    </button>
                  )}
                </div>

                {showHoldings && holdings.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead className="bg-gray-100">
                        <tr>
                          <th className="px-2 py-1.5 text-left font-medium text-gray-600">종목</th>
                          <th className="px-2 py-1.5 text-right font-medium text-gray-600">5일</th>
                          <th className="px-2 py-1.5 text-right font-medium text-gray-600">외국인</th>
                          <th className="px-2 py-1.5 text-right font-medium text-gray-600">기관</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {holdings.map((h, idx) => (
                          <tr key={h.stock_code} className={h.in_my_ideas ? 'bg-yellow-50' : ''}>
                            <td className="px-2 py-1.5">
                              <div className="flex items-center gap-1">
                                <span className="text-gray-400 text-xs w-4">{idx + 1}</span>
                                <span className="font-medium">{h.stock_name}</span>
                                {h.in_my_ideas && <span className="text-yellow-500">★</span>}
                              </div>
                              <span className="text-xs text-gray-400">{h.stock_code}</span>
                            </td>
                            <td className={`px-2 py-1.5 text-right font-medium ${getChangeColor(h.change_5d)}`}>
                              {h.change_5d !== null ? `${h.change_5d > 0 ? '+' : ''}${h.change_5d.toFixed(1)}%` : '-'}
                            </td>
                            <td className={`px-2 py-1.5 text-right ${h.foreign_net && h.foreign_net > 0 ? 'text-red-600' : h.foreign_net && h.foreign_net < 0 ? 'text-blue-600' : 'text-gray-500'}`}>
                              {h.foreign_net !== null ? `${h.foreign_net > 0 ? '+' : ''}${(h.foreign_net / 100000000).toFixed(0)}억` : '-'}
                            </td>
                            <td className={`px-2 py-1.5 text-right ${h.inst_net && h.inst_net > 0 ? 'text-red-600' : h.inst_net && h.inst_net < 0 ? 'text-blue-600' : 'text-gray-500'}`}>
                              {h.inst_net !== null ? `${h.inst_net > 0 ? '+' : ''}${(h.inst_net / 100000000).toFixed(0)}억` : '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="text-xs text-gray-400 mt-2">★ = 내 아이디어에 있는 종목 | 수급은 최근 7일 합계</p>
                  </div>
                )}

                {showHoldings && holdings.length === 0 && (
                  <div className="text-center text-gray-400 py-4">구성 종목 정보가 없습니다</div>
                )}
              </div>

              {/* 연관 테마 */}
              {data.related_themes.length > 0 && (
                <div>
                  <h3 className="font-semibold text-gray-700 mb-3">연관 테마</h3>
                  <div className="flex flex-wrap gap-2">
                    {data.related_themes.map((theme) => (
                      <div
                        key={theme.name}
                        className="px-3 py-2 bg-gray-100 rounded-lg text-sm"
                      >
                        <span className="font-medium">{theme.name}</span>
                        {theme.change_5d !== null && (
                          <span className={`ml-2 ${getChangeColor(theme.change_5d)}`}>
                            {theme.change_5d > 0 ? '+' : ''}{theme.change_5d.toFixed(1)}%
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 테마 내 모든 ETF */}
              {data.all_etfs.length > 1 && (
                <div>
                  <h3 className="font-semibold text-gray-700 mb-3">테마 내 ETF</h3>
                  <div className="space-y-2">
                    {data.all_etfs.map((etf) => (
                      <div
                        key={etf.etf_code}
                        className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg text-sm"
                      >
                        <div>
                          <span className="font-medium">{etf.etf_name}</span>
                          <span className="text-gray-400 ml-1">({etf.etf_code})</span>
                          {etf.is_primary && (
                            <span className="ml-2 px-1.5 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">대표</span>
                          )}
                        </div>
                        <div className={`font-medium ${getChangeColor(etf.change_5d)}`}>
                          {etf.change_5d !== null ? `${etf.change_5d > 0 ? '+' : ''}${etf.change_5d.toFixed(1)}%` : '-'}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 뉴스 */}
              {data.news.length > 0 && (
                <div>
                  <h3 className="font-semibold text-gray-700 mb-3">최근 뉴스</h3>
                  <div className="space-y-2">
                    {data.news.slice(0, 5).map((news, idx) => (
                      <a
                        key={idx}
                        href={news.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block px-3 py-2 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                      >
                        <div className="flex items-start gap-2">
                          {news.is_quality && (
                            <span className="text-yellow-500 flex-shrink-0">★</span>
                          )}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-gray-900 line-clamp-2">{news.title}</p>
                            <p className="text-xs text-gray-400 mt-1">
                              {news.source && <span>{news.source} · </span>}
                              {news.published_at && new Date(news.published_at).toLocaleDateString('ko-KR')}
                            </p>
                          </div>
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {data.news.length === 0 && data.related_themes.length === 0 && (
                <div className="text-center text-gray-400 py-4">
                  추가 정보가 없습니다
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
