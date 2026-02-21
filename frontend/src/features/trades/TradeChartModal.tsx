import { useState, useEffect, useMemo } from 'react'
import { tradeApi } from '../../services/api'
import { StockChart } from '../../components/StockChart'
import type { TradeMarker } from '../../components/StockChart'

interface TradeChartModalProps {
  stockCode: string
  stockName: string
  isOpen: boolean
  onClose: () => void
}

export default function TradeChartModal({ stockCode, stockName, isOpen, onClose }: TradeChartModalProps) {
  const [tradeMarkers, setTradeMarkers] = useState<TradeMarker[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isOpen) return
    setLoading(true)
    tradeApi.getByStock(stockCode)
      .then(res => {
        setTradeMarkers(
          res.trades
            .filter((t: any) => t.trade_date && t.price)
            .map((t: any) => ({
              date: t.trade_date,
              price: t.price,
              quantity: t.quantity,
              trade_type: t.trade_type,
            }))
        )
      })
      .catch(() => setTradeMarkers([]))
      .finally(() => setLoading(false))
  }, [isOpen, stockCode])

  // 차트 기간 계산: 오늘부터 가장 오래된 매매까지 + 여유
  const chartDays = useMemo(() => {
    if (tradeMarkers.length === 0) return 180
    const dates = tradeMarkers.map(m => new Date(m.date).getTime())
    const minDate = Math.min(...dates)
    const now = Date.now()
    // 오늘부터 가장 오래된 매매까지의 달력일 → 거래일 환산 (5/7) + 여유
    const calendarDays = Math.ceil((now - minDate) / (1000 * 60 * 60 * 24))
    const tradingDays = Math.ceil(calendarDays * 5 / 7) + 30
    return Math.max(tradingDays, 180) // 최소 180일
  }, [tradeMarkers])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white dark:bg-t-bg-card rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="p-4 border-b border-gray-200 dark:border-t-border flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-t-text-primary">{stockName}</h3>
            <p className="text-xs text-gray-400">{stockCode} - 매매 기록 {tradeMarkers.length}건</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>
        <div className="p-4">
          {loading ? (
            <div className="h-[450px] flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
            </div>
          ) : (
            <StockChart
              stockCode={stockCode}
              stockName={stockName}
              height={450}
              days={chartDays}
              tradeMarkers={tradeMarkers}
              showTradeMarkers={true}
              showHeader={false}
            />
          )}
        </div>
      </div>
    </div>
  )
}
