import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './features/dashboard/Dashboard'
import IdeaList from './features/ideas/IdeaList'
import CreateIdea from './features/ideas/CreateIdea'
import IdeaDetail from './features/ideas/IdeaDetail'
import Analysis from './features/analysis/Analysis'
import DataMonitor from './features/data/DataMonitor'
import DisclosureList from './features/disclosures/DisclosureList'
import YouTubeTrending from './features/youtube/YouTubeTrending'
import TraderWatchlist from './features/traders/TraderWatchlist'
import ThemeRotation from './features/themes/ThemeRotation'
import EmergingThemes from './features/themes/EmergingThemes'
import ThemeSetupDetail from './features/themes/ThemeSetupDetail'
import QuickPositionInput from './features/positions/QuickPositionInput'
import AlertSettings from './features/alerts/AlertSettings'
import FlowRanking from './features/flow/FlowRanking'
import TelegramMonitor from './features/telegram/TelegramMonitor'
import EtfRotationHeatmap from './features/etf/EtfRotationHeatmap'
import SectorFlowPage from './features/sector-flow/SectorFlowPage'

function App() {
  return (
    <Layout>
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
        <Route path="/themes" element={<ThemeRotation />} />
        <Route path="/emerging" element={<EmergingThemes />} />
        <Route path="/emerging/:themeName" element={<ThemeSetupDetail />} />
        <Route path="/positions/quick" element={<QuickPositionInput />} />
        <Route path="/alerts" element={<AlertSettings />} />
        <Route path="/flow-ranking" element={<FlowRanking />} />
        <Route path="/sector-flow" element={<SectorFlowPage />} />
        <Route path="/telegram" element={<TelegramMonitor />} />
        <Route path="/etf-rotation" element={<EtfRotationHeatmap />} />
      </Routes>
    </Layout>
  )
}

export default App
