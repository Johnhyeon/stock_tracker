import { useState, useRef, useEffect, useCallback } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Stock {
  code: string
  name: string
  market: string
  stock_type: string | null
}

interface TickerSearchProps {
  onSelect: (stock: Stock) => void
  placeholder?: string
}

export default function TickerSearch({ onSelect, placeholder = '종목명 또는 코드 검색' }: TickerSearchProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Stock[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const [loading, setLoading] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const searchStocks = useCallback(async (searchQuery: string) => {
    if (!searchQuery || searchQuery.length < 1) {
      setResults([])
      setIsOpen(false)
      return
    }

    setLoading(true)
    try {
      const response = await fetch(
        `${API_URL}/api/v1/stocks/search?q=${encodeURIComponent(searchQuery)}&limit=15`
      )
      if (response.ok) {
        const data = await response.json()
        setResults(data)
        setIsOpen(data.length > 0)
      }
    } catch (err) {
      console.error('Search error:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const handleInputChange = (value: string) => {
    setQuery(value)
    setSelectedIndex(-1)

    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }

    debounceRef.current = setTimeout(() => {
      searchStocks(value)
    }, 200)
  }

  const handleSelect = (stock: Stock) => {
    onSelect(stock)
    setQuery('')
    setResults([])
    setIsOpen(false)
    inputRef.current?.focus()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) return

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex((prev) => (prev < results.length - 1 ? prev + 1 : prev))
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : prev))
        break
      case 'Enter':
        e.preventDefault()
        if (selectedIndex >= 0 && results[selectedIndex]) {
          handleSelect(results[selectedIndex])
        }
        break
      case 'Escape':
        setIsOpen(false)
        break
    }
  }

  const getMarketColor = (market: string) => {
    switch (market) {
      case 'KOSPI':
        return 'bg-blue-100 text-blue-700'
      case 'KOSDAQ':
        return 'bg-green-100 text-green-700'
      case 'ETF':
        return 'bg-purple-100 text-purple-700'
      default:
        return 'bg-gray-100 dark:bg-t-bg-elevated text-gray-700 dark:text-t-text-secondary'
    }
  }

  return (
    <div ref={wrapperRef} className="relative">
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => handleInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => query && results.length > 0 && setIsOpen(true)}
          placeholder={placeholder}
          className="block w-full rounded-md border-gray-300 dark:border-t-border shadow-sm focus:border-primary-500 focus:ring-primary-500 px-3 py-2 border text-sm pr-8"
        />
        {loading && (
          <div className="absolute right-2 top-1/2 -translate-y-1/2">
            <svg className="animate-spin h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        )}
      </div>

      {isOpen && results.length > 0 && (
        <div className="absolute z-10 w-full mt-1 bg-white dark:bg-t-bg-card border border-gray-200 dark:border-t-border rounded-md shadow-lg max-h-72 overflow-auto">
          {results.map((stock, index) => (
            <button
              key={stock.code}
              type="button"
              onClick={() => handleSelect(stock)}
              className={`w-full px-3 py-2.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-t-bg-elevated/50 dark:bg-t-bg-elevated flex justify-between items-center border-b border-gray-100 dark:border-t-border/50 last:border-b-0 ${
                index === selectedIndex ? 'bg-primary-50' : ''
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className="font-medium text-gray-900 dark:text-t-text-primary truncate">{stock.name}</div>
                <div className="text-xs text-gray-500 dark:text-t-text-muted">{stock.code}</div>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded ml-2 flex-shrink-0 ${getMarketColor(stock.market)}`}>
                {stock.market}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export type { Stock }
