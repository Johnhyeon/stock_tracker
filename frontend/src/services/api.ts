import axios from 'axios'
import type {
  Idea,
  IdeaCreate,
  IdeaUpdate,
  IdeaWithPositions,
  Position,
  PositionCreate,
  PositionExit,
  PositionAddBuy,
  PositionPartialExit,
  PositionUpdateData,
  ExitCheckResult,
  DashboardData,
  TimelineAnalysis,
  FomoAnalysis,
} from '../types/idea'
import type {
  PriceData,
  OHLCVData,
  Disclosure,
  DisclosureListResponse,
  DisclosureStats,
  DisclosureCollectRequest,
  DisclosureCollectResponse,
  DisclosureImportance,
  DisclosureType,
  YouTubeMention,
  YouTubeMentionListResponse,
  TrendingTicker,
  TickerMentionHistory,
  YouTubeCollectResponse,
  HotCollectResponse,
  RisingTicker,
  SchedulerStatus,
  AllAPIHealthStatus,
  APIHealthStatus,
  AlertRule,
  AlertType,
  NotificationLog,
  AlertSettings,
  TestNotificationRequest,
  TestNotificationResponse,
  ParsedPosition,
  ParseResult,
  BulkCreateResult,
  FileImportResult,
  ExpertHotStock,
  ExpertRisingStock,
  ExpertPerformanceStats,
  ExpertSyncResponse,
  ExpertNewMention,
  ExpertCrossCheck,
  ExpertPerformanceDetailResponse,
  ThemeRotationResponse,
  ThemeListItem,
  ThemeSearchResult,
  StockThemesResponse,
  MediaTimelineResponse,
  MentionBacktestResponse,
  OverheatResponse,
} from '../types/data'
import type {
  EmergingThemesResponse,
  ThemeSetupDetail,
  ChartPattern,
  NewsTrendItem,
  ThemeNewsItem,
  SetupHistoryItem,
} from '../types/theme_setup'
import type {
  ThemePulseResponse,
  TimelineResponse,
  CatalystDistributionResponse,
} from '../types/theme_pulse'

import type { PortfolioDashboardData } from '../types/dashboard_v2'
import type { MarketIntelData } from '../types/market_intel'
import { cachedFetch, invalidateDashboard, invalidateIdeas } from './apiCache'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const ideaApi = {
  list: async (params?: { status?: string; type?: string }) => {
    const { data } = await api.get<Idea[]>('/ideas', { params })
    return data
  },

  get: async (id: string) => {
    const { data } = await api.get<IdeaWithPositions>(`/ideas/${id}`)
    return data
  },

  create: async (idea: IdeaCreate) => {
    const { data } = await api.post<Idea>('/ideas', idea)
    invalidateIdeas()
    invalidateDashboard()
    return data
  },

  update: async (id: string, idea: IdeaUpdate) => {
    const { data } = await api.put<Idea>(`/ideas/${id}`, idea)
    invalidateIdeas()
    invalidateDashboard()
    return data
  },

  delete: async (id: string) => {
    await api.delete(`/ideas/${id}`)
    invalidateIdeas()
    invalidateDashboard()
  },

  checkExit: async (id: string) => {
    const { data } = await api.get<ExitCheckResult>(`/ideas/${id}/exit-check`)
    return data
  },

  createPosition: async (ideaId: string, position: PositionCreate) => {
    const { data } = await api.post<Position>(`/ideas/${ideaId}/positions`, position)
    invalidateDashboard()
    return data
  },

  // 아이디어에 등록된 모든 종목 목록 반환
  getIdeaStocks: async () => {
    const { data } = await api.get<Array<{ code: string; name: string; ticker_label: string }>>('/ideas/stocks/all')
    return data
  },

  // 종목 스파크라인 데이터 (codes 미지정시 활성/관찰 아이디어 종목)
  getStockSparklines: async (days = 60, codes?: string[]) => {
    const key = codes ? `sparklines-${codes.sort().join(',')}` : 'idea-stock-sparklines'
    return cachedFetch(key, async () => {
      const params: Record<string, unknown> = { days }
      if (codes) params.codes = codes.join(',')
      const { data } = await api.get<Record<string, { name: string; dates: string[]; closes: number[] }>>('/ideas/stock-sparklines', { params })
      return data
    }, 300_000)
  },
}

export const positionApi = {
  get: async (id: string) => {
    const { data } = await api.get<Position>(`/positions/${id}`)
    return data
  },

  update: async (id: string, updateData: PositionUpdateData) => {
    const { data } = await api.put<Position>(`/positions/${id}`, updateData)
    invalidateDashboard()
    return data
  },

  exit: async (id: string, exitData: PositionExit) => {
    const { data } = await api.put<Position>(`/positions/${id}/exit`, exitData)
    invalidateDashboard()
    return data
  },

  addBuy: async (id: string, addBuyData: PositionAddBuy) => {
    const { data } = await api.post<Position>(`/positions/${id}/add-buy`, addBuyData)
    invalidateDashboard()
    return data
  },

  partialExit: async (id: string, partialExitData: PositionPartialExit) => {
    const { data } = await api.post<Position>(`/positions/${id}/partial-exit`, partialExitData)
    invalidateDashboard()
    return data
  },

  delete: async (id: string) => {
    await api.delete(`/positions/${id}`)
    invalidateDashboard()
  },
}

export const dashboardApi = {
  get: async () => {
    return cachedFetch('dashboard', async () => {
      const { data } = await api.get<DashboardData>('/dashboard')
      return data
    }, 30_000) // 30초 캐시
  },
}

export const dashboardV2Api = {
  get: async () => {
    return cachedFetch('dashboard_v2', async () => {
      const { data } = await api.get<PortfolioDashboardData>('/dashboard/v2')
      return data
    }, 30_000) // 30초 캐시
  },
}

export const marketIntelApi = {
  getFeed: async (limit: number = 50) => {
    return cachedFetch(`market_intel:${limit}`, async () => {
      const { data } = await api.get<MarketIntelData>('/market-intel/feed', { params: { limit } })
      return data
    }, 120_000) // 2분 캐시
  },
}

export interface DashboardSignals {
  convergence_signals: TrendingMentionItem[]
  flow_spikes: Array<{ stock_code: string; spike_ratio: number; recent_amount: number }>
  chart_patterns: Array<{ stock_code: string; stock_name: string; pattern_type: string; confidence: number | null; analysis_date: string | null }>
  recent_ideas_stocks: Array<{ stock_code: string; stock_name: string; idea_count: number }>
  emerging_themes: Array<{ theme_name: string; setup_score: number }>
  new_ideas_7d: number
  generated_at: string
}

export const analysisApi = {
  getTimeline: async () => {
    const { data } = await api.get<TimelineAnalysis>('/analysis/timeline')
    return data
  },

  getFomo: async () => {
    const { data } = await api.get<FomoAnalysis>('/analysis/fomo')
    return data
  },

  getPerformance: async () => {
    const { data } = await api.get('/analysis/performance')
    return data
  },

  getDashboardSignals: async () => {
    return cachedFetch('dashboard-signals', async () => {
      const { data } = await api.get<DashboardSignals>('/analysis/dashboard-signals')
      return data
    }, 120_000) // 2분 캐시
  },

  getRiskMetrics: async (startDate?: string, endDate?: string) => {
    const suffix = `${startDate || ''}:${endDate || ''}`
    return cachedFetch(`risk-metrics:${suffix}`, async () => {
      const params: Record<string, string> = {}
      if (startDate) params.start_date = startDate
      if (endDate) params.end_date = endDate
      const { data } = await api.get<RiskMetrics>('/analysis/risk-metrics', { params })
      return data
    }, 300_000)
  },

  getTradeHabits: async (startDate?: string, endDate?: string) => {
    const suffix = `${startDate || ''}:${endDate || ''}`
    return cachedFetch(`trade-habits:${suffix}`, async () => {
      const params: Record<string, string> = {}
      if (startDate) params.start_date = startDate
      if (endDate) params.end_date = endDate
      const { data } = await api.get<TradeHabitsResponse>('/analysis/trade-habits', { params })
      return data
    }, 300_000)
  },

  getChartAnalysis: async (startDate?: string, endDate?: string) => {
    const suffix = `${startDate || ''}:${endDate || ''}`
    return cachedFetch(`chart-analysis:${suffix}`, async () => {
      const params: Record<string, string> = {}
      if (startDate) params.start_date = startDate
      if (endDate) params.end_date = endDate
      const { data } = await api.get<import('../types/chart_analysis').ChartAnalysisResponse>('/analysis/chart-analysis', { params })
      return data
    }, 300_000)
  },

  getWhatIf: async (startDate?: string, endDate?: string) => {
    const params: Record<string, string> = {}
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    const { data } = await api.get<import('../types/trade_review').WhatIfResponse>('/analysis/review/what-if', { params })
    return data
  },

  getTradeContext: async (positionId: string) => {
    const { data } = await api.get<import('../types/trade_review').TradeContextResponse>(`/analysis/review/context/${positionId}`)
    return data
  },

  getFlowWinRate: async (startDate?: string, endDate?: string) => {
    const params: Record<string, string> = {}
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    const { data } = await api.get<import('../types/trade_review').FlowWinRateResponse>('/analysis/review/flow-winrate', { params })
    return data
  },

  getTradeClusters: async (startDate?: string, endDate?: string) => {
    const params: Record<string, string> = {}
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    const { data } = await api.get<import('../types/trade_review').ClusterResponse>('/analysis/review/clusters', { params })
    return data
  },

  runSpikeBacktest: async (params?: BacktestParams) => {
    const { data } = await api.get<BacktestResult>('/analysis/backtest/spike', {
      params: {
        recent_days: params?.recent_days ?? 2,
        base_days: params?.base_days ?? 20,
        min_ratio: params?.min_ratio ?? 3.0,
        min_amount: params?.min_amount ?? 1_000_000_000,
        investor_type: params?.investor_type ?? 'all',
        holding_days: params?.holding_days ?? '5,10,20',
      },
    })
    return data
  },
}

export interface RiskMetrics {
  mdd: {
    max_drawdown_pct: number
    peak_date: string | null
    trough_date: string | null
  }
  sharpe_ratio: number | null
  win_rate_trend: Array<{
    trade_index: number
    date: string | null
    win_rate: number
  }>
  streak: {
    max_win_streak: number
    max_loss_streak: number
    current_streak: number
    current_type: 'win' | 'loss' | null
  }
  concentration: {
    hhi: number
    top_holding_pct: number
    holdings: Array<{
      ticker: string
      weight_pct: number
    }>
  }
  profit_factor: number | null
  total_closed_trades: number
}

export interface TradeHabitsExpectancy {
  expectancy: number
  expectancy_pct: number
  avg_win_amount: number
  avg_loss_amount: number
  avg_win_pct: number
  avg_loss_pct: number
  win_rate: number
  loss_rate: number
  is_positive: boolean
}

export interface TradeHabitsWinLossRatio {
  ratio: number
  avg_win_pct: number
  avg_loss_pct: number
  grade: 'excellent' | 'good' | 'average' | 'poor'
  comment: string
}

export interface HoldingPeriodBucket {
  period: string
  count: number
  win_rate: number
  avg_return_pct: number
}

export interface TradeHabitsHoldingPeriod {
  avg_win_days: number
  avg_loss_days: number
  diagnosis: string
  by_period: HoldingPeriodBucket[]
}

export interface SequentialStats {
  count: number
  win_rate: number
  avg_return_pct: number
}

export interface TradeHabitsSequentialPattern {
  after_win: SequentialStats | null
  after_loss: SequentialStats | null
  after_streak_loss: SequentialStats | null
  revenge_trading_detected: boolean
  overconfidence_detected: boolean
}

export interface WeekdayStats {
  day: string
  count: number
  win_rate: number
  avg_return_pct: number
  total_profit: number
}

export interface TradeHabitsWeekday {
  by_weekday: WeekdayStats[]
  best_day: string | null
  worst_day: string | null
}

export interface WeeklyData {
  week: string
  trade_count: number
  win_rate: number
  avg_return_pct: number
}

export interface FreqStats {
  count: number
  win_rate: number
  avg_return_pct: number
}

export interface TradeHabitsFrequency {
  avg_trades_per_week: number
  high_freq_stats: FreqStats | null
  low_freq_stats: FreqStats | null
  overtrading_warning: boolean
  weekly_data: WeeklyData[]
}

export interface TradeHabitsResponse {
  total_sell_trades: number
  expectancy: TradeHabitsExpectancy | null
  win_loss_ratio: TradeHabitsWinLossRatio | null
  holding_period: TradeHabitsHoldingPeriod | null
  sequential_pattern: TradeHabitsSequentialPattern | null
  weekday_performance: TradeHabitsWeekday | null
  frequency_analysis: TradeHabitsFrequency | null
}

export interface BacktestParams {
  recent_days?: number
  base_days?: number
  min_ratio?: number
  min_amount?: number
  investor_type?: 'all' | 'foreign' | 'institution'
  holding_days?: string
}

export interface BacktestResult {
  params: {
    recent_days: number
    base_days: number
    min_ratio: number
    min_amount: number
    investor_type: string
    holding_days: number[]
  }
  total_signals: number
  signal_days: number
  avg_signals_per_day?: number
  holding_stats: Record<string, {
    sample_count: number
    avg_return: number
    median: number
    win_rate: number
    q1: number
    q3: number
    max_return: number
    max_loss: number
  } | null>
  ratio_analysis: Array<{
    label: string
    count: number
    avg_return: number
    win_rate: number
  }>
  monthly_analysis: Array<{
    month: string
    signal_count: number
    avg_return: number
    win_rate: number
  }>
  top_performers: Array<Record<string, unknown>>
  worst_performers: Array<Record<string, unknown>>
}

// Data API (가격 조회)
export interface MarketIndexData {
  index_code: string
  index_name: string
  current_value: number
  change: number
  change_rate: number
  volume: number
  trading_value: number
}

export interface MarketIndicesResponse {
  kospi: MarketIndexData
  kosdaq: MarketIndexData
  sp500?: MarketIndexData
  nasdaq?: MarketIndexData
  dow?: MarketIndexData
  updated_at: string
}

export const dataApi = {
  getMarketIndex: async (): Promise<MarketIndicesResponse> => {
    return cachedFetch('market-index', async () => {
      const { data } = await api.get<MarketIndicesResponse>('/data/market-index')
      return data
    }, 60_000) // 1분 클라이언트 캐시
  },

  getPrice: async (stockCode: string, useCache = true) => {
    const { data } = await api.get<PriceData>(`/data/price/${stockCode}`, {
      params: { use_cache: useCache },
    })
    return data
  },

  getMultiplePrices: async (stockCodes: string[], useCache = true) => {
    const { data } = await api.post<Record<string, PriceData>>('/data/prices', {
      stock_codes: stockCodes,
    }, {
      params: { use_cache: useCache },
    })
    return data
  },

  getOHLCV: async (
    stockCode: string,
    period: 'D' | 'W' | 'M' = 'D',
    startDate?: string,
    endDate?: string
  ) => {
    const { data } = await api.get<OHLCVData>(`/data/ohlcv/${stockCode}`, {
      params: { period, start_date: startDate, end_date: endDate },
    })
    return data
  },

  clearCache: async () => {
    await api.post('/data/cache/clear')
  },
}

// Disclosure API (공시)
export const disclosureApi = {
  list: async (params?: {
    stock_code?: string
    importance?: DisclosureImportance
    disclosure_type?: DisclosureType
    unread_only?: boolean
    my_ideas_only?: boolean
    skip?: number
    limit?: number
  }) => {
    const { data } = await api.get<DisclosureListResponse>('/disclosures', { params })
    return data
  },

  get: async (id: string) => {
    const { data } = await api.get<Disclosure>(`/disclosures/${id}`)
    return data
  },

  getStats: async (stockCode?: string) => {
    const { data } = await api.get<DisclosureStats>('/disclosures/stats', {
      params: { stock_code: stockCode },
    })
    return data
  },

  markAsRead: async (id: string) => {
    const { data } = await api.post<Disclosure>(`/disclosures/${id}/read`)
    return data
  },

  markAllAsRead: async (stockCode?: string) => {
    const { data } = await api.post<{ marked_count: number }>('/disclosures/read-all', null, {
      params: { stock_code: stockCode },
    })
    return data
  },

  collect: async (request: DisclosureCollectRequest) => {
    const { data } = await api.post<DisclosureCollectResponse>('/disclosures/collect', request)
    return data
  },
}

// YouTube API
export const youtubeApi = {
  list: async (params?: {
    stock_code?: string
    channel_id?: string
    days_back?: number
    skip?: number
    limit?: number
  }) => {
    const { data } = await api.get<YouTubeMentionListResponse>('/youtube', { params })
    return data
  },

  get: async (id: string) => {
    const { data } = await api.get<YouTubeMention>(`/youtube/${id}`)
    return data
  },

  getTrending: async (daysBack = 7, limit = 20) => {
    const { data } = await api.get<TrendingTicker[]>('/youtube/trending', {
      params: { days_back: daysBack, limit },
    })
    return data
  },

  getHistory: async (stockCode: string, daysBack = 30) => {
    const { data } = await api.get<TickerMentionHistory[]>(`/youtube/history/${stockCode}`, {
      params: { days_back: daysBack },
    })
    return data
  },

  collect: async (hoursBack = 24) => {
    const { data } = await api.post<YouTubeCollectResponse>('/youtube/collect', {
      hours_back: hoursBack,
    })
    return data
  },

  collectHot: async (hoursBack = 48, mode: 'quick' | 'normal' | 'full' = 'normal') => {
    const { data } = await api.post<HotCollectResponse>('/youtube/collect-hot', {
      hours_back: hoursBack,
      mode,
    })
    return data
  },

  getRising: async (daysBack = 7, limit = 20) => {
    const { data } = await api.get<RisingTicker[]>('/youtube/rising', {
      params: { days_back: daysBack, limit },
    })
    return data
  },

  getStockTimeline: async (stockCode: string, daysBack = 90) => {
    const { data } = await api.get<MediaTimelineResponse>(`/youtube/stock-timeline/${stockCode}`, {
      params: { days_back: daysBack },
    })
    return data
  },

  getMentionBacktest: async (params?: {
    days_back?: number
    min_mentions?: number
    holding_days?: string
  }) => {
    const { data } = await api.get<MentionBacktestResponse>('/youtube/mention-backtest', { params })
    return data
  },

  getOverheat: async (recentDays = 3, baselineDays = 30) => {
    const { data } = await api.get<OverheatResponse>('/youtube/overheat', {
      params: { recent_days: recentDays, baseline_days: baselineDays },
    })
    return data
  },
}

// Scheduler API
export const schedulerApi = {
  getStatus: async () => {
    const { data } = await api.get<SchedulerStatus>('/scheduler/status')
    return data
  },
}

// Health Check API
export const healthApi = {
  checkAll: async () => {
    const { data } = await api.get<AllAPIHealthStatus>('/health/apis')
    return data
  },

  checkKIS: async () => {
    const { data } = await api.get<APIHealthStatus>('/health/kis')
    return data
  },

  checkDART: async () => {
    const { data } = await api.get<APIHealthStatus>('/health/dart')
    return data
  },

  checkYouTube: async () => {
    const { data } = await api.get<APIHealthStatus>('/health/youtube')
    return data
  },
}

// Alert API
export const alertApi = {
  // Rules
  listRules: async (params?: { enabled_only?: boolean; alert_type?: AlertType }) => {
    const { data } = await api.get<AlertRule[]>('/alerts/rules', { params })
    return data
  },

  getRule: async (id: string) => {
    const { data } = await api.get<AlertRule>(`/alerts/rules/${id}`)
    return data
  },

  createRule: async (rule: Omit<AlertRule, 'id' | 'created_at' | 'updated_at' | 'last_triggered_at'>) => {
    const { data } = await api.post<AlertRule>('/alerts/rules', rule)
    return data
  },

  updateRule: async (id: string, rule: Partial<AlertRule>) => {
    const { data } = await api.patch<AlertRule>(`/alerts/rules/${id}`, rule)
    return data
  },

  deleteRule: async (id: string) => {
    await api.delete(`/alerts/rules/${id}`)
  },

  toggleRule: async (id: string) => {
    const { data } = await api.post<AlertRule>(`/alerts/rules/${id}/toggle`)
    return data
  },

  // Logs
  listLogs: async (params?: { limit?: number; alert_type?: AlertType; success_only?: boolean }) => {
    const { data } = await api.get<NotificationLog[]>('/alerts/logs', { params })
    return data
  },

  // Test & Settings
  testNotification: async (request: TestNotificationRequest) => {
    const { data } = await api.post<TestNotificationResponse>('/alerts/test', request)
    return data
  },

  getSettings: async () => {
    const { data } = await api.get<AlertSettings>('/alerts/settings')
    return data
  },

  triggerCheck: async () => {
    const { data } = await api.post<{ message: string; triggered_count: number }>('/alerts/check')
    return data
  },
}

// Position Bulk API
export const positionBulkApi = {
  // Parsing
  parseQuick: async (text: string) => {
    const { data } = await api.post<ParsedPosition>('/positions/bulk/parse/quick', { text })
    return data
  },

  parseBulk: async (text: string) => {
    const { data } = await api.post<ParseResult>('/positions/bulk/parse/bulk', { text })
    return data
  },

  parseBrokerage: async (text: string) => {
    const { data } = await api.post<ParseResult>('/positions/bulk/parse/brokerage', { text })
    return data
  },

  // File Import
  importCSV: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post<FileImportResult>('/positions/bulk/import/csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  importJSON: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post<FileImportResult>('/positions/bulk/import/json', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  importExcel: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post<FileImportResult>('/positions/bulk/import/excel', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  // Bulk Create
  createBulk: async (positions: ParsedPosition[], createIdeas = true, ideaId?: string) => {
    const { data } = await api.post<BulkCreateResult>('/positions/bulk/create', {
      idea_id: ideaId,
      positions: positions.filter(p => p.is_valid).map(p => ({
        stock_code: p.stock_code,
        stock_name: p.stock_name,
        quantity: p.quantity,
        avg_price: p.avg_price,
      })),
      create_ideas: createIdeas,
    })
    return data
  },
}

// Stock Search API
export const stockApi = {
  search: async (query: string, limit = 15) => {
    const { data } = await api.get<Array<{
      code: string
      name: string
      market: string
      stock_type?: string
      name_chosung?: string
    }>>('/stocks/search', { params: { q: query, limit } })
    return data
  },

  getCount: async () => {
    const { data } = await api.get<{
      total: number
      kospi: number
      kosdaq: number
      etf: number
    }>('/stocks/count')
    return data
  },
}

// Expert Watchlist API
export const expertApi = {
  sync: async (filePath?: string) => {
    const { data } = await api.post<ExpertSyncResponse>('/experts/sync', {
      file_path: filePath,
    })
    return data
  },

  getHotStocks: async (daysBack = 7, limit = 20, includePrice = true) => {
    const { data } = await api.get<ExpertHotStock[]>('/experts/hot', {
      params: { days_back: daysBack, limit, include_price: includePrice },
    })
    return data
  },

  getRisingStocks: async (daysBack = 7, limit = 20, includePrice = true) => {
    const { data } = await api.get<ExpertRisingStock[]>('/experts/rising', {
      params: { days_back: daysBack, limit, include_price: includePrice },
    })
    return data
  },

  getPerformanceStats: async (daysBack = 30) => {
    const { data } = await api.get<ExpertPerformanceStats>('/experts/performance', {
      params: { days_back: daysBack },
    })
    return data
  },

  getPerformanceDetail: async (daysBack = 30) => {
    const { data } = await api.get<ExpertPerformanceDetailResponse>('/experts/performance-detail', {
      params: { days_back: daysBack },
    })
    return data
  },

  getNewMentions: async (sinceHours = 24) => {
    const { data } = await api.get<ExpertNewMention[]>('/experts/new-mentions', {
      params: { since_hours: sinceHours },
    })
    return data
  },

  getCrossCheck: async () => {
    const { data } = await api.get<ExpertCrossCheck[]>('/experts/cross-check')
    return data
  },
}

// Theme Rotation API
export const themeApi = {
  getRotation: async (daysBack = 7) => {
    const { data } = await api.get<ThemeRotationResponse>('/themes/rotation', {
      params: { days_back: daysBack },
    })
    return data
  },

  getList: async () => {
    const { data } = await api.get<ThemeListItem[]>('/themes/list')
    return data
  },

  search: async (query: string) => {
    const { data } = await api.get<ThemeSearchResult[]>('/themes/search', {
      params: { q: query },
    })
    return data
  },

  getThemeStocks: async (themeName: string) => {
    const { data } = await api.get<{
      theme_name: string
      stocks: Array<{ code: string; name: string }>
      stock_count: number
    }>(`/themes/${encodeURIComponent(themeName)}/stocks`)
    return data
  },

  getStockThemes: async (stockCode: string) => {
    const { data } = await api.get<StockThemesResponse>(`/themes/stock/${stockCode}/themes`)
    return data
  },
}

// Theme Setup API (자리 잡는 테마)
export const themeSetupApi = {
  // 수집 상태 조회
  getCollectionStatus: async () => {
    const { data } = await api.get<{
      investor_flow: { is_running: boolean; started_at: string | null; progress: string }
      patterns: { is_running: boolean; started_at: string | null; progress: string }
      calculate: { is_running: boolean; started_at: string | null; progress: string }
    }>('/theme-setup/collection-status')
    return data
  },

  // 이머징 테마 목록 조회
  getEmerging: async (limit = 20, minScore = 30) => {
    return cachedFetch(`emerging:${limit}:${minScore}`, async () => {
      const { data } = await api.get<EmergingThemesResponse>('/theme-setup/emerging', {
        params: { limit, min_score: minScore },
      })
      return data
    }, 120_000) // 2분 캐시
  },

  // 테마 셋업 상세 조회
  getDetail: async (themeName: string) => {
    const { data } = await api.get<ThemeSetupDetail>(`/theme-setup/${encodeURIComponent(themeName)}/detail`)
    return data
  },

  // 테마 차트 패턴 조회
  getPatterns: async (themeName: string) => {
    const { data } = await api.get<ChartPattern[]>(`/theme-setup/${encodeURIComponent(themeName)}/patterns`)
    return data
  },

  // 테마 뉴스 추이 조회
  getNewsTrend: async (themeName: string, days = 14) => {
    const { data } = await api.get<NewsTrendItem[]>(`/theme-setup/${encodeURIComponent(themeName)}/news-trend`, {
      params: { days },
    })
    return data
  },

  // 테마 최근 뉴스 조회
  getRecentNews: async (themeName: string, limit = 10) => {
    const { data } = await api.get<{ news: ThemeNewsItem[]; count: number }>(`/theme-setup/${encodeURIComponent(themeName)}/news`, {
      params: { limit },
    })
    return data
  },

  // 종목 패턴 조회
  getStockPattern: async (stockCode: string) => {
    const { data } = await api.get<ChartPattern>(`/theme-setup/stock/${stockCode}/pattern`)
    return data
  },

  // 테마 셋업 히스토리 조회
  getHistory: async (themeName: string, days = 30) => {
    const { data } = await api.get<{ theme_name: string; history: SetupHistoryItem[] }>(`/theme-setup/${encodeURIComponent(themeName)}/history`, {
      params: { days },
    })
    return data
  },

  // 셋업 점수 수동 계산
  calculate: async () => {
    const { data } = await api.post<{ calculated_count: number; emerging_count: number; timestamp: string }>('/theme-setup/calculate')
    return data
  },

  // 뉴스 수동 수집
  collectNews: async () => {
    const { data } = await api.post<{ naver_count: number; rss_count: number; total_count: number; collected_at: string }>('/theme-setup/collect-news')
    return data
  },

  // 패턴 수동 분석
  analyzePatterns: async () => {
    const { data } = await api.post<{ analyzed_themes: number; stocks_with_pattern: number; analysis_date: string }>('/theme-setup/analyze-patterns')
    return data
  },

  // 수급 데이터 수동 수집
  collectInvestorFlow: async () => {
    const { data } = await api.post<{ collected_count: number; failed_count: number; total_stocks: number; collected_at: string }>('/theme-setup/collect-investor-flow')
    return data
  },

  // 테마 수급 현황 조회
  getInvestorFlow: async (themeName: string, days = 5) => {
    const { data } = await api.get<{
      theme_name: string
      days: number
      summary: {
        foreign_net_sum: number
        institution_net_sum: number
        positive_foreign: number
        positive_institution: number
        total_stocks: number
        avg_flow_score: number
      }
      stocks: Array<{
        stock_code: string
        stock_name: string
        flow_date: string
        foreign_net: number
        institution_net: number
        individual_net: number
        flow_score: number
      }>
    }>(`/theme-setup/${encodeURIComponent(themeName)}/investor-flow`, {
      params: { days },
    })
    return data
  },

  // 종목 수급 히스토리 조회
  getStockInvestorFlow: async (stockCode: string, days = 30) => {
    const { data } = await api.get<{
      stock_code: string
      days: number
      history: Array<{
        flow_date: string
        foreign_net: number
        institution_net: number
        individual_net: number
        flow_score: number
      }>
    }>(`/theme-setup/stock/${stockCode}/investor-flow`, {
      params: { days },
    })
    return data
  },

  // 상위 테마 순위 추이 조회
  getRankTrend: async (days = 14, topN = 10) => {
    const { data } = await api.get<{
      dates: string[]
      themes: Array<{
        name: string
        data: Array<{ date: string; rank: number; score: number }>
      }>
    }>('/theme-setup/rank-trend', {
      params: { days, top_n: topN },
    })
    return data
  },

  // 종목 OHLCV 데이터 조회 (차트용)
  getStockOHLCV: async (stockCode: string, days = 90, beforeDate?: string) => {
    const fetcher = async () => {
      const params: Record<string, unknown> = { days }
      if (beforeDate) {
        params.before_date = beforeDate
      }
      const { data } = await api.get<{
        stock_code: string
        candles: Array<{
          time: number
          open: number
          high: number
          low: number
          close: number
          volume: number
        }>
        count: number
        has_more: boolean
        oldest_date: number | null
      }>(`/theme-setup/stock/${stockCode}/ohlcv`, { params })
      return data
    }

    // 초기 로드(beforeDate 없음)만 캐시, 스크롤 추가 로드는 캐시 안 함
    if (!beforeDate) {
      return cachedFetch(`ohlcv:${stockCode}:${days}`, fetcher, 300_000)
    }
    return fetcher()
  },
}

// 수급 랭킹 API
export interface FlowRankingStock {
  stock_code: string
  stock_name: string
  foreign_sum: number
  institution_sum: number
  individual_sum: number
  total_sum: number
  // 금액 필드 (단위: 원)
  foreign_amount_sum: number
  institution_amount_sum: number
  individual_amount_sum: number
  total_amount_sum: number
  avg_score: number
  data_days: number
  latest_date: string | null
  themes: string[]
}

export interface ConsecutiveStock {
  stock_code: string
  stock_name: string
  consecutive_days: number
  foreign_sum: number
  institution_sum: number
  individual_sum: number
  // 금액 필드 (단위: 원)
  foreign_amount_sum: number
  institution_amount_sum: number
  individual_amount_sum: number
  total_amount_sum: number
  themes: string[]
}

export interface SpikeStock {
  stock_code: string
  stock_name: string
  recent_amount: number      // 최근 N일 순매수금액
  base_avg: number           // 기준 기간 일평균
  spike_ratio: number        // 급증 배율
  recent_days: number        // 최근 데이터 일수
  foreign_amount_sum: number
  institution_amount_sum: number
  latest_date: string | null
  themes: string[]
}

export interface RealtimeSpikeStock {
  stock_code: string
  stock_name: string
  today_amount: number       // 당일 순매수금액
  daily_avg: number          // 과거 일평균
  spike_ratio: number        // 급증 배율
  foreign_amount: number
  institution_amount: number
  trade_date: string | null
  themes: string[]
}

export interface RealtimeSpikeResponse {
  stocks: RealtimeSpikeStock[]
  count: number
  total_checked: number
  base_days: number
  min_ratio: number
  min_amount: number
  investor_type: string
  market_status: 'open' | 'closed'
  generated_at: string
}

export const flowRankingApi = {
  // 수급 상위 종목
  getTop: async (days = 5, limit = 30, investorType: 'all' | 'foreign' | 'institution' | 'individual' = 'all') => {
    return cachedFetch(`flow-top:${days}:${limit}:${investorType}`, async () => {
      const { data } = await api.get<{
        stocks: FlowRankingStock[]
        count: number
        days: number
        investor_type: string
        generated_at: string
      }>('/flow-ranking/top', {
        params: { days, limit, investor_type: investorType },
      })
      return data
    }, 120_000) // 2분 캐시
  },

  // 수급 하위 종목 (순매도 상위)
  getBottom: async (days = 5, limit = 30, investorType: 'all' | 'foreign' | 'institution' | 'individual' = 'all') => {
    const { data } = await api.get<{
      stocks: FlowRankingStock[]
      count: number
      days: number
      investor_type: string
      generated_at: string
    }>('/flow-ranking/bottom', {
      params: { days, limit, investor_type: investorType },
    })
    return data
  },

  // 연속 순매수 종목
  getConsecutive: async (minDays = 3, limit = 30, investorType: 'all' | 'foreign' | 'institution' | 'individual' = 'all') => {
    return cachedFetch(`flow-consecutive:${minDays}:${limit}:${investorType}`, async () => {
      const { data } = await api.get<{
        stocks: ConsecutiveStock[]
        count: number
        min_days: number
        investor_type: string
        generated_at: string
      }>('/flow-ranking/consecutive', {
        params: { min_days: minDays, limit, investor_type: investorType },
      })
      return data
    }, 120_000) // 2분 캐시
  },

  // 수급 급증 종목
  getSpike: async (
    recentDays = 2,
    baseDays = 20,
    minRatio = 3.0,
    minAmount = 1000000000,
    limit = 30,
    investorType: 'all' | 'foreign' | 'institution' = 'all'
  ) => {
    const { data } = await api.get<{
      stocks: SpikeStock[]
      count: number
      recent_days: number
      base_days: number
      min_ratio: number
      min_amount: number
      investor_type: string
      generated_at: string
    }>('/flow-ranking/spike', {
      params: {
        recent_days: recentDays,
        base_days: baseDays,
        min_ratio: minRatio,
        min_amount: minAmount,
        limit,
        investor_type: investorType,
      },
    })
    return data
  },

  // 실시간 수급 급증 종목 (KIS API)
  getRealtimeSpike: async (
    baseDays = 20,
    minRatio = 2.0,
    minAmount = 500000000,
    limit = 30,
    investorType: 'all' | 'foreign' | 'institution' = 'all'
  ) => {
    const { data } = await api.get<RealtimeSpikeResponse>('/flow-ranking/realtime-spike', {
      params: {
        base_days: baseDays,
        min_ratio: minRatio,
        min_amount: minAmount,
        limit,
        investor_type: investorType,
      },
    })
    return data
  },
}

// 텔레그램 모니터링 API
import type {
  TelegramChannel,
  TelegramChannelCreate,
  TelegramKeywordMatch,
  TelegramMonitorStatus,
  TelegramKeywordList,
  TelegramMonitorCycleResult,
} from '../types/telegram'

// Data Status API (데이터 상태 확인 및 새로고침)
import type { AllDataStatusResponse } from '../types/data_status'

export interface DataStatusItem {
  name: string
  last_updated: string | null
  record_count: number
  is_stale: boolean
  status: 'ok' | 'stale' | 'empty' | 'error'
}

export interface DataStatusResponse {
  investor_flow: DataStatusItem
  ohlcv: DataStatusItem
  chart_patterns: DataStatusItem
  theme_setups: DataStatusItem
  overall_status: 'ok' | 'needs_refresh' | 'critical'
  checked_at: string
}

export interface RefreshStatus {
  is_running: boolean
  started_at: string | null
  completed_at: string | null
  progress: Record<string, string>
  errors: string[]
}

export const dataStatusApi = {
  // 기존 데이터 상태 조회 (하위 호환성)
  getStatus: async () => {
    const { data } = await api.get<DataStatusResponse>('/data-status/status')
    return data
  },

  // 전체 데이터 상태 조회 (신규 - 카테고리별 그룹화)
  getAllStatus: async () => {
    const { data } = await api.get<AllDataStatusResponse>('/data-status/status/all')
    return data
  },

  // 데이터 새로고침 시작
  refresh: async (targets: string[] = [], forceFull = false) => {
    const { data } = await api.post<{
      started: boolean
      message: string
      targets: string[]
    }>('/data-status/refresh', {
      targets,
      force_full: forceFull,
    })
    return data
  },

  // 새로고침 진행 상태 조회
  getRefreshStatus: async () => {
    const { data } = await api.get<RefreshStatus>('/data-status/refresh/status')
    return data
  },
}

export const telegramMonitorApi = {
  // 모니터링 상태 조회
  getStatus: async () => {
    const { data } = await api.get<TelegramMonitorStatus>('/telegram-monitor/status')
    return data
  },

  // 채널 목록 조회
  getChannels: async () => {
    const { data } = await api.get<TelegramChannel[]>('/telegram-monitor/channels')
    return data
  },

  // 채널 추가
  addChannel: async (channel: TelegramChannelCreate) => {
    const { data } = await api.post<TelegramChannel>('/telegram-monitor/channels', channel)
    return data
  },

  // 채널 삭제
  deleteChannel: async (channelId: number) => {
    await api.delete(`/telegram-monitor/channels/${channelId}`)
  },

  // 채널 활성화/비활성화 토글
  toggleChannel: async (channelId: number) => {
    const { data } = await api.patch<{ channel_id: number; is_enabled: boolean }>(
      `/telegram-monitor/channels/${channelId}/toggle`
    )
    return data
  },

  // 키워드 목록 조회
  getKeywords: async () => {
    const { data } = await api.get<TelegramKeywordList>('/telegram-monitor/keywords')
    return data
  },

  // 최근 매칭 기록 조회
  getMatches: async (days = 7, limit = 50) => {
    const { data } = await api.get<TelegramKeywordMatch[]>('/telegram-monitor/matches', {
      params: { days, limit },
    })
    return data
  },

  // 수동 모니터링 실행
  runMonitor: async () => {
    const { data } = await api.post<TelegramMonitorCycleResult>('/telegram-monitor/run')
    return data
  },

  // 연결 테스트
  testConnection: async () => {
    const { data } = await api.post<{ status: string; message: string }>('/telegram-monitor/test-connection')
    return data
  },
}

// ETF 순환매 분석 API
export interface EtfHeatmapItem {
  etf_code: string
  etf_name: string
  theme: string
  is_primary: boolean
  current_price: number
  change_1d: number | null
  change_5d: number | null
  change_20d: number | null
  change_60d: number | null
  trading_value: number | null
  trading_value_avg_20d: number | null
  trading_value_ratio: number | null
  volume: number | null
  trade_date: string | null
  rank?: number
}

export interface RealtimeEtfItem {
  etf_code: string
  etf_name: string
  theme: string
  is_primary: boolean
  current_price: number
  prev_close: number
  change_1d: number | null
  change_5d: number | null
  change_20d: number | null
  volume: number | null
  high_price: number
  low_price: number
  open_price: number
  rank: number
}

export interface RealtimeHeatmapResponse {
  themes: RealtimeEtfItem[]
  updated_at: string
  market_status: 'open' | 'closed' | 'error'
  total_count: number
  error_count: number
  error?: string
}

export interface RotationSignal {
  theme: string
  etf_code: string
  etf_name: string
  signal_type: 'STRONG_UP' | 'STRONG_DOWN' | 'MOMENTUM_UP' | 'REVERSAL_UP'
  signal_strength: number
  change_5d: number
  change_20d: number
  trading_value_ratio: number
  reasons: string[]
}

export interface EtfChartCandle {
  etf_code: string
  etf_name: string | null
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  trading_value: number | null
  change_rate: number | null
}

export const etfRotationApi = {
  // 테마별 ETF 히트맵 데이터
  getHeatmap: async (period: '1d' | '5d' | '20d' | '60d' = '5d') => {
    const { data } = await api.get<{
      period: string
      themes: EtfHeatmapItem[]
      count: number
      generated_at: string
    }>('/etf-rotation/heatmap', {
      params: { period },
    })
    return data
  },

  // 실시간 ETF 히트맵 데이터 (KIS API 사용)
  getRealtimeHeatmap: async () => {
    const { data } = await api.get<RealtimeHeatmapResponse>('/etf-rotation/realtime-heatmap')
    return data
  },

  // 전체 ETF 상세 데이터
  getAllEtfs: async () => {
    const { data } = await api.get<{
      etfs: EtfHeatmapItem[]
      count: number
      generated_at: string
    }>('/etf-rotation/all-etfs')
    return data
  },

  // 순환매 시그널
  getSignals: async () => {
    const { data } = await api.get<{
      signals: RotationSignal[]
      summary: {
        strong_up: number
        momentum_up: number
        reversal_up: number
        strong_down: number
        total: number
      }
      top_signals: RotationSignal[]
      generated_at: string
    }>('/etf-rotation/signals')
    return data
  },

  // ETF 차트 데이터
  getChart: async (etfCode: string, days = 60) => {
    const { data } = await api.get<{
      etf_code: string
      days: number
      candles: EtfChartCandle[]
      count: number
    }>(`/etf-rotation/chart/${etfCode}`, {
      params: { days },
    })
    return data
  },

  // ETF 비교 차트
  compareEtfs: async (codes: string[], days = 60) => {
    const { data } = await api.get<{
      etfs: Record<string, { etf_name: string | null; candles: EtfChartCandle[] }>
      days: number
      generated_at: string
    }>('/etf-rotation/compare', {
      params: { codes: codes.join(','), days },
    })
    return data
  },

  // 테마 상세 정보
  getThemeDetail: async (themeName: string) => {
    const { data } = await api.get<ThemeDetailResponse>(`/etf-rotation/theme/${encodeURIComponent(themeName)}`)
    return data
  },

  // ETF 구성 종목
  getEtfHoldings: async (etfCode: string, limit = 15) => {
    const { data } = await api.get<EtfHoldingsResponse>(`/etf-rotation/holdings/${etfCode}`, {
      params: { limit },
    })
    return data
  },

  // 전체 ETF 수익률 비교
  getAllEtfCompare: async (startDate = '2025-01-02') => {
    const { data } = await api.get<AllEtfCompareResponse>('/etf-rotation/all-compare', {
      params: { start_date: startDate },
    })
    return data
  },
}

// 전체 ETF 비교 응답 타입
export interface AllEtfCompareResponse {
  start_date: string
  etfs: EtfCompareItem[]
  count: number
  generated_at: string
}

export interface EtfCompareItem {
  theme: string
  etf_code: string
  etf_name: string
  data: { date: string; price: number; pct: number }[]
  latest_pct: number
}

// 테마 상세 응답 타입
export interface ThemeDetailResponse {
  theme: string
  etf: {
    code: string
    name: string
    current_price: number
    changes: {
      '1d': number | null
      '5d': number | null
      '20d': number | null
      '60d': number | null
    }
    trading_value: number | null
    trading_value_avg_20d: number | null
    trading_value_ratio: number | null
    trade_date: string | null
  }
  all_etfs: EtfHeatmapItem[]
  chart: EtfChartCandle[]
  related_themes: {
    name: string
    etf_code: string | null
    change_5d: number | null
    trading_value_ratio: number | null
  }[]
  news: {
    title: string
    source: string | null
    url: string
    published_at: string | null
    is_quality: boolean
  }[]
  generated_at: string
}

// ETF 구성 종목 응답 타입
export interface EtfHoldingsResponse {
  etf_code: string
  holdings: EtfHolding[]
  count: number
  generated_at: string
}

export interface EtfHolding {
  stock_code: string
  stock_name: string
  amount: number
  weight: number | null
  change_1d: number | null
  change_5d: number | null
  foreign_net: number | null
  inst_net: number | null
  in_my_ideas: boolean
}

// 섹터 수급 API
export interface SectorFlowItem {
  sector_name: string
  stock_count: number
  today_trading_value: number
  avg_5d: number
  avg_10d: number
  avg_20d: number
  ratio_5d: number
  ratio_10d: number
  ratio_20d: number
  is_hot: boolean
  foreign_net: number
  institution_net: number
  weight: number
}

export interface SectorFlowSummaryResponse {
  sectors: SectorFlowItem[]
  total_trading_value: number
  trade_date: string
  generated_at: string
}

export interface SectorTreemapItem {
  name: string
  value: number
  weight: number
  ratio: number
  color_level: 'extreme' | 'hot' | 'warm' | 'neutral' | 'cool' | 'cold'
  is_hot: boolean
  foreign_net: number
  institution_net: number
  stock_count: number
}

export interface SectorTreemapResponse {
  data: SectorTreemapItem[]
  period: string
  total_value: number
  trade_date: string
  generated_at: string
}

export interface SectorStockItem {
  stock_code: string
  stock_name: string
  close_price: number
  volume: number
  trading_value: number
  foreign_net: number
  institution_net: number
  individual_net: number
}

export interface RealtimeSectorFlowItem {
  sector_name: string
  stock_count: number
  today_trading_value: number
  estimated_full_day: number
  avg_5d: number
  ratio_5d: number
  is_hot: boolean
  foreign_net: number
  institution_net: number
  time_ratio: number
  weight: number
}

export interface RealtimeSectorFlowResponse {
  sectors: RealtimeSectorFlowItem[]
  total_trading_value: number
  market_status: 'open' | 'closed' | 'error'
  is_realtime: boolean
  time_ratio: number
  generated_at: string
}

// 종목 프로필 API (통합 조회)
export interface StockProfileData {
  stock_code: string
  stock_info: { code: string; name: string; market: string | null } | null
  ohlcv: {
    has_data: boolean
    latest_price?: number
    change_rate?: number
    volume?: number
    trade_date?: string
    data_count?: number
  }
  investor_flow: {
    has_data: boolean
    days?: number
    foreign_net_total?: number
    institution_net_total?: number
    consecutive_foreign_buy?: number
    latest_date?: string
  }
  youtube_mentions: {
    video_count: number
    period_days: number
    is_trending: boolean
  }
  expert_mentions: {
    mention_count: number
    total_mentions: number
    period_days: number
  }
  disclosures: Array<{
    title: string | null
    date: string | null
    type: string | null
  }>
  telegram_ideas: Array<{
    message_text: string
    author: string | null
    date: string | null
    source_type: string | null
  }>
  sentiment: {
    analysis_count: number
    avg_score: number
    period_days: number
  }
  chart_patterns: Array<{
    pattern_type: string | null
    confidence: number | null
    analysis_date: string | null
  }>
  themes: string[]
}

export interface TrendingMentionItem {
  stock_code: string
  stock_name: string
  youtube_count: number
  expert_count: number
  telegram_count: number
  total_mentions: number
  source_count: number
}

export const stockProfileApi = {
  getProfile: async (stockCode: string) => {
    const { data } = await api.get<StockProfileData>(`/stocks/${stockCode}/profile`)
    return data
  },
}

export const mentionsApi = {
  getTrending: async (days = 7, limit = 20) => {
    const { data } = await api.get<TrendingMentionItem[]>('/mentions/trending', {
      params: { days, limit },
    })
    return data
  },

  getConvergence: async (days = 7, minSources = 2) => {
    const { data } = await api.get<TrendingMentionItem[]>('/mentions/convergence', {
      params: { days, min_sources: minSources },
    })
    return data
  },
}

// 텔레그램 아이디어 API
export const telegramIdeaApi = {
  list: async (params?: {
    source?: string
    days?: number
    stock_code?: string
    author?: string
    sentiment?: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL'
    limit?: number
    offset?: number
  }) => {
    const { data } = await api.get('/telegram-ideas', { params })
    return data
  },

  getStockStats: async (days = 30) => {
    const { data } = await api.get('/telegram-ideas/stats/stocks', {
      params: { days },
    })
    return data
  },

  getAuthorStats: async (days = 30) => {
    const { data } = await api.get('/telegram-ideas/stats/authors', {
      params: { days },
    })
    return data
  },

  collect: async (limit = 100) => {
    const { data } = await api.post('/telegram-ideas/collect', null, {
      params: { limit },
    })
    return data
  },

  getTraderRanking: async (days = 90, minMentions = 3) => {
    return cachedFetch(`trader-ranking-${days}-${minMentions}`, async () => {
      const { data } = await api.get('/telegram-ideas/stats/trader-ranking', {
        params: { days, min_mentions: minMentions },
      })
      return data
    }, 600_000)
  },
}

// 매매 내역 API
export interface Trade {
  id: string
  position_id: string
  trade_type: string
  trade_date: string
  price: number
  quantity: number
  total_amount: number
  realized_profit?: number
  realized_return_pct?: number
  avg_price_after?: number
  quantity_after?: number
  reason?: string
  notes?: string
  created_at?: string
  stock_code?: string
  stock_name?: string
}

export interface TradeListResponse {
  trades: Trade[]
  total_count: number
}

export interface TradeSummary {
  total_trades: number
  buy_count: number
  sell_count: number
  total_buy_amount: number
  total_sell_amount: number
  total_realized_profit: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  avg_profit_per_trade: number
  avg_return_pct: number
}

export interface MonthlyTradeStats {
  month: string
  trade_count: number
  buy_count: number
  sell_count: number
  realized_profit: number
  win_rate: number
}

export interface TickerTradeStats {
  ticker: string
  stock_name?: string
  trade_count: number
  total_buy_amount: number
  total_sell_amount: number
  realized_profit: number
  avg_return_pct: number
  winning_trades: number
  losing_trades: number
  win_rate: number
}

export interface TradeAnalysisResponse {
  summary: TradeSummary
  monthly_stats: MonthlyTradeStats[]
  ticker_stats: TickerTradeStats[]
  recent_trades: Trade[]
}

export const tradeApi = {
  list: async (params?: {
    limit?: number
    offset?: number
    trade_type?: string
    start_date?: string
    end_date?: string
    stock_code?: string
  }) => {
    const { data } = await api.get<TradeListResponse>('/trades', { params })
    return data
  },

  getByStock: async (stockCode: string) => {
    const { data } = await api.get<TradeListResponse>('/trades', { params: { stock_code: stockCode, limit: 200 } })
    return data
  },

  getByPosition: async (positionId: string) => {
    const { data } = await api.get<TradeListResponse>(`/trades/position/${positionId}`)
    return data
  },

  getAnalysis: async (startDate?: string, endDate?: string) => {
    const params: Record<string, string> = {}
    if (startDate) params.start_date = startDate
    if (endDate) params.end_date = endDate
    const { data } = await api.get<TradeAnalysisResponse>('/trades/analysis', { params })
    return data
  },

  update: async (tradeId: string, updateData: Record<string, unknown>) => {
    const { data } = await api.put(`/trades/${tradeId}`, updateData)
    return data
  },

  delete: async (tradeId: string) => {
    await api.delete(`/trades/${tradeId}`)
  },

  importCsv: async (file: File, clearExisting: boolean = true) => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post(`/trades/import/csv?clear_existing=${clearExisting}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    invalidateDashboard()
    return data
  },
}

export const sectorFlowApi = {
  // 섹터별 거래대금 현황
  getSummary: async () => {
    const { data } = await api.get<SectorFlowSummaryResponse>('/sector-flow/summary')
    return data
  },

  // 실시간 섹터별 거래대금/수급
  getRealtime: async () => {
    const { data } = await api.get<RealtimeSectorFlowResponse>('/sector-flow/realtime')
    return data
  },

  // 섹터별 랭킹
  getRanking: async (period: '5d' | '10d' | '20d' = '5d', sortBy: 'ratio' | 'value' | 'flow' = 'ratio', limit = 30) => {
    const { data } = await api.get<{
      sectors: SectorFlowItem[]
      period: string
      sort_by: string
      count: number
      trade_date: string
      generated_at: string
    }>('/sector-flow/ranking', {
      params: { period, sort_by: sortBy, limit },
    })
    return data
  },

  // 트리맵 데이터
  getTreemap: async (period: '5d' | '10d' | '20d' = '5d') => {
    const { data } = await api.get<SectorTreemapResponse>('/sector-flow/treemap', {
      params: { period },
    })
    return data
  },

  // 섹터 내 종목 상세
  getSectorStocks: async (sectorName: string, limit = 20) => {
    const { data } = await api.get<{
      sector_name: string
      stocks: SectorStockItem[]
      count: number
      trade_date: string
      generated_at: string
    }>(`/sector-flow/${encodeURIComponent(sectorName)}/stocks`, {
      params: { limit },
    })
    return data
  },
}

// Snapshot API (포트폴리오 스냅샷)
export interface SnapshotData {
  id: string
  idea_id: string
  snapshot_date: string
  price_data: {
    positions: Array<{
      ticker: string
      stock_name?: string
      quantity: number
      entry_price: number
      current_price: number | null
      invested: number
      eval: number
      days_held: number
    }>
    total_invested: number
    total_eval: number
    unrealized_profit: number
  } | null
  days_held: number | null
  unrealized_return_pct: number | null
  created_at: string
}

export interface PortfolioSummary {
  total_invested: number
  total_eval: number
  total_unrealized_profit: number
  total_return_pct: number
  active_ideas_count: number
  ideas: Array<{
    idea_id: string
    tickers: string[]
    snapshot_date: string
    invested: number
    eval: number
    unrealized_return_pct: number
    days_held: number | null
  }>
}

export const snapshotApi = {
  getByIdea: async (ideaId: string, limit = 30) => {
    const { data } = await api.get<SnapshotData[]>(`/ideas/${ideaId}/snapshots`, {
      params: { limit },
    })
    return data
  },

  getPortfolioSummary: async () => {
    return cachedFetch('portfolio-summary', async () => {
      const { data } = await api.get<PortfolioSummary>('/portfolio/summary')
      return data
    }, 300_000) // 5분 캐시
  },
}

// 재무제표 API
import type { FinancialSummary, FinancialRatios as FinancialRatiosType, FinancialCollectResponse } from '../types/financial'

export const financialApi = {
  getSummary: async (stockCode: string) => {
    const { data } = await api.get<FinancialSummary>(`/financial/${stockCode}/summary`)
    return data
  },

  getRatios: async (stockCode: string, bsnsYear?: string) => {
    const { data } = await api.get<FinancialRatiosType>(`/financial/${stockCode}/ratios`, {
      params: bsnsYear ? { bsns_year: bsnsYear } : undefined,
    })
    return data
  },

  getStatements: async (stockCode: string, bsnsYear?: string, reprtCode?: string, fsDiv?: string) => {
    const { data } = await api.get(`/financial/${stockCode}/statements`, {
      params: { bsns_year: bsnsYear, reprt_code: reprtCode, fs_div: fsDiv },
    })
    return data
  },

  collect: async (stockCode: string, years = 3) => {
    const { data } = await api.post<FinancialCollectResponse>(`/financial/${stockCode}/collect`, { years })
    return data
  },

  getEarningsDates: async (stockCode: string) => {
    const { data } = await api.get<Array<{ date: string; label: string }>>(`/financial/${stockCode}/earnings-dates`)
    return data
  },

  syncCorpCodes: async () => {
    const { data } = await api.post<{ synced_count: number; message: string }>('/financial/corp-codes/sync')
    return data
  },
}

// 차트 시그널 스캐너 API
export type SignalType = 'pullback' | 'high_breakout' | 'resistance_test' | 'support_test' | 'mss_proximity' | 'momentum_zone' | 'ma120_turn' | 'candle_squeeze' | 'candle_expansion'

export interface SignalStock {
  stock_code: string
  stock_name: string
  signal_type: SignalType
  current_price: number
  total_score: number
  grade: string
  themes: string[]
  ma20: number | null
  ma50: number | null
  ma20_distance_pct: number | null
  ma50_distance_pct: number | null
  volume_ratio: number | null
  high_price_60d: number | null
  low_price_60d: number | null
  percentile_60d: number | null
  score_breakdown: Record<string, number>
  // 눌림목
  pullback_pct: number | null
  support_line: number | null
  support_distance_pct: number | null
  volume_decreasing: boolean
  surge_pct: number | null
  // 전고점 돌파
  prev_high_price: number | null
  prev_high_date: string | null
  breakout_pct: number | null
  breakout_volume_ratio: number | null
  // 저항 돌파 시도
  resistance_price: number | null
  resistance_touch_count: number | null
  resistance_distance_pct: number | null
  // 지지선 테스트
  support_price: number | null
  support_touch_count: number | null
  consolidation_days: number | null
  ma_support_aligned: boolean | null
  // MSS 근접
  mss_level: number | null
  mss_type: string | null
  mss_distance_pct: number | null
  mss_touch_count: number | null
  mss_timeframe: string | null
  // 관성 구간
  mz_surge_pct: number | null
  mz_surge_days: number | null
  mz_consolidation_days: number | null
  mz_consolidation_range_pct: number | null
  mz_atr_contraction_ratio: number | null
  mz_volume_shrink_ratio: number | null
  mz_upper_bound: number | null
  mz_distance_to_upper_pct: number | null
  // 120일선 전환
  ma120: number | null
  ma120_slope_pct: number | null
  ma120_distance_pct: number | null
  recovery_pct: number | null
  has_double_bottom: boolean
  resistance_broken: boolean
  has_new_high_volume: boolean
  volume_surge_ratio: number | null
  // 캔들 수축
  cs_contraction_pct: number | null
  cs_body_contraction_pct: number | null
  cs_volume_shrink_ratio: number | null
  cs_correction_days: number | null
  cs_correction_depth_pct: number | null
  // 캔들 확장
  ce_expansion_pct: number | null
  ce_body_expansion_pct: number | null
  ce_volume_surge_ratio: number | null
  ce_bullish_pct: number | null
  // 수급 참조
  foreign_net_5d: number
  institution_net_5d: number
  // 품질
  is_profitable: boolean | null
  is_growing: boolean | null
  has_institutional_buying: boolean | null
  quality_score: number | null
  revenue_growth: number | null
}

export interface SignalResponse {
  stocks: SignalStock[]
  count: number
  signal_type: string
  generated_at: string
}

export interface TrendTheme {
  theme: string
  count: number
  stocks: string[]
}

export interface SqueezeThemeStock {
  name: string
  code: string
  score: number
  contraction_pct: number | null
  correction_days: number | null
  correction_depth_pct: number | null
  volume_shrink: number | null
}

export interface SqueezeTheme {
  theme: string
  count: number
  avg_score: number
  avg_contraction_pct: number
  avg_correction_depth_pct: number
  avg_volume_shrink: number
  readiness: number
  stocks: SqueezeThemeStock[]
}

export interface SignalSummary {
  pullback: number
  high_breakout: number
  resistance_test: number
  support_test: number
  mss_proximity: number
  momentum_zone: number
  ma120_turn: number
  candle_squeeze: number
  candle_expansion: number
  top_picks?: number
  total: number
  trend_themes: TrendTheme[]
  squeeze_themes: SqueezeTheme[]
  generated_at: string
}

export interface SignalDetailResponse {
  stock: Record<string, unknown>
  price_history: Array<{
    date: string
    open: number
    high: number
    low: number
    close: number
    volume: number
  }>
  flow_history: Array<{
    date: string
    foreign_net: number
    institution_net: number
    individual_net: number
    flow_score: number
  }>
  analysis_summary: string
  generated_at: string
}

// 관성 구간 백테스트 타입
export interface MZBacktestHoldingStats {
  sample_count: number
  avg_return: number
  median: number
  win_rate: number
  q1: number
  q3: number
  max_return: number
  max_loss: number
}

export interface MZBacktestScoreBucket {
  label: string
  count: number
  avg_return: number
  win_rate: number
}

export interface MZBacktestMonthly {
  month: string
  signal_count: number
  avg_return: number
  win_rate: number
}

export interface MZBacktestSignal {
  stock_code: string
  stock_name: string
  signal_date: string
  entry_date: string
  entry_price: number
  score: number
  surge_pct: number
  consol_days: number
  consol_range_pct: number
  [key: string]: unknown  // dynamic holding period keys like "5d", "10d"
}

export interface MZBacktestResponse {
  params: {
    lookback_days: number
    holding_days: number[]
    min_score: number
    step_days: number
  }
  total_signals: number
  holding_stats: Record<string, MZBacktestHoldingStats | null>
  score_analysis: MZBacktestScoreBucket[]
  monthly_analysis: MZBacktestMonthly[]
  top_performers: MZBacktestSignal[]
  worst_performers: MZBacktestSignal[]
}

export const pullbackApi = {
  getSignals: async (params?: { signal_type?: SignalType; min_score?: number; limit?: number; only_profitable?: boolean; only_growing?: boolean; only_institutional?: boolean; only_surge_pullback?: boolean; mss_timeframe?: string }) => {
    const { data } = await api.get<SignalResponse>('/pullback/signals', { params })
    return data
  },

  getSummary: async () => {
    return cachedFetch('signal-summary', async () => {
      const { data } = await api.get<SignalSummary>('/pullback/signals/summary')
      return data
    }, 120_000)
  },

  getDetail: async (stockCode: string) => {
    const { data } = await api.get<SignalDetailResponse>(`/pullback/signals/${stockCode}`)
    return data
  },

  getTopPicks: async (limit = 20) => {
    const { data } = await api.get<SignalResponse>('/pullback/top-picks', { params: { limit } })
    return data
  },

  analyzeByCode: async (stockCodes: string[], minScore = 0, limit = 50) => {
    const { data } = await api.post<SignalResponse>('/pullback/signals/by-codes', {
      stock_codes: stockCodes,
      min_score: minScore,
      limit,
    })
    return data
  },

  getMZBacktest: async (params?: {
    lookback_days?: number
    holding_days?: string
    min_score?: number
    step_days?: number
  }) => {
    const { data } = await api.get<MZBacktestResponse>('/pullback/backtest/momentum-zone', { params })
    return data
  },
}

// ── 시그널 스캐너 (매매 어드바이저) ──

export type ABCDPhase = 'A' | 'B' | 'C' | 'D' | 'unknown'
export type GapType = 'common' | 'breakaway' | 'runaway' | 'exhaustion' | 'none'
export type MAAlignment = 'bullish' | 'bearish' | 'mixed'

export interface ScannerSignal {
  stock_code: string
  stock_name: string
  current_price: number
  total_score: number
  grade: string
  abcd_phase: ABCDPhase
  ma_alignment: MAAlignment
  gap_type: GapType
  score_breakdown: Record<string, number>
  themes: string[]
  ma5: number | null
  ma20: number | null
  ma60: number | null
  ma120: number | null
  volume_ratio: number | null
  has_record_volume: boolean
  has_kkandolji: boolean
  pullback_quality: number | null
  ma20_distance_pct: number | null
  bb_position: number | null
}

export interface ChecklistItem {
  name: string
  label: string
  passed: boolean
  score: number
  max_score: number
  detail: string
}

export interface ScannerSignalResponse {
  signals: ScannerSignal[]
  count: number
  generated_at: string
}

export interface ScannerDetailResponse {
  signal: ScannerSignal
  checklist: ChecklistItem[]
  price_history: Array<{
    date: string
    open: number
    high: number
    low: number
    close: number
    volume: number
  }>
  generated_at: string
}

export interface ProvenPattern {
  conditions: Record<string, string>
  win_rate: number
  avg_return_pct: number
  trade_count: number
}

export interface ProvenPatternsResponse {
  patterns: ProvenPattern[]
  generated_at: string
}

export interface ScannerAIAdvice {
  abcd_phase: string
  phase_description: string
  entry_recommendation: string
  risk_assessment: string
  key_observations: string[]
  entry_conditions: string[]
  exit_conditions: string[]
  confidence: number
}

export interface ScannerAIAdviceResponse {
  stock_code: string
  stock_name: string
  advice: ScannerAIAdvice
  generated_at: string
}

export interface WatchlistGroup {
  id: number
  name: string
  color: string | null
  order: number
  created_at: string
}

export interface WatchlistItemFull {
  id: number
  stock_code: string
  stock_name: string | null
  memo: string | null
  group_id: number | null
  created_at: string
}

export const watchlistApi = {
  getCodes: async () => {
    const { data } = await api.get<string[]>('/watchlist/codes')
    return data
  },

  getItems: async () => {
    const { data } = await api.get<WatchlistItemFull[]>('/watchlist')
    return data
  },

  toggle: async (stock_code: string, stock_name?: string, group_id?: number) => {
    const { data } = await api.post<{ stock_code: string; is_watched: boolean }>('/watchlist/toggle', { stock_code, stock_name, group_id })
    return data
  },

  delete: async (stock_code: string) => {
    const { data } = await api.delete<{ deleted: boolean }>(`/watchlist/${stock_code}`)
    return data
  },

  // 그룹 CRUD
  getGroups: async () => {
    const { data } = await api.get<WatchlistGroup[]>('/watchlist/groups')
    return data
  },

  createGroup: async (name: string, color?: string) => {
    const { data } = await api.post<WatchlistGroup>('/watchlist/groups', { name, color })
    return data
  },

  updateGroup: async (groupId: number, update: { name?: string; color?: string }) => {
    const { data } = await api.put<WatchlistGroup>(`/watchlist/groups/${groupId}`, update)
    return data
  },

  deleteGroup: async (groupId: number) => {
    const { data } = await api.delete<{ deleted: boolean }>(`/watchlist/groups/${groupId}`)
    return data
  },

  moveToGroup: async (stock_codes: string[], group_id: number | null) => {
    const { data } = await api.post<{ moved: number }>('/watchlist/move', { stock_codes, group_id })
    return data
  },

  reorderGroups: async (group_ids: number[]) => {
    const { data } = await api.post<{ ok: boolean }>('/watchlist/groups/reorder', { group_ids })
    return data
  },

  getGrouped: async () => {
    const { data } = await api.get<{ groups: WatchlistGroup[]; items: WatchlistItemFull[] }>('/watchlist/grouped')
    return data
  },
}

// Smart Scanner API (4차원 교차검증)
import type { SmartScannerResponse, NarrativeBriefing } from '../types/smart_scanner'

export const smartScannerApi = {
  scan: async (params?: { min_score?: number; limit?: number; sort_by?: string; exclude_expert?: boolean }) => {
    return cachedFetch(`smart-scanner:${JSON.stringify(params || {})}`, async () => {
      const { data } = await api.get<SmartScannerResponse>('/smart-scanner/scan', { params })
      return data
    }, 300_000) // 5분 캐시
  },

  getStockDetail: async (stockCode: string) => {
    const { data } = await api.get(`/smart-scanner/stock/${stockCode}`)
    return data
  },

  getNarrative: async (stockCode: string, forceRefresh = false) => {
    const { data } = await api.get<NarrativeBriefing>(`/smart-scanner/narrative/${stockCode}`, {
      params: forceRefresh ? { force_refresh: true } : undefined,
    })
    return data
  },
}

// Stock News API (종목별 뉴스)
import type { StockNewsItem, CatalystSummary, HotNewsStock, CatalystEvent, CatalystStats } from '../types/catalyst'

export const stockNewsApi = {
  getStockNews: async (stockCode: string, days = 7, limit = 20) => {
    const { data } = await api.get<StockNewsItem[]>(`/stock-news/${stockCode}`, {
      params: { days, limit },
    })
    return data
  },

  getCatalystSummary: async (stockCode: string, days = 14) => {
    const { data } = await api.get<CatalystSummary>(`/stock-news/${stockCode}/catalyst-summary`, {
      params: { days },
    })
    return data
  },

  getHotStocks: async (limit = 30, days = 3) => {
    const { data } = await api.get<HotNewsStock[]>('/stock-news/hot/ranking', {
      params: { limit, days },
    })
    return data
  },
}

// Catalyst Tracker API
import type { EnrichedCatalystEvent } from '../types/catalyst'

export const catalystApi = {
  getActive: async (params?: { status?: string; catalyst_type?: string; limit?: number }) => {
    const { data } = await api.get<CatalystEvent[]>('/catalyst/active', { params })
    return data
  },

  getEnriched: async (params?: { status?: string; catalyst_type?: string; limit?: number }) => {
    const { data } = await api.get<EnrichedCatalystEvent[]>('/catalyst/enriched', { params })
    return data
  },

  getImpact: async (eventId: string) => {
    const { data } = await api.get<{ impact: string }>(`/catalyst/${eventId}/impact`)
    return data
  },

  getSimilar: async (eventId: string, limit = 5) => {
    const { data } = await api.get<CatalystEvent[]>(`/catalyst/${eventId}/similar`, {
      params: { limit },
    })
    return data
  },

  getStockCatalysts: async (stockCode: string, limit = 20) => {
    const { data } = await api.get<CatalystEvent[]>(`/catalyst/stock/${stockCode}`, {
      params: { limit },
    })
    return data
  },

  getStats: async () => {
    const { data } = await api.get<CatalystStats>('/catalyst/stats')
    return data
  },
}

export const themePulseApi = {
  getPulse: async (days = 7, limit = 30) => {
    return cachedFetch(`theme-pulse:${days}:${limit}`, async () => {
      const { data } = await api.get<ThemePulseResponse>('/theme-pulse/pulse', {
        params: { days, limit },
      })
      return data
    }, 180_000)
  },

  getTimeline: async (days = 14, topN = 8) => {
    return cachedFetch(`theme-timeline:${days}:${topN}`, async () => {
      const { data } = await api.get<TimelineResponse>('/theme-pulse/timeline', {
        params: { days, top_n: topN },
      })
      return data
    }, 180_000)
  },

  getCatalystDistribution: async (days = 7) => {
    return cachedFetch(`theme-catalyst-dist:${days}`, async () => {
      const { data } = await api.get<CatalystDistributionResponse>('/theme-pulse/catalyst-distribution', {
        params: { days },
      })
      return data
    }, 180_000)
  },
}

export const signalScannerApi = {
  getSignals: async (params?: { min_score?: number; limit?: number }) => {
    const { data } = await api.get<ScannerSignalResponse>('/signal-scanner/signals', { params })
    return data
  },

  getDetail: async (stockCode: string) => {
    const { data } = await api.get<ScannerDetailResponse>(`/signal-scanner/signals/${stockCode}`)
    return data
  },

  getChecklist: async (stockCode: string) => {
    const { data } = await api.get<{ stock_code: string; checklist: ChecklistItem[]; total_score: number; max_score: number }>(`/signal-scanner/checklist/${stockCode}`)
    return data
  },

  getAIAdvice: async (stockCode: string) => {
    const { data } = await api.get<ScannerAIAdviceResponse>(`/signal-scanner/ai-advice/${stockCode}`)
    return data
  },

  getProvenPatterns: async () => {
    const { data } = await api.get<ProvenPatternsResponse>('/signal-scanner/proven-patterns')
    return data
  },
}

// ── 기업 프로필 ──

export interface CompanyProfileData {
  stock_code: string
  stock_name: string | null
  ceo_name: string | null
  industry_name: string | null
  website: string | null
  business_summary: string | null
  main_products: string | null
  sector: string | null
  report_source: string | null
  report_url: string | null
  last_updated: string | null
}

// ── 장중 갭다운 회복 분석 ──
import type { GapRecoveryResponse } from '../types/recovery'

export const recoveryApi = {
  getRealtime: async (minGapPct = 0.5, limit = 30) => {
    const { data } = await api.get<GapRecoveryResponse>('/analysis/recovery/realtime', {
      params: { min_gap_pct: minGapPct, limit },
    })
    return data
  },
}

export const companyProfileApi = {
  getProfile: async (stockCode: string) => {
    const { data } = await api.get<CompanyProfileData>(`/company-profile/${stockCode}`)
    return data
  },

  generateProfile: async (stockCode: string, force = false) => {
    const { data } = await api.post<CompanyProfileData>(`/company-profile/${stockCode}/generate`, null, {
      params: force ? { force: true } : undefined,
    })
    return data
  },
}

// ── 재무 저평가 스크리너 ──
import type { ValueScreenerResponse, ValueMetrics } from '../types/value_screener'

export const valueScreenerApi = {
  scan: async (params?: { min_score?: number; limit?: number; sort_by?: string }) => {
    return cachedFetch(`value-screener:${JSON.stringify(params || {})}`, async () => {
      const { data } = await api.get<ValueScreenerResponse>('/value-screener/scan', { params })
      return data
    }, 3_600_000) // 1시간 - 서버도 6시간 캐시, 재무데이터 기반이라 자주 안 바뀜
  },

  getStockDetail: async (stockCode: string) => {
    const { data } = await api.get<ValueMetrics>(`/value-screener/stock/${stockCode}`)
    return data
  },
}

// ── 백테스트 ──

export interface BacktestParams {
  start_date: string
  end_date: string
  initial_capital?: number
  max_positions?: number
  min_signal_score?: number
  stop_loss_pct?: number
  take_profit_pct?: number
  max_holding_days?: number
  trailing_stop_pct?: number
  ma_deviation_exit_pct?: number
  adaptive_trailing?: boolean
  adaptive_dev_mid?: number
  adaptive_dev_high?: number
  adaptive_trail_low?: number
  adaptive_trail_mid?: number
  adaptive_trail_high?: number
  adaptive_peak_drop?: number
  adaptive_profit_trigger?: number
  signal_types?: string[]
  step_days?: number
  cooldown_days?: number
}

export interface BacktestTrade {
  stock_code: string
  stock_name: string
  signal_type: string
  signal_score: number
  entry_date: string
  entry_price: number
  exit_date: string
  exit_price: number
  exit_reason: string
  return_pct: number
  profit: number
  holding_days: number
}

export interface BacktestSummary {
  initial_capital: number
  final_capital: number
  total_return_pct: number
  annualized_return_pct: number
  mdd_pct: number
  win_rate: number
  total_trades: number
  avg_return_pct: number
  avg_holding_days: number
  profit_factor: number
  sharpe_ratio: number
}

export interface EquityCurvePoint {
  date: string
  value: number
  cash: number
  positions_value: number
}

export interface SignalPerformance {
  signal_type: string
  count: number
  win_rate: number
  avg_return_pct: number
  total_profit: number
}

export interface MonthlyPerformance {
  month: string
  return_pct: number
  trades: number
  win_rate: number
}

export interface IndexPoint {
  date: string
  value: number
}

export interface BacktestResponse {
  params: BacktestParams
  summary: BacktestSummary
  equity_curve: EquityCurvePoint[]
  kospi_curve: IndexPoint[]
  kosdaq_curve: IndexPoint[]
  signal_performance: SignalPerformance[]
  monthly_performance: MonthlyPerformance[]
  trades: BacktestTrade[]
}

// Feature Flags API
export const featuresApi = {
  get: async () => {
    const { data } = await api.get<{ telegram: boolean; expert: boolean }>('/features')
    return data
  },
  toggle: async (flags: Partial<{ telegram: boolean; expert: boolean }>) => {
    const { data } = await api.post<{ telegram: boolean; expert: boolean }>('/features', flags)
    return data
  },
}

export const backtestApi = {
  run: async (params: BacktestParams) => {
    const { data } = await api.post<BacktestResponse>('/backtest/run', params, {
      timeout: 600_000,
    })
    return data
  },
}
