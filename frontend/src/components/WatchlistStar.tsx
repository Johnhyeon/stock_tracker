import { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { useWatchlistStore } from '../store/useWatchlistStore'

interface WatchlistStarProps {
  stockCode: string
  stockName: string
}

export function WatchlistStar({ stockCode, stockName }: WatchlistStarProps) {
  const isWatched = useWatchlistStore(s => !!s.watchedMap[stockCode])
  const groups = useWatchlistStore(s => s.groups)
  const toggleWatch = useWatchlistStore(s => s.toggleWatch)
  const init = useWatchlistStore(s => s.init)
  const [showDropdown, setShowDropdown] = useState(false)
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 })
  const buttonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => { init() }, [init])

  // 외부 클릭 시 닫기
  useEffect(() => {
    if (!showDropdown) return
    const handler = (e: MouseEvent) => {
      if (buttonRef.current?.contains(e.target as Node)) return
      setShowDropdown(false)
    }
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handler)
    }, 0)
    return () => {
      clearTimeout(timer)
      document.removeEventListener('mousedown', handler)
    }
  }, [showDropdown])

  // 스크롤 시 닫기
  useEffect(() => {
    if (!showDropdown) return
    const close = () => setShowDropdown(false)
    window.addEventListener('scroll', close, true)
    return () => window.removeEventListener('scroll', close, true)
  }, [showDropdown])

  const handleClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()

    if (isWatched) {
      toggleWatch(stockCode, stockName)
    } else if (groups.length > 0) {
      if (buttonRef.current) {
        const rect = buttonRef.current.getBoundingClientRect()
        const estimatedHeight = (groups.length + 2) * 30 + 20
        const spaceBelow = window.innerHeight - rect.bottom
        const showAbove = spaceBelow < estimatedHeight && rect.top > estimatedHeight

        setDropdownPos({
          top: showAbove ? rect.top - estimatedHeight - 4 : rect.bottom + 4,
          left: Math.max(8, Math.min(rect.left + rect.width / 2 - 80, window.innerWidth - 168)),
        })
      }
      setShowDropdown(true)
    } else {
      toggleWatch(stockCode, stockName)
    }
  }, [isWatched, groups.length, stockCode, stockName, toggleWatch])

  const handleSelectGroup = useCallback((e: React.MouseEvent, groupId: number | null) => {
    e.stopPropagation()
    e.preventDefault()
    toggleWatch(stockCode, stockName, groupId ?? undefined)
    setShowDropdown(false)
  }, [stockCode, stockName, toggleWatch])

  return (
    <>
      <button
        ref={buttonRef}
        onClick={handleClick}
        className={`inline-flex items-center justify-center w-5 h-5 mr-1.5 shrink-0 transition-colors ${
          isWatched
            ? 'text-yellow-400 hover:text-yellow-500'
            : 'text-gray-300 dark:text-gray-600 hover:text-yellow-300 dark:hover:text-yellow-500'
        }`}
        title={isWatched ? '관심종목 해제' : '관심종목 추가'}
      >
        {isWatched ? (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
          </svg>
        )}
      </button>

      {showDropdown && createPortal(
        <div
          className="fixed z-[9999]"
          style={{ top: dropdownPos.top, left: dropdownPos.left }}
          onMouseDown={e => e.stopPropagation()}
        >
          <div className="w-40 bg-white dark:bg-t-bg-card border border-gray-200 dark:border-t-border rounded-lg shadow-xl overflow-hidden">
            <div className="py-1">
              <div className="px-3 py-1.5 text-[10px] font-medium text-gray-400 dark:text-t-text-muted uppercase tracking-wider">
                그룹 선택
              </div>
              {groups.map(g => (
                <button
                  key={g.id}
                  onClick={e => handleSelectGroup(e, g.id)}
                  className="w-full px-3 py-1.5 text-left text-sm text-gray-700 dark:text-t-text-secondary hover:bg-gray-50 dark:hover:bg-t-bg-elevated flex items-center gap-2 transition-colors"
                >
                  <div
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: g.color || '#6366f1' }}
                  />
                  <span className="truncate">{g.name}</span>
                </button>
              ))}
              <div className="border-t border-gray-100 dark:border-t-border" />
              <button
                onClick={e => handleSelectGroup(e, null)}
                className="w-full px-3 py-1.5 text-left text-sm text-gray-500 dark:text-t-text-muted hover:bg-gray-50 dark:hover:bg-t-bg-elevated transition-colors"
              >
                미분류
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  )
}
