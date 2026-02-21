/** SVG 미니 스파크라인 */
export default function MiniSparkline({
  prices,
  width = 56,
  height = 22,
}: {
  prices: number[]
  width?: number
  height?: number
}) {
  if (prices.length < 2) return null
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const range = max - min || 1
  const pad = height * 0.1

  const points = prices
    .map((p, i) => {
      const x = (i / (prices.length - 1)) * width
      const y = height - pad - ((p - min) / range) * (height - pad * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  const isUp = prices[prices.length - 1] >= prices[0]
  const color = isUp ? '#ef4444' : '#3b82f6'

  return (
    <svg width={width} height={height} className="flex-shrink-0">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export type SparklineMap = Record<string, { name: string; dates: string[]; closes: number[] }>

/** 특정 날짜 이후 스파크라인 데이터 추출 */
export function getSparklineSinceDate(
  sparkline: { dates: string[]; closes: number[] },
  sinceDate: string,
): { prices: number[]; changePct: number } | null {
  const sinceTs = new Date(sinceDate).getTime()
  let startIdx = 0
  for (let i = 0; i < sparkline.dates.length; i++) {
    if (new Date(sparkline.dates[i]).getTime() >= sinceTs) {
      startIdx = i
      break
    }
  }
  const prices = sparkline.closes.slice(Math.max(0, startIdx - 1))
  if (prices.length < 2) return null
  const changePct = ((prices[prices.length - 1] - prices[0]) / prices[0]) * 100
  return { prices, changePct }
}
