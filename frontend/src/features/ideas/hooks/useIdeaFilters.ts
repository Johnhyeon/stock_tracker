import { useState, useCallback, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

export type SentimentFilter = 'all' | 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL'
export type SourceFilter = 'all' | 'my' | 'others'

export interface IdeaFilters {
  period: number          // 7, 14, 30, 90
  source: SourceFilter    // all, my, others
  sentiment: SentimentFilter
  search: string          // 종목명/코드 검색
  hashtags: string[]      // 선택된 해시태그
  author: string | null   // 발신자 필터
}

const DEFAULT_FILTERS: IdeaFilters = {
  period: 7,
  source: 'all',
  sentiment: 'all',
  search: '',
  hashtags: [],
  author: null,
}

const STORAGE_KEY = 'idea-filters'

interface UseIdeaFiltersReturn {
  filters: IdeaFilters
  setFilters: React.Dispatch<React.SetStateAction<IdeaFilters>>
  updateFilter: <K extends keyof IdeaFilters>(key: K, value: IdeaFilters[K]) => void
  resetFilters: () => void
  addHashtag: (tag: string) => void
  removeHashtag: (tag: string) => void
  toggleHashtag: (tag: string) => void
  clearHashtags: () => void
}

/**
 * 아이디어 필터 상태 관리 훅
 * - URL 파라미터 동기화 (공유 가능)
 * - localStorage 저장 (기본값 유지)
 */
export function useIdeaFilters(): UseIdeaFiltersReturn {
  const [searchParams, setSearchParams] = useSearchParams()

  // URL 또는 localStorage에서 초기값 로드
  const getInitialFilters = (): IdeaFilters => {
    // URL 파라미터 우선
    const periodParam = searchParams.get('period')
    const sourceParam = searchParams.get('source')
    const sentimentParam = searchParams.get('sentiment')
    const searchParam = searchParams.get('search')
    const hashtagsParam = searchParams.get('hashtags')
    const authorParam = searchParams.get('author')

    const hasUrlParams = periodParam || sourceParam || sentimentParam ||
                         searchParam || hashtagsParam || authorParam

    if (hasUrlParams) {
      return {
        period: periodParam ? parseInt(periodParam, 10) : DEFAULT_FILTERS.period,
        source: (sourceParam as SourceFilter) || DEFAULT_FILTERS.source,
        sentiment: (sentimentParam as SentimentFilter) || DEFAULT_FILTERS.sentiment,
        search: searchParam || DEFAULT_FILTERS.search,
        hashtags: hashtagsParam ? hashtagsParam.split(',').filter(Boolean) : [],
        author: authorParam || null,
      }
    }

    // localStorage에서 로드
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        return { ...DEFAULT_FILTERS, ...parsed }
      }
    } catch {
      // 무시
    }

    return DEFAULT_FILTERS
  }

  const [filters, setFilters] = useState<IdeaFilters>(getInitialFilters)

  // URL 및 localStorage 동기화
  useEffect(() => {
    const params = new URLSearchParams()

    // 기본값과 다른 경우에만 URL에 추가
    if (filters.period !== DEFAULT_FILTERS.period) {
      params.set('period', String(filters.period))
    }
    if (filters.source !== DEFAULT_FILTERS.source) {
      params.set('source', filters.source)
    }
    if (filters.sentiment !== DEFAULT_FILTERS.sentiment) {
      params.set('sentiment', filters.sentiment)
    }
    if (filters.search) {
      params.set('search', filters.search)
    }
    if (filters.hashtags.length > 0) {
      params.set('hashtags', filters.hashtags.join(','))
    }
    if (filters.author) {
      params.set('author', filters.author)
    }

    setSearchParams(params, { replace: true })

    // localStorage에 저장
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filters))
    } catch {
      // 무시
    }
  }, [filters, setSearchParams])

  const updateFilter = useCallback(<K extends keyof IdeaFilters>(
    key: K,
    value: IdeaFilters[K]
  ) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }, [])

  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS)
  }, [])

  const addHashtag = useCallback((tag: string) => {
    setFilters(prev => {
      if (prev.hashtags.includes(tag)) return prev
      return { ...prev, hashtags: [...prev.hashtags, tag] }
    })
  }, [])

  const removeHashtag = useCallback((tag: string) => {
    setFilters(prev => ({
      ...prev,
      hashtags: prev.hashtags.filter(t => t !== tag)
    }))
  }, [])

  const toggleHashtag = useCallback((tag: string) => {
    setFilters(prev => {
      if (prev.hashtags.includes(tag)) {
        return { ...prev, hashtags: prev.hashtags.filter(t => t !== tag) }
      }
      return { ...prev, hashtags: [...prev.hashtags, tag] }
    })
  }, [])

  const clearHashtags = useCallback(() => {
    setFilters(prev => ({ ...prev, hashtags: [] }))
  }, [])

  return {
    filters,
    setFilters,
    updateFilter,
    resetFilters,
    addHashtag,
    removeHashtag,
    toggleHashtag,
    clearHashtags,
  }
}
