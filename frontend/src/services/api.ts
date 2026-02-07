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
  TraderHotStock,
  TraderRisingStock,
  TraderPerformanceStats,
  TraderSyncResponse,
  TraderNewMention,
  TraderCrossCheck,
  ThemeRotationResponse,
  ThemeListItem,
  ThemeSearchResult,
  StockThemesResponse,
} from '../types/data'
import type {
  EmergingThemesResponse,
  ThemeSetupDetail,
  ChartPattern,
  NewsTrendItem,
  ThemeNewsItem,
  SetupHistoryItem,
} from '../types/theme_setup'

import { cachedFetch } from './apiCache'

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
    return data
  },

  update: async (id: string, idea: IdeaUpdate) => {
    const { data } = await api.put<Idea>(`/ideas/${id}`, idea)
    return data
  },

  delete: async (id: string) => {
    await api.delete(`/ideas/${id}`)
  },

  checkExit: async (id: string) => {
    const { data } = await api.get<ExitCheckResult>(`/ideas/${id}/exit-check`)
    return data
  },

  createPosition: async (ideaId: string, position: PositionCreate) => {
    const { data } = await api.post<Position>(`/ideas/${ideaId}/positions`, position)
    return data
  },

  // 아이디어에 등록된 모든 종목 목록 반환
  getIdeaStocks: async () => {
    const { data } = await api.get<Array<{ code: string; name: string; ticker_label: string }>>('/ideas/stocks/all')
    return data
  },
}

export const positionApi = {
  get: async (id: string) => {
    const { data } = await api.get<Position>(`/positions/${id}`)
    return data
  },

  exit: async (id: string, exitData: PositionExit) => {
    const { data } = await api.put<Position>(`/positions/${id}/exit`, exitData)
    return data
  },

  addBuy: async (id: string, addBuyData: PositionAddBuy) => {
    const { data } = await api.post<Position>(`/positions/${id}/add-buy`, addBuyData)
    return data
  },

  partialExit: async (id: string, partialExitData: PositionPartialExit) => {
    const { data } = await api.post<Position>(`/positions/${id}/partial-exit`, partialExitData)
    return data
  },

  delete: async (id: string) => {
    await api.delete(`/positions/${id}`)
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

// Trader Watchlist API
export const traderApi = {
  sync: async (filePath?: string) => {
    const { data } = await api.post<TraderSyncResponse>('/traders/sync', {
      file_path: filePath,
    })
    return data
  },

  getHotStocks: async (daysBack = 7, limit = 20, includePrice = true) => {
    const { data } = await api.get<TraderHotStock[]>('/traders/hot', {
      params: { days_back: daysBack, limit, include_price: includePrice },
    })
    return data
  },

  getRisingStocks: async (daysBack = 7, limit = 20, includePrice = true) => {
    const { data } = await api.get<TraderRisingStock[]>('/traders/rising', {
      params: { days_back: daysBack, limit, include_price: includePrice },
    })
    return data
  },

  getPerformanceStats: async (daysBack = 30) => {
    const { data } = await api.get<TraderPerformanceStats>('/traders/performance', {
      params: { days_back: daysBack },
    })
    return data
  },

  getNewMentions: async (sinceHours = 24) => {
    const { data } = await api.get<TraderNewMention[]>('/traders/new-mentions', {
      params: { since_hours: sinceHours },
    })
    return data
  },

  getCrossCheck: async () => {
    const { data } = await api.get<TraderCrossCheck[]>('/traders/cross-check')
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
