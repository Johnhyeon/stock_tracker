import { create } from 'zustand'
import type {
  PriceData,
  Disclosure,
  DisclosureStats,
  DisclosureImportance,
  YouTubeMention,
  TrendingTicker,
  SchedulerStatus,
  RisingTicker,
  TraderHotStock,
  TraderRisingStock,
  TraderPerformanceStats,
  TraderNewMention,
  TraderCrossCheck,
  TraderSyncResponse,
} from '../types/data'
import { dataApi, disclosureApi, youtubeApi, schedulerApi, traderApi } from '../services/api'

// 수집 결과 타입
interface CollectResult {
  collected: number
  new: number
  tickers_searched?: string[]
  tickers_found?: string[]
  mode?: 'quick' | 'normal' | 'full'
}

interface DataState {
  // Price data
  prices: Record<string, PriceData>
  pricesLoading: boolean

  // Disclosure data
  disclosures: Disclosure[]
  disclosureStats: DisclosureStats | null
  disclosuresLoading: boolean

  // YouTube data
  youtubeMentions: YouTubeMention[]
  trendingTickers: TrendingTicker[]
  risingTickers: RisingTicker[]
  trendingLoading: boolean
  mentionsLoading: boolean
  risingLoading: boolean

  // YouTube 수집 상태 (전역)
  youtubeCollecting: boolean
  youtubeHotCollecting: boolean
  youtubeCollectResult: CollectResult | null
  youtubeHotCollectResult: CollectResult | null

  // Trader Watchlist data
  traderHotStocks: TraderHotStock[]
  traderRisingStocks: TraderRisingStock[]
  traderPerformance: TraderPerformanceStats | null
  traderNewMentions: TraderNewMention[]
  traderCrossCheck: TraderCrossCheck[]
  traderHotLoading: boolean
  traderRisingLoading: boolean
  traderPerformanceLoading: boolean
  traderSyncing: boolean
  traderSyncResult: TraderSyncResponse | null

  // Scheduler
  schedulerStatus: SchedulerStatus | null
  schedulerLoading: boolean

  // Theme Setup 수집 상태 (전역)
  themeCalculating: boolean
  themeAnalyzing: boolean
  themeCollectingFlow: boolean

  // Error
  error: string | null

  // Actions
  fetchPrice: (stockCode: string) => Promise<void>
  fetchMultiplePrices: (stockCodes: string[]) => Promise<void>
  fetchDisclosures: (params?: { stock_code?: string; unread_only?: boolean; importance?: DisclosureImportance; my_ideas_only?: boolean }) => Promise<void>
  fetchDisclosureStats: (stockCode?: string) => Promise<void>
  fetchYouTubeMentions: (params?: { stock_code?: string; days_back?: number }) => Promise<void>
  fetchTrendingTickers: (daysBack?: number) => Promise<void>
  fetchRisingTickers: (daysBack?: number) => Promise<void>
  collectYouTube: (hoursBack?: number) => Promise<void>
  collectYouTubeHot: (hoursBack?: number, mode?: 'quick' | 'normal' | 'full') => Promise<void>
  fetchSchedulerStatus: () => Promise<void>
  // Trader actions
  syncTraderMentions: () => Promise<void>
  fetchTraderHotStocks: (daysBack?: number) => Promise<void>
  fetchTraderRisingStocks: (daysBack?: number) => Promise<void>
  fetchTraderPerformance: (daysBack?: number) => Promise<void>
  fetchTraderNewMentions: (sinceHours?: number) => Promise<void>
  fetchTraderCrossCheck: () => Promise<void>
  clearError: () => void
  clearCollectResults: () => void
}

export const useDataStore = create<DataState>((set, get) => ({
  // Initial state
  prices: {},
  pricesLoading: false,
  disclosures: [],
  disclosureStats: null,
  disclosuresLoading: false,
  youtubeMentions: [],
  trendingTickers: [],
  risingTickers: [],
  trendingLoading: false,
  mentionsLoading: false,
  risingLoading: false,
  youtubeCollecting: false,
  youtubeHotCollecting: false,
  youtubeCollectResult: null,
  youtubeHotCollectResult: null,
  // Trader Watchlist
  traderHotStocks: [],
  traderRisingStocks: [],
  traderPerformance: null,
  traderNewMentions: [],
  traderCrossCheck: [],
  traderHotLoading: false,
  traderRisingLoading: false,
  traderPerformanceLoading: false,
  // Theme Setup
  themeCalculating: false,
  themeAnalyzing: false,
  themeCollectingFlow: false,
  traderSyncing: false,
  traderSyncResult: null,
  schedulerStatus: null,
  schedulerLoading: false,
  error: null,

  // Actions
  fetchPrice: async (stockCode) => {
    set({ pricesLoading: true, error: null })
    try {
      const price = await dataApi.getPrice(stockCode)
      set((state) => ({
        prices: { ...state.prices, [stockCode]: price },
        pricesLoading: false,
      }))
    } catch (err) {
      set({ error: '가격 정보를 불러오는데 실패했습니다.', pricesLoading: false })
    }
  },

  fetchMultiplePrices: async (stockCodes) => {
    set({ pricesLoading: true, error: null })
    try {
      const prices = await dataApi.getMultiplePrices(stockCodes)
      set((state) => ({
        prices: { ...state.prices, ...prices },
        pricesLoading: false,
      }))
    } catch (err) {
      set({ error: '가격 정보를 불러오는데 실패했습니다.', pricesLoading: false })
    }
  },

  fetchDisclosures: async (params) => {
    set({ disclosuresLoading: true, error: null })
    try {
      const response = await disclosureApi.list(params)
      set({ disclosures: response.items, disclosuresLoading: false })
    } catch (err) {
      set({ error: '공시 목록을 불러오는데 실패했습니다.', disclosuresLoading: false })
    }
  },

  fetchDisclosureStats: async (stockCode) => {
    try {
      const stats = await disclosureApi.getStats(stockCode)
      set({ disclosureStats: stats })
    } catch (err) {
      console.error('Failed to fetch disclosure stats:', err)
    }
  },

  fetchYouTubeMentions: async (params) => {
    set({ mentionsLoading: true, error: null })
    try {
      const response = await youtubeApi.list(params)
      set({ youtubeMentions: response.items, mentionsLoading: false })
    } catch (err) {
      set({ error: 'YouTube 언급을 불러오는데 실패했습니다.', mentionsLoading: false })
    }
  },

  fetchTrendingTickers: async (daysBack = 7) => {
    set({ trendingLoading: true, error: null })
    try {
      const trending = await youtubeApi.getTrending(daysBack)
      set({ trendingTickers: trending, trendingLoading: false })
    } catch (err) {
      set({ error: '트렌딩 종목을 불러오는데 실패했습니다.', trendingLoading: false })
    }
  },

  fetchRisingTickers: async (daysBack = 7) => {
    set({ risingLoading: true })
    try {
      const rising = await youtubeApi.getRising(daysBack, 20)
      set({ risingTickers: rising, risingLoading: false })
    } catch (err) {
      console.error('Failed to fetch rising tickers:', err)
      set({ risingLoading: false })
    }
  },

  collectYouTube: async (hoursBack = 48) => {
    set({ youtubeCollecting: true, youtubeCollectResult: null })
    try {
      const result = await youtubeApi.collect(hoursBack)
      set({
        youtubeCollecting: false,
        youtubeCollectResult: result
      })
      // 수집 후 데이터 새로고침
      get().fetchTrendingTickers()
      get().fetchYouTubeMentions({ days_back: 7 })
    } catch (err) {
      set({ youtubeCollecting: false, error: 'YouTube 수집에 실패했습니다.' })
    }
  },

  collectYouTubeHot: async (hoursBack = 48, mode: 'quick' | 'normal' | 'full' = 'normal') => {
    set({ youtubeHotCollecting: true, youtubeHotCollectResult: null })
    try {
      const result = await youtubeApi.collectHot(hoursBack, mode)
      set({
        youtubeHotCollecting: false,
        youtubeHotCollectResult: result
      })
      // 수집 후 데이터 새로고침
      get().fetchTrendingTickers()
      get().fetchRisingTickers()
    } catch (err) {
      set({ youtubeHotCollecting: false, error: '핫 영상 수집에 실패했습니다.' })
    }
  },

  fetchSchedulerStatus: async () => {
    set({ schedulerLoading: true })
    try {
      const status = await schedulerApi.getStatus()
      set({ schedulerStatus: status, schedulerLoading: false })
    } catch (err) {
      set({ schedulerLoading: false })
    }
  },

  clearError: () => set({ error: null }),

  clearCollectResults: () => set({
    youtubeCollectResult: null,
    youtubeHotCollectResult: null,
    traderSyncResult: null,
  }),

  // Trader Actions
  syncTraderMentions: async () => {
    set({ traderSyncing: true, traderSyncResult: null })
    try {
      const result = await traderApi.sync()
      set({ traderSyncing: false, traderSyncResult: result })
      // 동기화 후 데이터 새로고침
      get().fetchTraderHotStocks()
      get().fetchTraderRisingStocks()
      get().fetchTraderPerformance()
    } catch (err) {
      set({ traderSyncing: false, error: '트레이더 데이터 동기화에 실패했습니다.' })
    }
  },

  fetchTraderHotStocks: async (daysBack = 7) => {
    set({ traderHotLoading: true })
    try {
      const stocks = await traderApi.getHotStocks(daysBack, 20, true)
      set({ traderHotStocks: stocks, traderHotLoading: false })
    } catch (err) {
      console.error('Failed to fetch trader hot stocks:', err)
      set({ traderHotLoading: false })
    }
  },

  fetchTraderRisingStocks: async (daysBack = 7) => {
    set({ traderRisingLoading: true })
    try {
      const stocks = await traderApi.getRisingStocks(daysBack, 20, true)
      set({ traderRisingStocks: stocks, traderRisingLoading: false })
    } catch (err) {
      console.error('Failed to fetch trader rising stocks:', err)
      set({ traderRisingLoading: false })
    }
  },

  fetchTraderPerformance: async (daysBack = 30) => {
    set({ traderPerformanceLoading: true })
    try {
      const stats = await traderApi.getPerformanceStats(daysBack)
      set({ traderPerformance: stats, traderPerformanceLoading: false })
    } catch (err) {
      console.error('Failed to fetch trader performance:', err)
      set({ traderPerformanceLoading: false })
    }
  },

  fetchTraderNewMentions: async (sinceHours = 24) => {
    try {
      const mentions = await traderApi.getNewMentions(sinceHours)
      set({ traderNewMentions: mentions })
    } catch (err) {
      console.error('Failed to fetch new mentions:', err)
    }
  },

  fetchTraderCrossCheck: async () => {
    try {
      const crossCheck = await traderApi.getCrossCheck()
      set({ traderCrossCheck: crossCheck })
    } catch (err) {
      console.error('Failed to fetch cross check:', err)
    }
  },
}))
