import { Suspense, lazy } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import ErrorBoundary from './components/ErrorBoundary'
import { useFeatureFlags } from './hooks/useFeatureFlags'

// 즉시 로드: 가장 자주 사용하는 대시보드
import DashboardV2 from './features/dashboard/DashboardV2'

// Lazy 로드: 나머지 페이지들은 라우트 진입 시 로드
const IdeaList = lazy(() => import('./features/ideas/IdeaList'))
const CreateIdea = lazy(() => import('./features/ideas/CreateIdea'))
const IdeaDetail = lazy(() => import('./features/ideas/IdeaDetail'))
const Analysis = lazy(() => import('./features/analysis/Analysis'))
const DataMonitor = lazy(() => import('./features/data/DataMonitor'))
const DisclosureList = lazy(() => import('./features/disclosures/DisclosureList'))
const YouTubeTrending = lazy(() => import('./features/youtube/YouTubeTrending'))
const ExpertWatchlist = lazy(() => import('./features/experts/ExpertWatchlist'))
const ThemesPage = lazy(() => import('./features/themes/ThemesPage'))
const ThemeSetupDetail = lazy(() => import('./features/themes/ThemeSetupDetail'))
const QuickPositionInput = lazy(() => import('./features/positions/QuickPositionInput'))
const AlertSettings = lazy(() => import('./features/alerts/AlertSettings'))
const MarketFlowPage = lazy(() => import('./features/flow/MarketFlowPage'))
const TelegramMonitor = lazy(() => import('./features/telegram/TelegramMonitor'))
const StockDetailPage = lazy(() => import('./features/stocks/StockDetailPage'))
const TradeAnalysis = lazy(() => import('./features/trades/TradeAnalysis'))
const StockSearchPage = lazy(() => import('./features/stock-search/StockSearchPage'))
const ConvergenceView = lazy(() => import('./features/analysis/ConvergenceView'))
const PullbackPage = lazy(() => import('./features/pullback/PullbackPage'))
const SignalScannerPage = lazy(() => import('./features/signal-scanner/SignalScannerPage'))
const SmartScannerPage = lazy(() => import('./features/smart-scanner/SmartScannerPage'))
const CatalystTracker = lazy(() => import('./features/catalyst/CatalystTracker'))
const ThemePulsePage = lazy(() => import('./features/theme-pulse/ThemePulsePage'))
const RecoveryPage = lazy(() => import('./features/analysis/RecoveryPage'))
const MarketIntelPage = lazy(() => import('./features/market-intel/MarketIntelPage'))
const ValueScreenerPage = lazy(() => import('./features/value-screener/ValueScreenerPage'))
const BacktestPage = lazy(() => import('./features/backtest/BacktestPage'))
const WatchlistPage = lazy(() => import('./features/watchlist/WatchlistPage'))
const LandingPage = lazy(() => import('./features/landing/LandingPage'))


function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
    </div>
  )
}

function App() {
  const location = useLocation()
  const features = useFeatureFlags()
  const isLandingRoute = location.pathname === '/landing'

  if (isLandingRoute) {
    return (
      <ErrorBoundary>
        <Suspense fallback={<LoadingSpinner />}>
          <Routes>
            <Route path="/landing" element={<LandingPage />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    )
  }

  return (
    <Layout>
      <ErrorBoundary>
      <Suspense fallback={<LoadingSpinner />}>
        <Routes>
          <Route path="/" element={<DashboardV2 />} />
          <Route path="/ideas" element={<IdeaList />} />
          <Route path="/ideas/create" element={<CreateIdea />} />
          <Route path="/ideas/:id" element={<IdeaDetail />} />
          <Route path="/analysis" element={<Analysis />} />
          <Route path="/data" element={<DataMonitor />} />
          <Route path="/disclosures" element={<DisclosureList />} />
          <Route path="/youtube" element={<YouTubeTrending />} />
          {features.expert && <Route path="/experts" element={<ExpertWatchlist />} />}

          {/* 테마 통합 */}
          <Route path="/themes" element={<ThemesPage />} />
          <Route path="/themes/:themeName" element={<ThemeSetupDetail />} />
          {/* 기존 라우트 리다이렉트 */}
          <Route path="/emerging" element={<Navigate to="/themes?tab=emerging" replace />} />
          <Route path="/emerging/:themeName" element={<ThemeSetupDetail />} />
          <Route path="/etf-rotation" element={<Navigate to="/themes?tab=etf" replace />} />

          {/* 수급 통합 */}
          <Route path="/flow" element={<MarketFlowPage />} />
          <Route path="/flow-ranking" element={<Navigate to="/flow?tab=ranking" replace />} />
          <Route path="/sector-flow" element={<Navigate to="/flow?tab=sector" replace />} />
          {/* 시그널 스캐너 독립 라우트 */}
          <Route path="/pullback" element={<PullbackPage />} />
          <Route path="/signal-scanner" element={<SignalScannerPage />} />

          <Route path="/positions/quick" element={<QuickPositionInput />} />
          <Route path="/alerts" element={<AlertSettings />} />
          {features.telegram && <Route path="/telegram" element={<TelegramMonitor />} />}
          <Route path="/stock-search" element={<StockSearchPage />} />
          <Route path="/stocks/:stockCode" element={<StockDetailPage />} />
          <Route path="/trades" element={<TradeAnalysis />} />
          <Route path="/smart-scanner" element={<SmartScannerPage />} />
          <Route path="/catalyst" element={<CatalystTracker />} />
          <Route path="/theme-pulse" element={<ThemePulsePage />} />
          <Route path="/convergence" element={<ConvergenceView />} />
          <Route path="/recovery" element={<RecoveryPage />} />
          <Route path="/intel" element={<MarketIntelPage />} />
          <Route path="/value-screener" element={<ValueScreenerPage />} />
          <Route path="/backtest" element={<BacktestPage />} />
          <Route path="/watchlist" element={<WatchlistPage />} />

        </Routes>
      </Suspense>
      </ErrorBoundary>
    </Layout>
  )
}

export default App
