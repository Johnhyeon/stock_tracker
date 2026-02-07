import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'

// 즉시 로드: 가장 자주 사용하는 대시보드
import Dashboard from './features/dashboard/Dashboard'

// Lazy 로드: 나머지 페이지들은 라우트 진입 시 로드
const IdeaList = lazy(() => import('./features/ideas/IdeaList'))
const CreateIdea = lazy(() => import('./features/ideas/CreateIdea'))
const IdeaDetail = lazy(() => import('./features/ideas/IdeaDetail'))
const Analysis = lazy(() => import('./features/analysis/Analysis'))
const DataMonitor = lazy(() => import('./features/data/DataMonitor'))
const DisclosureList = lazy(() => import('./features/disclosures/DisclosureList'))
const YouTubeTrending = lazy(() => import('./features/youtube/YouTubeTrending'))
const TraderWatchlist = lazy(() => import('./features/traders/TraderWatchlist'))
const ThemesPage = lazy(() => import('./features/themes/ThemesPage'))
const ThemeSetupDetail = lazy(() => import('./features/themes/ThemeSetupDetail'))
const QuickPositionInput = lazy(() => import('./features/positions/QuickPositionInput'))
const AlertSettings = lazy(() => import('./features/alerts/AlertSettings'))
const MarketFlowPage = lazy(() => import('./features/flow/MarketFlowPage'))
const TelegramMonitor = lazy(() => import('./features/telegram/TelegramMonitor'))
const StockDetailPage = lazy(() => import('./features/stocks/StockDetailPage'))
const TradeAnalysis = lazy(() => import('./features/trades/TradeAnalysis'))

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
    </div>
  )
}

function App() {
  return (
    <Layout>
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/ideas" element={<IdeaList />} />
          <Route path="/ideas/create" element={<CreateIdea />} />
          <Route path="/ideas/:id" element={<IdeaDetail />} />
          <Route path="/analysis" element={<Analysis />} />
          <Route path="/data" element={<DataMonitor />} />
          <Route path="/disclosures" element={<DisclosureList />} />
          <Route path="/youtube" element={<YouTubeTrending />} />
          <Route path="/traders" element={<TraderWatchlist />} />

          {/* 테마 통합 */}
          <Route path="/themes" element={<ThemesPage />} />
          <Route path="/themes/:themeName" element={<ThemeSetupDetail />} />
          {/* 기존 라우트 리다이렉트 */}
          <Route path="/emerging" element={<Navigate to="/themes?tab=emerging" replace />} />
          <Route path="/emerging/:themeName" element={<ThemeSetupDetail />} />
          <Route path="/etf-rotation" element={<Navigate to="/themes?tab=etf" replace />} />

          {/* 수급 통합 */}
          <Route path="/flow" element={<MarketFlowPage />} />
          {/* 기존 라우트 리다이렉트 */}
          <Route path="/flow-ranking" element={<Navigate to="/flow?tab=ranking" replace />} />
          <Route path="/sector-flow" element={<Navigate to="/flow?tab=sector" replace />} />
          <Route path="/pullback" element={<Navigate to="/flow?tab=pullback" replace />} />

          <Route path="/positions/quick" element={<QuickPositionInput />} />
          <Route path="/alerts" element={<AlertSettings />} />
          <Route path="/telegram" element={<TelegramMonitor />} />
          <Route path="/stocks/:stockCode" element={<StockDetailPage />} />
          <Route path="/trades" element={<TradeAnalysis />} />
        </Routes>
      </Suspense>
    </Layout>
  )
}

export default App
