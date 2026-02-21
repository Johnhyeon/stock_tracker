import { Fragment, useEffect, useState, useRef, useCallback } from 'react'
import { flowRankingApi, themeSetupApi, FlowRankingStock, ConsecutiveStock, SpikeStock, RealtimeSpikeStock } from '../../services/api'
import { Card } from '../../components/ui/Card'
import { StockChart } from '../../components/StockChart'

type InvestorType = 'all' | 'foreign' | 'institution' | 'individual'
type SpikeInvestorType = 'all' | 'foreign' | 'institution'
type TabType = 'top' | 'bottom' | 'consecutive' | 'spike'
type SpikeMode = 'realtime' | 'history'

interface FlowHistory {
  flow_date: string
  foreign_net: number
  institution_net: number
  individual_net: number
  flow_score: number
}

// 수량 포맷 (만주 단위)
function formatQty(qty: number): string {
  const sign = qty >= 0 ? '+' : ''
  const abs = Math.abs(qty)
  if (abs >= 10000) {
    return `${sign}${(qty / 10000).toFixed(1)}만`
  }
  return `${sign}${qty.toLocaleString()}`
}

// 금액 포맷 (억원 단위)
function formatAmount(amount: number): string {
  const sign = amount >= 0 ? '+' : ''
  const abs = Math.abs(amount)
  // 억원 단위로 표시
  const billions = amount / 100000000
  if (abs >= 100000000) {
    return `${sign}${billions.toFixed(0)}억`
  } else if (abs >= 10000000) {
    return `${sign}${billions.toFixed(1)}억`
  } else if (abs >= 1000000) {
    // 백만원 단위
    return `${sign}${(amount / 1000000).toFixed(0)}백만`
  }
  return `${sign}${amount.toLocaleString()}`
}

export default function FlowRanking() {
  const [activeTab, setActiveTab] = useState<TabType>('top')
  const [days, setDays] = useState(5)
  const [investorType, setInvestorType] = useState<InvestorType>('all')
  const [topStocks, setTopStocks] = useState<FlowRankingStock[]>([])
  const [bottomStocks, setBottomStocks] = useState<FlowRankingStock[]>([])
  const [consecutiveStocks, setConsecutiveStocks] = useState<ConsecutiveStock[]>([])
  const [spikeStocks, setSpikeStocks] = useState<SpikeStock[]>([])
  const [realtimeSpikeStocks, setRealtimeSpikeStocks] = useState<RealtimeSpikeStock[]>([])
  const [minRatio, setMinRatio] = useState(3.0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [generatedAt, setGeneratedAt] = useState<string | null>(null)

  // 급증 탭 모드 (실시간/히스토리)
  const [spikeMode, setSpikeMode] = useState<SpikeMode>('realtime')
  const [marketStatus, setMarketStatus] = useState<'open' | 'closed'>('closed')
  const refreshIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 선택된 종목 상태
  const [selectedStock, setSelectedStock] = useState<string | null>(null)
  const [flowHistory, setFlowHistory] = useState<FlowHistory[]>([])
  const [flowLoading, setFlowLoading] = useState(false)

  // 실시간 급증 데이터 조회
  const fetchRealtimeSpike = useCallback(async () => {
    try {
      const spikeInvestorType = investorType === 'individual' ? 'all' : investorType as SpikeInvestorType
      const result = await flowRankingApi.getRealtimeSpike(20, minRatio, 500000000, 50, spikeInvestorType)
      setRealtimeSpikeStocks(result.stocks)
      setMarketStatus(result.market_status)
      setGeneratedAt(result.generated_at)
      setError(null)
    } catch (err) {
      console.error('실시간 급증 조회 실패:', err)
      setError('실시간 수급 데이터를 불러오는데 실패했습니다.')
    }
  }, [investorType, minRatio])

  useEffect(() => {
    fetchData()
  }, [activeTab, days, investorType, minRatio, spikeMode])

  // 실시간 모드일 때 1분마다 자동 갱신
  useEffect(() => {
    if (activeTab === 'spike' && spikeMode === 'realtime') {
      refreshIntervalRef.current = setInterval(() => {
        fetchRealtimeSpike()
      }, 60000) // 1분
    }

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
        refreshIntervalRef.current = null
      }
    }
  }, [activeTab, spikeMode, fetchRealtimeSpike])

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    setSelectedStock(null) // 탭 변경 시 선택 해제
    try {
      if (activeTab === 'top') {
        const result = await flowRankingApi.getTop(days, 50, investorType)
        setTopStocks(result.stocks)
        setGeneratedAt(result.generated_at)
      } else if (activeTab === 'bottom') {
        const result = await flowRankingApi.getBottom(days, 50, investorType)
        setBottomStocks(result.stocks)
        setGeneratedAt(result.generated_at)
      } else if (activeTab === 'consecutive') {
        const result = await flowRankingApi.getConsecutive(3, 50, investorType)
        setConsecutiveStocks(result.stocks)
        setGeneratedAt(result.generated_at)
      } else if (activeTab === 'spike') {
        // 급증 탭: individual 제외
        const spikeInvestorType = investorType === 'individual' ? 'all' : investorType as SpikeInvestorType
        if (spikeMode === 'realtime') {
          // 실시간 모드
          const result = await flowRankingApi.getRealtimeSpike(20, minRatio, 500000000, 50, spikeInvestorType)
          setRealtimeSpikeStocks(result.stocks)
          setMarketStatus(result.market_status)
          setGeneratedAt(result.generated_at)
        } else {
          // 히스토리 모드
          const result = await flowRankingApi.getSpike(2, 20, minRatio, 1000000000, 50, spikeInvestorType)
          setSpikeStocks(result.stocks)
          setGeneratedAt(result.generated_at)
        }
      }
    } catch (err) {
      setError('데이터를 불러오는데 실패했습니다.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleStockClick = async (stockCode: string) => {
    if (selectedStock === stockCode) {
      setSelectedStock(null)
      setFlowHistory([])
      return
    }

    setSelectedStock(stockCode)
    setFlowLoading(true)
    try {
      const result = await themeSetupApi.getStockInvestorFlow(stockCode, 20)
      setFlowHistory(result.history)
    } catch (err) {
      console.error('수급 히스토리 로드 실패:', err)
      setFlowHistory([])
    } finally {
      setFlowLoading(false)
    }
  }

  const currentStocks = activeTab === 'top' ? topStocks : activeTab === 'bottom' ? bottomStocks : []

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">수급 랭킹</h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-sm text-gray-500 dark:text-t-text-muted">
              외국인/기관 순매수 상위 종목
            </p>
            {activeTab === 'spike' && spikeMode === 'realtime' && (
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                marketStatus === 'open'
                  ? 'bg-green-100 text-green-700'
                  : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted'
              }`}>
                {marketStatus === 'open' ? '🟢 장중' : '⚪ 장마감'}
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2 items-center">
          {activeTab === 'spike' && (
            <>
              {/* 실시간/히스토리 토글 */}
              <div className="flex gap-1 mr-2">
                <button
                  onClick={() => setSpikeMode('realtime')}
                  className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                    spikeMode === 'realtime'
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border'
                  }`}
                >
                  실시간
                </button>
                <button
                  onClick={() => setSpikeMode('history')}
                  className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                    spikeMode === 'history'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted hover:bg-gray-200 dark:hover:bg-t-border dark:bg-t-border'
                  }`}
                >
                  히스토리
                </button>
              </div>
              {/* 실시간 새로고침 버튼 */}
              {spikeMode === 'realtime' && (
                <button
                  onClick={fetchRealtimeSpike}
                  disabled={loading}
                  className="px-2 py-1 text-xs font-medium rounded bg-green-500 text-white hover:bg-green-600 disabled:opacity-50"
                >
                  {loading ? '갱신중...' : '🔄'}
                </button>
              )}
              {/* 급증 탭 전용 필터 */}
              <select
                value={minRatio}
                onChange={(e) => setMinRatio(Number(e.target.value))}
                className="text-sm border rounded px-2 py-1 bg-white dark:bg-t-bg-elevated dark:border-t-border-hover dark:text-t-text-primary"
              >
                <option value={2}>2배 이상</option>
                <option value={3}>3배 이상</option>
                <option value={5}>5배 이상</option>
                <option value={10}>10배 이상</option>
              </select>
            </>
          )}
          {activeTab !== 'spike' && (
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="text-sm border rounded px-2 py-1 bg-white dark:bg-t-bg-elevated dark:border-t-border-hover dark:text-t-text-primary"
              disabled={activeTab === 'consecutive'}
            >
              <option value={1}>당일</option>
              <option value={3}>3일</option>
              <option value={5}>5일</option>
              <option value={10}>10일</option>
              <option value={20}>20일</option>
            </select>
          )}
          <select
            value={investorType}
            onChange={(e) => setInvestorType(e.target.value as InvestorType)}
            className="text-sm border rounded px-2 py-1 bg-white dark:bg-t-bg-elevated dark:border-t-border-hover dark:text-t-text-primary"
          >
            <option value="all">외인+기관</option>
            <option value="foreign">외국인</option>
            <option value="institution">기관</option>
            {activeTab !== 'spike' && <option value="individual">개인</option>}
          </select>
        </div>
      </div>

      {/* 탭 */}
      <div className="flex gap-2 border-b border-gray-200 dark:border-t-border">
        <button
          onClick={() => setActiveTab('top')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'top'
              ? 'border-red-500 text-red-600'
              : 'border-transparent text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary'
          }`}
        >
          순매수 상위
        </button>
        <button
          onClick={() => setActiveTab('bottom')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'bottom'
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary'
          }`}
        >
          순매도 상위
        </button>
        <button
          onClick={() => setActiveTab('consecutive')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'consecutive'
              ? 'border-green-500 text-green-600'
              : 'border-transparent text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary'
          }`}
        >
          연속 순매수
        </button>
        <button
          onClick={() => setActiveTab('spike')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            activeTab === 'spike'
              ? 'border-orange-500 text-orange-600'
              : 'border-transparent text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary'
          }`}
        >
          🔥 급증
        </button>
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
      ) : activeTab === 'spike' ? (
        /* 수급 급증 */
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            {spikeMode === 'realtime' ? (
              // 실시간 모드 테이블
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-t-bg-elevated">
                  <tr>
                    <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">#</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">종목</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">급증 배율</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">당일 순매수</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">일평균</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">외국인</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">기관</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">테마</th>
                  </tr>
                </thead>
                <tbody>
                  {realtimeSpikeStocks.map((stock, idx) => (
                    <Fragment key={stock.stock_code}>
                      <tr
                        className={`border-t hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 dark:bg-t-bg-elevated cursor-pointer ${
                          selectedStock === stock.stock_code ? 'bg-green-50' : ''
                        }`}
                        onClick={() => handleStockClick(stock.stock_code)}
                      >
                        <td className="py-3 px-4 text-gray-400">{idx + 1}</td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-1">
                            <span className="text-gray-400 text-xs">
                              {selectedStock === stock.stock_code ? '▼' : '▶'}
                            </span>
                            <div>
                              <div className="font-medium">{stock.stock_name}</div>
                              <div className="text-xs text-gray-400">{stock.stock_code}</div>
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className={`inline-block px-2 py-1 rounded font-bold ${
                            stock.spike_ratio >= 10 ? 'bg-red-100 text-red-700' :
                            stock.spike_ratio >= 5 ? 'bg-orange-100 text-orange-700' :
                            'bg-yellow-100 text-yellow-700'
                          }`}>
                            {stock.spike_ratio}배
                          </span>
                        </td>
                        <td className={`py-3 px-4 text-right font-bold ${stock.today_amount >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                          {formatAmount(stock.today_amount)}
                        </td>
                        <td className="py-3 px-4 text-right text-gray-500 dark:text-t-text-muted">
                          {formatAmount(stock.daily_avg)}
                        </td>
                        <td className={`py-3 px-4 text-right font-medium ${stock.foreign_amount >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                          {formatAmount(stock.foreign_amount)}
                        </td>
                        <td className={`py-3 px-4 text-right font-medium ${stock.institution_amount >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                          {formatAmount(stock.institution_amount)}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex flex-wrap gap-1">
                            {stock.themes.slice(0, 2).map((theme) => (
                              <span key={theme} className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted rounded">
                                {theme}
                              </span>
                            ))}
                            {stock.themes.length > 2 && (
                              <span className="text-xs text-gray-400">+{stock.themes.length - 2}</span>
                            )}
                          </div>
                        </td>
                      </tr>
                      {/* 차트 & 수급 상세 */}
                      {selectedStock === stock.stock_code && (
                        <tr>
                          <td colSpan={8} className="bg-gray-50 dark:bg-t-bg-elevated p-4">
                            <StockDetailPanel
                              stockCode={stock.stock_code}
                              stockName={stock.stock_name}
                              flowHistory={flowHistory}
                              flowLoading={flowLoading}
                            />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            ) : (
              // 히스토리 모드 테이블
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-t-bg-elevated">
                  <tr>
                    <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">#</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">종목</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">급증 배율</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">최근 2일</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">일평균</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">외국인</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">기관</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">테마</th>
                  </tr>
                </thead>
                <tbody>
                  {spikeStocks.map((stock, idx) => (
                    <Fragment key={stock.stock_code}>
                      <tr
                        className={`border-t hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 dark:bg-t-bg-elevated cursor-pointer ${
                          selectedStock === stock.stock_code ? 'bg-orange-50' : ''
                        }`}
                        onClick={() => handleStockClick(stock.stock_code)}
                      >
                        <td className="py-3 px-4 text-gray-400">{idx + 1}</td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-1">
                            <span className="text-gray-400 text-xs">
                              {selectedStock === stock.stock_code ? '▼' : '▶'}
                            </span>
                            <div>
                              <div className="font-medium">{stock.stock_name}</div>
                              <div className="text-xs text-gray-400">{stock.stock_code}</div>
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <span className={`inline-block px-2 py-1 rounded font-bold ${
                            stock.spike_ratio >= 10 ? 'bg-red-100 text-red-700' :
                            stock.spike_ratio >= 5 ? 'bg-orange-100 text-orange-700' :
                            'bg-yellow-100 text-yellow-700'
                          }`}>
                            {stock.spike_ratio}배
                          </span>
                        </td>
                        <td className={`py-3 px-4 text-right font-medium ${stock.recent_amount >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                          {formatAmount(stock.recent_amount)}
                        </td>
                        <td className="py-3 px-4 text-right text-gray-500 dark:text-t-text-muted">
                          {formatAmount(stock.base_avg)}
                        </td>
                        <td className={`py-3 px-4 text-right font-medium ${stock.foreign_amount_sum >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                          {formatAmount(stock.foreign_amount_sum)}
                        </td>
                        <td className={`py-3 px-4 text-right font-medium ${stock.institution_amount_sum >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                          {formatAmount(stock.institution_amount_sum)}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex flex-wrap gap-1">
                            {stock.themes.slice(0, 2).map((theme) => (
                              <span key={theme} className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted rounded">
                                {theme}
                              </span>
                            ))}
                            {stock.themes.length > 2 && (
                              <span className="text-xs text-gray-400">+{stock.themes.length - 2}</span>
                            )}
                          </div>
                        </td>
                      </tr>
                      {/* 차트 & 수급 상세 */}
                      {selectedStock === stock.stock_code && (
                        <tr>
                          <td colSpan={8} className="bg-gray-50 dark:bg-t-bg-elevated p-4">
                            <StockDetailPanel
                              stockCode={stock.stock_code}
                              stockName={stock.stock_name}
                              flowHistory={flowHistory}
                              flowLoading={flowLoading}
                            />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {spikeMode === 'realtime' && realtimeSpikeStocks.length === 0 && (
            <div className="p-8 text-center text-gray-500 dark:text-t-text-muted">
              조건에 맞는 종목이 없습니다. (최소 {minRatio}배 이상, 5억원 이상)
              <p className="text-xs mt-2">장중에는 KIS API를 통해 실시간 수급 데이터가 조회됩니다.</p>
            </div>
          )}
          {spikeMode === 'history' && spikeStocks.length === 0 && (
            <div className="p-8 text-center text-gray-500 dark:text-t-text-muted">
              조건에 맞는 종목이 없습니다. (최소 {minRatio}배 이상, 10억원 이상)
            </div>
          )}
        </Card>
      ) : activeTab === 'consecutive' ? (
        /* 연속 순매수 */
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-t-bg-elevated">
                <tr>
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">#</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">종목</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">연속일</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">외국인</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">기관</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">개인</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">테마</th>
                </tr>
              </thead>
              <tbody>
                {consecutiveStocks.map((stock, idx) => (
                  <Fragment key={stock.stock_code}>
                    <tr
                      className={`border-t hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 dark:bg-t-bg-elevated cursor-pointer ${
                        selectedStock === stock.stock_code ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                      }`}
                      onClick={() => handleStockClick(stock.stock_code)}
                    >
                      <td className="py-3 px-4 text-gray-400">{idx + 1}</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1">
                          <span className="text-gray-400 text-xs">
                            {selectedStock === stock.stock_code ? '▼' : '▶'}
                          </span>
                          <div>
                            <div className="font-medium">{stock.stock_name}</div>
                            <div className="text-xs text-gray-400">{stock.stock_code}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className="inline-block px-2 py-1 bg-green-100 text-green-700 rounded font-medium">
                          {stock.consecutive_days}일
                        </span>
                      </td>
                      <td className={`py-3 px-4 text-right font-medium ${(stock.foreign_amount_sum || 0) >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        {formatAmount(stock.foreign_amount_sum || 0)}
                      </td>
                      <td className={`py-3 px-4 text-right font-medium ${(stock.institution_amount_sum || 0) >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        {formatAmount(stock.institution_amount_sum || 0)}
                      </td>
                      <td className={`py-3 px-4 text-right ${(stock.individual_amount_sum || 0) >= 0 ? 'text-red-400' : 'text-blue-400'}`}>
                        {formatAmount(stock.individual_amount_sum || 0)}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex flex-wrap gap-1">
                          {stock.themes.slice(0, 2).map((theme) => (
                            <span key={theme} className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted rounded">
                              {theme}
                            </span>
                          ))}
                          {stock.themes.length > 2 && (
                            <span className="text-xs text-gray-400">+{stock.themes.length - 2}</span>
                          )}
                        </div>
                      </td>
                    </tr>
                    {/* 차트 & 수급 상세 */}
                    {selectedStock === stock.stock_code && (
                      <tr>
                        <td colSpan={7} className="bg-gray-50 dark:bg-t-bg-elevated p-4">
                          <StockDetailPanel
                            stockCode={stock.stock_code}
                            stockName={stock.stock_name}
                            flowHistory={flowHistory}
                            flowLoading={flowLoading}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          {consecutiveStocks.length === 0 && (
            <div className="p-8 text-center text-gray-500 dark:text-t-text-muted">
              조건에 맞는 종목이 없습니다.
            </div>
          )}
        </Card>
      ) : (
        /* 순매수/순매도 상위 */
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-t-bg-elevated">
                <tr>
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">#</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">종목</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">외국인</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">기관</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">개인</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">합계</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">점수</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-t-text-muted">테마</th>
                </tr>
              </thead>
              <tbody>
                {currentStocks.map((stock, idx) => (
                  <Fragment key={stock.stock_code}>
                    <tr
                      className={`border-t hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 dark:bg-t-bg-elevated cursor-pointer ${
                        selectedStock === stock.stock_code ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                      }`}
                      onClick={() => handleStockClick(stock.stock_code)}
                    >
                      <td className="py-3 px-4 text-gray-400">{idx + 1}</td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1">
                          <span className="text-gray-400 text-xs">
                            {selectedStock === stock.stock_code ? '▼' : '▶'}
                          </span>
                          <div>
                            <div className="font-medium">{stock.stock_name}</div>
                            <div className="text-xs text-gray-400">{stock.stock_code}</div>
                          </div>
                        </div>
                      </td>
                      <td className={`py-3 px-4 text-right font-medium ${stock.foreign_amount_sum >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        {formatAmount(stock.foreign_amount_sum)}
                      </td>
                      <td className={`py-3 px-4 text-right font-medium ${stock.institution_amount_sum >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        {formatAmount(stock.institution_amount_sum)}
                      </td>
                      <td className={`py-3 px-4 text-right ${stock.individual_amount_sum >= 0 ? 'text-red-400' : 'text-blue-400'}`}>
                        {formatAmount(stock.individual_amount_sum)}
                      </td>
                      <td className={`py-3 px-4 text-right font-bold ${stock.total_amount_sum >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                        {formatAmount(stock.total_amount_sum)}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className={`inline-block px-2 py-0.5 rounded text-xs ${
                          stock.avg_score >= 60 ? 'bg-red-100 text-red-700' :
                          stock.avg_score >= 50 ? 'bg-orange-100 text-orange-700' :
                          stock.avg_score >= 40 ? 'bg-gray-100 dark:bg-t-bg-elevated text-gray-700 dark:text-t-text-secondary' :
                          'bg-blue-100 text-blue-700'
                        }`}>
                          {stock.avg_score.toFixed(0)}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex flex-wrap gap-1">
                          {stock.themes.slice(0, 2).map((theme) => (
                            <span key={theme} className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-t-bg-elevated text-gray-600 dark:text-t-text-muted rounded">
                              {theme}
                            </span>
                          ))}
                          {stock.themes.length > 2 && (
                            <span className="text-xs text-gray-400">+{stock.themes.length - 2}</span>
                          )}
                        </div>
                      </td>
                    </tr>
                    {/* 차트 & 수급 상세 */}
                    {selectedStock === stock.stock_code && (
                      <tr>
                        <td colSpan={8} className="bg-gray-50 dark:bg-t-bg-elevated p-4">
                          <StockDetailPanel
                            stockCode={stock.stock_code}
                            stockName={stock.stock_name}
                            flowHistory={flowHistory}
                            flowLoading={flowLoading}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
          {currentStocks.length === 0 && (
            <div className="p-8 text-center text-gray-500 dark:text-t-text-muted">
              조건에 맞는 종목이 없습니다.
            </div>
          )}
        </Card>
      )}

      {/* 범례 */}
      <Card className="p-3 bg-gray-50 dark:bg-t-bg-elevated">
        <div className="flex flex-wrap gap-4 text-xs text-gray-500 dark:text-t-text-muted">
          <span><span className="text-red-500 font-medium">빨간색</span>: 순매수</span>
          <span><span className="text-blue-500 font-medium">파란색</span>: 순매도</span>
          <span>점수 50 이상: 매수 우위</span>
          {generatedAt && (
            <span className="ml-auto">
              업데이트: {new Date(generatedAt).toLocaleString('ko-KR')}
            </span>
          )}
        </div>
      </Card>
    </div>
  )
}

// 종목 상세 패널 (차트 + 수급 내역)
interface StockDetailPanelProps {
  stockCode: string
  stockName: string
  flowHistory: FlowHistory[]
  flowLoading: boolean
}

function StockDetailPanel({ stockCode, stockName, flowHistory, flowLoading }: StockDetailPanelProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* 차트 */}
      <div className="bg-white dark:bg-t-bg-card rounded-lg p-3 border">
        <StockChart
          stockCode={stockCode}
          stockName={stockName}
          height={350}
          days={180}
        />
      </div>

      {/* 수급 내역 */}
      <div className="bg-white dark:bg-t-bg-card rounded-lg p-3 border">
        <h4 className="text-sm font-medium text-gray-600 dark:text-t-text-muted mb-3">최근 20일 수급</h4>
        {flowLoading ? (
          <div className="text-center text-gray-400 py-4">로딩 중...</div>
        ) : flowHistory.length > 0 ? (
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-white dark:bg-t-bg-card">
                <tr className="border-b">
                  <th className="text-left py-1.5 px-2">날짜</th>
                  <th className="text-right py-1.5 px-2">외국인</th>
                  <th className="text-right py-1.5 px-2">기관</th>
                  <th className="text-right py-1.5 px-2">개인</th>
                  <th className="text-right py-1.5 px-2">합계</th>
                </tr>
              </thead>
              <tbody>
                {flowHistory.map((h) => {
                  const total = h.foreign_net + h.institution_net
                  return (
                    <tr key={h.flow_date} className="border-b border-gray-100 dark:border-t-border/50 hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 dark:bg-t-bg-elevated">
                      <td className="py-1.5 px-2 text-gray-600 dark:text-t-text-muted">{h.flow_date}</td>
                      <td className={`py-1.5 px-2 text-right ${h.foreign_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        {formatQty(h.foreign_net)}
                      </td>
                      <td className={`py-1.5 px-2 text-right ${h.institution_net >= 0 ? 'text-red-500' : 'text-blue-500'}`}>
                        {formatQty(h.institution_net)}
                      </td>
                      <td className={`py-1.5 px-2 text-right ${h.individual_net >= 0 ? 'text-red-400' : 'text-blue-400'}`}>
                        {formatQty(h.individual_net)}
                      </td>
                      <td className={`py-1.5 px-2 text-right font-medium ${total >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                        {formatQty(total)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center text-gray-400 py-4">수급 데이터 없음</div>
        )}

        {/* 수급 요약 */}
        {flowHistory.length > 0 && (
          <div className="mt-3 pt-3 border-t grid grid-cols-3 gap-2 text-xs">
            <div className="text-center">
              <div className="text-gray-500 dark:text-t-text-muted">5일 합계</div>
              <div className={`font-medium ${
                flowHistory.slice(0, 5).reduce((sum, h) => sum + h.foreign_net + h.institution_net, 0) >= 0
                  ? 'text-red-600' : 'text-blue-600'
              }`}>
                {formatQty(flowHistory.slice(0, 5).reduce((sum, h) => sum + h.foreign_net + h.institution_net, 0))}
              </div>
            </div>
            <div className="text-center">
              <div className="text-gray-500 dark:text-t-text-muted">10일 합계</div>
              <div className={`font-medium ${
                flowHistory.slice(0, 10).reduce((sum, h) => sum + h.foreign_net + h.institution_net, 0) >= 0
                  ? 'text-red-600' : 'text-blue-600'
              }`}>
                {formatQty(flowHistory.slice(0, 10).reduce((sum, h) => sum + h.foreign_net + h.institution_net, 0))}
              </div>
            </div>
            <div className="text-center">
              <div className="text-gray-500 dark:text-t-text-muted">20일 합계</div>
              <div className={`font-medium ${
                flowHistory.reduce((sum, h) => sum + h.foreign_net + h.institution_net, 0) >= 0
                  ? 'text-red-600' : 'text-blue-600'
              }`}>
                {formatQty(flowHistory.reduce((sum, h) => sum + h.foreign_net + h.institution_net, 0))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
