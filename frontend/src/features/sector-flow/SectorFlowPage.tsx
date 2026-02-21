import { useEffect, useState, useMemo, useRef, useCallback } from 'react'
import { sectorFlowApi, SectorFlowItem, SectorTreemapItem, SectorStockItem, RealtimeSectorFlowItem } from '../../services/api'
import { Card } from '../../components/ui/Card'
import { Treemap, ResponsiveContainer, Tooltip } from 'recharts'

type ViewMode = 'table' | 'treemap'
type DataMode = 'realtime' | 'history'
type PeriodType = '5d' | '10d' | '20d'
type SortType = 'ratio' | 'value' | 'flow'

// 금액 포맷 (억원 단위)
function formatAmount(amount: number): string {
  const sign = amount >= 0 ? '+' : ''
  const abs = Math.abs(amount)
  const billions = amount / 100000000
  if (abs >= 100000000) {
    return `${sign}${billions.toFixed(0)}억`
  } else if (abs >= 10000000) {
    return `${sign}${billions.toFixed(1)}억`
  } else if (abs >= 1000000) {
    return `${sign}${(amount / 1000000).toFixed(0)}백만`
  }
  return `${sign}${amount.toLocaleString()}`
}

// 거래대금 포맷 (조/억 단위)
function formatTradingValue(value: number): string {
  if (value >= 1000000000000) {
    return `${(value / 1000000000000).toFixed(1)}조`
  } else if (value >= 100000000) {
    return `${(value / 100000000).toFixed(0)}억`
  }
  return value.toLocaleString()
}

// 비율에 따른 색상
function getRatioColor(ratio: number): string {
  if (ratio >= 300) return 'text-red-700 font-bold'
  if (ratio >= 200) return 'text-red-600 font-semibold'
  if (ratio >= 150) return 'text-orange-600'
  if (ratio >= 100) return 'text-gray-700 dark:text-t-text-secondary'
  if (ratio >= 70) return 'text-blue-500'
  return 'text-blue-700'
}

// 비율에 따른 배경색
function getRatioBgColor(ratio: number): string {
  if (ratio >= 300) return 'bg-red-100'
  if (ratio >= 200) return 'bg-yellow-100'
  if (ratio >= 150) return 'bg-orange-50'
  if (ratio >= 100) return 'bg-gray-50 dark:bg-t-bg-elevated'
  if (ratio >= 70) return 'bg-blue-50 dark:bg-blue-900/20'
  return 'bg-blue-100'
}

// 트리맵 색상
function getTreemapColor(colorLevel: string): string {
  switch (colorLevel) {
    case 'extreme': return '#dc2626'
    case 'hot': return '#f97316'
    case 'warm': return '#fbbf24'
    case 'neutral': return '#9ca3af'
    case 'cool': return '#60a5fa'
    case 'cold': return '#2563eb'
    default: return '#9ca3af'
  }
}

function getColorLevelFromRatio(ratio: number): string {
  if (ratio >= 300) return 'extreme'
  if (ratio >= 200) return 'hot'
  if (ratio >= 150) return 'warm'
  if (ratio >= 100) return 'neutral'
  if (ratio >= 70) return 'cool'
  return 'cold'
}

// 커스텀 트리맵 콘텐츠
interface TreemapContentProps {
  x: number
  y: number
  width: number
  height: number
  name: string
  ratio: number
  color_level: string
}

const CustomTreemapContent = ({ x, y, width, height, name, ratio, color_level }: TreemapContentProps) => {
  const fontSize = width > 80 ? 12 : width > 50 ? 10 : 8
  const showText = width > 40 && height > 30

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={getTreemapColor(color_level)}
        stroke="#fff"
        strokeWidth={2}
        rx={4}
      />
      {showText && (
        <>
          <text
            x={x + width / 2}
            y={y + height / 2 - 6}
            textAnchor="middle"
            fill="#fff"
            fontSize={fontSize}
            fontWeight="bold"
          >
            {name}
          </text>
          <text
            x={x + width / 2}
            y={y + height / 2 + 10}
            textAnchor="middle"
            fill="#fff"
            fontSize={fontSize - 1}
          >
            {ratio}%
          </text>
        </>
      )}
    </g>
  )
}

// 트리맵 툴팁
interface TooltipPayload {
  name: string
  value: number
  weight: number
  ratio: number
  foreign_net: number
  institution_net: number
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ payload: TooltipPayload }>
}

const CustomTooltip = ({ active, payload }: CustomTooltipProps) => {
  if (!active || !payload || !payload.length) return null
  const data = payload[0].payload

  return (
    <div className="bg-white dark:bg-t-bg-card p-3 rounded-lg shadow-lg border text-sm">
      <div className="font-bold text-gray-900 dark:text-t-text-primary mb-2">{data.name}</div>
      <div className="space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-gray-500 dark:text-t-text-muted">거래대금:</span>
          <span className="font-medium">{formatTradingValue(data.value)}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500 dark:text-t-text-muted">비중:</span>
          <span className="font-medium">{data.weight}%</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500 dark:text-t-text-muted">평균대비:</span>
          <span className={`font-medium ${getRatioColor(data.ratio)}`}>{data.ratio}%</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500 dark:text-t-text-muted">외국인:</span>
          <span className={`font-medium ${data.foreign_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
            {formatAmount(data.foreign_net)}
          </span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500 dark:text-t-text-muted">기관:</span>
          <span className={`font-medium ${data.institution_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
            {formatAmount(data.institution_net)}
          </span>
        </div>
      </div>
    </div>
  )
}

export default function SectorFlowPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('table')
  const [dataMode, setDataMode] = useState<DataMode>('realtime')
  const [period, setPeriod] = useState<PeriodType>('5d')
  const [sortBy, setSortBy] = useState<SortType>('ratio')
  const [sectors, setSectors] = useState<SectorFlowItem[]>([])
  const [realtimeSectors, setRealtimeSectors] = useState<RealtimeSectorFlowItem[]>([])
  const [treemapData, setTreemapData] = useState<SectorTreemapItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tradeDate, setTradeDate] = useState<string | null>(null)
  const [marketStatus, setMarketStatus] = useState<'open' | 'closed' | 'error'>('closed')
  const [timeRatio, setTimeRatio] = useState<number>(0)

  // 자동 갱신
  const refreshIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 섹터 상세
  const [selectedSector, setSelectedSector] = useState<string | null>(null)
  const [sectorStocks, setSectorStocks] = useState<SectorStockItem[]>([])
  const [stocksLoading, setStocksLoading] = useState(false)

  // 실시간 데이터 fetch
  const fetchRealtimeData = useCallback(async () => {
    try {
      const result = await sectorFlowApi.getRealtime()
      setRealtimeSectors(result.sectors)
      setMarketStatus(result.market_status)
      setTimeRatio(result.time_ratio)
      setError(null)
    } catch (err) {
      console.error('실시간 데이터 로드 실패:', err)
      setError('실시간 데이터를 불러오는데 실패했습니다.')
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [period, sortBy, viewMode, dataMode])

  // 실시간 모드: 1분마다 자동 갱신
  useEffect(() => {
    if (dataMode === 'realtime' && viewMode === 'table') {
      refreshIntervalRef.current = setInterval(() => {
        fetchRealtimeData()
      }, 60000)
    }

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
        refreshIntervalRef.current = null
      }
    }
  }, [dataMode, viewMode, fetchRealtimeData])

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      if (dataMode === 'realtime' && viewMode === 'table') {
        const result = await sectorFlowApi.getRealtime()
        setRealtimeSectors(result.sectors)
        setMarketStatus(result.market_status)
        setTimeRatio(result.time_ratio)
      } else if (viewMode === 'table') {
        const result = await sectorFlowApi.getRanking(period, sortBy)
        setSectors(result.sectors)
        setTradeDate(result.trade_date)
      } else {
        const result = await sectorFlowApi.getTreemap(period)
        setTreemapData(result.data)
        setTradeDate(result.trade_date)
      }
    } catch (err) {
      console.error('섹터 수급 데이터 로드 실패:', err)
      setError('데이터를 불러오는데 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const handleSectorClick = async (sectorName: string) => {
    if (selectedSector === sectorName) {
      setSelectedSector(null)
      return
    }

    setSelectedSector(sectorName)
    setStocksLoading(true)
    try {
      const result = await sectorFlowApi.getSectorStocks(sectorName, 15)
      setSectorStocks(result.stocks)
    } catch (err) {
      console.error('섹터 종목 로드 실패:', err)
      setSectorStocks([])
    } finally {
      setStocksLoading(false)
    }
  }

  // 트리맵 데이터 변환
  const treemapChartData = useMemo(() => {
    if (dataMode === 'realtime' && viewMode === 'treemap') {
      // 실시간 데이터를 트리맵 형식으로 변환
      return realtimeSectors.map(item => ({
        name: item.sector_name,
        value: item.today_trading_value,
        size: item.today_trading_value,
        weight: item.weight,
        ratio: item.ratio_5d,
        color_level: getColorLevelFromRatio(item.ratio_5d),
        is_hot: item.is_hot,
        foreign_net: item.foreign_net,
        institution_net: item.institution_net,
        stock_count: item.stock_count,
      }))
    }
    return treemapData.map(item => ({
      ...item,
      size: item.value,
    }))
  }, [treemapData, realtimeSectors, dataMode, viewMode])

  // 정렬된 실시간 데이터
  const sortedRealtimeSectors = useMemo(() => {
    const sorted = [...realtimeSectors]
    if (sortBy === 'ratio') {
      sorted.sort((a, b) => b.ratio_5d - a.ratio_5d)
    } else if (sortBy === 'value') {
      sorted.sort((a, b) => b.today_trading_value - a.today_trading_value)
    } else if (sortBy === 'flow') {
      sorted.sort((a, b) => (b.foreign_net + b.institution_net) - (a.foreign_net + a.institution_net))
    }
    return sorted
  }, [realtimeSectors, sortBy])

  const ratioKey = `ratio_${period.replace('d', '')}d` as keyof SectorFlowItem

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">섹터별 수급</h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-gray-500 dark:text-t-text-muted">
              어디에 돈이 몰리고 있는가?
            </p>
            {dataMode === 'realtime' && (
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                marketStatus === 'open'
                  ? 'bg-green-100 text-green-700'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted'
              }`}>
                {marketStatus === 'open' ? `장중 (${timeRatio}%)` : '장마감'}
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2 items-center">
          {/* 실시간/히스토리 토글 */}
          <div className="flex gap-1 mr-2">
            <button
              onClick={() => setDataMode('realtime')}
              className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                dataMode === 'realtime'
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border'
              }`}
            >
              실시간
            </button>
            <button
              onClick={() => setDataMode('history')}
              className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                dataMode === 'history'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border'
              }`}
            >
              DB
            </button>
          </div>

          {/* 뷰 모드 토글 */}
          <div className="flex gap-1 mr-2">
            <button
              onClick={() => setViewMode('table')}
              className={`px-3 py-1.5 text-sm font-medium rounded transition-colors ${
                viewMode === 'table'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border'
              }`}
            >
              테이블
            </button>
            <button
              onClick={() => setViewMode('treemap')}
              className={`px-3 py-1.5 text-sm font-medium rounded transition-colors ${
                viewMode === 'treemap'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border'
              }`}
            >
              트리맵
            </button>
          </div>

          {/* 기간 선택 (DB 모드만) */}
          {dataMode === 'history' && (
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value as PeriodType)}
              className="text-sm border rounded px-2 py-1.5"
            >
              <option value="5d">5일 평균</option>
              <option value="10d">10일 평균</option>
              <option value="20d">20일 평균</option>
            </select>
          )}

          {/* 정렬 */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortType)}
            className="text-sm border rounded px-2 py-1.5"
          >
            <option value="ratio">비율순</option>
            <option value="value">거래대금순</option>
            <option value="flow">수급순</option>
          </select>

          {/* 새로고침 */}
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-1.5 text-sm font-medium rounded bg-gray-100 dark:bg-t-bg-elevated hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border disabled:opacity-50"
          >
            {loading ? '...' : '새로고침'}
          </button>
        </div>
      </div>

      {/* 에러 */}
      {error && (
        <Card className="p-4 bg-red-50 dark:bg-red-900/20 border-red-200">
          <p className="text-sm text-red-700">{error}</p>
        </Card>
      )}

      {/* 로딩 */}
      {loading ? (
        <Card className="p-8 text-center">
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 dark:bg-t-border rounded w-1/3 mx-auto mb-4"></div>
            <div className="h-4 bg-gray-200 dark:bg-t-border rounded w-1/2 mx-auto"></div>
          </div>
        </Card>
      ) : viewMode === 'treemap' ? (
        /* 트리맵 뷰 */
        <Card className="p-4">
          <div className="h-[500px]">
            <ResponsiveContainer width="100%" height="100%">
              <Treemap
                data={treemapChartData}
                dataKey="size"
                aspectRatio={4 / 3}
                stroke="#fff"
                content={<CustomTreemapContent x={0} y={0} width={0} height={0} name="" ratio={0} color_level="" />}
              >
                <Tooltip content={<CustomTooltip />} />
              </Treemap>
            </ResponsiveContainer>
          </div>
          {/* 범례 */}
          <div className="flex flex-wrap gap-3 mt-4 pt-4 border-t text-xs">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded" style={{ background: '#dc2626' }}></span>
              300%+ 극급등
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded" style={{ background: '#f97316' }}></span>
              200%+ 급등
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded" style={{ background: '#fbbf24' }}></span>
              150%+ 상승
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded" style={{ background: '#9ca3af' }}></span>
              100% 평균
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded" style={{ background: '#60a5fa' }}></span>
              70%+ 하락
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded" style={{ background: '#2563eb' }}></span>
              70%- 급락
            </span>
          </div>
        </Card>
      ) : dataMode === 'realtime' ? (
        /* 실시간 테이블 뷰 */
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-t-bg-elevated">
                <tr>
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">#</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">섹터</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">현재 거래대금</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">예상 전일대비</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">5일 평균</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">비율</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">외국인</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">기관</th>
                </tr>
              </thead>
              <tbody>
                {sortedRealtimeSectors.map((sector, idx) => (
                  <>
                    <tr
                      key={sector.sector_name}
                      className={`border-t hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 dark:bg-t-bg-elevated cursor-pointer ${
                        sector.is_hot ? 'bg-yellow-50 dark:bg-yellow-900/20' : ''
                      } ${selectedSector === sector.sector_name ? 'bg-blue-50 dark:bg-blue-900/20' : ''}`}
                      onClick={() => handleSectorClick(sector.sector_name)}
                    >
                      <td className="py-3 px-4 text-gray-400">{idx + 1}</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span className="text-gray-400 text-xs">
                            {selectedSector === sector.sector_name ? '▼' : '▶'}
                          </span>
                          <div>
                            <div className="font-medium flex items-center gap-1">
                              {sector.sector_name}
                              {sector.is_hot && (
                                <span className="text-xs bg-red-100 text-red-600 px-1 rounded">HOT</span>
                              )}
                            </div>
                            <div className="text-xs text-gray-400">{sector.stock_count}종목</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right font-medium">
                        {formatTradingValue(sector.today_trading_value)}
                      </td>
                      <td className="py-3 px-4 text-right text-gray-500 dark:text-t-text-muted">
                        {formatTradingValue(sector.estimated_full_day)}
                      </td>
                      <td className="py-3 px-4 text-right text-gray-500 dark:text-t-text-muted">
                        {formatTradingValue(sector.avg_5d)}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className={`inline-block px-2 py-1 rounded ${getRatioBgColor(sector.ratio_5d)} ${getRatioColor(sector.ratio_5d)}`}>
                          {sector.ratio_5d}%
                        </span>
                      </td>
                      <td className={`py-3 px-4 text-right font-medium ${sector.foreign_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        {formatAmount(sector.foreign_net)}
                      </td>
                      <td className={`py-3 px-4 text-right font-medium ${sector.institution_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        {formatAmount(sector.institution_net)}
                      </td>
                    </tr>
                    {/* 섹터 상세 */}
                    {selectedSector === sector.sector_name && (
                      <tr key={`${sector.sector_name}-detail`}>
                        <td colSpan={8} className="bg-gray-50 dark:bg-t-bg-elevated p-4">
                          <SectorStocksPanel
                            sectorName={sector.sector_name}
                            stocks={sectorStocks}
                            loading={stocksLoading}
                          />
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
          {sortedRealtimeSectors.length === 0 && (
            <div className="p-8 text-center text-gray-500 dark:text-t-text-muted">
              데이터가 없습니다.
            </div>
          )}
        </Card>
      ) : (
        /* DB 테이블 뷰 */
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-t-bg-elevated">
                <tr>
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">#</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">섹터</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">당일 거래대금</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">5일 평균</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">10일 평균</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">20일 평균</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">비율</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">외국인</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">기관</th>
                </tr>
              </thead>
              <tbody>
                {sectors.map((sector, idx) => {
                  const ratio = sector[ratioKey] as number
                  return (
                    <>
                      <tr
                        key={sector.sector_name}
                        className={`border-t hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 dark:bg-t-bg-elevated cursor-pointer ${
                          sector.is_hot ? 'bg-yellow-50 dark:bg-yellow-900/20' : ''
                        } ${selectedSector === sector.sector_name ? 'bg-blue-50 dark:bg-blue-900/20' : ''}`}
                        onClick={() => handleSectorClick(sector.sector_name)}
                      >
                        <td className="py-3 px-4 text-gray-400">{idx + 1}</td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <span className="text-gray-400 text-xs">
                              {selectedSector === sector.sector_name ? '▼' : '▶'}
                            </span>
                            <div>
                              <div className="font-medium flex items-center gap-1">
                                {sector.sector_name}
                                {sector.is_hot && (
                                  <span className="text-xs bg-red-100 text-red-600 px-1 rounded">HOT</span>
                                )}
                              </div>
                              <div className="text-xs text-gray-400">{sector.stock_count}종목</div>
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right font-medium">
                          {formatTradingValue(sector.today_trading_value)}
                        </td>
                        <td className="py-3 px-4 text-right text-gray-500 dark:text-t-text-muted">
                          {formatTradingValue(sector.avg_5d)}
                        </td>
                        <td className="py-3 px-4 text-right text-gray-500 dark:text-t-text-muted">
                          {formatTradingValue(sector.avg_10d)}
                        </td>
                        <td className="py-3 px-4 text-right text-gray-500 dark:text-t-text-muted">
                          {formatTradingValue(sector.avg_20d)}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className={`inline-block px-2 py-1 rounded ${getRatioBgColor(ratio)} ${getRatioColor(ratio)}`}>
                            {ratio}%
                          </span>
                        </td>
                        <td className={`py-3 px-4 text-right font-medium ${sector.foreign_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                          {formatAmount(sector.foreign_net)}
                        </td>
                        <td className={`py-3 px-4 text-right font-medium ${sector.institution_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                          {formatAmount(sector.institution_net)}
                        </td>
                      </tr>
                      {/* 섹터 상세 */}
                      {selectedSector === sector.sector_name && (
                        <tr key={`${sector.sector_name}-detail`}>
                          <td colSpan={9} className="bg-gray-50 dark:bg-t-bg-elevated p-4">
                            <SectorStocksPanel
                              sectorName={sector.sector_name}
                              stocks={sectorStocks}
                              loading={stocksLoading}
                            />
                          </td>
                        </tr>
                      )}
                    </>
                  )
                })}
              </tbody>
            </table>
          </div>
          {sectors.length === 0 && (
            <div className="p-8 text-center text-gray-500 dark:text-t-text-muted">
              데이터가 없습니다.
            </div>
          )}
        </Card>
      )}

      {/* 범례 및 정보 */}
      <Card className="p-3 bg-gray-50 dark:bg-t-bg-elevated">
        <div className="flex flex-wrap gap-4 text-xs text-gray-500 dark:text-t-text-muted">
          <span><span className="bg-yellow-100 px-1 rounded">노란색 배경</span>: 200% 이상 (HOT 섹터)</span>
          <span><span className="text-red-500 font-medium">빨간색</span>: 순매수</span>
          <span><span className="text-blue-500 font-medium">파란색</span>: 순매도</span>
          {dataMode === 'realtime' && marketStatus === 'open' && (
            <span className="text-green-600">1분마다 자동 갱신</span>
          )}
          {tradeDate && dataMode === 'history' && (
            <span className="ml-auto">기준일: {tradeDate}</span>
          )}
        </div>
      </Card>
    </div>
  )
}

// 섹터 내 종목 상세 패널
interface SectorStocksPanelProps {
  sectorName: string
  stocks: SectorStockItem[]
  loading: boolean
}

function SectorStocksPanel({ sectorName, stocks, loading }: SectorStocksPanelProps) {
  if (loading) {
    return (
      <div className="text-center text-gray-400 py-4">
        로딩 중...
      </div>
    )
  }

  if (stocks.length === 0) {
    return (
      <div className="text-center text-gray-400 py-4">
        종목 데이터가 없습니다.
      </div>
    )
  }

  return (
    <div>
      <h4 className="text-sm font-medium text-gray-700 dark:text-t-text-secondary mb-3">
        {sectorName} 섹터 종목 (거래대금 상위)
      </h4>
      <div className="bg-white dark:bg-t-bg-card rounded-lg border overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-gray-100 dark:bg-t-bg-elevated">
            <tr>
              <th className="text-left py-2 px-3">종목</th>
              <th className="text-right py-2 px-3">현재가</th>
              <th className="text-right py-2 px-3">거래대금</th>
              <th className="text-right py-2 px-3">외국인</th>
              <th className="text-right py-2 px-3">기관</th>
              <th className="text-right py-2 px-3">개인</th>
            </tr>
          </thead>
          <tbody>
            {stocks.map((stock) => (
              <tr key={stock.stock_code} className="border-t hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 dark:bg-t-bg-elevated">
                <td className="py-2 px-3">
                  <div className="font-medium">{stock.stock_name}</div>
                  <div className="text-gray-400">{stock.stock_code}</div>
                </td>
                <td className="py-2 px-3 text-right">
                  {stock.close_price.toLocaleString()}원
                </td>
                <td className="py-2 px-3 text-right font-medium">
                  {formatTradingValue(stock.trading_value)}
                </td>
                <td className={`py-2 px-3 text-right ${stock.foreign_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                  {formatAmount(stock.foreign_net)}
                </td>
                <td className={`py-2 px-3 text-right ${stock.institution_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                  {formatAmount(stock.institution_net)}
                </td>
                <td className={`py-2 px-3 text-right ${stock.individual_net >= 0 ? 'text-red-400' : 'text-blue-400'}`}>
                  {formatAmount(stock.individual_net)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
