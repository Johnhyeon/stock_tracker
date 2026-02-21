import type { SmartScoreBadge as SmartScoreBadgeType } from '../../types/dashboard_v2'

const gradeColor: Record<string, string> = {
  A: 'bg-red-500',
  B: 'bg-orange-400',
  C: 'bg-yellow-400',
  D: 'bg-gray-300 dark:bg-gray-600',
}

const gradeTextColor: Record<string, string> = {
  A: 'text-red-600 dark:text-red-400',
  B: 'text-orange-500 dark:text-orange-400',
  C: 'text-yellow-600 dark:text-yellow-400',
  D: 'text-gray-400 dark:text-gray-500',
}

interface SmartScoreBadgeProps {
  score: SmartScoreBadgeType
  compact?: boolean
}

export default function SmartScoreBadge({ score, compact = false }: SmartScoreBadgeProps) {
  const dimensions = [
    { key: 'C', grade: score.chart_grade, label: '차트' },
    { key: 'N', grade: score.narrative_grade, label: '내러티브' },
    { key: 'F', grade: score.flow_grade, label: '수급' },
    { key: 'S', grade: score.social_grade, label: '소셜' },
  ]

  if (compact) {
    return (
      <div className="flex items-center gap-0.5">
        {dimensions.map(d => (
          <div
            key={d.key}
            className={`w-3.5 h-3.5 rounded-sm flex items-center justify-center text-[8px] font-bold text-white ${gradeColor[d.grade] || gradeColor.D}`}
            title={`${d.label}: ${d.grade}`}
          >
            {d.grade}
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1.5">
      <span className={`text-sm font-bold ${gradeTextColor[score.composite_grade] || gradeTextColor.D}`}>
        {score.composite_grade}
      </span>
      <span className="text-xs text-gray-400">{Math.round(score.composite_score)}pt</span>
      <div className="flex gap-0.5 ml-1">
        {dimensions.map(d => (
          <div
            key={d.key}
            className={`w-4 h-4 rounded-sm flex items-center justify-center text-[9px] font-bold text-white ${gradeColor[d.grade] || gradeColor.D}`}
            title={`${d.label}: ${d.grade}`}
          >
            {d.key}
          </div>
        ))}
      </div>
    </div>
  )
}
