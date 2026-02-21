import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import EmergingThemes from './EmergingThemes'
import ThemeRotation from './ThemeRotation'
import EtfRotationHeatmap from '../etf/EtfRotationHeatmap'

type ThemeTab = 'emerging' | 'rotation' | 'etf'

const TABS: { id: ThemeTab; label: string }[] = [
  { id: 'emerging', label: '신흥 테마' },
  { id: 'rotation', label: '테마 순환' },
  { id: 'etf', label: 'ETF 순환매' },
]

export default function ThemesPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab') as ThemeTab | null
  const [activeTab, setActiveTab] = useState<ThemeTab>(
    tabParam && TABS.some(t => t.id === tabParam) ? tabParam : 'emerging'
  )

  const handleTabChange = (tab: ThemeTab) => {
    setActiveTab(tab)
    setSearchParams({ tab })
  }

  return (
    <div>
      {/* 탭 */}
      <div className="border-b border-gray-200 dark:border-t-border mb-6">
        <nav className="flex gap-6 -mb-px">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`py-2.5 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                  : 'border-transparent text-gray-500 dark:text-t-text-muted hover:text-gray-700 dark:hover:text-t-text-secondary'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* 탭 콘텐츠 */}
      {activeTab === 'emerging' && <EmergingThemes />}
      {activeTab === 'rotation' && <ThemeRotation />}
      {activeTab === 'etf' && <EtfRotationHeatmap />}
    </div>
  )
}
