import { useEffect, useState, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { telegramIdeaApi, ideaApi } from '../../services/api'
import type { SparklineMap } from '../../components/MiniSparkline'
import TelegramIdeaCard from './TelegramIdeaCard'
import IdeaFilterPanel from './components/IdeaFilterPanel'
import Button from '../../components/ui/Button'
import type { TelegramIdea, IdeaSourceType, AuthorStats } from '../../types/telegram_idea'
import type { IdeaFilters } from './hooks/useIdeaFilters'

interface TelegramIdeaListProps {
  sourceType?: IdeaSourceType | 'all'
  showSourceFilter?: boolean
  initialFilters?: Partial<IdeaFilters>
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
  const [sparklineMap, setSparklineMap] = useState<SparklineMap>({})
  const [expandedStocks, setExpandedStocks] = useState<Set<string>>(new Set())
  const [groupByStock, setGroupByStock] = useState(
    sourceType === 'others' || filters.source === 'others'
  )

  const limit = 100

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

      if (effectiveSource) params.source = effectiveSource
      if (filters.author) params.author = filters.author
      if (filters.sentiment !== 'all') params.sentiment = filters.sentiment

      const response = await telegramIdeaApi.list(params)

      let filteredItems = response.items

      if (filters.search) {
        const searchLower = filters.search.toLowerCase()
        filteredItems = filteredItems.filter(
          (idea: TelegramIdea) =>
            (idea.stock_name?.toLowerCase().includes(searchLower)) ||
            (idea.stock_code?.toLowerCase().includes(searchLower))
        )
      }

      if (filters.hashtags.length > 0) {
        filteredItems = filteredItems.filter((idea: TelegramIdea) =>
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

  // 아이디어 로드 후 종목 스파크라인 데이터 가져오기
  useEffect(() => {
    const codes = [...new Set(ideas.filter((i) => i.stock_code).map((i) => i.stock_code!))]
    if (codes.length > 0) {
      ideaApi.getStockSparklines(60, codes).then(setSparklineMap).catch(() => {})
    }
  }, [ideas])

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
      if (prev.hashtags.includes(tag)) return prev
      return { ...prev, hashtags: [...prev.hashtags, tag] }
    })
  }, [])

  const handleCollect = async () => {
    setCollecting(true)
    try {
      const result = await telegramIdeaApi.collect(500)
      alert(`수집 완료: ${result.total_ideas || 0}개 아이디어`)
      fetchIdeas()
    } catch (err) {
      alert('수집 실패: ' + (err instanceof Error ? err.message : '알 수 없는 오류'))
    } finally {
      setCollecting(false)
    }
  }

  // 종목상세 네비게이션 컨텍스트
  const stockNavList = useMemo(() => {
    const seen = new Set<string>()
    return ideas
      .filter(i => { if (!i.stock_code || seen.has(i.stock_code)) return false; seen.add(i.stock_code); return true })
      .map(i => ({ code: i.stock_code!, name: i.stock_name || i.stock_code! }))
  }, [ideas])

  const handleStockClick = (stockCode: string) => {
    const idx = stockNavList.findIndex(s => s.code === stockCode)
    navigate(`/stocks/${stockCode}`, {
      state: { stockListContext: { source: '텔레그램', stocks: stockNavList, currentIndex: Math.max(0, idx) } }
    })
  }
  const handleAuthorClick = (author: string) => handleFilterChange('author', author)
  const handlePrevPage = () => setOffset(Math.max(0, offset - limit))
  const handleNextPage = () => { if (offset + limit < total) setOffset(offset + limit) }

  const toggleStockExpand = (stockKey: string) => {
    setExpandedStocks((prev) => {
      const next = new Set(prev)
      if (next.has(stockKey)) next.delete(stockKey)
      else next.add(stockKey)
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
      if (idea.original_date > group.latestDate) group.latestDate = idea.original_date
    }
    return Array.from(groups.values()).sort(
      (a, b) => new Date(b.latestDate).getTime() - new Date(a.latestDate).getTime()
    )
  }, [ideas, groupByStock])

  if (loading && ideas.length === 0) {
    return <div className="text-center py-10 text-gray-500 dark:text-t-text-muted">로딩 중...</div>
  }

  if (error) {
    return <div className="text-center py-10 text-red-600 dark:text-red-400">{error}</div>
  }

  // 필터 바 우측 액션들
  const filterExtraActions = (
    <div className="flex items-center gap-2">
      {effectiveSource === 'others' && (
        <label className="flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-t-text-muted cursor-pointer">
          <input
            type="checkbox"
            checked={groupByStock}
            onChange={(e) => setGroupByStock(e.target.checked)}
            className="rounded border-gray-300 dark:border-t-border-hover w-3 h-3"
          />
          종목별
        </label>
      )}
      <span className="text-[11px] text-gray-400 dark:text-t-text-muted">{total}개</span>
      <Button onClick={handleCollect} disabled={collecting} variant="secondary" size="sm">
        {collecting ? '...' : '수집'}
      </Button>
    </div>
  )

  return (
    <div className="flex gap-4">
      {/* 메인 컨텐츠 */}
      <div className="flex-1 min-w-0">
        {/* 필터 + 액션 (한 줄) */}
        <div className="mb-4">
          <IdeaFilterPanel
            filters={filters}
            onFilterChange={handleFilterChange}
            onReset={handleResetFilters}
            onHashtagRemove={handleHashtagRemove}
            showSourceFilter={showSourceFilter && (!sourceType || sourceType === 'all')}
            showAuthorFilter
            extraActions={filterExtraActions}
          />
        </div>

        {/* 아이디어 목록 */}
        {ideas.length === 0 ? (
          <div className="text-center py-10 text-gray-500 dark:text-t-text-muted">
            아이디어가 없습니다.
          </div>
        ) : groupByStock && stockGroups.length > 0 ? (
          // 종목별 그룹 뷰
          <div className="space-y-2">
            {stockGroups.map((group) => {
              const key = group.stockCode || 'no_stock'
              const isExpanded = expandedStocks.has(key)
              const hasMultiple = group.ideas.length > 1

              return (
                <div
                  key={key}
                  className="bg-white dark:bg-t-bg-card rounded-lg border border-gray-200 dark:border-t-border overflow-hidden"
                >
                  <button
                    onClick={() => hasMultiple && toggleStockExpand(key)}
                    disabled={!hasMultiple}
                    className={`w-full flex items-center justify-between px-3 py-2 ${
                      hasMultiple ? 'hover:bg-gray-50 dark:hover:bg-t-border/50 cursor-pointer' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {hasMultiple && (
                        <span className="text-xs text-gray-400 dark:text-t-text-muted">
                          {isExpanded ? '\u25BC' : '\u25B6'}
                        </span>
                      )}
                      {group.stockCode ? (
                        <span
                          onClick={(e) => {
                            e.stopPropagation()
                            handleStockClick(group.stockCode!)
                          }}
                          className="text-sm font-medium text-primary-600 dark:text-primary-400 hover:underline cursor-pointer"
                        >
                          {group.stockName || group.stockCode}
                        </span>
                      ) : (
                        <span className="text-sm text-gray-500 dark:text-t-text-muted">종목 없음</span>
                      )}
                      <span className="text-[10px] text-gray-500 dark:text-t-text-muted bg-gray-100 dark:bg-t-bg-elevated px-1.5 py-0.5 rounded-full">
                        {group.ideas.length}
                      </span>
                    </div>
                    <span className="text-[10px] text-gray-500 dark:text-t-text-muted">
                      {new Date(group.latestDate).toLocaleDateString()}
                    </span>
                  </button>

                  <div className="border-t border-gray-100 dark:border-t-border">
                    {(isExpanded ? group.ideas : group.ideas.slice(0, 1)).map((idea, idx) => (
                      <div
                        key={idea.id}
                        className={idx > 0 ? 'border-t border-gray-100 dark:border-t-border' : ''}
                      >
                        <TelegramIdeaCard
                          idea={idea}
                          onStockClick={handleStockClick}
                          onAuthorClick={handleAuthorClick}
                          onHashtagClick={handleHashtagClick}
                          compact
                          hideStock
                          sparklineMap={sparklineMap}
                        />
                      </div>
                    ))}
                    {!isExpanded && hasMultiple && (
                      <button
                        onClick={() => toggleStockExpand(key)}
                        className="w-full py-1.5 text-[10px] text-gray-500 dark:text-t-text-muted hover:bg-gray-50 dark:hover:bg-t-border/50"
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
          // 그리드 뷰 (3-4열)
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {ideas.map((idea) => (
              <TelegramIdeaCard
                key={idea.id}
                idea={idea}
                onStockClick={handleStockClick}
                onAuthorClick={handleAuthorClick}
                onHashtagClick={handleHashtagClick}
                sparklineMap={sparklineMap}
              />
            ))}
          </div>
        )}

        {/* 페이지네이션 */}
        {total > limit && (
          <div className="flex items-center justify-center gap-3 mt-4">
            <Button onClick={handlePrevPage} disabled={offset === 0} variant="secondary" size="sm">
              이전
            </Button>
            <span className="text-xs text-gray-500 dark:text-t-text-muted">
              {Math.floor(offset / limit) + 1} / {Math.ceil(total / limit)}
            </span>
            <Button onClick={handleNextPage} disabled={offset + limit >= total} variant="secondary" size="sm">
              다음
            </Button>
          </div>
        )}
      </div>

      {/* 사이드바: 발신자 통계 */}
      {effectiveSource === 'others' && authors.length > 0 && (
        <div className="w-56 shrink-0 hidden lg:block">
          <div className="bg-white dark:bg-t-bg-card rounded-lg border border-gray-200 dark:border-t-border p-3 sticky top-4">
            <h3 className="text-xs font-semibold text-gray-700 dark:text-t-text-secondary mb-3">
              발신자 통계
            </h3>
            <div className="space-y-1.5 max-h-[60vh] overflow-y-auto">
              {authors.map((author) => (
                <button
                  key={author.name}
                  onClick={() => handleAuthorClick(author.name)}
                  className={`w-full text-left p-1.5 rounded text-xs hover:bg-gray-100 dark:hover:bg-t-border/50 transition-colors ${
                    filters.author === author.name ? 'bg-primary-50 dark:bg-primary-900/20' : ''
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-gray-900 dark:text-t-text-primary truncate">
                      {author.name}
                    </span>
                    <span className="text-gray-400 dark:text-t-text-muted ml-1">
                      {author.idea_count}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-0.5 mt-0.5">
                    {author.top_stocks.slice(0, 3).map((stock) => (
                      <span
                        key={stock.stock_code}
                        className="text-[10px] bg-gray-100 dark:bg-t-bg-elevated text-gray-500 dark:text-t-text-muted px-1 py-0.5 rounded"
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
