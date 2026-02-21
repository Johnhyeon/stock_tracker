import { useState, useEffect, useMemo, useRef, useCallback, lazy, Suspense } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { clsx } from 'clsx'
import { useDarkMode } from '../hooks/useDarkMode'
import { useFeatureFlags, toggleFeatureFlag } from '../hooks/useFeatureFlags'

const MarketOverview = lazy(() => import('./MarketOverview'))

interface LayoutProps {
  children: React.ReactNode
}

// 사이드바 메뉴 정의
const menuSections = [
  {
    items: [
      { path: '/', label: '대시보드', icon: 'dashboard' },
      { path: '/intel', label: '시장인텔', icon: 'radar' },
      { path: '/ideas', label: '아이디어', icon: 'lightbulb' },
      { path: '/watchlist', label: '관심종목', icon: 'star' },
      { path: '/stock-search', label: '종목검색', icon: 'search' },
    ],
  },
  {
    title: '분석',
    items: [
      { path: '/emerging', label: '뜨는 테마', icon: 'trending' },
      { path: '/etf-rotation', label: '순환매', icon: 'refresh' },
      { path: '/smart-scanner', label: 'Smart Scanner', icon: 'crosshair' },
      { path: '/flow-ranking', label: '수급랭킹', icon: 'signal' },
      { path: '/pullback', label: '차트시그널', icon: 'radar' },
      { path: '/signal-scanner', label: '시그널스캐너', icon: 'crosshair' },
      { path: '/catalyst', label: 'Catalyst', icon: 'zap' },
      { path: '/theme-pulse', label: '테마 펄스', icon: 'pulse' },
      { path: '/recovery', label: '회복분석', icon: 'refresh' },
      { path: '/value-screener', label: '저평가', icon: 'signal' },
      { path: '/trades', label: '매매분석', icon: 'chart' },
      { path: '/backtest', label: '백테스트', icon: 'chart' },
    ],
  },
  {
    title: '정보',
    items: [
      { path: '/youtube', label: 'YouTube', icon: 'play' },
      { path: '/experts', label: '전문가', icon: 'users' },
      { path: '/themes', label: 'Themes', icon: 'tag' },
      { path: '/disclosures', label: '공시', icon: 'document' },
    ],
  },
  {
    title: '도구',
    items: [
      { path: '/positions/quick', label: '빠른입력', icon: 'zap' },
      { path: '/alerts', label: '알림', icon: 'bell' },
      { path: '/telegram', label: '텔레그램', icon: 'send' },
      { path: '/data', label: '데이터', icon: 'database' },
    ],
  },
]

function MenuIcon({ icon, className }: { icon: string; className?: string }) {
  const cls = clsx('w-5 h-5 flex-shrink-0', className)
  switch (icon) {
    case 'dashboard':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
    case 'lightbulb':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
    case 'search':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
    case 'trending':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
    case 'refresh':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
    case 'crosshair':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8V4m0 4a4 4 0 100 8 4 4 0 000-8zm0 8v4m-8-8H0m4 0a8 8 0 1016 0H4z" /><circle cx="12" cy="12" r="2" strokeWidth={1.5} /></svg>
    case 'chart':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
    case 'play':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
    case 'users':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
    case 'tag':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" /></svg>
    case 'document':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
    case 'zap':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
    case 'star':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" /></svg>
    case 'bell':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" /></svg>
    case 'send':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
    case 'database':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg>
    case 'signal':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 21h18M3 17h2v4H3v-4zm4-4h2v8H7v-8zm4-4h2v12h-2V9zm4-3h2v15h-2V6zm4-3h2v18h-2V3z" /></svg>
    case 'radar':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 2a10 10 0 0110 10M12 2v10l7.07 7.07M12 2a10 10 0 00-10 10 10 10 0 0010 10 10 10 0 0010-10" /><circle cx="12" cy="12" r="3" strokeWidth={1.5} /></svg>
    case 'pulse':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 12h4l3-9 4 18 3-9h4" /></svg>
    case 'cat':
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 21c-4.97 0-9-3.582-9-8s4.03-8 9-8 9 3.582 9 8-4.03 8-9 8zM3 5l3 4M21 5l-3 4" /><circle cx="9" cy="12" r="1" fill="currentColor" /><circle cx="15" cy="12" r="1" fill="currentColor" /><path strokeLinecap="round" strokeWidth={1.5} d="M10 15s.9 1 2 1 2-1 2-1" /></svg>
    default:
      return <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" strokeWidth={1.5} /></svg>
  }
}

// 테마 모드 아이콘
function ThemeIcon({ mode }: { mode: 'light' | 'dark' | 'auto' }) {
  const cls = 'w-5 h-5'
  if (mode === 'light') {
    return (
      <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
    )
  }
  if (mode === 'dark') {
    return (
      <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
      </svg>
    )
  }
  return (
    <svg className={cls} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const { mode, toggleMode } = useDarkMode()
  const features = useFeatureFlags()

  // 숨겨진 피처 토글: ST 로고 5번 빠르게 클릭하면 패널 열림
  const [showFeaturePanel, setShowFeaturePanel] = useState(false)
  const clickCountRef = useRef(0)
  const clickTimerRef = useRef<ReturnType<typeof setTimeout>>()
  const handleLogoClick = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    clickCountRef.current++
    if (clickTimerRef.current) clearTimeout(clickTimerRef.current)
    if (clickCountRef.current >= 5) {
      clickCountRef.current = 0
      setShowFeaturePanel(p => !p)
    } else {
      clickTimerRef.current = setTimeout(() => { clickCountRef.current = 0 }, 1000)
    }
  }, [])

  const filteredSections = useMemo(() => {
    const hiddenPaths: string[] = []
    if (!features.telegram) hiddenPaths.push('/telegram')
    if (!features.expert) hiddenPaths.push('/experts')
    if (hiddenPaths.length === 0) return menuSections
    return menuSections.map(section => ({
      ...section,
      items: section.items.filter(item => !hiddenPaths.includes(item.path)),
    }))
  }, [features.telegram, features.expert])

  const [collapsed, setCollapsed] = useState(() => {
    const saved = localStorage.getItem('sidebar-collapsed')
    return saved === 'true'
  })

  useEffect(() => {
    localStorage.setItem('sidebar-collapsed', String(collapsed))
  }, [collapsed])

  const modeLabel = mode === 'auto' ? '자동' : mode === 'light' ? '라이트' : '다크'
  const sidebarWidth = collapsed ? 'w-16' : 'w-56'

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-t-bg transition-colors flex">
      {/* 사이드바 */}
      <aside
        className={clsx(
          'fixed top-0 left-0 h-full z-40 flex flex-col transition-[width] duration-300 ease-in-out',
          'bg-white dark:bg-t-bg-card border-r border-gray-200 dark:border-t-border',
          sidebarWidth
        )}
      >
        {/* 로고 */}
        <div className="flex items-center h-12 px-4 border-b border-gray-200 dark:border-t-border flex-shrink-0">
          <Link to="/" className="flex items-center gap-2 overflow-hidden">
            <div
              onClick={handleLogoClick}
              className="w-7 h-7 rounded-lg bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center flex-shrink-0 cursor-pointer select-none"
            >
              <span className="text-xs font-bold text-white">ST</span>
            </div>
            {!collapsed && (
              <span className="text-sm font-bold text-gray-900 dark:text-t-text-primary whitespace-nowrap">
                Stock Tracker
              </span>
            )}
          </Link>
        </div>

        {/* 메뉴 */}
        <nav className="flex-1 overflow-y-auto overflow-x-hidden py-2 px-2">
          {filteredSections.map((section, sIdx) => (
            <div key={sIdx} className={sIdx > 0 ? 'mt-3 pt-3 border-t border-gray-100 dark:border-t-border' : ''}>
              {section.title && !collapsed && (
                <div className="px-2 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-t-text-muted">
                  {section.title}
                </div>
              )}
              {section.items.map((item) => {
                const isActive = item.path === '/'
                  ? location.pathname === '/'
                  : location.pathname.startsWith(item.path)
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    title={collapsed ? item.label : undefined}
                    className={clsx(
                      'flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm font-medium transition-all duration-150 relative group mb-0.5',
                      isActive
                        ? 'bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400'
                        : 'text-gray-600 dark:text-t-text-secondary hover:bg-gray-100 dark:hover:bg-t-border/50 hover:text-gray-900 dark:hover:text-t-text-primary'
                    )}
                  >
                    {/* 활성 표시 바 */}
                    {isActive && (
                      <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-amber-500 dark:bg-amber-400" />
                    )}
                    <MenuIcon icon={item.icon} className={isActive ? 'text-amber-600 dark:text-amber-400' : ''} />
                    {!collapsed && (
                      <span className="truncate">{item.label}</span>
                    )}
                  </Link>
                )
              })}
            </div>
          ))}
        </nav>

        {/* 하단 고정: 새 아이디어, 테마 토글, 접기/펼치기 */}
        <div className="flex-shrink-0 border-t border-gray-200 dark:border-t-border p-2 space-y-1">
          {/* 새 아이디어 버튼 */}
          <Link
            to="/ideas/create"
            className={clsx(
              'flex items-center gap-2 px-2.5 py-2 rounded-lg text-sm font-medium transition-colors',
              'bg-amber-500 hover:bg-amber-600 text-white',
              collapsed && 'justify-center'
            )}
          >
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            {!collapsed && <span>새 아이디어</span>}
          </Link>

          {/* 테마 토글 */}
          <button
            onClick={toggleMode}
            className={clsx(
              'flex items-center gap-2 w-full px-2.5 py-2 rounded-lg text-sm transition-colors',
              'text-gray-500 dark:text-t-text-muted hover:bg-gray-100 dark:hover:bg-t-border/50',
              collapsed && 'justify-center'
            )}
            title={`현재: ${modeLabel}`}
          >
            <ThemeIcon mode={mode} />
            {!collapsed && <span className="text-xs">{modeLabel}</span>}
          </button>

          {/* 접기/펼치기 */}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className={clsx(
              'flex items-center gap-2 w-full px-2.5 py-2 rounded-lg text-sm transition-colors',
              'text-gray-400 dark:text-t-text-muted hover:bg-gray-100 dark:hover:bg-t-border/50',
              collapsed && 'justify-center'
            )}
          >
            <svg className={clsx('w-4 h-4 transition-transform', collapsed && 'rotate-180')} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
            {!collapsed && <span className="text-xs">접기</span>}
          </button>

          {/* 숨겨진 피처 토글 패널 (ST 로고 5번 클릭으로 열기) */}
          {showFeaturePanel && !collapsed && (
            <div className="mt-1 p-2 rounded-lg bg-gray-100 dark:bg-t-border/30 space-y-1.5">
              <div className="text-[10px] font-semibold text-gray-400 dark:text-t-text-muted uppercase tracking-wider">Features</div>
              {([
                { key: 'telegram' as const, label: 'Telegram' },
                { key: 'expert' as const, label: 'Expert' },
              ]).map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => toggleFeatureFlag(key, !features[key])}
                  className="flex items-center justify-between w-full px-1.5 py-1 rounded text-xs"
                >
                  <span className="text-gray-600 dark:text-t-text-secondary">{label}</span>
                  <span className={clsx(
                    'px-1.5 py-0.5 rounded-full text-[10px] font-bold',
                    features[key]
                      ? 'bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-400'
                      : 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-400'
                  )}>
                    {features[key] ? 'ON' : 'OFF'}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* 메인 콘텐츠 영역 */}
      <div className={clsx('flex-1 transition-[margin-left] duration-300 ease-in-out', collapsed ? 'ml-16' : 'ml-56')}>
        {/* 상단 티커 바 */}
        <header className="sticky top-0 z-30 h-10 flex items-center bg-white dark:bg-t-bg-card border-b border-gray-200 dark:border-t-border overflow-hidden">
          <Suspense fallback={null}>
            <MarketOverview />
          </Suspense>
        </header>

        {/* 메인 콘텐츠 */}
        <main className="p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
