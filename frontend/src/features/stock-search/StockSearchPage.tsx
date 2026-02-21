import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { stockApi, mentionsApi } from '../../services/api'
import type { TrendingMentionItem } from '../../services/api'
import { WatchlistStar } from '../../components/WatchlistStar'

const RECENT_KEY = 'stock-search-recent'
const MAX_RECENT = 10

interface RecentStock {
  code: string
  name: string
  market?: string
}

interface SearchResult {
  code: string
  name: string
  market: string
  stock_type?: string
}

function getRecentStocks(): RecentStock[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]')
  } catch {
    return []
  }
}

function addRecentStock(stock: RecentStock) {
  const list = getRecentStocks().filter((s) => s.code !== stock.code)
  list.unshift(stock)
  localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, MAX_RECENT)))
}

export default function StockSearchPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [recent, setRecent] = useState<RecentStock[]>(getRecentStocks)
  const [trending, setTrending] = useState<TrendingMentionItem[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
    mentionsApi.getTrending(7, 15).then(setTrending).catch(() => {})
  }, [])

  const search = useCallback(async (q: string) => {
    if (!q || q.length < 1) {
      setResults([])
      return
    }
    setLoading(true)
    try {
      const data = await stockApi.search(q, 20)
      setResults(data)
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [])

  const handleInput = (value: string) => {
    setQuery(value)
    setSelectedIndex(-1)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => search(value), 200)
  }

  const goToStock = (code: string, name: string, market?: string) => {
    addRecentStock({ code, name, market })
    setRecent(getRecentStocks())
    // 검색 결과가 있으면 네비게이션 컨텍스트 전달
    const navStocks = results.length > 0
      ? results.map(s => ({ code: s.code, name: s.name }))
      : trending.length > 0
      ? trending.map(s => ({ code: s.stock_code, name: s.stock_name || s.stock_code }))
      : []
    const idx = navStocks.findIndex(s => s.code === code)
    navigate(`/stocks/${code}`, {
      state: idx >= 0 ? { stockListContext: { source: '검색', stocks: navStocks, currentIndex: idx } } : undefined
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (results.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((i) => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && selectedIndex >= 0) {
      e.preventDefault()
      const s = results[selectedIndex]
      goToStock(s.code, s.name, s.market)
    }
  }

  const marketColor = (market: string) => {
    if (market === 'KOSPI') return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
    if (market === 'KOSDAQ') return 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
    if (market === 'ETF') return 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300'
    return 'bg-gray-100 text-gray-700 dark:bg-t-bg-elevated dark:text-t-text-secondary'
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      {/* 검색바 */}
      <div className="pt-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-t-text-primary mb-4 text-center">
          종목 검색
        </h1>
        <div className="relative">
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => handleInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="종목명 또는 코드를 입력하세요"
            className="w-full px-5 py-4 text-lg border-2 border-gray-300 dark:border-t-border-hover rounded-xl
              bg-white dark:bg-t-bg-card text-gray-900 dark:text-t-text-primary
              focus:border-primary-500 dark:focus:border-primary-400 focus:ring-2 focus:ring-primary-200
              dark:focus:ring-primary-800 outline-none transition-colors"
          />
          {loading && (
            <div className="absolute right-4 top-1/2 -translate-y-1/2">
              <div className="animate-spin h-5 w-5 border-2 border-gray-300 dark:border-t-border border-t-primary-500 rounded-full" />
            </div>
          )}

          {/* 검색 결과 드롭다운 */}
          {results.length > 0 && query && (
            <div className="absolute z-20 w-full mt-2 bg-white dark:bg-t-bg-card border border-gray-200 dark:border-t-border
              rounded-xl shadow-xl max-h-96 overflow-auto">
              {results.map((stock, i) => (
                <button
                  key={stock.code}
                  onClick={() => goToStock(stock.code, stock.name, stock.market)}
                  className={`w-full px-4 py-3 text-left flex items-center justify-between
                    border-b border-gray-100 dark:border-t-border last:border-0
                    hover:bg-gray-50 dark:hover:bg-t-bg-elevated transition-colors
                    ${i === selectedIndex ? 'bg-primary-50 dark:bg-primary-900/30' : ''}`}
                >
                  <div className="flex items-center gap-1">
                    <WatchlistStar stockCode={stock.code} stockName={stock.name} />
                    <div>
                      <div className="font-medium text-gray-900 dark:text-t-text-primary">{stock.name}</div>
                      <div className="text-xs text-gray-500 dark:text-t-text-muted">{stock.code}</div>
                    </div>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded ${marketColor(stock.market)}`}>
                    {stock.market}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 최근 검색 */}
      {!query && recent.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-gray-500 dark:text-t-text-muted mb-3">최근 검색</h2>
          <div className="flex flex-wrap gap-2">
            {recent.map((s) => (
              <div key={s.code} className="flex items-center gap-0.5">
                <WatchlistStar stockCode={s.code} stockName={s.name} />
                <button
                  onClick={() => goToStock(s.code, s.name, s.market)}
                  className="px-3 py-1.5 bg-white dark:bg-t-bg-card border border-gray-200 dark:border-t-border
                    rounded-lg text-sm text-gray-700 dark:text-t-text-secondary
                    hover:bg-gray-50 dark:hover:bg-t-bg-elevated transition-colors"
                >
                  {s.name}
                  <span className="text-gray-400 dark:text-t-text-muted ml-1.5">{s.code}</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 인기 종목 */}
      {!query && trending.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-gray-500 dark:text-t-text-muted mb-3">인기 언급 종목</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {trending.map((item, i) => (
              <button
                key={item.stock_code}
                onClick={() => goToStock(item.stock_code, item.stock_name)}
                className="flex items-center gap-3 px-4 py-3 bg-white dark:bg-t-bg-card border border-gray-200 dark:border-t-border
                  rounded-lg hover:bg-gray-50 dark:hover:bg-t-bg-elevated transition-colors text-left"
              >
                <span className="text-lg font-bold text-gray-400 dark:text-t-text-muted w-6 text-right">
                  {i + 1}
                </span>
                <WatchlistStar stockCode={item.stock_code} stockName={item.stock_name || item.stock_code} />
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-gray-900 dark:text-t-text-primary truncate">
                    {item.stock_name || item.stock_code}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-t-text-muted">
                    {item.stock_code}
                    {item.source_count > 1 && (
                      <span className="ml-2 text-primary-600 dark:text-primary-400">
                        {item.source_count}개 소스
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold text-gray-900 dark:text-t-text-primary">
                    {item.total_mentions}
                  </div>
                  <div className="text-xs text-gray-400 dark:text-t-text-muted">언급</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
