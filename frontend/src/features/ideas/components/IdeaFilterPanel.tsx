import Select from '../../../components/ui/Select'
import Button from '../../../components/ui/Button'
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
}

export default function IdeaFilterPanel({
  filters,
  onFilterChange,
  onReset,
  onHashtagRemove,
  showSourceFilter = true,
  showAuthorFilter = true,
  compact = false,
}: IdeaFilterPanelProps) {
  const hasActiveFilters =
    filters.period !== 7 ||
    filters.source !== 'all' ||
    filters.sentiment !== 'all' ||
    filters.search !== '' ||
    filters.hashtags.length > 0 ||
    filters.author !== null

  return (
    <div className="space-y-3">
      {/* 주요 필터 */}
      <div className={`flex flex-wrap gap-3 ${compact ? 'items-center' : ''}`}>
        {/* 기간 필터 */}
        <Select
          options={[
            { value: '7', label: '최근 7일' },
            { value: '14', label: '최근 14일' },
            { value: '30', label: '최근 30일' },
            { value: '90', label: '최근 90일' },
          ]}
          value={String(filters.period)}
          onChange={(e) => onFilterChange('period', Number(e.target.value))}
        />

        {/* 소스 필터 */}
        {showSourceFilter && (
          <Select
            options={[
              { value: 'all', label: '전체 소스' },
              { value: 'my', label: '내 아이디어' },
              { value: 'others', label: '타인 아이디어' },
            ]}
            value={filters.source}
            onChange={(e) => onFilterChange('source', e.target.value as SourceFilter)}
          />
        )}

        {/* 감정 필터 */}
        <Select
          options={[
            { value: 'all', label: '전체 감정' },
            { value: 'POSITIVE', label: '긍정' },
            { value: 'NEGATIVE', label: '부정' },
            { value: 'NEUTRAL', label: '중립' },
          ]}
          value={filters.sentiment}
          onChange={(e) => onFilterChange('sentiment', e.target.value as SentimentFilter)}
        />

        {/* 검색 */}
        <div className="relative">
          <input
            type="text"
            placeholder="종목명/코드 검색..."
            value={filters.search}
            onChange={(e) => onFilterChange('search', e.target.value)}
            className="w-40 px-3 py-1.5 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
          {filters.search && (
            <button
              onClick={() => onFilterChange('search', '')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* 초기화 */}
        {hasActiveFilters && (
          <Button
            variant="secondary"
            size="sm"
            onClick={onReset}
          >
            초기화
          </Button>
        )}
      </div>

      {/* 발신자 필터 표시 */}
      {showAuthorFilter && filters.author && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-600 dark:text-gray-400">발신자:</span>
          <span className="font-medium text-gray-900 dark:text-gray-100">{filters.author}</span>
          <button
            onClick={() => onFilterChange('author', null)}
            className="text-red-500 hover:text-red-700 text-xs"
          >
            해제
          </button>
        </div>
      )}

      {/* 선택된 해시태그 */}
      {filters.hashtags.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600 dark:text-gray-400">해시태그:</span>
          <HashtagChips
            hashtags={filters.hashtags}
            maxVisible={10}
            onHashtagClick={onHashtagRemove}
          />
          <button
            onClick={() => filters.hashtags.forEach(onHashtagRemove)}
            className="text-xs text-red-500 hover:text-red-700"
          >
            전체 해제
          </button>
        </div>
      )}
    </div>
  )
}
