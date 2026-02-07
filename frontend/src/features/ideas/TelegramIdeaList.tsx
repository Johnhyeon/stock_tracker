import { useEffect, useState, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { telegramIdeaApi } from '../../services/api'
import TelegramIdeaCard from './TelegramIdeaCard'
import IdeaFilterPanel from './components/IdeaFilterPanel'
import Button from '../../components/ui/Button'
import type { TelegramIdea, IdeaSourceType, AuthorStats } from '../../types/telegram_idea'
import type { IdeaFilters } from './hooks/useIdeaFilters'

interface TelegramIdeaListProps {
  sourceType?: IdeaSourceType | 'all'  // 외부에서 고정된 소스 타입 (선택적)
  showSourceFilter?: boolean            // 소스 필터 표시 여부
  initialFilters?: Partial<IdeaFilters> // 초기 필터값
}

interface StockGroup {
  stockCode: string | null
  stockName: string | null
  ideas: TelegramIdea[]
  latestDate: string
}

const DEFAULT_FILTERS: IdeaFilters = {
  period: 7,
  source: 'all',
  sentiment: 'all',
  search: '',
  hashtags: [],
  author: null,
}

export default function TelegramIdeaList({
  sourceType,
  showSourceFilter = true,
  initialFilters,
}: TelegramIdeaListProps) {
  const navigate = useNavigate()
  const [ideas, setIdeas] = useState<TelegramIdea[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [filters, setFilters] = useState<IdeaFilters>(() => ({
    ...DEFAULT_FILTERS,
    ...initialFilters,
    source: sourceType && sourceType !== 'all' ? sourceType : (initialFilters?.source || 'all'),
  }))
  const [authors, setAuthors] = useState<AuthorStats[]>([])
  const [collecting, setCollecting] = useState(false)
  const [expandedStocks, setExpandedStocks] = useState<Set<string>>(new Set())
  const [groupByStock, setGroupByStock] = useState(
    sourceType === 'others' || filters.source === 'others'
  )

  const limit = 100

  // 실제 사용할 소스 타입 계산
  const effectiveSource = useMemo(() => {
    if (sourceType && sourceType !== 'all') return sourceType
    if (filters.source !== 'all') return filters.source
    return undefined
  }, [sourceType, filters.source])

  const fetchIdeas = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: {
        source?: IdeaSourceType
        days: number
        limit: number
        offset: number
        author?: string
        sentiment?: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL'
      } = {
        days: filters.period,
        limit,
        offset,
      }

      if (effectiveSource) {
        params.source = effectiveSource
      }
      if (filters.author) {
        params.author = filters.author
      }
      if (filters.sentiment !== 'all') {
        params.sentiment = filters.sentiment
      }

      const response = await telegramIdeaApi.list(params)

      // 클라이언트 측 필터링: 검색어, 해시태그
      let filteredItems = response.items

      if (filters.search) {
        const searchLower = filters.search.toLowerCase()
        filteredItems = filteredItems.filter(
          (idea) =>
            (idea.stock_name?.toLowerCase().includes(searchLower)) ||
            (idea.stock_code?.includes(filters.search))
        )
      }

      if (filters.hashtags.length > 0) {
        filteredItems = filteredItems.filter((idea) =>
          filters.hashtags.some((tag) => idea.raw_hashtags?.includes(tag))
        )
      }

      setIdeas(filteredItems)
      setTotal(response.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : '데이터를 불러오는 데 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }, [filters, offset, effectiveSource])

  const fetchAuthors = useCallback(async () => {
    if (effectiveSource !== 'others') return
    try {
      const response = await telegramIdeaApi.getAuthorStats(filters.period)
      setAuthors(response.authors)
    } catch (err) {
      console.error('발신자 통계 로드 실패:', err)
    }
  }, [effectiveSource, filters.period])

  useEffect(() => {
    fetchIdeas()
    fetchAuthors()
  }, [fetchIdeas, fetchAuthors])

  // 소스 타입 변경 시 그룹핑 기본값 설정
  useEffect(() => {
    setGroupByStock(effectiveSource === 'others')
    setExpandedStocks(new Set())
  }, [effectiveSource])

  const handleFilterChange = useCallback(<K extends keyof IdeaFilters>(
    key: K,
    value: IdeaFilters[K]
  ) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
    setOffset(0)
  }, [])

  const handleResetFilters = useCallback(() => {
    setFilters({
      ...DEFAULT_FILTERS,
      source: sourceType && sourceType !== 'all' ? sourceType : 'all',
    })
    setOffset(0)
  }, [sourceType])

  const handleHashtagRemove = useCallback((tag: string) => {
    setFilters((prev) => ({
      ...prev,
      hashtags: prev.hashtags.filter((t) => t !== tag),
    }))
  }, [])

  const handleHashtagClick = useCallback((tag: string) => {
    setFilters((prev) => {
      if (prev.hashtags.includes(tag)) {
        return prev
      }
      return { ...prev, hashtags: [...prev.hashtags, tag] }
    })
  }, [])

  const handleCollect = async (collectOlder = false) => {
    setCollecting(true)
    try {
      const result = await telegramIdeaApi.collect(500, collectOlder)
      alert(`수집 완료: ${result.total_ideas}개 아이디어 (${collectOlder ? '이전 메시지' : '최신 메시지'})`)
      fetchIdeas()
    } catch (err) {
      alert('수집 실패: ' + (err instanceof Error ? err.message : '알 수 없는 오류'))
    } finally {
      setCollecting(false)
    }
  }

  const handleStockClick = (stockCode: string) => {
    navigate(`/stocks/${stockCode}`)
  }

  const handleAuthorClick = (author: string) => {
    handleFilterChange('author', author)
  }

  const handlePrevPage = () => {
    setOffset(Math.max(0, offset - limit))
  }

  const handleNextPage = () => {
    if (offset + limit < total) {
      setOffset(offset + limit)
    }
  }

  const toggleStockExpand = (stockKey: string) => {
    setExpandedStocks((prev) => {
      const next = new Set(prev)
      if (next.has(stockKey)) {
        next.delete(stockKey)
      } else {
        next.add(stockKey)
      }
      return next
    })
  }

  // 종목별 그룹핑
  const stockGroups = useMemo<StockGroup[]>(() => {
    if (!groupByStock) return []

    const groups = new Map<string, StockGroup>()

    for (const idea of ideas) {
      const key = idea.stock_code || 'no_stock'

      if (!groups.has(key)) {
        groups.set(key, {
          stockCode: idea.stock_code,
          stockName: idea.stock_name,
          ideas: [],
          latestDate: idea.original_date,
        })
      }

      const group = groups.get(key)!
      group.ideas.push(idea)

      // 최신 날짜 업데이트
      if (idea.original_date > group.latestDate) {
        group.latestDate = idea.original_date
      }
    }

    // 최신 날짜순 정렬
    return Array.from(groups.values()).sort(
      (a, b) => new Date(b.latestDate).getTime() - new Date(a.latestDate).getTime()
    )
  }, [ideas, groupByStock])

  if (loading && ideas.length === 0) {
    return <div className="text-center py-10 text-gray-500 dark:text-gray-400">로딩 중...</div>
  }

  if (error) {
    return <div className="text-center py-10 text-red-600 dark:text-red-400">{error}</div>
  }

  return (
    <div className="flex gap-6">
      {/* 메인 컨텐츠 */}
      <div className="flex-1">
        {/* 필터 패널 */}
        <div className="mb-4">
          <IdeaFilterPanel
            filters={filters}
            onFilterChange={handleFilterChange}
            onReset={handleResetFilters}
            onHashtagRemove={handleHashtagRemove}
            showSourceFilter={showSourceFilter && (!sourceType || sourceType === 'all')}
            showAuthorFilter
            compact
          />
        </div>

        {/* 액션 버튼 */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            {effectiveSource === 'others' && (
              <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                <input
                  type="checkbox"
                  checked={groupByStock}
                  onChange={(e) => setGroupByStock(e.target.checked)}
                  className="rounded border-gray-300 dark:border-gray-600"
                />
                종목별 그룹
              </label>
            )}
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              총 {total}개
            </span>
            <Button
              onClick={() => handleCollect(false)}
              disabled={collecting}
              variant="secondary"
              size="sm"
            >
              {collecting ? '수집 중...' : '최신 수집'}
            </Button>
            <Button
              onClick={() => handleCollect(true)}
              disabled={collecting}
              variant="secondary"
              size="sm"
            >
              이전 수집
            </Button>
          </div>
        </div>

        {/* 아이디어 목록 */}
        {ideas.length === 0 ? (
          <div className="text-center py-10 text-gray-500 dark:text-gray-400">
            아이디어가 없습니다.
          </div>
        ) : groupByStock && stockGroups.length > 0 ? (
          // 종목별 그룹 뷰
          <div className="space-y-3">
            {stockGroups.map((group) => {
              const key = group.stockCode || 'no_stock'
              const isExpanded = expandedStocks.has(key)
              const hasMultiple = group.ideas.length > 1

              return (
                <div
                  key={key}
                  className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden"
                >
                  {/* 그룹 헤더 */}
                  <button
                    onClick={() => hasMultiple && toggleStockExpand(key)}
                    disabled={!hasMultiple}
                    className={`w-full flex items-center justify-between p-3 ${
                      hasMultiple ? 'hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer' : ''
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {hasMultiple && (
                        <span className="text-gray-400 dark:text-gray-500">
                          {isExpanded ? '\u25BC' : '\u25B6'}
                        </span>
                      )}
                      {group.stockCode ? (
                        <span
                          onClick={(e) => {
                            e.stopPropagation()
                            handleStockClick(group.stockCode!)
                          }}
                          className="font-medium text-primary-600 dark:text-primary-400 hover:underline cursor-pointer"
                        >
                          {group.stockName || group.stockCode}
                        </span>
                      ) : (
                        <span className="font-medium text-gray-500 dark:text-gray-400">
                          종목 없음
                        </span>
                      )}
                      <span className="text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded-full">
                        {group.ideas.length}개
                      </span>
                    </div>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {new Date(group.latestDate).toLocaleDateString()}
                    </span>
                  </button>

                  {/* 아이디어 목록 (첫 번째는 항상 표시, 나머지는 펼쳤을 때만) */}
                  <div className="border-t border-gray-100 dark:border-gray-700">
                    {(isExpanded ? group.ideas : group.ideas.slice(0, 1)).map((idea, idx) => (
                      <div
                        key={idea.id}
                        className={idx > 0 ? 'border-t border-gray-100 dark:border-gray-700' : ''}
                      >
                        <TelegramIdeaCard
                          idea={idea}
                          onStockClick={handleStockClick}
                          onAuthorClick={handleAuthorClick}
                          onHashtagClick={handleHashtagClick}
                          compact
                          hideStock
                        />
                      </div>
                    ))}
                    {!isExpanded && hasMultiple && (
                      <button
                        onClick={() => toggleStockExpand(key)}
                        className="w-full py-2 text-xs text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
                      >
                        + {group.ideas.length - 1}개 더보기
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          // 기본 목록 뷰
          <div className="space-y-3">
            {ideas.map((idea) => (
              <TelegramIdeaCard
                key={idea.id}
                idea={idea}
                onStockClick={handleStockClick}
                onAuthorClick={handleAuthorClick}
                onHashtagClick={handleHashtagClick}
              />
            ))}
          </div>
        )}

        {/* 페이지네이션 */}
        {total > limit && (
          <div className="flex items-center justify-center gap-4 mt-6">
            <Button
              onClick={handlePrevPage}
              disabled={offset === 0}
              variant="secondary"
              size="sm"
            >
              이전
            </Button>
            <span className="text-sm text-gray-600 dark:text-gray-400">
              {Math.floor(offset / limit) + 1} / {Math.ceil(total / limit)}
            </span>
            <Button
              onClick={handleNextPage}
              disabled={offset + limit >= total}
              variant="secondary"
              size="sm"
            >
              다음
            </Button>
          </div>
        )}
      </div>

      {/* 사이드바: 발신자 통계 (타인 아이디어만) */}
      {effectiveSource === 'others' && authors.length > 0 && (
        <div className="w-64 shrink-0">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4 sticky top-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">
              발신자별 통계
            </h3>
            <div className="space-y-3 max-h-[60vh] overflow-y-auto">
              {authors.map((author) => (
                <button
                  key={author.name}
                  onClick={() => handleAuthorClick(author.name)}
                  className={`w-full text-left p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                    filters.author === author.name ? 'bg-primary-50 dark:bg-primary-900/20' : ''
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm text-gray-900 dark:text-gray-100 truncate">
                      {author.name}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {author.idea_count}개
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {author.top_stocks.slice(0, 3).map((stock) => (
                      <span
                        key={stock.stock_code}
                        className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 px-1.5 py-0.5 rounded"
                      >
                        {stock.stock_name}
                      </span>
                    ))}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
