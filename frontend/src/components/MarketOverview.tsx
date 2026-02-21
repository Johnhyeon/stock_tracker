import { useState, useEffect, useCallback, useRef } from 'react'
import { dataApi } from '../services/api'
import type { MarketIndicesResponse, MarketIndexData } from '../services/api'
import { useMarketStatus } from '../hooks/useMarketStatus'
import { useRealtimePolling } from '../hooks/useRealtimePolling'

function IndexChip({ name, data }: { name: string; data: MarketIndexData }) {
  const isUp = data.change >= 0
  const color = isUp ? 'text-t-bull' : 'text-t-bear'

  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-[10px] font-medium text-gray-500 dark:text-t-text-muted uppercase">{name}</span>
      <span className="text-[12px] font-semibold font-mono text-gray-900 dark:text-t-text-primary">
        {data.current_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </span>
      <span className={`text-[11px] font-mono font-medium ${color}`}>
        {isUp ? '+' : ''}{data.change_rate.toFixed(2)}%
      </span>
    </span>
  )
}

const SEP = <span className="text-gray-300 dark:text-t-border mx-1 text-[10px]">•</span>

export default function MarketOverview() {
  const [indices, setIndices] = useState<MarketIndicesResponse | null>(null)
  const { isMarketOpen } = useMarketStatus()
  const containerRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const [needsScroll, setNeedsScroll] = useState(false)

  const fetchIndices = useCallback(async () => {
    try {
      const data = await dataApi.getMarketIndex()
      setIndices(data)
    } catch {
      // 조용히 실패
    }
  }, [])

  useEffect(() => {
    fetchIndices()
  }, [fetchIndices])

  useRealtimePolling(fetchIndices, 60_000, { onlyMarketHours: true })

  // 콘텐츠가 컨테이너보다 넓은지 감지
  useEffect(() => {
    const check = () => {
      if (containerRef.current && contentRef.current) {
        setNeedsScroll(contentRef.current.scrollWidth > containerRef.current.clientWidth)
      }
    }
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [indices])

  if (!indices || (indices.kospi.current_value === 0 && indices.kosdaq.current_value === 0)) return null

  const hasUs = indices.sp500 || indices.nasdaq || indices.dow

  const tickerContent = (
    <>
      <IndexChip name="KOSPI" data={indices.kospi} />
      {SEP}
      <IndexChip name="KOSDAQ" data={indices.kosdaq} />
      {isMarketOpen && (
        <span className="inline-flex items-center gap-0.5 ml-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse-live" />
          <span className="text-[9px] text-emerald-500 font-medium">LIVE</span>
        </span>
      )}
      {hasUs && (
        <>
          <span className="text-gray-300 dark:text-t-border-hover mx-2 text-[10px]">│</span>
          {indices.sp500 && <IndexChip name="S&P" data={indices.sp500} />}
          {indices.sp500 && indices.nasdaq && SEP}
          {indices.nasdaq && <IndexChip name="NDQ" data={indices.nasdaq} />}
          {(indices.sp500 || indices.nasdaq) && indices.dow && SEP}
          {indices.dow && <IndexChip name="DOW" data={indices.dow} />}
        </>
      )}
    </>
  )

  // 스크롤 불필요 → 정적 표시
  if (!needsScroll) {
    return (
      <div ref={containerRef} className="w-full overflow-hidden px-4">
        <div ref={contentRef} className="flex items-center gap-1 whitespace-nowrap">
          {tickerContent}
        </div>
      </div>
    )
  }

  // 스크롤 필요 → 마키 애니메이션
  return (
    <div ref={containerRef} className="w-full overflow-hidden px-4 ticker-wrapper">
      <div ref={contentRef} className="inline-flex items-center gap-1 whitespace-nowrap ticker-scroll">
        <span className="inline-flex items-center gap-1">{tickerContent}</span>
        <span className="mx-8 text-gray-300 dark:text-t-border">|</span>
        <span className="inline-flex items-center gap-1">{tickerContent}</span>
      </div>
    </div>
  )
}
