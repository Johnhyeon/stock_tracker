import { useEffect, useState } from 'react'
import { StockChart, OHLCVCandle } from './StockChart'
import { themeSetupApi } from '../services/api'
import type { ChartPattern } from '../types/theme_setup'
import { PATTERN_TYPE_LABELS, PATTERN_TYPE_COLORS } from '../types/theme_setup'

// 주식 수량 포맷 (만주 단위)
function formatShareCount(count: number): string {
  const sign = count >= 0 ? '+' : ''
  const abs = Math.abs(count)
  if (abs >= 10000) {
    return `${sign}${(count / 10000).toFixed(1)}만주`
  }
  return `${sign}${count.toLocaleString()}주`
}

interface FlowData {
  flow_date: string
  foreign_net: number
  institution_net: number
  individual_net: number
  flow_score: number
}

// 매수 마커 타입
interface EntryMarker {
  date: string
  price: number
  quantity?: number
}

interface IdeaStockChartProps {
  stockCode: string
  stockName: string
  initialPrice?: number  // metadata에서 전달, 없으면 null
  avgEntryPrice?: number  // 포지션 평균 매수가
  entryMarkers?: EntryMarker[]  // 매수 지점 마커
  createdAt: string
  height?: number
}

export function IdeaStockChart({
  stockCode,
  stockName,
  initialPrice,
  avgEntryPrice,
  entryMarkers,
  createdAt,
  height = 200,
}: IdeaStockChartProps) {
  // 포지션 유무에 따른 라벨: 포지션 있으면 "평단가", 없으면 "등록일 기준가"
  const hasPosition = avgEntryPrice !== undefined && avgEntryPrice > 0
  const priceLabel = hasPosition ? '평단가' : '등록일 기준가'
  const [chartData, setChartData] = useState<OHLCVCandle[]>([])
  // 포지션이 있으면 avgEntryPrice 사용, 없으면 initialPrice 사용
  const [entryPrice, setEntryPrice] = useState<number | null>(hasPosition ? avgEntryPrice : (initialPrice || null))
  const [currentPrice, setCurrentPrice] = useState<number | null>(null)
  const [returnPct, setReturnPct] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [, setFlowData] = useState<FlowData[]>([])
  const [flowSummary, setFlowSummary] = useState<{
    foreignTotal: number
    institutionTotal: number
    recentTrend: 'buy' | 'sell' | 'neutral'
  } | null>(null)
  const [patternData, setPatternData] = useState<ChartPattern | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        // 최소 180일, 생성일 이후 기간 중 큰 값 사용
        const daysSince = Math.ceil(
          (Date.now() - new Date(createdAt).getTime()) / (1000 * 60 * 60 * 24)
        )
        const daysToFetch = Math.max(180, daysSince + 10)

        // OHLCV, 수급, 패턴 데이터 동시 조회
        const [ohlcv, flowResult, patternResult] = await Promise.all([
          themeSetupApi.getStockOHLCV(stockCode, daysToFetch),
          themeSetupApi.getStockInvestorFlow(stockCode, 20).catch(() => null),
          themeSetupApi.getStockPattern(stockCode).catch(() => null),
        ])

        // 패턴 데이터 설정
        if (patternResult) {
          setPatternData(patternResult)
        }

        if (!ohlcv.candles || ohlcv.candles.length === 0) {
          setError('데이터 없음')
          return
        }

        // 전체 데이터를 차트에 표시 (생성일 이전 데이터도 포함)
        setChartData(ohlcv.candles)
        setCurrentPrice(ohlcv.candles[ohlcv.candles.length - 1].close)

        // 진입가/기준가 설정:
        // 1. 포지션이 있으면 avgEntryPrice 사용
        // 2. metadata에 initialPrice 있으면 사용
        // 3. 없으면 생성일 종가 찾기
        if (avgEntryPrice && avgEntryPrice > 0) {
          setEntryPrice(avgEntryPrice)
        } else if (!initialPrice) {
          const createdDate = new Date(createdAt).setHours(0, 0, 0, 0)
          const entryCandle = ohlcv.candles.find(
            (c: OHLCVCandle) => c.time * 1000 >= createdDate
          )
          if (entryCandle) {
            setEntryPrice(entryCandle.close)
          } else {
            // 생성일 데이터가 없으면 첫 번째 캔들 사용
            setEntryPrice(ohlcv.candles[0].close)
          }
        } else {
          setEntryPrice(initialPrice)
        }

        // 수급 데이터 처리
        if (flowResult?.history && flowResult.history.length > 0) {
          setFlowData(flowResult.history)

          // 최근 5일 수급 합계
          const recent5 = flowResult.history.slice(-5)
          const foreignTotal = recent5.reduce((sum, d) => sum + d.foreign_net, 0)
          const institutionTotal = recent5.reduce((sum, d) => sum + d.institution_net, 0)

          // 최근 추세 판단
          const netTotal = foreignTotal + institutionTotal
          const recentTrend = netTotal > 100000000 ? 'buy' : netTotal < -100000000 ? 'sell' : 'neutral'

          setFlowSummary({ foreignTotal, institutionTotal, recentTrend })
        }
      } catch (err: unknown) {
        console.error('차트 데이터 로드 실패:', stockCode, err)
        const errorMessage = err instanceof Error ? err.message : '알 수 없는 오류'
        // axios 에러인 경우 더 자세한 메시지
        if (err && typeof err === 'object' && 'response' in err) {
          const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } }
          if (axiosErr.response?.status === 404) {
            setError('종목 데이터 없음')
          } else if (axiosErr.response?.data?.detail) {
            setError(axiosErr.response.data.detail)
          } else {
            setError(`로드 실패 (${axiosErr.response?.status || errorMessage})`)
          }
        } else {
          setError(`로드 실패: ${errorMessage}`)
        }
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [stockCode, createdAt, initialPrice, avgEntryPrice])

  // 수익률 계산
  useEffect(() => {
    if (entryPrice && currentPrice) {
      setReturnPct(((currentPrice - entryPrice) / entryPrice) * 100)
    }
  }, [entryPrice, currentPrice])

  // TradingView 링크
  const tradingViewUrl = `https://kr.tradingview.com/chart/?symbol=KRX:${stockCode}`

  if (loading) {
    return (
      <div className="border rounded-lg p-4">
        <div className="flex justify-between items-center mb-2">
          <span className="font-medium">{stockName}</span>
        </div>
        <div
          className="flex items-center justify-center bg-gray-50 rounded"
          style={{ height: `${height}px` }}
        >
          <span className="text-gray-400 text-sm animate-pulse">로딩 중...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="border rounded-lg p-4">
        <div className="flex justify-between items-center mb-2">
          <span className="font-medium">{stockName}</span>
        </div>
        <div
          className="flex items-center justify-center bg-gray-50 rounded"
          style={{ height: `${height}px` }}
        >
          <span className="text-red-400 text-sm">{error}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="border rounded-lg p-4">
      {/* 헤더: 종목명, 수익률 */}
      <div className="flex justify-between items-center mb-2">
        <a
          href={tradingViewUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium hover:text-blue-600 hover:underline"
        >
          {stockName}
          <span className="text-xs text-gray-400 ml-1">({stockCode})</span>
        </a>
        {returnPct !== null && (
          <span
            className={`font-semibold ${
              returnPct >= 0 ? 'text-red-600' : 'text-blue-600'
            }`}
          >
            {returnPct >= 0 ? '+' : ''}
            {returnPct.toFixed(2)}%
          </span>
        )}
      </div>

      {/* 가격 정보 및 수급 요약 */}
      <div className="flex justify-between items-center text-sm text-gray-500 mb-2">
        {entryPrice && (
          <div>
            <span>{priceLabel}: {entryPrice.toLocaleString()}원</span>
            <span className="mx-2">→</span>
            <span>현재가: {currentPrice?.toLocaleString()}원</span>
          </div>
        )}
        {flowSummary && (
          <div className="flex items-center gap-2">
            <span
              className={`text-xs px-1.5 py-0.5 rounded ${
                flowSummary.recentTrend === 'buy'
                  ? 'bg-red-100 text-red-700'
                  : flowSummary.recentTrend === 'sell'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-600'
              }`}
            >
              {flowSummary.recentTrend === 'buy' ? '매집' : flowSummary.recentTrend === 'sell' ? '이탈' : '중립'}
            </span>
            <span className="text-xs">
              외인{' '}
              <span className={flowSummary.foreignTotal >= 0 ? 'text-red-600' : 'text-blue-600'}>
                {formatShareCount(flowSummary.foreignTotal)}
              </span>
              {' / '}기관{' '}
              <span className={flowSummary.institutionTotal >= 0 ? 'text-red-600' : 'text-blue-600'}>
                {formatShareCount(flowSummary.institutionTotal)}
              </span>
              <span className="text-gray-400 ml-1">(5일)</span>
            </span>
          </div>
        )}
      </div>

      {/* 차트 패턴 정보 */}
      {patternData && (
        <div className="flex items-center gap-2 text-sm mb-2">
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium ${
              PATTERN_TYPE_COLORS[patternData.pattern_type] || 'bg-gray-100 text-gray-800'
            }`}
          >
            {PATTERN_TYPE_LABELS[patternData.pattern_type] || patternData.pattern_type}
          </span>
          <span className="text-xs text-gray-500">
            신뢰도 {patternData.confidence}%
          </span>
          {patternData.price_from_support_pct !== undefined && patternData.price_from_support_pct !== null && (
            <span className="text-xs text-gray-500">
              지지선 대비{' '}
              <span className={patternData.price_from_support_pct >= 0 ? 'text-red-600' : 'text-blue-600'}>
                {patternData.price_from_support_pct >= 0 ? '+' : ''}{patternData.price_from_support_pct.toFixed(1)}%
              </span>
            </span>
          )}
        </div>
      )}

      {/* 차트 */}
      <StockChart
        stockCode={stockCode}
        stockName={stockName}
        height={height}
        ohlcvData={chartData}
        initialPriceLine={entryPrice || undefined}
        priceLineLabel={priceLabel}
        avgEntryPrice={avgEntryPrice}
        entryMarkers={entryMarkers}
        showHeader={false}
      />
    </div>
  )
}
