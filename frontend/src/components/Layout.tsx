import { useState, useRef, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { clsx } from 'clsx'

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
          'inline-flex items-center px-3 py-2 text-sm font-medium rounded-md',
          isActive ? 'bg-primary-100 text-primary-700' : 'text-gray-600 hover:bg-gray-100'
        )}
      >
        {label}
        <svg className="ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="absolute left-0 mt-1 w-36 bg-white border border-gray-200 rounded-md shadow-lg z-50">
          {items.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              onClick={() => setOpen(false)}
              className={clsx(
                'block px-4 py-2 text-sm',
                location.pathname === item.path
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-700 hover:bg-gray-100'
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

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <Link to="/" className="flex items-center">
                <span className="text-xl font-bold text-primary-600">
                  Investment Tracker
                </span>
              </Link>
              <div className="hidden sm:ml-8 sm:flex sm:items-center sm:space-x-2">
                {/* 메인 메뉴 */}
                {mainNavItems.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={clsx(
                      'inline-flex items-center px-3 py-2 text-sm font-medium rounded-md',
                      location.pathname === item.path
                        ? 'bg-primary-100 text-primary-700'
                        : 'text-gray-600 hover:bg-gray-100'
                    )}
                  >
                    {item.label}
                  </Link>
                ))}
                {/* 수급 드롭다운 */}
                <DropdownMenu label="수급" items={flowMenuItems} />
                {/* 드롭다운 메뉴 */}
                {dropdownMenus.map((menu) => (
                  <DropdownMenu key={menu.label} label={menu.label} items={menu.items} />
                ))}
              </div>
            </div>
            <div className="flex items-center">
              <Link
                to="/ideas/create"
                className="bg-primary-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-primary-700"
              >
                + 새 아이디어
              </Link>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  )
}
