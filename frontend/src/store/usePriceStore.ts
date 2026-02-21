import { create } from 'zustand'
import type { PriceData } from '../types/data'
import { dataApi } from '../services/api'

interface PriceState {
  prices: Record<string, PriceData>
  loading: boolean
  error: string | null

  fetchPrice: (stockCode: string) => Promise<void>
  fetchMultiplePrices: (stockCodes: string[]) => Promise<void>
  clearError: () => void
}

export const usePriceStore = create<PriceState>((set) => ({
  prices: {},
  loading: false,
  error: null,

  fetchPrice: async (stockCode) => {
    set({ loading: true, error: null })
    try {
      const price = await dataApi.getPrice(stockCode)
      set((state) => ({
        prices: { ...state.prices, [stockCode]: price },
        loading: false,
      }))
    } catch {
      set({ error: '가격 정보를 불러오는데 실패했습니다.', loading: false })
    }
  },

  fetchMultiplePrices: async (stockCodes) => {
    set({ loading: true, error: null })
    try {
      const prices = await dataApi.getMultiplePrices(stockCodes)
      set((state) => ({
        prices: { ...state.prices, ...prices },
        loading: false,
      }))
    } catch {
      set({ error: '가격 정보를 불러오는데 실패했습니다.', loading: false })
    }
  },

  clearError: () => set({ error: null }),
}))
