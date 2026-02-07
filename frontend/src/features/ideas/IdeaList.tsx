import { useEffect, useState, useMemo, lazy, Suspense } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useIdeaStore } from '../../store/useIdeaStore'
import { Card, CardContent } from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Select from '../../components/ui/Select'
import TelegramIdeaList from './TelegramIdeaList'
import type { Idea, IdeaStatus, IdeaType } from '../../types/idea'

// Lazy load heavy components
const UnifiedIdeaList = lazy(() => import('./views/UnifiedIdeaList'))
const IdeaAnalytics = lazy(() => import('./views/IdeaAnalytics'))

type ViewMode = 'card' | 'list'
type TabType = 'unified' | 'manual' | 'telegram' | 'analytics'

const TAB_LABELS: Record<TabType, string> = {
  unified: '통합',
  manual: '수동',
  telegram: '텔레그램',
  analytics: '분석',
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

const healthBadge = (health: string, size: 'sm' | 'md' = 'sm') => {
  const variants: Record<string, 'success' | 'warning' | 'danger'> = {
    healthy: 'success',
    deteriorating: 'warning',
    broken: 'danger',
  }
  const labels: Record<string, string> = {
    healthy: '건강',
    deteriorating: '악화',
    broken: '손상',
  }
  return variants[health] ? (
    <Badge variant={variants[health]} size={size}>
      {labels[health]}
    </Badge>
  ) : null
}

// thesis에서 이미지 URL 추출
function extractImages(text: string): string[] {
  const markdownImagePattern = /!\[.*?\]\((https?:\/\/[^\s)]+)\)/g
  const plainUrlPattern = /(https?:\/\/[^\s<>]+\.(?:jpg|jpeg|png|gif|webp|bmp|svg)(?:\?[^\s<>]*)?)/gi

  const images: string[] = []
  let match

  while ((match = markdownImagePattern.exec(text)) !== null) {
    images.push(match[1])
  }

  if (images.length === 0) {
    while ((match = plainUrlPattern.exec(text)) !== null) {
      images.push(match[0])
    }
  }

  return images
}

// thesis에서 이미지 관련 텍스트 제거하고 순수 텍스트만 추출
function extractText(text: string): string {
  return text
    .replace(/!\[.*?\]\([^)]+\)/g, '')
    .replace(/(https?:\/\/[^\s<>]+\.(?:jpg|jpeg|png|gif|webp|bmp|svg)(?:\?[^\s<>]*)?)/gi, '')
    .replace(/\n+/g, ' ')
    .trim()
}

// 뷰 모드 토글 버튼
function ViewModeToggle({
  viewMode,
  onChange,
}: {
  viewMode: ViewMode
  onChange: (mode: ViewMode) => void
}) {
  return (
    <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-700 rounded-lg p-1">
      <button
        onClick={() => onChange('card')}
        className={`p-1.5 rounded transition-colors ${
          viewMode === 'card' ? 'bg-white dark:bg-gray-600 shadow-sm text-primary-600 dark:text-primary-400' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
        }`}
        title="카드 보기"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
        </svg>
      </button>
      <button
        onClick={() => onChange('list')}
        className={`p-1.5 rounded transition-colors ${
          viewMode === 'list' ? 'bg-white dark:bg-gray-600 shadow-sm text-primary-600 dark:text-primary-400' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
        }`}
        title="목록 보기"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
    </div>
  )
}

// 카드 뷰 컴포넌트
function IdeaCard({ idea }: { idea: Idea }) {
  const images = useMemo(() => extractImages(idea.thesis), [idea.thesis])
  const textContent = useMemo(() => extractText(idea.thesis), [idea.thesis])

  return (
    <Link to={`/ideas/${idea.id}`}>
      <Card className="hover:shadow-md transition-shadow h-full">
        <CardContent>
          <div className="flex items-center justify-between mb-3">
            <Badge variant={idea.type === 'research' ? 'info' : 'default'}>
              {typeLabels[idea.type]}
            </Badge>
            {healthBadge(idea.fundamental_health)}
          </div>

          <div className="mb-2">
            <span className="text-sm text-gray-500 dark:text-gray-400">종목:</span>
            <span className="ml-2 font-medium text-gray-900 dark:text-gray-100">
              {idea.tickers.join(', ') || '-'}
            </span>
          </div>

          {idea.sector && (
            <div className="mb-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">섹터:</span>
              <span className="ml-2 text-gray-900 dark:text-gray-100">{idea.sector}</span>
            </div>
          )}

          {images.length > 0 && (
            <div className="mb-3 -mx-2">
              <img
                src={images[0]}
                alt="아이디어 이미지"
                className="w-full h-32 object-cover rounded-lg"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = 'none'
                }}
              />
            </div>
          )}

          <p className="text-sm text-gray-700 dark:text-gray-300 line-clamp-3 mb-3">
            {textContent || idea.thesis}
          </p>

          <div className="flex justify-between items-center text-sm text-gray-500 dark:text-gray-400">
            <span>목표: {Number(idea.target_return_pct)}%</span>
            <span>기간: {idea.expected_timeframe_days}일</span>
          </div>

          <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
            <Badge variant={idea.status === 'active' ? 'success' : 'default'}>
              {statusLabels[idea.status]}
            </Badge>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

// 목록 뷰 컴포넌트
function IdeaListItem({ idea }: { idea: Idea }) {
  const images = useMemo(() => extractImages(idea.thesis), [idea.thesis])
  const textContent = useMemo(() => extractText(idea.thesis), [idea.thesis])

  return (
    <Link to={`/ideas/${idea.id}`}>
      <div className="flex gap-4 p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:shadow-md transition-shadow">
        {images.length > 0 && (
          <div className="flex-shrink-0">
            <img
              src={images[0]}
              alt="아이디어 이미지"
              className="w-20 h-20 object-cover rounded-lg"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none'
              }}
            />
          </div>
        )}

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <Badge variant={idea.type === 'research' ? 'info' : 'default'} size="sm">
              {typeLabels[idea.type]}
            </Badge>
            <span className="font-semibold text-base truncate text-gray-900 dark:text-gray-100">
              {idea.tickers.join(', ') || '종목 미지정'}
            </span>
            {idea.sector && (
              <span className="text-xs text-gray-500 dark:text-gray-400">({idea.sector})</span>
            )}
            {healthBadge(idea.fundamental_health, 'sm')}
            <Badge variant={idea.status === 'active' ? 'success' : 'default'} size="sm">
              {statusLabels[idea.status]}
            </Badge>
          </div>

          <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-1 mb-2">{textContent || idea.thesis}</p>

          <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
            <span>목표: {Number(idea.target_return_pct)}%</span>
            <span>기간: {idea.expected_timeframe_days}일</span>
            <span className="text-gray-400 dark:text-gray-500">
              {new Date(idea.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
      </div>
    </Link>
  )
}

// 수동 아이디어 목록 (기존)
function ManualIdeaList() {
  const { ideas, loading, error, fetchIdeas } = useIdeaStore()
  const [filterStatus, setFilterStatus] = useState<string>('')
  const [filterType, setFilterType] = useState<string>('')
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    const saved = localStorage.getItem('idea-list-view-mode')
    return (saved as ViewMode) || 'card'
  })

  useEffect(() => {
    const params: { status?: string; type?: string } = {}
    if (filterStatus) params.status = filterStatus
    if (filterType) params.type = filterType
    fetchIdeas(params)
  }, [fetchIdeas, filterStatus, filterType])

  useEffect(() => {
    localStorage.setItem('idea-list-view-mode', viewMode)
  }, [viewMode])

  if (loading) {
    return <div className="text-center py-10 text-gray-500 dark:text-gray-400">로딩 중...</div>
  }

  if (error) {
    return <div className="text-center py-10 text-red-600 dark:text-red-400">{error}</div>
  }

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <Select
          options={[
            { value: '', label: '모든 상태' },
            { value: 'active', label: '활성' },
            { value: 'watching', label: '관찰' },
            { value: 'exited', label: '청산' },
          ]}
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
        />
        <Select
          options={[
            { value: '', label: '모든 유형' },
            { value: 'research', label: '리서치' },
            { value: 'chart', label: '차트' },
          ]}
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
        />
        <ViewModeToggle viewMode={viewMode} onChange={setViewMode} />
      </div>

      {ideas.length === 0 ? (
        <div className="text-center py-10 text-gray-500 dark:text-gray-400">
          아이디어가 없습니다. 새로운 아이디어를 추가해보세요.
        </div>
      ) : viewMode === 'card' ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {ideas.map((idea: Idea) => (
            <IdeaCard key={idea.id} idea={idea} />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {ideas.map((idea: Idea) => (
            <IdeaListItem key={idea.id} idea={idea} />
          ))}
        </div>
      )}
    </div>
  )
}

// 탭 컴포넌트
function Tab({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
        active
          ? 'border-primary-600 text-primary-600 dark:border-primary-400 dark:text-primary-400'
          : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
      }`}
    >
      {label}
    </button>
  )
}

// 로딩 스피너
function LoadingSpinner() {
  return (
    <div className="text-center py-10 text-gray-500 dark:text-gray-400">
      로딩 중...
    </div>
  )
}

export default function IdeaList() {
  const [searchParams, setSearchParams] = useSearchParams()

  // URL에서 탭 상태 읽기
  const activeTab = useMemo<TabType>(() => {
    const tabParam = searchParams.get('tab')
    if (tabParam && ['unified', 'manual', 'telegram', 'analytics'].includes(tabParam)) {
      return tabParam as TabType
    }
    // localStorage fallback
    const saved = localStorage.getItem('idea-list-active-tab')
    if (saved && ['unified', 'manual', 'telegram', 'analytics'].includes(saved)) {
      return saved as TabType
    }
    return 'unified'
  }, [searchParams])

  const setActiveTab = (tab: TabType) => {
    setSearchParams({ tab })
    localStorage.setItem('idea-list-active-tab', tab)
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">아이디어</h1>
      </div>

      {/* 탭 */}
      <div className="flex border-b border-gray-200 dark:border-gray-700 mb-6">
        {(Object.keys(TAB_LABELS) as TabType[]).map((tab) => (
          <Tab
            key={tab}
            label={TAB_LABELS[tab]}
            active={activeTab === tab}
            onClick={() => setActiveTab(tab)}
          />
        ))}
      </div>

      {/* 탭 내용 */}
      <Suspense fallback={<LoadingSpinner />}>
        {activeTab === 'unified' && <UnifiedIdeaList />}
        {activeTab === 'manual' && <ManualIdeaList />}
        {activeTab === 'telegram' && <TelegramIdeaList showSourceFilter />}
        {activeTab === 'analytics' && <IdeaAnalytics />}
      </Suspense>
    </div>
  )
}
