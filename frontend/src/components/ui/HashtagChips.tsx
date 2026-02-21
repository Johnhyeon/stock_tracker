import { clsx } from 'clsx'

interface HashtagChipsProps {
  hashtags: string[]
  maxVisible?: number
  size?: 'sm' | 'md'
  onHashtagClick?: (hashtag: string) => void
  className?: string
}

/**
 * 해시태그 배열을 클릭 가능한 칩으로 표시
 */
export default function HashtagChips({
  hashtags,
  maxVisible = 5,
  size = 'sm',
  onHashtagClick,
  className,
}: HashtagChipsProps) {
  if (!hashtags || hashtags.length === 0) return null

  const visible = hashtags.slice(0, maxVisible)
  const remaining = hashtags.length - maxVisible

  const chipClasses = clsx(
    'inline-flex items-center rounded-full transition-colors',
    size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-1 text-sm',
    'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300',
    onHashtagClick && 'cursor-pointer hover:bg-primary-100 dark:hover:bg-primary-900/50'
  )

  return (
    <div className={clsx('flex flex-wrap gap-1', className)}>
      {visible.map((tag) => (
        <span
          key={tag}
          className={chipClasses}
          onClick={(e) => {
            if (onHashtagClick) {
              e.stopPropagation()
              onHashtagClick(tag)
            }
          }}
        >
          {tag}
        </span>
      ))}
      {remaining > 0 && (
        <span
          className={clsx(
            'inline-flex items-center rounded-full',
            size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-1 text-sm',
            'bg-gray-100 text-gray-600 dark:bg-t-bg-elevated dark:text-t-text-muted'
          )}
        >
          +{remaining}
        </span>
      )}
    </div>
  )
}
