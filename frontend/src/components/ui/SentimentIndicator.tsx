import { clsx } from 'clsx'

interface SentimentIndicatorProps {
  score: number | null  // -1.0 ~ 1.0
  size?: 'sm' | 'md'
  showTooltip?: boolean
}

/**
 * 감정 점수를 5단계 도트 인디케이터로 표시
 * -1.0 ~ 1.0 → 부정(빨강) ~ 중립(회색) ~ 긍정(초록)
 */
export default function SentimentIndicator({
  score,
  size = 'sm',
  showTooltip = true,
}: SentimentIndicatorProps) {
  if (score === null || score === undefined) return null

  // 점수를 0~4 단계로 변환 (-1 → 0, 0 → 2, 1 → 4)
  const level = Math.round((score + 1) * 2) // 0, 1, 2, 3, 4

  const dotSize = size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2'
  const gap = size === 'sm' ? 'gap-0.5' : 'gap-1'

  // 레벨별 색상
  const getColor = (dotIndex: number, currentLevel: number) => {
    if (dotIndex > currentLevel) {
      return 'bg-gray-200 dark:bg-gray-600'
    }

    // 레벨에 따른 색상 그라데이션
    if (currentLevel <= 1) {
      // 부정 (빨강)
      return 'bg-red-500 dark:bg-red-400'
    } else if (currentLevel === 2) {
      // 중립 (회색)
      return 'bg-gray-400 dark:bg-gray-500'
    } else {
      // 긍정 (초록)
      return 'bg-green-500 dark:bg-green-400'
    }
  }

  const scoreLabel = score > 0 ? `+${score.toFixed(2)}` : score.toFixed(2)
  const sentimentLabel =
    score > 0.3 ? '긍정' : score < -0.3 ? '부정' : '중립'

  return (
    <div
      className={clsx('flex items-center', gap)}
      title={showTooltip ? `${sentimentLabel} (${scoreLabel})` : undefined}
    >
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className={clsx('rounded-full', dotSize, getColor(i, level))}
        />
      ))}
    </div>
  )
}
