import { useState, useRef, useEffect, lazy, Suspense } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { clsx } from 'clsx'
import { useDarkMode } from '../hooks/useDarkMode'

const MarketOverview = lazy(() => import('./MarketOverview'))

interface LayoutProps {
  children: React.ReactNode
}

// 메인 메뉴 (항상 표시)
const mainNavItems = [
  { path: '/', label: '대시보드' },
  { path: '/ideas', label: '아이디어' },
  { path: '/emerging', label: '뜨는 테마' },
  { path: '/etf-rotation', label: '순환매' },
]

// 수급 서브메뉴
const flowMenuItems = [
  { path: '/sector-flow', label: '섹터 수급' },
  { path: '/flow-ranking', label: '종목 수급' },
]

// 드롭다운 메뉴
const dropdownMenus = [
  {
    label: '정보',
    items: [
      { path: '/youtube', label: 'YouTube' },
      { path: '/traders', label: 'Traders' },
      { path: '/themes', label: 'Themes' },
      { path: '/disclosures', label: '공시' },
    ],
  },
  {
    label: '도구',
    items: [
      { path: '/positions/quick', label: '빠른입력' },
      { path: '/analysis', label: '분석' },
      { path: '/alerts', label: '알림' },
      { path: '/telegram', label: '텔레그램' },
      { path: '/data', label: '데이터' },
    ],
  },
]

// 테마 모드 아이콘
function ThemeIcon({ mode }: { mode: 'light' | 'dark' | 'auto' }) {
  if (mode === 'light') {
    return (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
    )
  }
  if (mode === 'dark') {
    return (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
      </svg>
    )
  }
  // auto
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

function DropdownMenu({ label, items }: { label: string; items: { path: string; label: string }[] }) {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const ref = useRef<HTMLDivElement>(null)

  // 메뉴 밖 클릭 시 닫기
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const isActive = items.some((item) => location.pathname === item.path)

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={clsx(
          'inline-flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors',
          isActive
            ? 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300'
            : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
        )}
      >
        {label}
        <svg className="ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="absolute left-0 mt-1 w-36 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg z-50">
          {items.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              onClick={() => setOpen(false)}
              className={clsx(
                'block px-4 py-2 text-sm transition-colors',
                location.pathname === item.path
                  ? 'bg-primary-50 text-primary-700 dark:bg-primary-900 dark:text-primary-300'
                  : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
              )}
            >
              {item.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const { mode, toggleMode } = useDarkMode()

  const modeLabel = mode === 'auto' ? '자동' : mode === 'light' ? '라이트' : '다크'

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors">
      <nav className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-14">
            <div className="flex">
              <Link to="/" className="flex items-center">
                <span className="text-xl font-bold text-primary-600 dark:text-primary-400">
                  Investment Tracker
                </span>
              </Link>
              <div className="hidden sm:ml-8 sm:flex sm:items-center sm:space-x-2">
                {/* 메인 메뉴 */}
                {mainNavItems.map((item) => {
                  const isActive = item.path === '/'
                    ? location.pathname === '/'
                    : location.pathname.startsWith(item.path)
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={clsx(
                        'inline-flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors',
                        isActive
                          ? 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300'
                          : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
                      )}
                    >
                      {item.label}
                    </Link>
                  )
                })}
                {/* 드롭다운 메뉴 */}
                {dropdownMenus.map((menu) => (
                  <DropdownMenu key={menu.label} label={menu.label} items={menu.items} />
                ))}
              </div>
            </div>
            <div className="flex items-center space-x-3">
              {/* 테마 토글 버튼 */}
              <button
                onClick={toggleMode}
                className="p-2 rounded-md text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700 transition-colors"
                title={`현재: ${modeLabel} (클릭하여 변경)`}
              >
                <ThemeIcon mode={mode} />
              </button>
              <Link
                to="/ideas/create"
                className="bg-primary-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-primary-700 dark:bg-primary-500 dark:hover:bg-primary-600 transition-colors"
              >
                + 새 아이디어
              </Link>
            </div>
          </div>
          {/* 마켓 오버뷰 */}
          <div className="hidden sm:flex items-center h-8 -mt-1">
            <Suspense fallback={null}>
              <MarketOverview />
            </Suspense>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}
