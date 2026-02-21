import Select from '../../../components/ui/Select'
import HashtagChips from '../../../components/ui/HashtagChips'
import type { IdeaFilters, SentimentFilter, SourceFilter } from '../hooks/useIdeaFilters'

interface IdeaFilterPanelProps {
  filters: IdeaFilters
  onFilterChange: <K extends keyof IdeaFilters>(key: K, value: IdeaFilters[K]) => void
  onReset: () => void
  onHashtagRemove: (tag: string) => void
  showSourceFilter?: boolean
  showAuthorFilter?: boolean
  compact?: boolean
  extraActions?: React.ReactNode
}

export default function IdeaFilterPanel({
  filters,
  onFilterChange,
  onReset,
  onHashtagRemove,
  showSourceFilter = true,
  showAuthorFilter = true,
  extraActions,
}: IdeaFilterPanelProps) {
  const hasActiveFilters =
    filters.period !== 7 ||
    filters.source !== 'all' ||
    filters.sentiment !== 'all' ||
    filters.search !== '' ||
    filters.hashtags.length > 0 ||
    filters.author !== null

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* 기간 */}
      <Select
        options={[
          { value: '7', label: '7일' },
          { value: '14', label: '14일' },
          { value: '30', label: '30일' },
          { value: '90', label: '90일' },
        ]}
        value={String(filters.period)}
        onChange={(e) => onFilterChange('period', Number(e.target.value))}
        className="!w-20 !py-1 !text-xs"
      />

      {/* 소스 */}
      {showSourceFilter && (
        <Select
          options={[
            { value: 'all', label: '전체' },
            { value: 'my', label: '내 아이디어' },
            { value: 'others', label: '타인' },
          ]}
          value={filters.source}
          onChange={(e) => onFilterChange('source', e.target.value as SourceFilter)}
          className="!w-28 !py-1 !text-xs"
        />
      )}

      {/* 감정 */}
      <Select
        options={[
          { value: 'all', label: '감정 전체' },
          { value: 'POSITIVE', label: '긍정' },
          { value: 'NEGATIVE', label: '부정' },
          { value: 'NEUTRAL', label: '중립' },
        ]}
        value={filters.sentiment}
        onChange={(e) => onFilterChange('sentiment', e.target.value as SentimentFilter)}
        className="!w-24 !py-1 !text-xs"
      />

      {/* 검색 */}
      <div className="relative">
        <input
          type="text"
          placeholder="종목명/코드..."
          value={filters.search}
          onChange={(e) => onFilterChange('search', e.target.value)}
          className="w-32 px-2 py-1 text-xs rounded-md border border-gray-300 dark:border-t-border-hover bg-white dark:bg-t-bg-elevated text-gray-900 dark:text-t-text-primary focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
        />
        {filters.search && (
          <button
            onClick={() => onFilterChange('search', '')}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* 발신자 필터 (인라인 배지) */}
      {showAuthorFilter && filters.author && (
        <span className="inline-flex items-center gap-1 text-xs bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-400 px-2 py-0.5 rounded-full">
          {filters.author}
          <button
            onClick={() => onFilterChange('author', null)}
            className="hover:text-red-500 ml-0.5"
          >
            &times;
          </button>
        </span>
      )}

      {/* 선택된 해시태그 (인라인) */}
      {filters.hashtags.length > 0 && (
        <div className="flex items-center gap-1">
          <HashtagChips
            hashtags={filters.hashtags}
            maxVisible={5}
            size="sm"
            onHashtagClick={onHashtagRemove}
          />
        </div>
      )}

      {/* 초기화 */}
      {hasActiveFilters && (
        <button
          onClick={onReset}
          className="text-[10px] text-gray-400 dark:text-t-text-muted hover:text-red-500 dark:hover:text-red-400"
        >
          초기화
        </button>
      )}

      {/* 추가 액션 (우측 정렬) */}
      {extraActions && (
        <>
          <div className="flex-1" />
          {extraActions}
        </>
      )}
    </div>
  )
}
