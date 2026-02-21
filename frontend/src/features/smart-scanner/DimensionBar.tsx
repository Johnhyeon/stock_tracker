import type { SmartSignalDimension } from '../../types/smart_scanner'

interface DimensionBarProps {
  label: string
  dimension: SmartSignalDimension
  colorClass?: string
}

const gradeColors: Record<string, string> = {
  A: 'bg-emerald-500 dark:bg-emerald-400',
  B: 'bg-blue-500 dark:bg-blue-400',
  C: 'bg-amber-500 dark:bg-amber-400',
  D: 'bg-gray-400 dark:bg-gray-500',
}

export default function DimensionBar({ label, dimension, colorClass }: DimensionBarProps) {
  const pct = dimension.max_score > 0
    ? Math.round((dimension.score / dimension.max_score) * 100)
    : 0
  const barColor = colorClass || gradeColors[dimension.grade] || gradeColors.D

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 dark:text-t-text-muted w-14 shrink-0 text-right">
        {label}
      </span>
      <div className="flex-1 h-2 bg-gray-200 dark:bg-t-bg-elevated rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-medium text-gray-700 dark:text-t-text-secondary w-12 shrink-0">
        {dimension.score}/{dimension.max_score}
      </span>
    </div>
  )
}
