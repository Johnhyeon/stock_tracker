import { useEffect, useState, useCallback, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ideaApi, telegramIdeaApi } from '../../../services/api'
import TelegramIdeaCard from '../TelegramIdeaCard'
import IdeaFilterPanel from '../components/IdeaFilterPanel'
import Badge from '../../../components/ui/Badge'
import { Card, CardContent } from '../../../components/ui/Card'
import type { Idea, IdeaStatus, IdeaType } from '../../../types/idea'
import type { TelegramIdea } from '../../../types/telegram_idea'
import type { IdeaFilters } from '../hooks/useIdeaFilters'

interface UnifiedItem {
  type: 'manual' | 'telegram'
  date: Date
  data: Idea | TelegramIdea
}

const statusLabels: Record<IdeaStatus, string> = {
  active: '활성',
  exited: '청산',
  watching: '관찰',
}

const typeLabels: Record<IdeaType, string> = {
  research: '리서치',
  chart: '차트',
}

const DEFAULT_FILTERS: IdeaFilters = {
  period: 30,
  source: 'all',
  sentiment: 'all',
  search: '',
  hashtags: [],
  author: null,
}

// 수동 아이디어 카드
function ManualIdeaCard({ idea }: { idea: Idea }) {
  return (
    <Link to={`/ideas/${idea.id}`}>
      <Card className="hover:shadow-md transition-shadow">
        <CardContent className="p-4">
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="info" size="sm">수동</Badge>
              <Badge variant={idea.type === 'research' ? 'default' : 'warning'} size="sm">
                {typeLabels[idea.type]}
              </Badge>
              <span className="font-semibold text-gray-900 dark:text-t-text-primary">
                {idea.tickers.join(', ') || '종목 미지정'}
              </span>
            </div>
            <Badge variant={idea.status === 'active' ? 'success' : 'default'} size="sm">
              {statusLabels[idea.status]}
            </Badge>
          </div>

          <p className="text-sm text-gray-600 dark:text-t-text-muted line-clamp-2 mb-2">
            {idea.thesis}
          </p>

          <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-t-text-muted">
            <span>목표: {Number(idea.target_return_pct)}%</span>
            <span>기간: {idea.expected_timeframe_days}일</span>
            <span>{new Date(idea.created_at).toLocaleDateString()}</span>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

export default function UnifiedIdeaList() {
  const navigate = useNavigate()
  const [manualIdeas, setManualIdeas] = useState<Idea[]>([])
  const [telegramIdeas, setTelegramIdeas] = useState<TelegramIdea[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<IdeaFilters>(DEFAULT_FILTERS)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // 두 가지 데이터 소스 병렬 로드
      const [manualRes, telegramRes] = await Promise.all([
        ideaApi.list(),
        telegramIdeaApi.list({
          days: filters.period,
          sentiment: filters.sentiment !== 'all' ? filters.sentiment : undefined,
          author: filters.author || undefined,
          limit: 200,
        }),
      ])

      setManualIdeas(manualRes)
      setTelegramIdeas(telegramRes.items)
    } catch (err) {
      setError(err instanceof Error ? err.message : '데이터를 불러오는 데 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }, [filters.period, filters.sentiment, filters.author])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleFilterChange = useCallback(<K extends keyof IdeaFilters>(
    key: K,
    value: IdeaFilters[K]
  ) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }, [])

  const handleResetFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS)
  }, [])

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

  // 종목상세 네비게이션 컨텍스트
  const stockNavList = useMemo(() => {
    const seen = new Set<string>()
    return telegramIdeas
      .filter(i => { if (!i.stock_code || seen.has(i.stock_code)) return false; seen.add(i.stock_code); return true })
      .map(i => ({ code: i.stock_code!, name: i.stock_name || i.stock_code! }))
  }, [telegramIdeas])

  const handleStockClick = (stockCode: string) => {
    const idx = stockNavList.findIndex(s => s.code === stockCode)
    navigate(`/stocks/${stockCode}`, {
      state: { stockListContext: { source: '아이디어', stocks: stockNavList, currentIndex: Math.max(0, idx) } }
    })
  }

  const handleAuthorClick = (author: string) => {
    handleFilterChange('author', author)
  }

  // 통합 목록 생성 및 정렬
  const unifiedItems = useMemo<UnifiedItem[]>(() => {
    const items: UnifiedItem[] = []

    // 수동 아이디어 추가 (소스 필터 확인)
    if (filters.source === 'all' || filters.source === 'my') {
      for (const idea of manualIdeas) {
        // 검색어 필터링
        if (filters.search) {
          const searchLower = filters.search.toLowerCase()
          const matchesTicker = idea.tickers.some((t) =>
            t.toLowerCase().includes(searchLower)
          )
          if (!matchesTicker) continue
        }

        items.push({
          type: 'manual',
          date: new Date(idea.created_at),
          data: idea,
        })
      }
    }

    // 텔레그램 아이디어 추가 (소스 필터 확인)
    for (const idea of telegramIdeas) {
      // 소스 필터
      if (filters.source !== 'all') {
        if (filters.source === 'my' && idea.source_type !== 'my') continue
        if (filters.source === 'others' && idea.source_type !== 'others') continue
      }

      // 검색어 필터링
      if (filters.search) {
        const searchLower = filters.search.toLowerCase()
        const matchesStock =
          idea.stock_name?.toLowerCase().includes(searchLower) ||
          idea.stock_code?.toLowerCase().includes(searchLower)
        if (!matchesStock) continue
      }

      // 해시태그 필터링
      if (filters.hashtags.length > 0) {
        const hasMatchingTag = filters.hashtags.some((tag) =>
          idea.raw_hashtags?.includes(tag)
        )
        if (!hasMatchingTag) continue
      }

      items.push({
        type: 'telegram',
        date: new Date(idea.original_date),
        data: idea,
      })
    }

    // 날짜순 정렬 (최신순)
    items.sort((a, b) => b.date.getTime() - a.date.getTime())

    return items
  }, [manualIdeas, telegramIdeas, filters])

  if (loading) {
    return <div className="text-center py-10 text-gray-500 dark:text-t-text-muted">로딩 중...</div>
  }

  if (error) {
    return <div className="text-center py-10 text-red-600 dark:text-red-400">{error}</div>
  }

  return (
    <div>
      {/* 필터 패널 */}
      <div className="mb-4">
        <IdeaFilterPanel
          filters={filters}
          onFilterChange={handleFilterChange}
          onReset={handleResetFilters}
          onHashtagRemove={handleHashtagRemove}
          showSourceFilter
          showAuthorFilter
          compact
        />
      </div>

      {/* 통계 */}
      <div className="flex items-center gap-4 mb-4 text-sm text-gray-500 dark:text-t-text-muted">
        <span>총 {unifiedItems.length}개</span>
        <span>수동: {unifiedItems.filter((i) => i.type === 'manual').length}개</span>
        <span>텔레그램: {unifiedItems.filter((i) => i.type === 'telegram').length}개</span>
      </div>

      {/* 통합 목록 */}
      {unifiedItems.length === 0 ? (
        <div className="text-center py-10 text-gray-500 dark:text-t-text-muted">
          아이디어가 없습니다.
        </div>
      ) : (
        <div className="space-y-3">
          {unifiedItems.map((item) =>
            item.type === 'manual' ? (
              <ManualIdeaCard key={`manual-${(item.data as Idea).id}`} idea={item.data as Idea} />
            ) : (
              <TelegramIdeaCard
                key={`telegram-${(item.data as TelegramIdea).id}`}
                idea={item.data as TelegramIdea}
                onStockClick={handleStockClick}
                onAuthorClick={handleAuthorClick}
                onHashtagClick={handleHashtagClick}
              />
            )
          )}
        </div>
      )}
    </div>
  )
}
