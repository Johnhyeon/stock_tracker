import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import FlowRanking from './FlowRanking'
import SectorFlowPage from '../sector-flow/SectorFlowPage'
import PullbackPage from '../pullback/PullbackPage'

type FlowTab = 'ranking' | 'sector' | 'pullback'

const TABS: { id: FlowTab; label: string }[] = [
  { id: 'ranking', label: '수급 랭킹' },
  { id: 'sector', label: '섹터 수급' },
  { id: 'pullback', label: '눌림목' },
]

export default function MarketFlowPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab') as FlowTab | null
  const [activeTab, setActiveTab] = useState<FlowTab>(
    tabParam && TABS.some(t => t.id === tabParam) ? tabParam : 'ranking'
  )

  const handleTabChange = (tab: FlowTab) => {
    setActiveTab(tab)
    setSearchParams({ tab })
  }

  return (
    <div>
      {/* 탭 */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="flex gap-6 -mb-px">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`py-2.5 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* 탭 콘텐츠 */}
      {activeTab === 'ranking' && <FlowRanking />}
      {activeTab === 'sector' && <SectorFlowPage />}
      {activeTab === 'pullback' && <PullbackPage />}
    </div>
  )
}
